import re

import frappe
from frappe.utils import cint, flt, getdate, nowdate


HS_CODE_PATTERN = re.compile(r"^[0-9]{2,8}(\.[0-9]{1,8})?$")


# ============================================================
# LEDGIX TAX ENGINE HELPERS
# ============================================================

def is_tax_enabled():
    """
    Returns whether Ledgix taxation is enabled from Single Tax Profile.
    """
    if not frappe.db.exists("DocType", "Ledgix Tax Profile"):
        return False

    return bool(frappe.db.get_single_value("Ledgix Tax Profile", "tax_enabled"))


def get_tax_profile():
    """
    Returns main Single Tax Profile values used by the tax engine.
    """
    if not frappe.db.exists("DocType", "Ledgix Tax Profile"):
        return {
            "tax_enabled": False,
            "price_includes_tax": False,
            "default_tax_category": "",
            "receipt_tax_display_enabled": False,
            "default_sales_type": "",
            "default_buyer_type": "",
        }

    return {
        "tax_enabled": bool(frappe.db.get_single_value("Ledgix Tax Profile", "tax_enabled")),
        "price_includes_tax": bool(frappe.db.get_single_value("Ledgix Tax Profile", "price_includes_tax")),
        "default_tax_category": frappe.db.get_single_value("Ledgix Tax Profile", "default_tax_category") or "",
        "receipt_tax_display_enabled": bool(
            frappe.db.get_single_value("Ledgix Tax Profile", "receipt_tax_display_enabled")
        ),
        "default_sales_type": frappe.db.get_single_value("Ledgix Tax Profile", "default_sales_type") or "",
        "default_buyer_type": frappe.db.get_single_value("Ledgix Tax Profile", "default_buyer_type") or "",
    }


def get_item_tax_profile(item):
    """
    Returns active tax profile mapping for a Ledgix Item.
    """
    if not item:
        return {}

    if not frappe.db.exists("DocType", "Ledgix Item Tax Profile"):
        return {}

    profiles = frappe.get_all(
        "Ledgix Item Tax Profile",
        filters={
            "item": item,
            "active": 1,
        },
        fields=[
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
            "needs_review",
        ],
        order_by="modified desc",
        limit=1,
    )

    return profiles[0] if profiles else {}


def get_item_product_category(item):
    if not item or not frappe.db.exists("DocType", "Ledgix Item"):
        return ""
    if not frappe.db.exists("Ledgix Item", item):
        return ""
    return frappe.db.get_value("Ledgix Item", item, "category") or ""


def get_category_tax_defaults(category_name):
    empty = {
        "tax_defaults_enabled": False,
        "default_tax_category": "",
        "default_taxable": 1,
        "default_sales_type": "",
        "default_uom_for_fbr": "",
        "default_scenario_id": "",
    }
    if not category_name or not frappe.db.exists("DocType", "Ledgix Category"):
        return empty
    if not frappe.db.exists("Ledgix Category", category_name):
        return empty

    meta = frappe.db.get_value(
        "Ledgix Category",
        category_name,
        [
            "tax_defaults_enabled",
            "default_tax_category",
            "default_taxable",
            "default_sales_type",
            "default_uom_for_fbr",
            "default_scenario_id",
        ],
        as_dict=True,
    ) or {}

    return {
        "tax_defaults_enabled": bool(cint(meta.get("tax_defaults_enabled"))),
        "default_tax_category": meta.get("default_tax_category") or "",
        "default_taxable": cint(meta.get("default_taxable", 1)),
        "default_sales_type": meta.get("default_sales_type") or "",
        "default_uom_for_fbr": meta.get("default_uom_for_fbr") or "",
        "default_scenario_id": meta.get("default_scenario_id") or "",
    }


def resolve_item_tax_context(item, profile=None):
    """
    Resolve effective tax + FBR fields for an item.

    Priority: Item Tax Profile -> Product Category defaults -> Shop default.
    """
    profile = profile or get_tax_profile()
    item_tax_profile = get_item_tax_profile(item) or {}
    product_category = get_item_product_category(item)
    category_defaults = get_category_tax_defaults(product_category)

    tax_source = ""
    tax_category = ""
    taxable = 1

    if item_tax_profile.get("tax_category"):
        tax_source = "item"
        tax_category = item_tax_profile.get("tax_category")
        taxable = cint(item_tax_profile.get("taxable", 1))
    elif category_defaults.get("tax_defaults_enabled") and category_defaults.get("default_tax_category"):
        tax_source = "category"
        tax_category = category_defaults.get("default_tax_category")
        taxable = cint(category_defaults.get("default_taxable", 1))
    elif profile.get("default_tax_category"):
        tax_source = "shop_default"
        tax_category = profile.get("default_tax_category")
        taxable = 1

    return {
        "item": item,
        "product_category": product_category,
        "tax_source": tax_source,
        "tax_category": tax_category,
        "taxable": taxable,
        "hs_code": item_tax_profile.get("hs_code") or "",
        "uom_for_fbr": item_tax_profile.get("uom_for_fbr") or category_defaults.get("default_uom_for_fbr") or "",
        "sales_type": (
            item_tax_profile.get("sales_type")
            or category_defaults.get("default_sales_type")
            or profile.get("default_sales_type")
            or ""
        ),
        "scenario_id": item_tax_profile.get("scenario_id") or category_defaults.get("default_scenario_id") or "",
        "sro_schedule_number": item_tax_profile.get("sro_schedule_number") or "",
        "sro_item_serial_number": item_tax_profile.get("sro_item_serial_number") or "",
        "has_item_tax_profile": bool(item_tax_profile),
        "category_tax_enabled": bool(category_defaults.get("tax_defaults_enabled")),
    }


def get_tax_category_meta(tax_category):
    """Tax category flags and default rate used by the sale tax engine."""
    empty = {"is_exempt": False, "is_zero_rated": False, "default_rate": 0}
    if not tax_category or not frappe.db.exists("DocType", "Ledgix Tax Category"):
        return empty
    if not frappe.db.exists("Ledgix Tax Category", tax_category):
        return empty

    meta = frappe.db.get_value(
        "Ledgix Tax Category",
        tax_category,
        ["is_exempt", "is_zero_rated", "default_rate"],
        as_dict=True,
    ) or {}

    return {
        "is_exempt": bool(meta.get("is_exempt")),
        "is_zero_rated": bool(meta.get("is_zero_rated")),
        "default_rate": flt(meta.get("default_rate")),
    }


def get_business_province():
    """Business province from Ledgix Tax Profile (used for province-specific rates)."""
    if not frappe.db.exists("DocType", "Ledgix Tax Profile"):
        return ""
    return frappe.db.get_single_value("Ledgix Tax Profile", "province") or ""


def _rate_matches_province(row_province, business_province):
    row_province = (row_province or "").strip()
    if not row_province:
        return True
    return row_province == (business_province or "").strip()


def _rate_province_priority(row_province, business_province):
    row_province = (row_province or "").strip()
    business_province = (business_province or "").strip()
    if row_province and row_province == business_province:
        return 2
    if not row_province:
        return 1
    return 0


def get_effective_tax_rate(tax_category, posting_date=None, applies_to="Sales", province=None):
    """
    Returns active effective tax rate for category/date.
    Uses tax rate history; never overwrites old rates.
    Province-specific rates take priority over blank-province (national) rates.
    """
    if not tax_category:
        return 0

    if not frappe.db.exists("DocType", "Ledgix Tax Rate"):
        return 0

    posting_date = getdate(posting_date or nowdate())
    if province is None:
        province = get_business_province()

    rates = frappe.get_all(
        "Ledgix Tax Rate",
        filters={
            "tax_category": tax_category,
            "active": 1,
            "effective_from": ["<=", posting_date],
        },
        fields=[
            "name",
            "rate",
            "effective_from",
            "effective_to",
            "applies_to",
            "province",
            "creation",
        ],
        order_by="effective_from desc, creation desc",
    )

    candidates = []

    for row in rates:
        effective_to = row.get("effective_to")

        if effective_to and getdate(effective_to) < posting_date:
            continue

        row_applies_to = row.get("applies_to")

        if row_applies_to not in (None, "", applies_to, "Both"):
            continue

        if not _rate_matches_province(row.get("province"), province):
            continue

        candidates.append(row)

    if not candidates:
        return 0

    candidates.sort(
        key=lambda row: (
            _rate_province_priority(row.get("province"), province),
            getdate(row.get("effective_from")),
            row.get("creation") or "",
        ),
        reverse=True,
    )

    return flt(candidates[0].get("rate"))


def resolve_tax_rate(tax_category, posting_date=None, applies_to="Sales", province=None):
    """
    Resolves sale tax rate using category flags, rate history, then category default.
    """
    meta = get_tax_category_meta(tax_category)
    if meta.get("is_exempt") or meta.get("is_zero_rated"):
        return 0

    rate = flt(
        get_effective_tax_rate(
            tax_category=tax_category,
            posting_date=posting_date,
            applies_to=applies_to,
            province=province,
        )
    )
    if rate:
        return rate

    return flt(meta.get("default_rate"))


def resolve_item_tax_category(item, profile=None):
    """Resolve tax category for an item using item, category, then shop defaults."""
    return resolve_item_tax_context(item, profile=profile).get("tax_category") or ""


def validate_hs_code_format(hs_code):
    return bool(HS_CODE_PATTERN.match((hs_code or "").strip()))


def validate_item_tax_profile_hs_code(doc):
    """Validate HS code on Ledgix Item Tax Profile save."""
    if not cint(getattr(doc, "active", 1)):
        return

    hs_code = (getattr(doc, "hs_code", None) or "").strip()
    if not hs_code:
        if cint(getattr(doc, "needs_review", 0)):
            return
        frappe.throw("HS Code is required for active item tax mappings.")

    if not validate_hs_code_format(hs_code):
        frappe.throw(
            "HS Code format is invalid. Use 2-8 digits with an optional decimal segment (e.g. 0101.21)."
        )

    digits = hs_code.replace(".", "")
    if len(digits) < 4 or len(digits) > 8:
        frappe.throw("HS Code should contain 4 to 8 digits.")


def validate_sale_item_tax_mappings(doc, throw=False):
    """
    Validate that each sale line can resolve tax mapping when taxation is enabled.
    """
    profile = get_tax_profile()
    if not profile.get("tax_enabled"):
        return {"valid": True, "errors": [], "warnings": []}

    errors = []
    warnings = []

    for row in doc.get("items") or []:
        item = row.get("item") or row.get("item_code") or row.get("ledgix_item")
        if not item:
            continue

        ctx = resolve_item_tax_context(item, profile=profile)
        tax_category = ctx.get("tax_category")

        if not tax_category:
            errors.append(
                f"Item {item} has no tax category. Set category tax defaults, create an Item Tax "
                "Profile mapping, or set a Default Tax Category in Tax Profile."
            )
            continue

        tax_source = ctx.get("tax_source")
        if tax_source == "category":
            warnings.append(
                f"Item {item} uses category tax ({ctx.get('product_category')} -> {tax_category})."
            )
        elif tax_source == "shop_default":
            warnings.append(
                f"Item {item} uses shop default tax category {tax_category}."
            )

        if not ctx.get("hs_code"):
            warnings.append(
                f"Item {item} has no HS code mapping yet (required for FBR submission)."
            )

    result = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }

    if throw and errors:
        frappe.throw("; ".join(errors))

    return result


def calculate_tax_amount(taxable_amount, tax_rate):
    """
    Tax-exclusive tax amount calculation.
    Kept for compatibility.
    """
    taxable_amount = flt(taxable_amount)
    tax_rate = flt(tax_rate)

    if taxable_amount <= 0 or tax_rate <= 0:
        return 0

    return flt((taxable_amount * tax_rate) / 100, 2)


def calculate_tax_breakdown(amount, tax_rate, price_includes_tax=False):
    """
    Calculates tax breakdown for both pricing modes.

    Exclusive:
        amount = taxable/base amount
        customer pays amount + tax

    Inclusive:
        amount = final customer/shelf price
        tax is extracted from inside amount
    """
    amount = flt(amount)
    tax_rate = flt(tax_rate)
    price_includes_tax = bool(price_includes_tax)

    if amount <= 0:
        return {
            "gross_amount": 0,
            "taxable_amount": 0,
            "tax_rate": flt(tax_rate, 2),
            "tax_amount": 0,
            "net_amount": 0,
            "price_includes_tax": 1 if price_includes_tax else 0,
        }

    if tax_rate <= 0:
        return {
            "gross_amount": flt(amount, 2),
            "taxable_amount": flt(amount, 2),
            "tax_rate": 0,
            "tax_amount": 0,
            "net_amount": flt(amount, 2),
            "price_includes_tax": 1 if price_includes_tax else 0,
        }

    if price_includes_tax:
        gross_amount = flt(amount, 2)
        taxable_amount = flt(gross_amount / (1 + (tax_rate / 100)), 2)
        tax_amount = flt(gross_amount - taxable_amount, 2)
        net_amount = gross_amount
    else:
        taxable_amount = flt(amount, 2)
        tax_amount = flt((taxable_amount * tax_rate) / 100, 2)
        net_amount = flt(taxable_amount + tax_amount, 2)
        gross_amount = flt(amount, 2)

    return {
        "gross_amount": flt(gross_amount, 2),
        "taxable_amount": flt(taxable_amount, 2),
        "tax_rate": flt(tax_rate, 2),
        "tax_amount": flt(tax_amount, 2),
        "net_amount": flt(net_amount, 2),
        "price_includes_tax": 1 if price_includes_tax else 0,
    }


# ============================================================
# SALE ITEM TAX SNAPSHOT
# ============================================================

def calculate_sale_item_tax_snapshot(
    item,
    taxable_amount,
    posting_date=None,
    qty=1,
    applies_to="Sales",
    price_includes_tax=None,
):
    """
    Build one immutable tax snapshot row for a sale item.

    This does not save anything.
    This does not modify Sale submit logic.
    """

    profile = get_tax_profile()

    if not profile.get("tax_enabled"):
        return None

    if price_includes_tax is None:
        price_includes_tax = bool(profile.get("price_includes_tax"))

    ctx = resolve_item_tax_context(item, profile=profile)
    tax_category = ctx.get("tax_category")

    if not tax_category:
        return None

    item_is_non_taxable = not cint(ctx.get("taxable", 1))
    category_meta = get_tax_category_meta(tax_category)
    category_is_non_taxable = bool(
        category_meta.get("is_exempt") or category_meta.get("is_zero_rated")
    )

    tax_rate = 0 if (item_is_non_taxable or category_is_non_taxable) else resolve_tax_rate(
        tax_category=tax_category,
        posting_date=posting_date,
        applies_to=applies_to,
    )

    breakdown = calculate_tax_breakdown(
        amount=taxable_amount,
        tax_rate=tax_rate,
        price_includes_tax=price_includes_tax,
    )

    return {
        "item": item,
        "qty": flt(qty),
        "tax_category": tax_category,
        "tax_source": ctx.get("tax_source"),
        "product_category": ctx.get("product_category"),
        "gross_amount": flt(breakdown.get("gross_amount")),
        "taxable_amount": flt(breakdown.get("taxable_amount")),
        "tax_rate": flt(breakdown.get("tax_rate")),
        "tax_amount": flt(breakdown.get("tax_amount")),
        "net_amount": flt(breakdown.get("net_amount")),
        "price_includes_tax": breakdown.get("price_includes_tax"),

        # Compliance snapshot fields
        "hs_code": ctx.get("hs_code"),
        "uom_for_fbr": ctx.get("uom_for_fbr"),
        "sales_type": ctx.get("sales_type"),
        "scenario_id": ctx.get("scenario_id"),
        "sro_schedule_number": ctx.get("sro_schedule_number"),
        "sro_item_serial_number": ctx.get("sro_item_serial_number"),
    }


def calculate_sale_tax_snapshot(items, posting_date=None):
    """
    Builds immutable tax snapshot rows for sale items.

    Expected item row shape:
    {
        "item": "ITEM-001",
        "qty": 2,
        "amount": 1000
    }

    This does not save anything.
    This does not modify Sale submit logic.
    """

    if not items:
        return []

    profile = get_tax_profile()
    price_includes_tax = bool(profile.get("price_includes_tax"))
    snapshot_rows = []

    for row in items:
        item = row.get("item") or row.get("item_code")
        qty = flt(row.get("qty") or row.get("quantity") or 1)
        amount = flt(
            row.get("taxable_amount")
            or row.get("amount")
            or row.get("total_amount")
            or 0
        )

        tax_row = calculate_sale_item_tax_snapshot(
            item=item,
            taxable_amount=amount,
            posting_date=posting_date,
            qty=qty,
            applies_to="Sales",
            price_includes_tax=price_includes_tax,
        )

        if tax_row:
            snapshot_rows.append(tax_row)

    return snapshot_rows


def summarize_tax_snapshot(snapshot_rows):
    """
    Returns total gross amount, taxable amount, tax amount, and net amount from snapshot rows.
    """

    total_gross_amount = 0
    total_taxable_amount = 0
    total_tax_amount = 0
    total_net_amount = 0
    price_includes_tax = 0

    for row in snapshot_rows or []:
        total_gross_amount += flt(row.get("gross_amount"))
        total_taxable_amount += flt(row.get("taxable_amount"))
        total_tax_amount += flt(row.get("tax_amount"))
        total_net_amount += flt(row.get("net_amount"))

        if row.get("price_includes_tax"):
            price_includes_tax = 1

    return {
        "total_gross_amount": flt(total_gross_amount, 2),
        "total_taxable_amount": flt(total_taxable_amount, 2),
        "total_tax_amount": flt(total_tax_amount, 2),
        "total_net_amount": flt(total_net_amount, 2),
        "price_includes_tax": price_includes_tax,
    }


def build_sale_tax_payable_summary(base_total, snapshot_summary):
    """
    Builds sale payable summary using base sale total and tax snapshot summary.

    Inclusive:
        payable_total = base_total

    Exclusive:
        payable_total = base_total + total_tax_amount
    """

    base_total = flt(base_total)
    total_tax_amount = flt((snapshot_summary or {}).get("total_tax_amount"))
    price_includes_tax = bool((snapshot_summary or {}).get("price_includes_tax"))

    if price_includes_tax:
        payable_total = flt(base_total, 2)
    else:
        payable_total = flt(base_total + total_tax_amount, 2)

    return {
        "base_total": flt(base_total, 2),
        "total_tax_amount": flt(total_tax_amount, 2),
        "payable_total": payable_total,
        "price_includes_tax": 1 if price_includes_tax else 0,
    }


# ============================================================
# SALE DOC TAX SNAPSHOT PREPARATION / APPLICATION
# ============================================================

def get_sale_doc_posting_date(doc):
    """
    Returns the posting date used for sale tax calculation.
    """

    return (
        getattr(doc, "sale_date", None)
        or getattr(doc, "posting_date", None)
        or nowdate()
    )


def prepare_sale_tax_snapshot_for_doc(doc):
    """
    Prepares immutable sale tax snapshot rows from a Ledgix Sale document.

    This does not save anything.
    This does not submit anything.
    This does not modify Sales submit logic.
    """

    empty_summary = {
        "total_gross_amount": 0,
        "total_taxable_amount": 0,
        "total_tax_amount": 0,
        "total_net_amount": 0,
        "price_includes_tax": 0,
    }

    if not doc:
        return {
            "tax_enabled": False,
            "posting_date": nowdate(),
            "snapshot_rows": [],
            "summary": empty_summary,
            "validation": {
                "valid": True,
                "messages": [],
            },
        }

    tax_enabled = is_tax_enabled()
    posting_date = get_sale_doc_posting_date(doc)

    if not tax_enabled:
        return {
            "tax_enabled": False,
            "posting_date": posting_date,
            "snapshot_rows": [],
            "summary": empty_summary,
            "validation": {
                "valid": True,
                "messages": [],
            },
        }

    profile = get_tax_profile()
    price_includes_tax = bool(profile.get("price_includes_tax"))

    sale_items = []

    for row in doc.get("items") or []:
        item = (
            row.get("item")
            or row.get("item_code")
            or row.get("ledgix_item")
        )

        qty = flt(
            row.get("qty")
            or row.get("quantity")
            or 1
        )

        rate = flt(row.get("rate") or 0)

        line_amount = flt(
            row.get("taxable_amount")
            or row.get("amount")
            or row.get("total_amount")
            or row.get("line_total")
            or (qty * rate)
            or 0
        )

        sale_items.append({
            "item": item,
            "qty": qty,
            "rate": rate,
            "line_amount": line_amount,
            "sale_item_row": row.get("name"),
            "gross_amount": line_amount,
            "discount_amount": flt(row.get("discount_amount") or 0),
        })

    snapshot_rows = []
    mapping_validation = validate_sale_item_tax_mappings(doc)
    snapshot_errors = list(mapping_validation.get("errors") or [])

    for row in sale_items:
        tax_row = calculate_sale_item_tax_snapshot(
            item=row.get("item"),
            taxable_amount=row.get("line_amount"),
            posting_date=posting_date,
            qty=row.get("qty"),
            applies_to="Sales",
            price_includes_tax=price_includes_tax,
        )

        if not tax_row:
            item_code = row.get("item") or "Unknown item"
            snapshot_errors.append(
                f"Item {item_code} could not generate a tax snapshot. "
                "Check item tax mapping or default tax category."
            )
            continue

        tax_row.update({
            "sale_item_row": row.get("sale_item_row"),
            "rate": flt(row.get("rate")),
            "gross_amount": flt(row.get("gross_amount")),
            "discount_amount": flt(row.get("discount_amount")),
        })

        snapshot_rows.append(tax_row)

    summary = summarize_tax_snapshot(snapshot_rows)
    validation = validate_tax_snapshot_totals(doc, summary)
    totals_messages = list(validation.pop("messages", []) or [])
    validation["errors"] = list(snapshot_errors) + totals_messages
    validation["warnings"] = list(mapping_validation.get("warnings") or [])
    validation["valid"] = validation.get("valid") and not validation["errors"]

    return {
        "tax_enabled": True,
        "posting_date": posting_date,
        "snapshot_rows": snapshot_rows,
        "summary": summary,
        "validation": validation,
    }


def validate_tax_snapshot_totals(doc, summary):
    """
    Validates prepared tax snapshot totals against the sale document.

    Soft validation only.
    Does not throw.
    Does not save.
    """

    messages = []

    sale_total = flt(getattr(doc, "total_amount", 0))
    price_includes_tax = bool((summary or {}).get("price_includes_tax"))

    if price_includes_tax:
        comparison_total = flt((summary or {}).get("total_gross_amount"))
        comparison_label = "gross snapshot total"
    else:
        comparison_total = flt((summary or {}).get("total_taxable_amount"))
        comparison_label = "taxable snapshot total"

    if sale_total > 0 and abs(sale_total - comparison_total) > 0.01:
        messages.append(
            f"Sale total amount {sale_total} does not match {comparison_label} {comparison_total}."
        )

    return {
        "valid": len(messages) == 0,
        "messages": messages,
    }


def apply_tax_snapshot_to_sale_doc(doc):
    """
    Applies calculated immutable tax snapshot rows to a Ledgix Sale document.

    This does not submit the document.
    This does not save the document.
    """

    prepared = prepare_sale_tax_snapshot_for_doc(doc)
    validation = prepared.get("validation") or {}

    if validation.get("errors"):
        frappe.throw("; ".join(validation.get("errors")))

    summary = prepared.get("summary") or {}

    base_total = flt(getattr(doc, "total_amount", 0))

    if not base_total:
        for row in doc.get("items") or []:
            qty = flt(row.get("qty") or row.get("quantity") or 0)
            rate = flt(row.get("rate") or 0)

            line_amount = flt(
                row.get("amount")
                or row.get("total_amount")
                or row.get("line_total")
                or (qty * rate)
                or 0
            )

            base_total += line_amount

        base_total = flt(base_total, 2)

    payable = build_sale_tax_payable_summary(
        base_total,
        summary,
    )

    if hasattr(doc, "total_amount"):
        doc.total_amount = flt(base_total, 2)

    doc.tax_amount = flt(payable.get("total_tax_amount"), 2)
    doc.grand_total = flt(payable.get("payable_total"), 2)

    if hasattr(doc, "tax_details"):
        doc.set("tax_details", [])

    for tax_row in prepared.get("snapshot_rows") or []:
        doc.append("tax_details", tax_row)

    return {
        "summary": summary,
        "payable": payable,
        "validation": validation,
    }


# ============================================================
# SALE FORM TAX PREVIEW API
# ============================================================

@frappe.whitelist()
def preview_sale_tax_for_form(items=None, posting_date=None, sale_date=None, customer=None):
    from ledgix_saas.api.security import require_ledgix_cashier_or_above

    require_ledgix_cashier_or_above()
    items = frappe.parse_json(items) if isinstance(items, str) else (items or [])
    posting_date = posting_date or sale_date

    normalized_items = []
    base_total = 0

    for row in items:
        item = row.get("item") or row.get("item_code")
        qty = flt(row.get("quantity") or row.get("qty") or 0)
        rate = flt(row.get("rate") or 0)
        amount = flt(row.get("amount") or (qty * rate))

        if not item or qty <= 0:
            continue

        base_total += amount

        normalized_items.append({
            "item": item,
            "qty": qty,
            "amount": amount,
            "taxable_amount": amount,
        })

    snapshot_rows = calculate_sale_tax_snapshot(
        normalized_items,
        posting_date=posting_date,
    )

    summary = summarize_tax_snapshot(snapshot_rows)

    payable = build_sale_tax_payable_summary(
        base_total,
        summary,
    )

    validation = {
        "valid": True,
        "messages": [],
    }

    return {
        "tax_enabled": is_tax_enabled(),
        "price_includes_tax": payable.get("price_includes_tax"),
        "total_amount": flt(base_total, 2),
        "tax_amount": flt(payable.get("total_tax_amount"), 2),
        "grand_total": flt(payable.get("payable_total"), 2),
        "tax_details": snapshot_rows,
        "summary": summary,
        "payable": payable,
        "validation": validation,
    }