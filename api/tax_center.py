import json

import frappe
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from ledgix_saas.api.fbr_settings import get_fbr_control_state, get_fbr_settings
from ledgix_saas.api.taxation import (
    calculate_tax_breakdown,
    get_category_tax_defaults,
    get_effective_tax_rate,
    resolve_item_tax_context,
    resolve_tax_rate,
)


VIEW_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager")
EDIT_ROLES = ("System Manager", "Ledgix Admin")
ITEM_MAPPING_EDIT_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager")

PROFILE_FIELDS = (
    "business_name",
    "ntn",
    "strn__sales_tax_registration_number",
    "province",
    "business_type",
    "default_tax_category",
    "default_sales_type",
    "default_buyer_type",
    "tax_enabled",
    "price_includes_tax",
    "receipt_tax_display_enabled",
    "pos_registration_number",
    "branch__outlet_name",
    "outlet_address",
)

CATEGORY_BASE_FIELDS = (
    "name",
    "category_name",
    "tax_type",
    "is_exempt",
    "is_zero_rated",
    "active",
    "description",
)

RATE_FIELDS = (
    "name",
    "tax_category",
    "rate",
    "effective_from",
    "effective_to",
    "applies_to",
    "province",
    "active",
)

ITEM_MAPPING_FIELDS = (
    "name",
    "item",
    "taxable",
    "tax_category",
    "hs_code",
    "uom_for_fbr",
    "sales_type",
    "scenario_id",
    "sro_schedule_number",
    "sro_item_serial_number",
    "default_tax_rate",
    "needs_review",
    "active",
)

PRODUCT_CATEGORY_TAX_FIELDS = (
    "name",
    "category_name",
    "is_active",
    "tax_defaults_enabled",
    "default_tax_category",
    "default_taxable",
    "default_sales_type",
    "default_uom_for_fbr",
    "default_scenario_id",
)

INVOICE_FIELDS = (
    "name",
    "modified",
    "sale",
    "sale_item_row",
    "item",
    "qty",
    "rate",
    "gross_amount",
    "discount_amount",
    "taxable_amount",
    "tax_category",
    "tax_rate",
    "tax_amount",
    "net_amount",
    "price_includes_tax",
    "hs_code",
    "uom_for_fbr",
    "sales_type",
    "scenario_id",
    "sro_schedule_number",
    "sro_item_serial_number",
)

RETURN_FIELDS = (
    "name",
    "modified",
    "sales_return",
    "original_sale",
    "original_sale_item_row",
    "item",
    "returned_qty",
    "original_tax_rate",
    "returned_taxable_amount",
    "returned_tax_amount",
    "gross_amount",
    "taxable_amount",
    "tax_rate",
    "tax_amount",
    "net_amount",
    "price_includes_tax",
    "tax_category",
    "hs_code",
    "uom_for_fbr",
    "sales_type",
    "scenario_id",
    "sro_schedule_number",
    "sro_item_serial_number",
)

FBR_LOG_FIELDS = (
    "name",
    "reference_doctype",
    "reference_name",
    "invoice_type",
    "fbr_status",
    "fbr_invoice_number",
    "attempt_count",
    "error_code",
    "error_message",
    "submitted_by",
    "submitted_at",
    "modified",
)


def _roles():
    return set(frappe.get_roles(frappe.session.user))


def _has_role(roles):
    return bool(_roles().intersection(set(roles)))


def _require_tax_view():
    if not _has_role(VIEW_ROLES):
        frappe.throw("You do not have permission to access Tax Center.", frappe.PermissionError)


def _require_tax_edit():
    if not _has_role(EDIT_ROLES):
        frappe.throw("You do not have permission to edit tax settings.", frappe.PermissionError)


def _require_item_mapping_edit():
    if not _has_role(ITEM_MAPPING_EDIT_ROLES):
        frappe.throw("You do not have permission to edit item tax mappings.", frappe.PermissionError)


def _permissions():
    can_view = _has_role(VIEW_ROLES)
    can_edit = _has_role(EDIT_ROLES)
    return {
        "can_view": can_view,
        "can_edit_setup": can_edit,
        "can_edit_masters": can_edit,
        "can_edit_item_mapping": _has_role(ITEM_MAPPING_EDIT_ROLES),
        "can_view_snapshots": can_view,
    }


def _json_values(values):
    if isinstance(values, str):
        return frappe.parse_json(values) or {}
    return values or {}


def _paginate(page, page_size):
    page = max(cint(page) or 1, 1)
    page_size = min(max(cint(page_size) or 15, 1), 100)
    return page, page_size, (page - 1) * page_size


def _like(value):
    return f"%{value}%"


def _has_doctype(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def _table(rows, total, page, page_size, summary=None):
    return {
        "rows": rows or [],
        "total": cint(total),
        "page": cint(page),
        "page_size": cint(page_size),
        "summary": summary or {},
    }


def _get_count(doctype, filters=None):
    if not _has_doctype(doctype):
        return 0
    rows = frappe.get_all(
        doctype,
        fields=["count(name) as total"],
        filters=filters or {},
        ignore_permissions=True,
    )
    return cint((rows[0] or {}).get("total")) if rows else 0

def _count_missing_hs_code():
    if not _has_doctype("Ledgix Item Tax Profile"):
        return 0

    return cint(
        frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM `tabLedgix Item Tax Profile`
            WHERE active = 1
              AND taxable = 1
              AND (hs_code IS NULL OR hs_code = '')
            """,
            as_list=True,
        )[0][0]
    )


def _count_missing_item_tax_field(fieldname):
    if not _has_doctype("Ledgix Item Tax Profile"):
        return 0

    return cint(
        frappe.db.sql(
            f"""
            SELECT COUNT(*)
            FROM `tabLedgix Item Tax Profile`
            WHERE active = 1
              AND taxable = 1
              AND ({fieldname} IS NULL OR {fieldname} = '')
            """,
            as_list=True,
        )[0][0]
    )


def _profile_dict():
    if not _has_doctype("Ledgix Tax Profile"):
        return {}
    return {field: frappe.db.get_single_value("Ledgix Tax Profile", field) for field in PROFILE_FIELDS}


def _has_column(doctype, fieldname):
    try:
        return bool(frappe.db.has_column(doctype, fieldname))
    except Exception:
        return False


def _category_rate_field():
    if _has_column("Ledgix Tax Category", "default_rate"):
        return "default_rate"
    if _has_column("Ledgix Tax Category", "default_rate_"):
        return "default_rate_"
    return "default_rate"


def _category_fields():
    return ("name", "category_name", "tax_type", _category_rate_field(), "is_exempt", "is_zero_rated", "active", "description")


def _normalize_category_rows(result):
    rate_field = _category_rate_field()
    for row in result.get("rows", []):
        row["default_rate"] = flt(row.get(rate_field))
        row.pop("default_rate_", None)
    return result


def _category_default_rate(tax_category):
    if not tax_category or not _has_doctype("Ledgix Tax Category"):
        return 0
    return flt(frappe.db.get_value("Ledgix Tax Category", tax_category, _category_rate_field()))


def _effective_or_default_rate(tax_category, applies_to="Sales"):
    from ledgix_saas.api.taxation import resolve_tax_rate

    return flt(resolve_tax_rate(tax_category=tax_category, posting_date=nowdate(), applies_to=applies_to))


def _insert_audit_log(reference_doctype, reference_name, field_changed, old_value, new_value, reason=None):
    if not _has_doctype("Ledgix Tax Audit Log"):
        return
    try:
        doc = frappe.get_doc(
            {
                "doctype": "Ledgix Tax Audit Log",
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "field_changed": field_changed,
                "old_value": json.dumps(old_value, default=str),
                "new_value": json.dumps(new_value, default=str),
                "changed_by": frappe.session.user,
                "changed_at": now_datetime(),
                "reason__note": reason,
            }
        )
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Ledgix Tax Center audit log insert failed")


def _get_rows(doctype, fields, filters=None, or_filters=None, order_by="modified desc", page=1, page_size=15):
    page, page_size, start = _paginate(page, page_size)
    if not _has_doctype(doctype):
        return _table([], 0, page, page_size)
    total_row = frappe.get_all(
        doctype,
        fields=["count(name) as total"],
        filters=filters or {},
        or_filters=or_filters or None,
        ignore_permissions=True,
    )
    total = (total_row[0] or {}).get("total") if total_row else 0
    rows = frappe.get_all(
        doctype,
        fields=list(fields),
        filters=filters or {},
        or_filters=or_filters or None,
        order_by=order_by,
        start=start,
        page_length=page_size,
        ignore_permissions=True,
    )
    return _table(rows, total, page, page_size)


def _bool_int(value):
    return 1 if cint(value) else 0


def _date_filter(filters, from_date=None, to_date=None):
    if from_date and to_date:
        filters["modified"] = ["between", [getdate(from_date), getdate(to_date)]]
    elif from_date:
        filters["modified"] = [">=", getdate(from_date)]
    elif to_date:
        filters["modified"] = ["<=", getdate(to_date)]


def _safe_fbr_settings_summary(settings=None):
    settings = settings or get_fbr_settings()
    control_state = get_fbr_control_state()
    return {
        "enabled": bool(settings.get("enabled")),
        "mode": settings.get("mode") or "Disabled",
        "submit_trigger": settings.get("submit_trigger") or "Manual",
        "sandbox_token_configured": bool(settings.get("sandbox_token_configured")),
        "production_token_configured": bool(settings.get("production_token_configured")),
        "seller_ntn_cnic": settings.get("seller_ntn_cnic") or "",
        "seller_business_name": settings.get("seller_business_name") or "",
        "seller_province": settings.get("seller_province") or "",
        "seller_address": settings.get("seller_address") or "",
        "block_sale_if_fbr_fails": bool(settings.get("block_sale_if_fbr_fails")),
        "retry_enabled": bool(settings.get("retry_enabled")),
        "max_retry_count": cint(settings.get("max_retry_count") or 0),
        "pause_reason": settings.get("pause_reason") or "",
        "paused_at": settings.get("paused_at"),
        "paused_by": settings.get("paused_by") or "",
        "last_sync_status": settings.get("last_sync_status") or "",
        "production_post_connected": bool(control_state.get("production_post_connected")),
        "auto_submit_active": bool(control_state.get("auto_submit_active")),
        "retry_worker_active": bool(control_state.get("retry_worker_active")),
        "can_manual_submit": bool(control_state.get("can_manual_submit")),
        "can_manual_validate": bool(control_state.get("can_manual_validate")),
    }


def _readiness_check(key, label, ready, value, level=None):
    if level is None:
        level = "ready" if ready else "missing"
    return {
        "key": key,
        "label": label,
        "ready": bool(ready),
        "value": value,
        "level": level,
    }


@frappe.whitelist()
def get_tax_center_boot():
    _require_tax_view()
    profile = _profile_dict()
    fbr_settings = get_fbr_settings()
    fbr_control_state = get_fbr_control_state()
    counts = {
        "items_need_review": _get_count("Ledgix Item Tax Profile", {"active": 1, "needs_review": 1}),
        "missing_hs_code": _count_missing_hs_code(),
        "active_categories": _get_count("Ledgix Tax Category", {"active": 1}),
        "category_tax_enabled": _get_count("Ledgix Category", {"tax_defaults_enabled": 1, "is_active": 1}),
        "active_rates": _get_count("Ledgix Tax Rate", {"active": 1}),
    }
    return {
        "profile": profile,
        "status": {
            "tax_enabled": bool(profile.get("tax_enabled")),
            "pricing_mode": "Inclusive" if cint(profile.get("price_includes_tax")) else "Exclusive",
            "fbr_enabled": bool(fbr_control_state.get("enabled")),
            "fbr_mode": fbr_control_state.get("mode") or "Disabled",
        },
        "permissions": _permissions(),
        "counts": counts,
        "fbr_settings_summary": _safe_fbr_settings_summary(fbr_settings),
        "fbr_control_state": fbr_control_state,
    }


@frappe.whitelist()
def get_tax_profile_settings():
    _require_tax_view()
    return _profile_dict()


@frappe.whitelist()
def save_tax_profile_settings(values):
    _require_tax_edit()
    values = _json_values(values)
    doc = frappe.get_single("Ledgix Tax Profile")
    for field in PROFILE_FIELDS:
        if field in values:
            setattr(doc, field, values.get(field))
    doc.save(ignore_permissions=True)
    return _profile_dict()


@frappe.whitelist()
def preview_tax_calculation(amount, tax_category=None, price_includes_tax=None):
    _require_tax_view()
    profile = _profile_dict()
    tax_category = tax_category or profile.get("default_tax_category")
    if price_includes_tax is None or price_includes_tax == "":
        price_includes_tax = profile.get("price_includes_tax")
    rate = _effective_or_default_rate(tax_category, "Sales")
    return calculate_tax_breakdown(amount=flt(amount), tax_rate=rate, price_includes_tax=cint(price_includes_tax))


@frappe.whitelist()
def get_tax_categories(page=1, page_size=15, search=None, status=None, tax_type=None):
    _require_tax_view()
    filters = {}
    if status in ("Active", "Inactive"):
        filters["active"] = 1 if status == "Active" else 0
    if tax_type and tax_type != "All":
        filters["tax_type"] = tax_type
    or_filters = None
    if search:
        term = _like(search)
        or_filters = {"category_name": ["like", term], "tax_type": ["like", term], "description": ["like", term]}
    return _normalize_category_rows(_get_rows("Ledgix Tax Category", _category_fields(), filters, or_filters, "category_name asc", page, page_size))


@frappe.whitelist()
def save_tax_category(values):
    _require_tax_edit()
    values = _json_values(values)

    name = (values.get("name") or "").strip()
    category_name = (values.get("category_name") or "").strip()

    if name:
        if not frappe.db.exists("Ledgix Tax Category", name):
            frappe.throw("Tax category does not exist.")

        doc = frappe.get_doc("Ledgix Tax Category", name)

        if category_name and category_name != doc.category_name:
            frappe.throw("Category name cannot be changed after creation. Create a new category instead.")

    else:
        if not category_name:
            frappe.throw("Category name is required.")

        if frappe.db.exists("Ledgix Tax Category", category_name):
            frappe.throw("A tax category with this name already exists.")

        doc = frappe.new_doc("Ledgix Tax Category")
        doc.category_name = category_name

    rate_field = _category_rate_field()
    if "default_rate" in values or "default_rate_" in values:
        setattr(doc, rate_field, values.get("default_rate", values.get("default_rate_")))

    for field in CATEGORY_BASE_FIELDS:
        if field in ("name", "category_name"):
            continue
        if field in values:
            setattr(doc, field, values.get(field))

    doc.save(ignore_permissions=True)
    return doc.as_dict()



@frappe.whitelist()
def toggle_tax_category(name, active):
    _require_tax_edit()
    frappe.db.set_value("Ledgix Tax Category", name, "active", _bool_int(active), update_modified=True)
    return {"name": name, "active": _bool_int(active)}


@frappe.whitelist()
def get_tax_rates(page=1, page_size=15, search=None, tax_category=None, active=None, applies_to=None):
    _require_tax_view()
    filters = {}
    if tax_category:
        filters["tax_category"] = tax_category
    if active in ("Active", "Inactive", 1, 0, "1", "0"):
        filters["active"] = 1 if active in ("Active", 1, "1") else 0
    if applies_to and applies_to != "All":
        filters["applies_to"] = applies_to
    or_filters = None
    if search:
        term = _like(search)
        or_filters = {"name": ["like", term], "tax_category": ["like", term], "province": ["like", term]}
    return _get_rows("Ledgix Tax Rate", RATE_FIELDS, filters, or_filters, "effective_from desc, modified desc", page, page_size)


@frappe.whitelist()
def save_tax_rate(values):
    _require_tax_edit()
    values = _json_values(values)

    name = (values.get("name") or "").strip()

    if name:
        if not frappe.db.exists("Ledgix Tax Rate", name):
            frappe.throw("Tax rate does not exist.")

        doc = frappe.get_doc("Ledgix Tax Rate", name)

        locked_fields = (
            "tax_category",
            "rate",
            "effective_from",
            "effective_to",
            "applies_to",
            "province",
            "active",
        )

        for field in locked_fields:
            if field not in values:
                continue

            old_value = doc.get(field)
            new_value = values.get(field)

            if field == "rate":
                changed = flt(old_value) != flt(new_value)
            elif field == "active":
                changed = cint(old_value) != cint(new_value)
            elif field in ("effective_from", "effective_to"):
                if old_value or new_value:
                    changed = getdate(old_value) != getdate(new_value)
                else:
                    changed = False
            else:
                changed = (old_value or "") != (new_value or "")

            if changed:
                frappe.throw(
                    "Existing tax rates cannot be edited because tax rate history must remain audit-safe. "
                    "Close the old rate and create a new effective rate instead."
                )

        return doc.as_dict()

    doc = frappe.new_doc("Ledgix Tax Rate")

    for field in RATE_FIELDS:
        if field != "name" and field in values:
            setattr(doc, field, values.get(field))

    doc.save(ignore_permissions=True)
    return doc.as_dict()



@frappe.whitelist()
def close_tax_rate(name, effective_to, reason=None):
    _require_tax_edit()
    if not effective_to:
        frappe.throw("Effective To date is required.")
    doc = frappe.get_doc("Ledgix Tax Rate", name)
    old = {"effective_to": doc.effective_to, "active": doc.active}
    doc.effective_to = getdate(effective_to)
    doc.active = 0
    doc.save(ignore_permissions=True)
    _insert_audit_log(
        "Ledgix Tax Rate",
        doc.name,
        "effective_to / active",
        old,
        {"effective_to": doc.effective_to, "active": doc.active},
        reason,
    )
    return doc.as_dict()


def _count_mapped_items_in_category(category_name):
    if not _has_doctype("Ledgix Item") or not _has_doctype("Ledgix Item Tax Profile"):
        return 0

    return cint(
        frappe.db.sql(
            """
            SELECT COUNT(DISTINCT i.name)
            FROM `tabLedgix Item` i
            INNER JOIN `tabLedgix Item Tax Profile` p ON p.item = i.name AND p.active = 1
            WHERE i.category = %(category)s
              AND i.active = 1
            """,
            {"category": category_name},
            as_list=True,
        )[0][0]
    )


def _count_items_in_category(category_name, active_only=True):
    filters = {"category": category_name}
    if active_only:
        filters["active"] = 1
    return _get_count("Ledgix Item", filters)


def _tax_source_label(tax_source):
    return {
        "item": "Item Override",
        "category": "Category",
        "shop_default": "Shop Default",
    }.get(tax_source or "", "Not Set")


@frappe.whitelist()
def get_category_tax_mappings(page=1, page_size=15, search=None, status=None, tax_enabled=None):
    _require_tax_view()
    filters = {}
    if status in ("Active", "Inactive"):
        filters["is_active"] = 1 if status == "Active" else 0
    if tax_enabled in ("Enabled", "Disabled", 1, 0, "1", "0"):
        filters["tax_defaults_enabled"] = 1 if tax_enabled in ("Enabled", 1, "1") else 0

    or_filters = None
    if search:
        term = _like(search)
        or_filters = {
            "name": ["like", term],
            "category_name": ["like", term],
            "default_tax_category": ["like", term],
            "default_sales_type": ["like", term],
        }

    result = _get_rows(
        "Ledgix Category",
        PRODUCT_CATEGORY_TAX_FIELDS,
        filters,
        or_filters,
        "category_name asc",
        page,
        page_size,
    )

    for row in result["rows"]:
        category_name = row.get("name") or row.get("category_name")
        row["item_count"] = _count_items_in_category(category_name)
        row["mapped_item_count"] = _count_mapped_items_in_category(category_name)
        row["unmapped_item_count"] = max(cint(row["item_count"]) - cint(row["mapped_item_count"]), 0)
        row["default_tax_rate"] = (
            _effective_or_default_rate(row.get("default_tax_category"), "Sales")
            if row.get("default_tax_category")
            else 0
        )

    result["summary"] = {
        "total_categories": _get_count("Ledgix Category"),
        "tax_enabled_categories": _get_count("Ledgix Category", {"tax_defaults_enabled": 1, "is_active": 1}),
        "categories_missing_tax_category": (
            cint(
                frappe.db.sql(
                    """
                    SELECT COUNT(*)
                    FROM `tabLedgix Category`
                    WHERE tax_defaults_enabled = 1
                      AND (default_tax_category IS NULL OR default_tax_category = '')
                    """,
                    as_list=True,
                )[0][0]
            )
            if _has_doctype("Ledgix Category")
            else 0
        ),
    }
    return result


@frappe.whitelist()
def save_category_tax_defaults(values):
    _require_item_mapping_edit()
    values = _json_values(values)
    name = values.get("name") or values.get("category_name")
    if not name:
        frappe.throw("Category is required.")

    if not frappe.db.exists("Ledgix Category", name):
        frappe.throw(f"Category {name} does not exist.")

    doc = frappe.get_doc("Ledgix Category", name)
    for field in (
        "tax_defaults_enabled",
        "default_tax_category",
        "default_taxable",
        "default_sales_type",
        "default_uom_for_fbr",
        "default_scenario_id",
    ):
        if field in values:
            setattr(doc, field, values.get(field))

    if cint(doc.tax_defaults_enabled) and not doc.default_tax_category:
        frappe.throw("Default Tax Category is required when category tax defaults are enabled.")

    doc.save(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def apply_category_tax_to_items(category, only_unmapped=1):
    _require_item_mapping_edit()
    if not category:
        frappe.throw("Category is required.")

    defaults = get_category_tax_defaults(category)
    if not defaults.get("tax_defaults_enabled"):
        frappe.throw("Enable tax defaults on this category first.")
    if not defaults.get("default_tax_category"):
        frappe.throw("Default tax category is required on this category.")

    items = frappe.get_all(
        "Ledgix Item",
        filters={"category": category, "active": 1},
        pluck="name",
    )

    created = 0
    skipped = 0
    for item in items:
        existing = frappe.db.get_value("Ledgix Item Tax Profile", {"item": item, "active": 1}, "name")
        if existing:
            skipped += 1
            continue

        doc = frappe.new_doc("Ledgix Item Tax Profile")
        doc.item = item
        doc.taxable = cint(defaults.get("default_taxable", 1))
        doc.tax_category = defaults.get("default_tax_category")
        doc.uom_for_fbr = defaults.get("default_uom_for_fbr") or ""
        doc.sales_type = defaults.get("default_sales_type") or ""
        doc.scenario_id = defaults.get("default_scenario_id") or ""
        doc.needs_review = 1
        doc.active = 1
        doc.default_tax_rate = _effective_or_default_rate(doc.tax_category, "Sales")
        doc.save(ignore_permissions=True)
        created += 1

    return {
        "category": category,
        "only_unmapped": cint(only_unmapped),
        "total_items": len(items),
        "created": created,
        "skipped": skipped,
    }


@frappe.whitelist()
def preview_item_effective_tax(item):
    _require_tax_view()
    if not item:
        frappe.throw("Item is required.")

    ctx = resolve_item_tax_context(item)
    tax_category = ctx.get("tax_category")
    rate = _effective_or_default_rate(tax_category, "Sales") if tax_category else 0

    return {
        **ctx,
        "tax_source_label": _tax_source_label(ctx.get("tax_source")),
        "effective_tax_rate": rate,
    }


@frappe.whitelist()
def get_item_tax_mappings(page=1, page_size=15, search=None, filter_type=None, active=None):
    _require_tax_view()
    filters = {}
    if active in ("Active", "Inactive", 1, 0, "1", "0"):
        filters["active"] = 1 if active in ("Active", 1, "1") else 0
    if filter_type == "needs_review":
        filters["needs_review"] = 1
    elif filter_type == "missing_hs_code":
        page, page_size, start = _paginate(page, page_size)

        conditions = [
            "active = 1",
            "taxable = 1",
            "(hs_code IS NULL OR hs_code = '')",
        ]
        values = {}

        if active in ("Active", "Inactive", 1, 0, "1", "0"):
            conditions[0] = "active = %(active)s"
            values["active"] = 1 if active in ("Active", 1, "1") else 0

        if search:
            values["term"] = _like(search)
            conditions.append(
                """
                (
                    name LIKE %(term)s
                    OR item LIKE %(term)s
                    OR tax_category LIKE %(term)s
                    OR sales_type LIKE %(term)s
                )
                """
            )

        where_clause = " AND ".join(conditions)

        total = frappe.db.sql(
            f"""
            SELECT COUNT(*)
            FROM `tabLedgix Item Tax Profile`
            WHERE {where_clause}
            """,
            values,
            as_list=True,
        )[0][0]

        rows = frappe.db.sql(
            f"""
            SELECT {", ".join(ITEM_MAPPING_FIELDS)}
            FROM `tabLedgix Item Tax Profile`
            WHERE {where_clause}
            ORDER BY modified DESC
            LIMIT %(page_size)s OFFSET %(start)s
            """,
            {**values, "page_size": page_size, "start": start},
            as_dict=True,
        )

        result = _table(rows, total, page, page_size)
    elif filter_type == "taxable":
        filters["taxable"] = 1
    elif filter_type == "exempt":
        filters["taxable"] = 0
    or_filters = None

    if search:
        term = _like(search)
        or_filters = {
            "name": ["like", term],
            "item": ["like", term],
            "hs_code": ["like", term],
            "tax_category": ["like", term],
            "sales_type": ["like", term],
        }

    if filter_type != "missing_hs_code":
        result = _get_rows(
            "Ledgix Item Tax Profile",
            ITEM_MAPPING_FIELDS,
            filters,
            or_filters,
            "modified desc",
            page,
            page_size,
        )
    for row in result["rows"]:
        item_data = frappe.db.get_value(
            "Ledgix Item",
            row.get("item"),
            ["item_name", "barcode", "sku", "category", "current_stock", "active"],
            as_dict=True,
        ) or {}
        ctx = resolve_item_tax_context(row.get("item"))
        row.update(
            {
                "item_name": item_data.get("item_name"),
                "barcode": item_data.get("barcode"),
                "sku": item_data.get("sku"),
                "item_category": item_data.get("category"),
                "current_stock": item_data.get("current_stock"),
                "item_active": item_data.get("active"),
                "product_category": ctx.get("product_category"),
                "tax_source": ctx.get("tax_source") or "item",
                "tax_source_label": _tax_source_label(ctx.get("tax_source") or "item"),
                "effective_tax_category": ctx.get("tax_category"),
            }
        )
    result["summary"] = {
        "total_mappings": _get_count("Ledgix Item Tax Profile"),
        "needs_review": _get_count("Ledgix Item Tax Profile", {"active": 1, "needs_review": 1}),
        "missing_hs_code": _count_missing_hs_code(),
        "active_taxable": _get_count("Ledgix Item Tax Profile", {"active": 1, "taxable": 1}),
    }
    return result


@frappe.whitelist()
def save_item_tax_mapping(values):
    _require_item_mapping_edit()
    values = _json_values(values)
    item = values.get("item")
    if not item:
        frappe.throw("Item is required.")
    name = values.get("name")
    existing = frappe.db.get_value("Ledgix Item Tax Profile", {"item": item, "active": 1}, "name")
    if existing and existing != name:
        name = existing
    doc = frappe.get_doc("Ledgix Item Tax Profile", name) if name else frappe.new_doc("Ledgix Item Tax Profile")
    for field in ITEM_MAPPING_FIELDS:
        if field != "name" and field in values:
            setattr(doc, field, values.get(field))
    doc.default_tax_rate = _effective_or_default_rate(doc.tax_category, "Sales")
    doc.save(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def mark_item_tax_reviewed(name):
    _require_item_mapping_edit()
    frappe.db.set_value("Ledgix Item Tax Profile", name, "needs_review", 0, update_modified=True)
    return {"name": name, "needs_review": 0}


@frappe.whitelist()
def toggle_item_tax_mapping(name, active):
    _require_item_mapping_edit()
    frappe.db.set_value("Ledgix Item Tax Profile", name, "active", _bool_int(active), update_modified=True)
    return {"name": name, "active": _bool_int(active)}

def _snapshot_date_condition(date_field, from_date=None, to_date=None):
    conditions = []
    values = {}

    if from_date:
        conditions.append(f"DATE({date_field}) >= %(from_date)s")
        values["from_date"] = getdate(from_date)

    if to_date:
        conditions.append(f"DATE({date_field}) <= %(to_date)s")
        values["to_date"] = getdate(to_date)

    return conditions, values



def _snapshot_filters(search=None, from_date=None, to_date=None, tax_category=None, pricing_mode=None):
    filters = {}
    _date_filter(filters, from_date, to_date)
    if tax_category:
        filters["tax_category"] = tax_category
    if pricing_mode == "Inclusive":
        filters["price_includes_tax"] = 1
    elif pricing_mode == "Exclusive":
        filters["price_includes_tax"] = 0
    return filters


@frappe.whitelist()
def get_invoice_tax_snapshots(page=1, page_size=15, search=None, from_date=None, to_date=None, tax_category=None, pricing_mode=None):
    _require_tax_view()
    page, page_size, start = _paginate(page, page_size)

    conditions = []
    values = {}

    date_conditions, date_values = _snapshot_date_condition("s.sale_date", from_date, to_date)
    conditions.extend(date_conditions)
    values.update(date_values)

    if tax_category:
        conditions.append("d.tax_category = %(tax_category)s")
        values["tax_category"] = tax_category

    if pricing_mode == "Inclusive":
        conditions.append("d.price_includes_tax = 1")
    elif pricing_mode == "Exclusive":
        conditions.append("d.price_includes_tax = 0")

    sale_expr = "COALESCE(NULLIF(d.sale, ''), d.parent)"

    if search:
        conditions.append(
            """
            (
                COALESCE(NULLIF(d.sale, ''), d.parent) LIKE %(term)s
                OR d.item LIKE %(term)s
                OR d.tax_category LIKE %(term)s
                OR d.hs_code LIKE %(term)s
            )
            """
        )
        values["term"] = _like(search)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = frappe.db.sql(
        f"""
        SELECT COUNT(*)
        FROM `tabLedgix Invoice Tax Detail` d
        LEFT JOIN `tabLedgix Sale` s ON s.name = {sale_expr}
        {where_clause}
        """,
        values,
        as_list=True,
    )[0][0]

    rows = frappe.db.sql(
        f"""
        SELECT
            d.name, d.modified, {sale_expr} AS sale, d.sale_item_row, d.item, d.qty,
            d.rate, d.gross_amount, d.discount_amount, d.taxable_amount,
            d.tax_category, d.tax_rate, d.tax_amount, d.net_amount,
            d.price_includes_tax, d.hs_code, d.uom_for_fbr, d.sales_type,
            d.scenario_id, d.sro_schedule_number, d.sro_item_serial_number
        FROM `tabLedgix Invoice Tax Detail` d
        LEFT JOIN `tabLedgix Sale` s ON s.name = {sale_expr}
        {where_clause}
        ORDER BY s.sale_date DESC, d.modified DESC
        LIMIT %(page_size)s OFFSET %(start)s
        """,
        {**values, "page_size": page_size, "start": start},
        as_dict=True,
    )

    return _table(rows, total, page, page_size)



@frappe.whitelist()
def get_return_tax_snapshots(page=1, page_size=15, search=None, from_date=None, to_date=None, tax_category=None, pricing_mode=None):
    _require_tax_view()
    page, page_size, start = _paginate(page, page_size)

    conditions = []
    values = {}

    date_conditions, date_values = _snapshot_date_condition("r.creation", from_date, to_date)
    conditions.extend(date_conditions)
    values.update(date_values)

    if tax_category:
        conditions.append("d.tax_category = %(tax_category)s")
        values["tax_category"] = tax_category

    if pricing_mode == "Inclusive":
        conditions.append("d.price_includes_tax = 1")
    elif pricing_mode == "Exclusive":
        conditions.append("d.price_includes_tax = 0")

    sales_return_expr = "COALESCE(NULLIF(d.sales_return, ''), d.parent)"
    original_sale_expr = "COALESCE(NULLIF(d.original_sale, ''), r.original_sale)"

    if search:
        conditions.append(
            """
            (
                COALESCE(NULLIF(d.sales_return, ''), d.parent) LIKE %(term)s
                OR COALESCE(NULLIF(d.original_sale, ''), r.original_sale) LIKE %(term)s
                OR d.item LIKE %(term)s
                OR d.tax_category LIKE %(term)s
                OR d.hs_code LIKE %(term)s
            )
            """
        )
        values["term"] = _like(search)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = frappe.db.sql(
        f"""
        SELECT COUNT(*)
        FROM `tabLedgix Return Tax Detail` d
        LEFT JOIN `tabLedgix Sales Return` r ON r.name = {sales_return_expr}
        {where_clause}
        """,
        values,
        as_list=True,
    )[0][0]

    rows = frappe.db.sql(
        f"""
        SELECT
            d.name, d.modified, {sales_return_expr} AS sales_return,
            {original_sale_expr} AS original_sale, d.original_sale_item_row, d.item,
            d.returned_qty, d.original_tax_rate, d.returned_taxable_amount,
            d.returned_tax_amount, d.gross_amount, d.taxable_amount, d.tax_rate,
            d.tax_amount, d.net_amount, d.price_includes_tax, d.tax_category,
            d.hs_code, d.uom_for_fbr, d.sales_type, d.scenario_id,
            d.sro_schedule_number, d.sro_item_serial_number
        FROM `tabLedgix Return Tax Detail` d
        LEFT JOIN `tabLedgix Sales Return` r ON r.name = {sales_return_expr}
        {where_clause}
        ORDER BY r.creation DESC, d.modified DESC
        LIMIT %(page_size)s OFFSET %(start)s
        """,
        {**values, "page_size": page_size, "start": start},
        as_dict=True,
    )

    return _table(rows, total, page, page_size)



@frappe.whitelist()
def get_fbr_readiness():
    _require_tax_view()
    settings = get_fbr_settings()
    control_state = get_fbr_control_state()
    settings_summary = _safe_fbr_settings_summary(settings)
    active_profiles = _get_count("Ledgix Item Tax Profile", {"active": 1})
    missing_hs = _count_missing_hs_code()
    missing_uom = _count_missing_item_tax_field("uom_for_fbr")
    missing_scenario = _count_missing_item_tax_field("scenario_id")
    needs_review = _get_count("Ledgix Item Tax Profile", {"active": 1, "needs_review": 1})
    hs_covered = max(active_profiles - missing_hs, 0)
    uom_covered = max(active_profiles - missing_uom, 0)
    scenario_covered = max(active_profiles - missing_scenario, 0)
    coverage = flt((hs_covered / active_profiles) * 100, 2) if active_profiles else 0
    uom_coverage = flt((uom_covered / active_profiles) * 100, 2) if active_profiles else 0
    scenario_coverage = flt((scenario_covered / active_profiles) * 100, 2) if active_profiles else 0
    mode = settings_summary.get("mode") or "Disabled"
    enabled = bool(settings_summary.get("enabled"))
    sandbox_token_ready = mode != "Sandbox" or bool(settings_summary.get("sandbox_token_configured"))
    production_token_ready = mode != "Production" or bool(settings_summary.get("production_token_configured"))
    scenario_ready = missing_scenario == 0
    scenario_level = "missing" if mode == "Sandbox" and not scenario_ready else ("warning" if not scenario_ready else "ready")
    production_post_connected = bool(control_state.get("production_post_connected"))
    auto_submit_active = bool(control_state.get("auto_submit_active"))
    retry_worker_active = bool(control_state.get("retry_worker_active"))
    sales_return_meta = frappe.get_meta("Ledgix Sales Return")
    return_fbr_ready = bool(
        sales_return_meta.has_field("fbr_status") and sales_return_meta.has_field("fbr_invoice_number")
    )
    qr_logo_ready = True
    checks = [
        _readiness_check("fbr_mode", "FBR Mode", mode in ("Sandbox", "Production"), mode),
        _readiness_check("fbr_enabled", "FBR Enabled", enabled and mode in ("Sandbox", "Production"), "Enabled" if enabled else "Disabled"),
        _readiness_check("sandbox_token", "Sandbox Token", sandbox_token_ready, "Configured" if settings_summary.get("sandbox_token_configured") else "Missing", "ready" if sandbox_token_ready else "missing"),
        _readiness_check("production_token", "Production Token", production_token_ready, "Configured" if settings_summary.get("production_token_configured") else "Missing", "ready" if production_token_ready else "warning"),
        _readiness_check("production_post", "Production Post", production_post_connected, "Connected" if production_post_connected else "Not Active", "ready" if production_post_connected else "warning"),
        _readiness_check("seller_ntn_cnic", "Seller NTN/CNIC", bool(settings_summary.get("seller_ntn_cnic")), settings_summary.get("seller_ntn_cnic") or "Missing"),
        _readiness_check("seller_business_name", "Seller Business Name", bool(settings_summary.get("seller_business_name")), settings_summary.get("seller_business_name") or "Missing"),
        _readiness_check("seller_province", "Seller Province", bool(settings_summary.get("seller_province")), settings_summary.get("seller_province") or "Missing"),
        _readiness_check("seller_address", "Seller Address", bool(settings_summary.get("seller_address")), settings_summary.get("seller_address") or "Missing"),
        _readiness_check("hs_code_coverage", "HS Code Coverage", active_profiles > 0 and missing_hs == 0, f"{coverage}%"),
        _readiness_check("uom_coverage", "UOM for FBR Coverage", active_profiles > 0 and missing_uom == 0, f"{uom_coverage}%"),
        _readiness_check("scenario_coverage", "Scenario ID Coverage", scenario_ready, f"{scenario_coverage}%", scenario_level),
        _readiness_check("item_review", "Items Needing Review", needs_review == 0, needs_review, "ready" if needs_review == 0 else "warning"),
        _readiness_check("auto_submit", "Auto Submit", auto_submit_active, "Active" if auto_submit_active else "Not Active", "ready" if auto_submit_active else "warning"),
        _readiness_check("retry_worker", "Retry Worker", retry_worker_active, "Active" if retry_worker_active else "Not Active", "ready" if retry_worker_active else "warning"),
        _readiness_check("reference_api_sync", "Reference API Sync", False, "Manual check required", "warning"),
        _readiness_check(
            "qr_logo_printing",
            "QR / Logo Printing",
            qr_logo_ready,
            "POS receipt shows FBR invoice # and QR when FBR returns them.",
            "ready",
        ),
        _readiness_check(
            "return_debit_note",
            "Sales Return / Debit Note",
            return_fbr_ready,
            "Credit note FBR flow available via Sales Return." if return_fbr_ready else "Sales Return FBR fields missing.",
            "ready" if return_fbr_ready else "warning",
        ),
    ]
    scorable_checks = [row for row in checks if row.get("key") not in {"production_post", "auto_submit", "retry_worker"}]
    ready_count = len([row for row in scorable_checks if row.get("ready")])
    return {
        "checks": checks,
        "stats": {
            "active_item_tax_profiles": active_profiles,
            "missing_hs_code": missing_hs,
            "missing_uom_for_fbr": missing_uom,
            "missing_scenario_id": missing_scenario,
            "items_needing_review": needs_review,
            "hs_code_coverage_percent": coverage,
            "uom_for_fbr_coverage_percent": uom_coverage,
            "scenario_id_coverage_percent": scenario_coverage,
            "fbr_enabled": bool(control_state.get("enabled")),
            "fbr_mode": control_state.get("mode") or "Disabled",
            "sandbox_token_configured": bool(settings_summary.get("sandbox_token_configured")),
            "production_token_configured": bool(settings_summary.get("production_token_configured")),
            "production_post_connected": production_post_connected,
            "auto_submit_active": auto_submit_active,
            "retry_worker_active": retry_worker_active,
            "qr_logo_ready": qr_logo_ready,
            "submission_status": "Production Post is connected when Production mode is enabled with a configured token.",
        },
        "ready_score": flt((ready_count / len(scorable_checks)) * 100, 2) if scorable_checks else 0,
        "settings_summary": settings_summary,
        "control_state": control_state,
    }


@frappe.whitelist()
def get_fbr_submission_logs(page=1, page_size=15, search=None, status=None, from_date=None, to_date=None):
    _require_tax_view()
    page, page_size, start = _paginate(page, page_size)

    if not _has_doctype("Ledgix FBR Submission Log"):
        return _table([], 0, page, page_size, summary={})

    filters = {}
    if status and status != "All":
        filters["fbr_status"] = status
    _date_filter(filters, from_date, to_date)

    or_filters = None
    if search:
        term = _like(search)
        or_filters = {
            "name": ["like", term],
            "reference_name": ["like", term],
            "invoice_type": ["like", term],
            "fbr_status": ["like", term],
            "error_code": ["like", term],
            "error_message": ["like", term],
        }

    result = _get_rows(
        "Ledgix FBR Submission Log",
        FBR_LOG_FIELDS,
        filters,
        or_filters,
        "modified desc",
        page,
        page_size,
    )

    summary_rows = frappe.get_all(
        "Ledgix FBR Submission Log",
        fields=["fbr_status", "count(name) as total"],
        filters=filters,
        group_by="fbr_status",
        ignore_permissions=True,
    )
    result["summary"] = {row.get("fbr_status") or "Unknown": cint(row.get("total")) for row in summary_rows}
    return result
