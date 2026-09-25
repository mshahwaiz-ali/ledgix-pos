from __future__ import annotations

import json
from base64 import b64encode
from io import BytesIO

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api.brand import get_brand_settings, get_print_logo_url
from ledgix_saas.services import erpnext_fbr_identity, fbr_v2_snapshot_persistence


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


def _v2_profile_public(company: str) -> dict:
    company = str(company or "").strip()
    if not company or not frappe.db.exists("DocType", "Ledgix FBR Integration Profile"):
        return {
            "profile_name": "",
            "software_registration_number": "",
            "digital_invoicing_logo": "",
        }

    row = frappe.db.get_value(
        "Ledgix FBR Integration Profile",
        {"company": company},
        ["name", "software_registration_number"],
        as_dict=True,
    )
    return {
        "profile_name": row.name if row else "",
        "software_registration_number": (
            row.software_registration_number if row else ""
        ) or "",
        # No authoritative V2 FBR-logo field exists yet. Do not reuse the
        # retired singleton setting or fabricate official artwork.
        "digital_invoicing_logo": "",
    }


def _identity_for_print(doc) -> tuple[dict, str, str]:
    version = cint(doc.get("custom_ledgix_fbr_v2_snapshot_version"))
    if version == fbr_v2_snapshot_persistence.SNAPSHOT_VERSION:
        persisted = fbr_v2_snapshot_persistence.read_persisted_v2_snapshot(
            doc.doctype,
            doc.name,
        )
        return (
            dict((persisted.get("header") or {}).get("identity") or {}),
            "persisted_v2",
            persisted.get("snapshot_hash") or "",
        )

    return (
        erpnext_fbr_identity.resolve_invoice_identity(doc),
        "erpnext_live",
        "",
    )


def _buyer(doc, identity: dict) -> dict:
    buyer = dict(identity.get("buyer") or {})
    return {
        "name": buyer.get("business_name") or doc.get("customer_name") or doc.get("customer") or "Walk-in Customer",
        "ntn_cnic": buyer.get("ntn_cnic") or "",
        "strn": buyer.get("strn") or "",
        "registration_type": buyer.get("registration_type") or "Unregistered",
        "province": buyer.get("province") or "",
        "address": buyer.get("address") or "",
    }


def _seller(doc, identity: dict) -> dict:
    brand = get_brand_settings()
    seller = dict(identity.get("seller") or {})
    profile = _v2_profile_public(doc.get("company"))
    return {
        "name": seller.get("business_name") or doc.get("company") or brand.get("brand_name") or "Ledgix",
        "address": seller.get("address") or "",
        "phone": "",
        "email": "",
        "ntn": seller.get("ntn_cnic") or "",
        "strn": seller.get("strn") or "",
        "province": seller.get("province") or "",
        "logo": get_print_logo_url(),
        "software_registration_number": profile.get("software_registration_number") or "",
        "digital_invoicing_logo": profile.get("digital_invoicing_logo") or "",
        "fbr_profile": profile.get("profile_name") or "",
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

    identity, identity_source, identity_snapshot_hash = _identity_for_print(doc)

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
        "title": "RETURN / ADJUSTMENT" if is_return else ("SALES RECEIPT" if doc.doctype == "POS Invoice" else "TAX INVOICE"),
        "is_return": is_return,
        "return_against": doc.get("return_against") or "",
        "posting_date": doc.get("posting_date"),
        "posting_time": doc.get("posting_time"),
        "company": doc.get("company") or "",
        "currency": doc.get("currency") or "PKR",
        "identity_source": identity_source,
        "identity_snapshot_hash": identity_snapshot_hash,
        "seller": _seller(doc, identity),
        "buyer": _buyer(doc, identity),
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
        "fbr_generated_at": doc.get("custom_ledgix_fbr_generated_at"),
        "fbr_offline_pending": (
            (doc.get("custom_ledgix_fbr_status") or "") == "Offline Pending"
        ),
        "fbr_offline_issued_at": doc.get("custom_ledgix_fbr_offline_issued_at"),
        "fbr_upload_due_at": doc.get("custom_ledgix_fbr_upload_due_at"),
        "fbr_offline_reason": doc.get("custom_ledgix_fbr_offline_reason") or "",
        "fbr_qr_data_uri": get_fbr_qr_data_uri(fbr_invoice_number),
        "original_fbr_invoice_number": original_fbr_invoice,
        "fbr_reconciliation_required": bool(cint(doc.get("custom_ledgix_fbr_reconciliation_required"))),
        "snapshot_version": cint(doc.get("custom_ledgix_fbr_snapshot_version")),
        "authority": "ERPNext Sales/POS Invoice + Ledgix FBR metadata",
    }
