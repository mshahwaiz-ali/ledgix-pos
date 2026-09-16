from __future__ import annotations

import json
from base64 import b64encode
from io import BytesIO

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api.brand import get_brand_settings, get_print_logo_url


SUPPORTED_PRINT_DOCTYPES = {"Sales Invoice", "POS Invoice"}


def get_fbr_qr_data_uri(fbr_invoice_number) -> str:
    """Return a self-contained SVG QR for the unique FBR invoice number."""

    value = str(fbr_invoice_number or "").strip()
    if not value:
        return ""

    from pyqrcode import create as qrcreate

    qr = qrcreate(value, error="L", version=2)
    stream = BytesIO()
    try:
        qr.svg(stream, scale=4, background="#ffffff", module_color="#000000")
        encoded = b64encode(stream.getvalue()).decode("ascii")
    finally:
        stream.close()

    return f"data:image/svg+xml;base64,{encoded}"


def _json(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def _fbr_settings_public() -> dict:
    if not frappe.db.exists("DocType", "Ledgix FBR Settings"):
        return {}
    settings = frappe.get_single("Ledgix FBR Settings")
    return {
        "seller_business_name": settings.get("seller_business_name") or "",
        "seller_ntn_cnic": settings.get("seller_ntn_cnic") or "",
        "seller_province": settings.get("seller_province") or "",
        "seller_address": settings.get("seller_address") or "",
        "software_registration_number": settings.get("software_registration_number") or "",
        "digital_invoicing_logo": settings.get("digital_invoicing_logo") or "",
    }


def _buyer(doc) -> dict:
    customer = None
    if doc.get("customer") and frappe.db.exists("Customer", doc.customer):
        customer = frappe.get_cached_doc("Customer", doc.customer)
    return {
        "name": doc.get("customer_name") or (customer.get("customer_name") if customer else "") or doc.get("customer") or "Walk-in Customer",
        "ntn_cnic": (customer.get("custom_ledgix_buyer_ntn_cnic") if customer else "") or (customer.get("tax_id") if customer else "") or "",
        "strn": (customer.get("custom_ledgix_buyer_strn") if customer else "") or "",
        "registration_type": (customer.get("custom_ledgix_buyer_registration_type") if customer else "") or "Unregistered",
        "province": (customer.get("custom_ledgix_buyer_province") if customer else "") or "",
        "address": doc.get("address_display") or (customer.get("custom_ledgix_buyer_fbr_address") if customer else "") or "",
    }


def _seller() -> dict:
    brand = get_brand_settings()
    fbr = _fbr_settings_public()
    return {
        "name": fbr.get("seller_business_name") or brand.get("brand_name") or "Ledgix",
        "address": fbr.get("seller_address") or "",
        "phone": "",
        "email": "",
        "ntn": fbr.get("seller_ntn_cnic") or "",
        "strn": "",
        "province": fbr.get("seller_province") or "",
        "logo": get_print_logo_url(),
        "software_registration_number": fbr.get("software_registration_number") or "",
        "digital_invoicing_logo": fbr.get("digital_invoicing_logo") or "",
    }


def _line_context(row) -> dict:
    snapshot = _json(row.get("custom_ledgix_fbr_snapshot_json"))
    tax = abs(flt(snapshot.get("sales_tax"), 2))
    extra = abs(flt(snapshot.get("extra_tax"), 2))
    further = abs(flt(snapshot.get("further_tax"), 2))
    fed = abs(flt(snapshot.get("fed_payable"), 2))
    withheld = abs(flt(snapshot.get("sales_tax_withheld_at_source"), 2))
    return {
        "item_code": row.get("item_code") or "",
        "item_name": row.get("item_name") or row.get("description") or row.get("item_code") or "",
        "description": row.get("description") or "",
        "qty": abs(flt(row.get("qty"), 3)),
        "uom": row.get("uom") or row.get("stock_uom") or "",
        "rate": abs(flt(row.get("rate"), 2)),
        "amount": abs(flt(row.get("amount"), 2)),
        "net_amount": abs(flt(row.get("net_amount"), 2)),
        "discount_amount": abs(flt(row.get("discount_amount"), 2)),
        "hs_code": snapshot.get("hs_code") or row.get("custom_ledgix_fbr_hs_code") or "",
        "fbr_uom": snapshot.get("uom_for_fbr") or row.get("custom_ledgix_fbr_uom") or "",
        "sales_type": snapshot.get("sales_type") or row.get("custom_ledgix_fbr_sales_type") or "",
        "rate_description": snapshot.get("fbr_rate_description") or row.get("custom_ledgix_fbr_rate_description") or "",
        "tax_rate": abs(flt(snapshot.get("tax_rate"), 2)),
        "taxable_amount": abs(flt(snapshot.get("taxable_amount"), 2)),
        "sales_tax": tax,
        "extra_tax": extra,
        "further_tax": further,
        "fed_payable": fed,
        "withheld_tax": withheld,
        "other_tax": extra + further + fed,
        "line_total": abs(flt(snapshot.get("erpnext_line_total") or row.get("amount"), 2)),
        "tax_basis": snapshot.get("tax_basis") or row.get("custom_ledgix_fbr_tax_basis") or "",
        "notified_retail_price": abs(flt(snapshot.get("notified_retail_price"), 2)),
        "snapshot_version": cint(snapshot.get("snapshot_version") or row.get("custom_ledgix_fbr_snapshot_version")),
    }


def get_native_invoice_print_context(reference_doctype, reference_name) -> dict:
    """Return a stable Ledgix print view over native ERPNext invoices.

    This helper is intentionally read-only. Amounts, tax rows, payment state and
    return identity are taken from ERPNext; FBR QR/reference/status are read from
    the Phase 9 metadata persisted on the same native document.
    """

    doctype = str(reference_doctype or "").strip()
    name = str(reference_name or "").strip()
    if doctype not in SUPPORTED_PRINT_DOCTYPES:
        frappe.throw("Ledgix native print source must be Sales Invoice or POS Invoice.")
    doc = frappe.get_doc(doctype, name)
    is_return = bool(cint(doc.get("is_return")))
    original = None
    if is_return and doc.get("return_against") and frappe.db.exists(doctype, doc.return_against):
        original = frappe.get_doc(doctype, doc.return_against)

    fbr_invoice_number = str(doc.get("custom_ledgix_fbr_invoice_number") or "").strip()
    original_fbr_invoice = str(original.get("custom_ledgix_fbr_invoice_number") or "").strip() if original else ""
    payments = []
    for payment in doc.get("payments") or []:
        payments.append(
            {
                "mode": payment.get("mode_of_payment") or "",
                "amount": abs(flt(payment.get("amount"), 2)),
                "reference": payment.get("reference_no") or "",
            }
        )

    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "title": "CREDIT NOTE" if is_return else ("SALES RECEIPT" if doc.doctype == "POS Invoice" else "TAX INVOICE"),
        "is_return": is_return,
        "return_against": doc.get("return_against") or "",
        "posting_date": doc.get("posting_date"),
        "posting_time": doc.get("posting_time"),
        "company": doc.get("company") or "",
        "currency": doc.get("currency") or "PKR",
        "seller": _seller(),
        "buyer": _buyer(doc),
        "items": [_line_context(row) for row in doc.get("items") or []],
        "net_total": abs(flt(doc.get("net_total"), 2)),
        "tax_total": abs(flt(doc.get("total_taxes_and_charges"), 2)),
        "grand_total": abs(flt(doc.get("grand_total"), 2)),
        "rounded_total": abs(flt(doc.get("rounded_total") or doc.get("grand_total"), 2)),
        "paid_amount": abs(flt(doc.get("paid_amount"), 2)),
        "outstanding_amount": abs(flt(doc.get("outstanding_amount"), 2)),
        "change_amount": abs(flt(doc.get("change_amount"), 2)),
        "payments": payments,
        "remarks": doc.get("remarks") or "",
        "fbr_status": doc.get("custom_ledgix_fbr_status") or "Not Submitted",
        "fbr_invoice_number": fbr_invoice_number,
        "fbr_reference": doc.get("custom_ledgix_fbr_reference") or "",
        "fbr_submitted_at": doc.get("custom_ledgix_fbr_submitted_at"),
        "fbr_qr_data_uri": get_fbr_qr_data_uri(fbr_invoice_number),
        "original_fbr_invoice_number": original_fbr_invoice,
        "fbr_reconciliation_required": bool(cint(doc.get("custom_ledgix_fbr_reconciliation_required"))),
        "snapshot_version": cint(doc.get("custom_ledgix_fbr_snapshot_version")),
        "authority": "ERPNext Sales/POS Invoice + Ledgix FBR metadata",
    }
