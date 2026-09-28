from __future__ import annotations

import json
from base64 import b64encode
from io import BytesIO

import frappe
from frappe.utils import cint, flt

from fbr_v1.protocol import transport
from fbr_v1.services import erpnext_fbr_identity, fbr_v1_snapshot_persistence
from fbr_v1.services.pos_identity import PROTOCOL, get_profile, profile_active
from fbr_v1.services.v1_configuration import (
    configuration_blockers,
    get_device_compliance_state,
)


SUPPORTED_PRINT_DOCTYPES = {"Sales Invoice", "POS Invoice"}
TERMINAL_FISCAL_STATUSES = {
    "Submitted",
    "Failed",
    "Reconciliation Required",
    "Offline Pending",
}


def _automatic_submission_expected(profile, status: str, snapshot) -> bool:
    if status != "Pending" or not snapshot or not profile_active(profile):
        return False
    if (
        profile.get("mode") not in {"Sandbox", "Production"}
        or profile.get("submit_trigger") != "On Submit"
        or not cint(profile.get("transport_enabled"))
    ):
        return False
    if not transport.network_cutover_active():
        return False
    if profile.get("mode") == "Production":
        if not transport.production_cutover_active():
            return False
    device = dict(
        ((snapshot.get("header") or {}).get("pos_device") or {})
    )
    mode = profile.get("mode")
    compliance = get_device_compliance_state(
        device.get("name"),
        include_production=mode == "Production",
    )
    return not configuration_blockers(profile, {**device, **compliance}, mode)


def _authorized_offline_evidence(doc, profile, snapshot) -> tuple[bool, str]:
    if not profile_active(profile):
        return False, "An active Federal V1 profile is required for offline printing."
    if profile.get("offline_policy") != "Operator Confirmed":
        return False, "The profile does not authorize Operator Confirmed offline receipts."
    authority_reference = str(profile.get("offline_authority_reference") or "").strip()
    authority_evidence = str(profile.get("offline_authority_evidence") or "").strip()
    if not authority_reference or not authority_evidence:
        return False, "Offline authority reference and attachment are required."
    if not frappe.db.exists("File", {"file_url": authority_evidence}):
        return False, "The offline authority evidence attachment is missing."
    if not doc.get("custom_ledgix_fbr_offline_issued_at"):
        return False, "The durable offline issue timestamp is missing."

    if not snapshot:
        return False, "The immutable Federal V1 snapshot is missing or failed verification."

    snapshot_hash = str(snapshot.get("snapshot_hash") or "").strip()
    snapshot_device = str(
        ((snapshot.get("header") or {}).get("pos_device") or {}).get("name") or ""
    ).strip()
    invoice_device = str(doc.get("custom_ledgix_fbr_pos_device") or "").strip()
    if not snapshot_hash or not snapshot_device or invoice_device != snapshot_device:
        return False, "Invoice POS Device does not match the immutable Federal V1 snapshot."

    common = {
        "reference_doctype": doc.doctype,
        "reference_name": doc.name,
        "pos_device": snapshot_device,
    }
    if not frappe.db.exists(
        "Ledgix FBR Submission Log",
        {
            **common,
            "protocol": PROTOCOL,
            "transport_outcome": "Offline Deferred",
            "source_snapshot_hash": snapshot_hash,
        },
    ):
        return False, "Matching durable Offline Deferred submission evidence is missing."
    if not frappe.db.exists(
        "Ledgix FBR Fiscal Event Log",
        {**common, "event_type": "Offline Invoice Issued"},
    ):
        return False, "Matching Offline Invoice Issued event evidence is missing."
    return True, "Authorized offline evidence is complete."


def get_invoice_fiscal_print_state(doc) -> dict:
    """Return the authoritative read-only fiscal wait/print decision."""

    if not doc or doc.doctype not in SUPPORTED_PRINT_DOCTYPES:
        frappe.throw("Fiscal print state requires Sales Invoice or POS Invoice.")

    profile = get_profile(doc.get("company"))
    has_v1_snapshot = doc.get("custom_ledgix_fbr_snapshot_protocol") == PROTOCOL
    fbr_required = bool(has_v1_snapshot or profile_active(profile))
    status = str(doc.get("custom_ledgix_fbr_status") or "").strip()
    if not fbr_required:
        status = "Not Required"
        message = "Federal V1 fiscalization is not required; normal printing is available."
        return {
            "fbr_required": False,
            "status": status,
            "invoice_number": "",
            "print_ready": True,
            "print_blocked": False,
            "offline_pending": False,
            "reconciliation_required": False,
            "terminal": True,
            "automatic_submission_expected": False,
            "reason": message,
            "message": message,
        }

    status = status or "Pending"
    snapshot = None
    if has_v1_snapshot:
        try:
            snapshot = fbr_v1_snapshot_persistence.read_persisted_v1_snapshot(
                doc.doctype,
                doc.name,
            )
        except Exception:
            snapshot = None
    invoice_number = str(doc.get("custom_ledgix_fbr_invoice_number") or "").strip()
    automatic = _automatic_submission_expected(profile, status, snapshot)
    terminal = status in TERMINAL_FISCAL_STATUSES or (
        status == "Pending" and not automatic
    )
    reconciliation = bool(
        status == "Reconciliation Required"
        or cint(doc.get("custom_ledgix_fbr_reconciliation_required"))
    )
    print_ready = False
    offline_pending = False

    if not snapshot:
        message = "The immutable Federal V1 snapshot is missing or failed verification."
    elif reconciliation:
        message = (
            "FBR reconciliation is required. Receipt printing is blocked; "
            "do not retransmit automatically."
        )
    elif status == "Submitted" and invoice_number:
        print_ready = True
        message = "The authoritative Federal V1 result is ready for printing."
    elif status == "Submitted":
        message = "Submitted status has no authoritative FBR invoice number; printing is blocked."
    elif status == "Offline Pending":
        print_ready, evidence_message = _authorized_offline_evidence(
            doc,
            profile,
            snapshot,
        )
        offline_pending = print_ready
        invoice_number = ""
        message = (
            "Authorized offline evidence is complete; print the OFFLINE PENDING receipt "
            "without an FBR number or QR."
            if print_ready
            else evidence_message
        )
    elif status == "Failed":
        message = "Fiscalization failed. Receipt printing is blocked; do not resend automatically."
    elif status == "Pending" and automatic:
        message = "Fiscalization is pending and automatic backend submission is expected."
    elif status == "Pending" and profile and profile.get("mode") == "Sandbox" and profile.get("submit_trigger") == "Manual":
        message = "Fiscal submission is pending manual Sandbox action."
    elif status == "Pending":
        message = "Fiscalization is pending, but automatic backend submission is not currently expected."
    else:
        message = f"Federal V1 status {status} is not ready for printing."

    return {
        "fbr_required": True,
        "status": status,
        "invoice_number": invoice_number if print_ready and not offline_pending else "",
        "print_ready": print_ready,
        "print_blocked": not print_ready,
        "offline_pending": offline_pending,
        "reconciliation_required": reconciliation,
        "terminal": terminal,
        "automatic_submission_expected": automatic,
        "reason": message,
        "message": message,
    }


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
    """Federal POS QR payload: the authoritative returned FBR invoice number."""
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
        ) or "/assets/fbr_v1/images/fbr-pos-logo.png",
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
    for k in ("qty", "rate", "net_rate", "amount", "net_amount"):
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
    fiscal_state = get_invoice_fiscal_print_state(doc)
    if fiscal_state["print_blocked"]:
        frappe.throw(fiscal_state["message"])
    snapshot = None
    if doc.get("custom_ledgix_fbr_snapshot_protocol") == PROTOCOL:
        snapshot = fbr_v1_snapshot_persistence.read_persisted_v1_snapshot(doctype, name)
    is_return = bool(cint(doc.get("is_return")))
    original = None
    if is_return and doc.get("return_against") and frappe.db.exists(doctype, doc.return_against):
        original = frappe.get_doc(doctype, doc.return_against)

    identity, identity_source, identity_snapshot_hash = _identity_for_print(doc)

    fbr_invoice_number = fiscal_state["invoice_number"]
    original_fbr_invoice = str(original.get("custom_ledgix_fbr_invoice_number") or "").strip() if original else ""
    seller = _seller(doc, identity)
    if snapshot:
        device = snapshot["header"]["pos_device"]
        seller["software_registration_number"] = device.get("software_registration_number") or ""
        seller["pos_id"] = device["pos_id"]
    else:
        seller["pos_id"] = ""
        fbr_invoice_number = ""
    qr_status = "QR encodes the authoritative FBR invoice number"
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
        "pos_service_fee": abs(flt((snapshot or {}).get("header", {}).get("pos_service_fee") or 0, 2)),
        "sales_tax_total": max(0, abs(flt(doc.get("total_taxes_and_charges"), 2)) - abs(flt((snapshot or {}).get("header", {}).get("pos_service_fee") or 0, 2))),
        "grand_total": abs(flt(doc.get("grand_total"), 2)),
        "rounded_total": abs(flt(doc.get("rounded_total") or doc.get("grand_total"), 2)),
        "paid_amount": abs(flt(doc.get("paid_amount"), 2)),
        "outstanding_amount": abs(flt(doc.get("outstanding_amount"), 2)),
        "change_amount": abs(flt(doc.get("change_amount"), 2)),
        "payments": payments,
        "remarks": doc.get("remarks") or "",
        "fbr_status": fiscal_state["status"],
        "fbr_invoice_number": fbr_invoice_number,
        "fbr_reference": doc.get("custom_ledgix_fbr_reference") or "",
        "fbr_submitted_at": doc.get("custom_ledgix_fbr_submitted_at"),
        "fbr_generated_at": doc.get("custom_ledgix_fbr_generated_at"),
        "fbr_offline_pending": fiscal_state["offline_pending"],
        "fbr_offline_issued_at": doc.get("custom_ledgix_fbr_offline_issued_at"),
        "fbr_upload_due_at": doc.get("custom_ledgix_fbr_upload_due_at"),
        "fbr_offline_reason": doc.get("custom_ledgix_fbr_offline_reason") or "",
        "fbr_qr_data_uri": get_fbr_qr_data_uri(fbr_invoice_number),
        "original_fbr_invoice_number": original_fbr_invoice,
        "fbr_reconciliation_required": fiscal_state["reconciliation_required"],
        "snapshot_version": cint(doc.get("custom_ledgix_fbr_snapshot_version")),
        "authority": "ERPNext Sales/POS Invoice + Ledgix FBR metadata",
    }
