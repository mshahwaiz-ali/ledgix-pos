from __future__ import annotations

"""ERPNext-native legal taxable-base inputs for FBR special tax treatment.

Ledgix does not calculate monetary tax here. It supplies the legally defined
per-line taxable base to ERPNext's ``erpnext_taxable_base_resolvers`` extension
point. ERPNext remains responsible for rate application, totals and GL.
"""

import frappe
from frappe.utils import cint, flt, getdate

SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}
MAPPING_DOCTYPE = "Ledgix FBR Item Mapping"

CHARGE_TYPE = "On Notified Retail Price"
TRANSACTION_VALUE = "Transaction Value"
NOTIFIED_RETAIL_PRICE = "Notified Retail Price"

BASIS_FIELD = "custom_ledgix_fbr_tax_basis"
NOTIFIED_VALUE_FIELD = "custom_ledgix_fbr_notified_retail_price"


def _effective_mapping(company: str, item_code: str, posting_date) -> dict | None:
    rows = frappe.get_all(
        MAPPING_DOCTYPE,
        filters={
            "company": company,
            "erpnext_item": item_code,
            "active": 1,
        },
        fields=[
            "name",
            "effective_from",
            "effective_to",
            "needs_review",
            "tax_basis",
            "notified_retail_price",
        ],
        order_by="effective_from desc, creation desc",
        limit_page_length=0,
    )

    date = getdate(posting_date)
    matches = []
    for row in rows:
        start = getdate(row.get("effective_from")) if row.get("effective_from") else None
        end = getdate(row.get("effective_to")) if row.get("effective_to") else None
        if start and date < start:
            continue
        if end and date > end:
            continue
        matches.append(dict(row))

    if len(matches) > 1:
        frappe.throw(
            f"Multiple active FBR Item Mappings overlap for {item_code} on {date}."
        )
    return matches[0] if matches else None


def _source_return_row(doc, item):
    source_name = str(doc.get("return_against") or "").strip()
    if not source_name or not frappe.db.exists(doc.doctype, source_name):
        return None

    source = frappe.get_doc(doc.doctype, source_name)
    ref_field = "sales_invoice_item" if doc.doctype == "Sales Invoice" else "pos_invoice_item"
    source_row_name = str(item.get(ref_field) or "").strip()

    if source_row_name:
        for row in source.get("items") or []:
            if row.name == source_row_name:
                return row

    candidates = [
        row
        for row in source.get("items") or []
        if row.get("item_code") == item.get("item_code")
    ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        frappe.throw(
            "Cannot preserve Third Schedule taxable base for return item "
            f"{item.get('item_code')}: source row is ambiguous."
        )
    return None


def _stamp_notified_value(item, notified_value: float) -> None:
    item.set(BASIS_FIELD, NOTIFIED_RETAIL_PRICE)
    item.set(NOTIFIED_VALUE_FIELD, flt(notified_value, 2))


def _preserve_return_basis(doc, item) -> bool:
    source_row = _source_return_row(doc, item)
    if not source_row:
        return False

    source_basis = str(source_row.get(BASIS_FIELD) or "").strip()
    if source_basis != NOTIFIED_RETAIL_PRICE:
        return False

    source_value = flt(source_row.get(NOTIFIED_VALUE_FIELD))
    if source_value <= 0:
        frappe.throw(
            "Source transaction has Third Schedule tax basis but no valid "
            f"notified retail price for item {item.get('item_code')}."
        )

    _stamp_notified_value(item, source_value)
    return True


def stamp_fbr_taxable_base_inputs(doc, method=None) -> None:
    """Stamp legal base inputs before ERPNext calculates tax; calculate no tax here."""

    if not doc or doc.doctype not in SUPPORTED_DOCTYPES:
        return

    company = str(doc.get("company") or "").strip()
    if not company:
        return

    posting_date = doc.get("posting_date") or doc.get("transaction_date") or frappe.utils.nowdate()

    for item in doc.get("items") or []:
        item_code = str(item.get("item_code") or "").strip()
        if not item_code:
            continue

        if cint(doc.get("is_return")) and _preserve_return_basis(doc, item):
            continue

        mapping = _effective_mapping(company, item_code, posting_date)
        if not mapping or mapping.get("tax_basis") != NOTIFIED_RETAIL_PRICE:
            if not cint(doc.get("is_return")):
                item.set(BASIS_FIELD, TRANSACTION_VALUE)
                item.set(NOTIFIED_VALUE_FIELD, 0)
            continue

        if cint(mapping.get("needs_review")):
            frappe.throw(
                "Third Schedule accounting is blocked because FBR Item Mapping "
                f"{mapping.get('name')} for {item_code} still Needs Review."
            )

        notified_value = flt(mapping.get("notified_retail_price"))
        if notified_value <= 0:
            frappe.throw(
                f"Approved Third Schedule mapping for {item_code} has no valid Notified Retail Price."
            )

        _stamp_notified_value(item, notified_value)


def resolve_notified_retail_price(calc, item, tax):
    """Return the legal base; ERPNext applies the tax rate and owns the amount."""

    basis = str(item.get(BASIS_FIELD) or "").strip()
    if basis != NOTIFIED_RETAIL_PRICE:
        return flt(item.get("net_amount"))

    notified_value = flt(item.get(NOTIFIED_VALUE_FIELD))
    if notified_value <= 0:
        frappe.throw(
            "Third Schedule invoice row is missing its stamped Notified Retail Price."
        )

    return flt(notified_value * flt(item.get("qty")))
