from __future__ import annotations

import frappe
from frappe.utils import cint, getdate

from ledgix_saas.api import fbr_v2_center, legacy_tax_guard


VIEW_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager")

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


def _require_tax_view():
    if not _roles().intersection(VIEW_ROLES):
        frappe.throw(
            "You do not have permission to access Tax Center.",
            frappe.PermissionError,
        )


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


def _get_rows(
    doctype,
    fields,
    filters=None,
    or_filters=None,
    order_by="modified desc",
    page=1,
    page_size=15,
):
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


def _date_filter(filters, from_date=None, to_date=None):
    if from_date and to_date:
        filters["modified"] = ["between", [getdate(from_date), getdate(to_date)]]
    elif from_date:
        filters["modified"] = [">=", getdate(from_date)]
    elif to_date:
        filters["modified"] = ["<=", getdate(to_date)]


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


@frappe.whitelist()
def get_tax_center_boot():
    return legacy_tax_guard.reject_legacy_tax_action(action="get_tax_center_boot")


@frappe.whitelist()
def get_tax_profile_settings():
    return legacy_tax_guard.reject_legacy_tax_action(action="get_tax_profile_settings")


@frappe.whitelist()
def save_tax_profile_settings(values):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="save_tax_profile_settings",
        values=values,
    )


@frappe.whitelist()
def preview_tax_calculation(amount, tax_category=None, price_includes_tax=None):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="preview_tax_calculation",
        amount=amount,
        tax_category=tax_category,
        price_includes_tax=price_includes_tax,
    )


@frappe.whitelist()
def get_tax_categories(page=1, page_size=15, search=None, status=None, tax_type=None):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="get_tax_categories",
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        tax_type=tax_type,
    )


@frappe.whitelist()
def save_tax_category(values):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="save_tax_category",
        values=values,
    )


@frappe.whitelist()
def toggle_tax_category(name, active):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="toggle_tax_category",
        name=name,
        active=active,
    )


@frappe.whitelist()
def get_tax_rates(
    page=1,
    page_size=15,
    search=None,
    tax_category=None,
    active=None,
    applies_to=None,
):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="get_tax_rates",
        page=page,
        page_size=page_size,
        search=search,
        tax_category=tax_category,
        active=active,
        applies_to=applies_to,
    )


@frappe.whitelist()
def save_tax_rate(values):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="save_tax_rate",
        values=values,
    )


@frappe.whitelist()
def close_tax_rate(name, effective_to, reason=None):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="close_tax_rate",
        name=name,
        effective_to=effective_to,
        reason=reason,
    )


@frappe.whitelist()
def get_category_tax_mappings(
    page=1,
    page_size=15,
    search=None,
    status=None,
    tax_enabled=None,
):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="get_category_tax_mappings",
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        tax_enabled=tax_enabled,
    )


@frappe.whitelist()
def save_category_tax_defaults(values):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="save_category_tax_defaults",
        values=values,
    )


@frappe.whitelist()
def apply_category_tax_to_items(category, only_unmapped=1):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="apply_category_tax_to_items",
        category=category,
        only_unmapped=only_unmapped,
    )


@frappe.whitelist()
def preview_item_effective_tax(item):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="preview_item_effective_tax",
        item=item,
    )


@frappe.whitelist()
def get_item_tax_mappings(
    page=1,
    page_size=15,
    search=None,
    filter_type=None,
    active=None,
):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="get_item_tax_mappings",
        page=page,
        page_size=page_size,
        search=search,
        filter_type=filter_type,
        active=active,
    )


@frappe.whitelist()
def save_item_tax_mapping(values):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="save_item_tax_mapping",
        values=values,
    )


@frappe.whitelist()
def mark_item_tax_reviewed(name):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="mark_item_tax_reviewed",
        name=name,
    )


@frappe.whitelist()
def toggle_item_tax_mapping(name, active):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="toggle_item_tax_mapping",
        name=name,
        active=active,
    )


@frappe.whitelist()
def get_invoice_tax_snapshots(
    page=1,
    page_size=15,
    search=None,
    from_date=None,
    to_date=None,
    tax_category=None,
    pricing_mode=None,
):
    _require_tax_view()
    page, page_size, start = _paginate(page, page_size)

    conditions = []
    values = {}

    date_conditions, date_values = _snapshot_date_condition(
        "s.sale_date",
        from_date,
        to_date,
    )
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
            d.name, d.modified, {sale_expr} AS sale, d.sale_item_row, d.item,
            d.qty, d.rate, d.gross_amount, d.discount_amount,
            d.taxable_amount, d.tax_category, d.tax_rate, d.tax_amount,
            d.net_amount, d.price_includes_tax, d.hs_code, d.uom_for_fbr,
            d.sales_type, d.scenario_id, d.sro_schedule_number,
            d.sro_item_serial_number
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
def get_return_tax_snapshots(
    page=1,
    page_size=15,
    search=None,
    from_date=None,
    to_date=None,
    tax_category=None,
    pricing_mode=None,
):
    _require_tax_view()
    page, page_size, start = _paginate(page, page_size)

    conditions = []
    values = {}

    date_conditions, date_values = _snapshot_date_condition(
        "r.creation",
        from_date,
        to_date,
    )
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
            {original_sale_expr} AS original_sale, d.original_sale_item_row,
            d.item, d.returned_qty, d.original_tax_rate,
            d.returned_taxable_amount, d.returned_tax_amount, d.gross_amount,
            d.taxable_amount, d.tax_rate, d.tax_amount, d.net_amount,
            d.price_includes_tax, d.tax_category, d.hs_code, d.uom_for_fbr,
            d.sales_type, d.scenario_id, d.sro_schedule_number,
            d.sro_item_serial_number
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
    return fbr_v2_center.get_fbr_readiness()


@frappe.whitelist()
def get_fbr_submission_logs(
    page=1,
    page_size=15,
    search=None,
    status=None,
    from_date=None,
    to_date=None,
):
    _require_tax_view()
    page, page_size, _ = _paginate(page, page_size)

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
    result["summary"] = {
        row.get("fbr_status") or "Unknown": cint(row.get("total"))
        for row in summary_rows
    }
    return result
