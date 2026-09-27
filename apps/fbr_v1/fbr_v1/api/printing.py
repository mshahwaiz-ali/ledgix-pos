from __future__ import annotations

import json
from base64 import b64encode
from io import BytesIO

import frappe
from frappe.utils import cint, flt

from fbr_v1.services import erpnext_fbr_identity, fbr_v1_snapshot_persistence


SUPPORTED_PRINT_DOCTYPES = {"Sales Invoice", "POS Invoice"}


def _asset_url(path: str | None) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "/")):
        return value
    return f"/files/{value}"


def _print_brand(company: str) -> dict:
    """Resolve print identity without requiring the Ledgix app.

    Existing Ledgix sites keep their configured Brand Settings as a compatibility
    fallback. Standalone ERPNext sites use the Company identity.
    """

    if frappe.db.exists("DocType", "Ledgix Brand Settings"):
        try:
            legacy = frappe.get_single("Ledgix Brand Settings")
            logo = _asset_url(
                legacy.get("full_logo") or legacy.get("symbol_logo") or ""
            )
            return {
                "brand_name": legacy.get("brand_name") or company or "FBR V1",
                "logo": logo,
                "source": "legacy_ledgix_brand_settings",
            }
        except Exception:
            pass

    company = str(company or "").strip()
    if company and frappe.db.exists("Company", company):
        meta = frappe.get_meta("Company")
        fields = ["company_name"]
        logo_field = ""
        for candidate in ("company_logo", "logo"):
            if meta.has_field(candidate):
                logo_field = candidate
                fields.append(candidate)
                break
        row = frappe.db.get_value("Company", company, fields, as_dict=True) or {}
        return {
            "brand_name": row.get("company_name") or company,
            "logo": _asset_url(row.get(logo_field)) if logo_field else "",
            "source": "erpnext_company",
        }

    return {"brand_name": company or "FBR V1", "logo": "", "source": "fallback"}


def provisional_qr_payload(fbr_invoice_number):
    """Returned number only; production verification encoding remains unresolved."""
    return str(fbr_invoice_number or "").strip()


def get_fbr_qr_data_uri(fbr_invoice_number) -> str:
    """Return a self-contained SVG QR for the unique FBR invoice number."""

    value = provisional_qr_payload(fbr_invoice_number)
    if not value:
        return ""

    from pyqrcode import create as qrcreate

    qr = qrcreate(value, error="L")
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


def _v1_profile_public(company: str) -> dict:
    company = str(company or "").strip()
    if not company or not frappe.db.exists("DocType", "Ledgix FBR Integration Profile"):
        return {
            "profile_name": "",
            "software_registration_number": "",
            "digital_invoicing_logo": "",
        }

    # Never fabricate official artwork; use only the configured authoritative profile attachment.
    row = frappe.db.get_value(
        "Ledgix FBR Integration Profile",
        {"company": company},
        ["name", "software_registration_number", "digital_invoicing_logo"],
        as_dict=True,
    )
    return {
        "profile_name": row.name if row else "",
        "software_registration_number": (
            row.software_registration_number if row else ""
        ) or "",
        "digital_invoicing_logo": (
            row.digital_invoicing_logo if row else ""
        ) or "",
    }


def _identity_for_print(doc) -> tuple[dict, str, str]:
    version = cint(doc.get("custom_ledgix_fbr_snapshot_version"))
    if version == fbr_v1_snapshot_persistence.SNAPSHOT_VERSION and doc.get("custom_ledgix_fbr_snapshot_protocol") == "Federal POS/IMS V1":
        persisted = fbr_v1_snapshot_persistence.read_persisted_v1_snapshot(
            doc.doctype,
            doc.name,
        )
        return (
            dict((persisted.get("header") or {}).get("identity") or {}),
            "persisted_v1",
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
    brand = _print_brand(doc.get("company"))
    seller = dict(identity.get("seller") or {})
    profile = _v1_profile_public(doc.get("company"))
    return {
        "name": seller.get("business_name") or doc.get("company") or brand.get("brand_name") or "FBR V1",
        "address": seller.get("address") or "",
        "phone": "",
        "email": "",
        "ntn": seller.get("ntn_cnic") or "",
        "strn": seller.get("strn") or "",
        "province": seller.get("province") or "",
        "logo": brand.get("logo") or "",
        "software_registration_number": profile.get("software_registration_number") or "",
        "digital_invoicing_logo": profile.get("digital_invoicing_logo") or "",
        "fbr_profile": profile.get("profile_name") or "",
    }


def _line_context(row, evidence=None):
    line = (evidence or {}).get("line") or {}
    mapping = line.get("fbr_mapping") or {}
    components = line.get("components") or {}
    rates = [r.get("tax_rate") for r in line.get("component_rows", []) if r.get("component") == "Sales Tax Applicable"]
    result = {k: line.get(k, row.get(k)) or "" for k in ("item_code", "item_name", "description", "uom")}
    for k in ("qty", "rate", "amount", "net_amount"):
        result[k] = abs(flt(line.get(k, row.get(k))))
    result.update({
        "hs_code": mapping.get("hs_code") or "", "fbr_uom": mapping.get("fbr_uom") or "",
        "sro_schedule_number": mapping.get("sro_schedule_number") or "",
        "sro_item_serial_number": mapping.get("sro_item_serial_number") or "",
        "sales_type": "", "rate_description": "", "tax_rate": rates[0] if len(rates) == 1 else 0,
        "tax_basis": mapping.get("tax_basis") or "", "notified_retail_price": mapping.get("notified_retail_price") or 0,
        "taxable_amount": result["net_amount"],
        "discount_amount": abs(flt(line.get("discount_amount")) * flt(line.get("qty"))) + abs(flt(line.get("distributed_discount_amount"))),
        "sales_tax": abs(flt(components.get("sales_tax"))),
        "extra_tax": abs(flt(components.get("extra_tax"))), "further_tax": abs(flt(components.get("further_tax"))),
        "fed_payable": abs(flt(components.get("fed_payable"))),
        "withheld_tax": abs(flt(components.get("sales_tax_withheld_at_source"))),
        "snapshot_version": (evidence or {}).get("snapshot_version", 0),
    })
    result["other_tax"] = result["extra_tax"] + result["further_tax"] + result["fed_payable"]
    result["line_total"] = result["net_amount"] + result["sales_tax"] + result["other_tax"]
    return result


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
    doc.check_permission("read")
    from fbr_v1.services.pos_identity import get_profile, profile_active, PROTOCOL
    profile = get_profile(doc.company)
    snapshot = None
    if doc.get("custom_ledgix_fbr_snapshot_protocol") == PROTOCOL:
        snapshot = fbr_v1_snapshot_persistence.read_persisted_v1_snapshot(doctype, name)
    if profile_active(profile) and cint(profile.get("block_print_without_fiscal_result")):
        if not snapshot or doc.get("custom_ledgix_fbr_status") != "Submitted" or not doc.get("custom_ledgix_fbr_invoice_number"):
            frappe.throw("Fiscal print is blocked until a valid V1 fiscal result exists.")
    is_return = bool(cint(doc.get("is_return")))
    original = None
    if is_return and doc.get("return_against") and frappe.db.exists(doctype, doc.return_against):
        original = frappe.get_doc(doctype, doc.return_against)

    identity, identity_source, identity_snapshot_hash = _identity_for_print(doc)

    fbr_invoice_number = str(doc.get("custom_ledgix_fbr_invoice_number") or "").strip()
    original_fbr_invoice = str(original.get("custom_ledgix_fbr_invoice_number") or "").strip() if original else ""
    seller = _seller(doc, identity)
    if snapshot:
        device = snapshot["header"]["pos_device"]
        seller["software_registration_number"] = device.get("software_registration_number") or ""
        seller["pos_id"] = device["pos_id"]
    else:
        seller["pos_id"] = ""
        fbr_invoice_number = ""
    qr_status = "Provisional number-only payload; externally unverified"
    if snapshot:
        verification = frappe.db.get_value("Ledgix FBR POS Device", device["name"],
            ["qr_verification_status", "qr_verification_reference", "qr_verification_evidence"], as_dict=True) or {}
        if verification.get("qr_verification_status") == "Verified" and verification.get("qr_verification_reference") and verification.get("qr_verification_evidence"):
            qr_status = "Configured V1 number-only QR encoding externally verified"
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
        "seller": seller,
        "tax_period": str(doc.get("posting_date") or "")[:7],
        "total_discount": sum(_line_context(r, snapshot["lines"].get(r.name))["discount_amount"] for r in doc.get("items") or []) if snapshot else abs(flt(doc.get("discount_amount"))),
        "qr_verification_status": qr_status,
        "buyer": _buyer(doc, identity),
        "items": [_line_context(row, snapshot["lines"].get(row.name) if snapshot else None) for row in doc.get("items") or []],
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
