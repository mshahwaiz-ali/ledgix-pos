from __future__ import annotations

"""FBR payload/submission adapter for ERPNext-native sales authority.

Phase 9 changes the source transaction from legacy Ledgix Sale/Return records to
submitted ERPNext Sales Invoice and POS Invoice documents. Ledgix continues to
own FBR settings, payload validation, transport, submission logs, reconciliation
safeguards and QR/reference metadata. This module never creates a second sales,
payment, stock or accounting ledger.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from ledgix_saas.api import fbr_client, fbr_payload
from ledgix_saas.api.fbr_settings import (
    get_fbr_control_state_internal,
    get_fbr_settings_internal,
)
from ledgix_saas.setup import erpnext_phase9_extensions

SUPPORTED_DOCTYPES = ("Sales Invoice", "POS Invoice")
RECONCILIATION_REQUIRED = "Reconciliation Required"
RECONCILIATION_CONFIRMATION = "CONFIRMED NOT RECEIVED BY FBR"
RECONCILIATION_MESSAGE = (
    "Production FBR POST outcome may be ambiguous. Reconcile the invoice with "
    "FBR/PRAL before any retransmission."
)
TOLERANCE = 0.05


def _require_role(action: str, *, submit: bool = False) -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    allowed = {"System Manager", "Ledgix Admin"}
    if not submit:
        allowed.add("Ledgix Manager")
    if not roles.intersection(allowed):
        frappe.throw(
            f"Only {', '.join(sorted(allowed))} can {action} native FBR data.",
            frappe.PermissionError,
        )


def _reference(reference_doctype: str, reference_name: str):
    doctype = str(reference_doctype or "").strip()
    name = str(reference_name or "").strip()
    if doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("FBR native source must be Sales Invoice or POS Invoice.")
    if not name or not frappe.db.exists(doctype, name):
        frappe.throw(f"{doctype} {name or ''} was not found.")
    return frappe.get_doc(doctype, name)


def _is_consolidated_pos_sales_invoice(doc) -> bool:
    if doc.doctype != "Sales Invoice" or cint(doc.get("is_return")):
        return False
    if frappe.db.exists("POS Invoice", {"consolidated_invoice": doc.name, "docstatus": 1}):
        return True
    # During ERPNext closing the POS rows may be linked immediately after the
    # consolidated Sales Invoice submit. A POS-shaped SI without a Ledgix sale
    # channel is accounting consolidation, not a second FBR source.
    return bool(cint(doc.get("is_pos")) and not str(doc.get("custom_ledgix_sale_channel") or "").strip())


def is_native_fbr_source(doc) -> bool:
    return bool(
        doc
        and doc.doctype in SUPPORTED_DOCTYPES
        and cint(doc.docstatus) == 1
        and not _is_consolidated_pos_sales_invoice(doc)
    )


def _seller_block() -> dict:
    return fbr_payload.build_fbr_seller_block()


def _buyer_block(customer_name: str) -> dict:
    defaults = fbr_payload._get_tax_profile_defaults()
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        return {
            "buyer_ntn_cnic": "",
            "buyer_strn": "",
            "buyer_registration_type": "Unregistered",
            "buyer_province": defaults.get("province") or "",
            "buyer_fbr_address": defaults.get("outlet_address") or "",
            "buyer_business_name": "Walk-in Customer",
        }
    customer = frappe.get_doc("Customer", customer_name)
    registration_type = fbr_payload._normalize_buyer_registration_type(
        customer.get("custom_ledgix_buyer_registration_type"),
        defaults.get("default_buyer_type"),
    )
    return {
        "buyer_ntn_cnic": customer.get("custom_ledgix_buyer_ntn_cnic") or customer.get("tax_id") or "",
        "buyer_strn": customer.get("custom_ledgix_buyer_strn") or "",
        "buyer_registration_type": registration_type or "Unregistered",
        "buyer_province": customer.get("custom_ledgix_buyer_province") or defaults.get("province") or "",
        "buyer_fbr_address": customer.get("custom_ledgix_buyer_fbr_address") or defaults.get("outlet_address") or "",
        "buyer_business_name": customer.get("customer_name") or customer.name,
    }


def _line_snapshot(row) -> dict:
    raw = row.get("custom_ledgix_fbr_snapshot_json")
    if not raw:
        frappe.throw(
            f"ERPNext invoice row {row.name or row.idx} has no immutable Ledgix FBR snapshot. "
            "Do not reconstruct legal tax data after submission."
        )
    try:
        snapshot = json.loads(raw)
    except Exception as exc:
        frappe.throw(f"ERPNext invoice row {row.name or row.idx} has invalid FBR snapshot JSON: {exc}")
    if cint(snapshot.get("snapshot_version")) <= 0:
        frappe.throw(f"ERPNext invoice row {row.name or row.idx} has no valid FBR snapshot version.")
    return snapshot


def _tax_rows(doc) -> list[dict]:
    rows = []
    for item in doc.get("items") or []:
        snapshot = _line_snapshot(item)
        rows.append(
            {
                "item": item.item_code,
                "item_name": item.get("item_name") or item.get("description") or item.item_code,
                "qty": abs(flt(snapshot.get("qty"))),
                "returned_qty": abs(flt(snapshot.get("qty"))),
                "rate": abs(flt(snapshot.get("rate"))),
                "gross_amount": abs(flt(snapshot.get("gross_amount"), 2)),
                "discount_amount": abs(flt(item.get("discount_amount"), 2)),
                "taxable_amount": abs(flt(snapshot.get("taxable_amount"), 2)),
                "tax_rate": abs(flt(snapshot.get("tax_rate"))),
                "fbr_rate_description": snapshot.get("fbr_rate_description") or "",
                "tax_amount": abs(flt(snapshot.get("sales_tax"), 2)),
                "sales_tax_withheld_at_source": abs(flt(snapshot.get("sales_tax_withheld_at_source"), 2)),
                "extra_tax": abs(flt(snapshot.get("extra_tax"), 2)),
                "further_tax": abs(flt(snapshot.get("further_tax"), 2)),
                "fed_payable": abs(flt(snapshot.get("fed_payable"), 2)),
                "net_amount": abs(flt(snapshot.get("erpnext_line_total"), 2)),
                "price_includes_tax": 1 if snapshot.get("price_includes_tax") else 0,
                "tax_category": snapshot.get("tax_category") or "",
                "tax_basis": snapshot.get("tax_basis") or "Transaction Value",
                "notified_retail_price": abs(flt(snapshot.get("notified_retail_price"), 2)),
                "hs_code": snapshot.get("hs_code") or "",
                "uom_for_fbr": snapshot.get("uom_for_fbr") or "",
                "sales_type": snapshot.get("sales_type") or "",
                "scenario_id": snapshot.get("scenario_id") or "",
                "sro_schedule_number": snapshot.get("sro_schedule_number") or "",
                "sro_item_serial_number": snapshot.get("sro_item_serial_number") or "",
            }
        )
    return rows


def _summary(doc) -> dict:
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "docstatus": cint(doc.docstatus),
        "customer": doc.get("customer") or "",
        "posting_date": doc.get("posting_date"),
        "is_return": bool(cint(doc.get("is_return"))),
        "return_against": doc.get("return_against") or "",
        "net_total": abs(flt(doc.get("net_total"), 2)),
        "tax_amount": abs(flt(doc.get("total_taxes_and_charges"), 2)),
        "grand_total": abs(flt(doc.get("grand_total"), 2)),
        "fbr_status": doc.get("custom_ledgix_fbr_status") or "Not Submitted",
        "fbr_invoice_number": doc.get("custom_ledgix_fbr_invoice_number") or "",
    }


def _original_for_return(doc):
    if not cint(doc.get("is_return")):
        return None
    original_name = str(doc.get("return_against") or "").strip()
    if not original_name:
        return None
    if not frappe.db.exists(doc.doctype, original_name):
        return None
    return frappe.get_doc(doc.doctype, original_name)


def validate_native_readiness_internal(reference_doctype: str, reference_name: str) -> dict:
    errors, warnings = [], []
    settings = get_fbr_settings_internal()
    control_state = get_fbr_control_state_internal()
    doc = _reference(reference_doctype, reference_name)

    if cint(doc.docstatus) == 0:
        errors.append("Draft ERPNext invoice cannot be used for FBR payload.")
    elif cint(doc.docstatus) == 2:
        errors.append("Cancelled ERPNext invoice cannot be used for FBR payload.")
    if _is_consolidated_pos_sales_invoice(doc):
        errors.append("Consolidated POS Sales Invoice is accounting-only; source POS Invoices own FBR submission.")
    if cint(doc.get("custom_ledgix_fbr_snapshot_version")) <= 0:
        errors.append("ERPNext invoice has no immutable Ledgix FBR header snapshot.")

    mode = settings.get("mode") or "Disabled"
    production = mode == "Production"
    seller = _seller_block()
    buyer = _buyer_block(doc.get("customer"))
    fbr_payload._validate_seller_block(seller, errors, warnings, production_mode=production)
    fbr_payload._validate_buyer_block(buyer, errors, warnings, production_mode=production)

    if mode in {"Sandbox", "Production"} and settings.get("enabled"):
        token_key = "sandbox_token_configured" if mode == "Sandbox" else "production_token_configured"
        if not settings.get(token_key):
            errors.append(f"{mode} FBR token is not configured.")

    tax_rows = []
    try:
        tax_rows = _tax_rows(doc)
    except Exception as exc:
        errors.append(str(exc))
    if tax_rows:
        charged_tax = flt(
            sum(
                flt(row.get("tax_amount"))
                + flt(row.get("extra_tax"))
                + flt(row.get("further_tax"))
                + flt(row.get("fed_payable"))
                for row in tax_rows
            ),
            2,
        )
        payload_total = flt(sum(flt(row.get("net_amount")) for row in tax_rows), 2)
        if abs(charged_tax - abs(flt(doc.get("total_taxes_and_charges"), 2))) > TOLERANCE:
            errors.append("ERPNext tax total does not match immutable FBR tax component total.")
        if abs(payload_total - abs(flt(doc.get("grand_total"), 2))) > TOLERANCE:
            errors.append("ERPNext grand total does not match immutable FBR line snapshot total.")
    fbr_payload._validate_tax_rows(tax_rows, errors, warnings, mode)
    if mode == "Sandbox":
        fbr_payload._validate_single_sandbox_scenario(tax_rows, errors)

    original = _original_for_return(doc)
    if cint(doc.get("is_return")):
        if not original:
            errors.append("Native Credit Note must reference an existing original ERPNext invoice.")
        else:
            original_fbr = str(original.get("custom_ledgix_fbr_invoice_number") or "").strip()
            if mode in {"Sandbox", "Production"} and not original_fbr:
                errors.append("Original ERPNext invoice must have an FBR invoice number before Credit Note submission.")
            if doc.get("posting_date") and original.get("posting_date"):
                age_days = (getdate(doc.posting_date) - getdate(original.posting_date)).days
                if age_days < 0:
                    errors.append("Credit Note date cannot be earlier than the original invoice date.")
                elif age_days > 180:
                    errors.append("FBR Credit Note date cannot be more than 180 days after the original invoice date.")
        if not str(doc.get("custom_ledgix_return_reason") or doc.get("remarks") or "").strip():
            errors.append("Credit Note reason is required for FBR payload.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "reference": _summary(doc),
        "settings": {
            "enabled": bool(control_state.get("enabled")),
            "mode": settings.get("mode") or "Disabled",
            "submit_trigger": settings.get("submit_trigger") or "Manual",
            "token_configured": bool(control_state.get("token_configured")),
        },
    }


def _official_item(row: dict) -> dict:
    return fbr_payload._official_item_payload(
        row,
        qty_field="returned_qty" if row.get("returned_qty") else "qty",
        discount_field="discount_amount",
    )


def build_native_payload_internal(reference_doctype: str, reference_name: str) -> dict:
    validation = validate_native_readiness_internal(reference_doctype, reference_name)
    doc = _reference(reference_doctype, reference_name)
    settings = get_fbr_settings_internal()
    seller = _seller_block()
    buyer = _buyer_block(doc.get("customer"))
    rows = _tax_rows(doc) if validation.get("reference") else []
    is_return = bool(cint(doc.get("is_return")))
    original = _original_for_return(doc)

    payload = {
        "invoiceType": "Credit Note" if is_return else "Sale Invoice",
        "invoiceDate": fbr_payload._format_invoice_date(doc.get("posting_date")),
        "sellerNTNCNIC": fbr_payload._clean_identifier(seller.get("seller_ntn_cnic")),
        "sellerBusinessName": seller.get("seller_business_name") or "",
        "sellerProvince": seller.get("seller_province") or "",
        "sellerAddress": seller.get("seller_address") or "",
        "buyerNTNCNIC": fbr_payload._clean_identifier(buyer.get("buyer_ntn_cnic")),
        "buyerBusinessName": buyer.get("buyer_business_name") or "",
        "buyerProvince": buyer.get("buyer_province") or "",
        "buyerAddress": buyer.get("buyer_fbr_address") or "",
        "buyerRegistrationType": buyer.get("buyer_registration_type") or "",
        "invoiceRefNo": (
            str(original.get("custom_ledgix_fbr_invoice_number") or "").strip()
            if original
            else ""
        ),
        "items": [_official_item(row) for row in rows],
    }
    if is_return:
        payload["reason"] = str(doc.get("custom_ledgix_return_reason") or doc.get("remarks") or "").strip()
        payload["reasonRemarks"] = str(doc.get("remarks") or "").strip()
    scenario_ids = fbr_payload._unique_scenario_ids(rows)
    if settings.get("mode") == "Sandbox" and len(scenario_ids) == 1:
        payload["scenarioId"] = scenario_ids[0]

    return {
        "validation": validation,
        "payload": payload,
        "source": {
            "doctype": doc.doctype,
            "name": doc.name,
            "is_return": is_return,
            "authority": "ERPNext",
        },
    }


@frappe.whitelist()
def build_native_invoice_payload(reference_doctype, reference_name):
    _require_role("preview")
    return build_native_payload_internal(reference_doctype, reference_name)


def _status_fields(doc) -> dict:
    return {
        "fbr_status": doc.get("custom_ledgix_fbr_status") or "Not Submitted",
        "fbr_invoice_number": doc.get("custom_ledgix_fbr_invoice_number") or "",
        "fbr_qr_code": doc.get("custom_ledgix_fbr_qr_code") or "",
        "fbr_reference": doc.get("custom_ledgix_fbr_reference") or "",
        "fbr_submitted_at": doc.get("custom_ledgix_fbr_submitted_at"),
        "fbr_upload_due_at": doc.get("custom_ledgix_fbr_upload_due_at"),
        "fbr_error_code": doc.get("custom_ledgix_fbr_error_code") or "",
        "fbr_error_message": doc.get("custom_ledgix_fbr_error_message") or "",
        "fbr_submission_log": doc.get("custom_ledgix_fbr_submission_log") or "",
        "fbr_reconciliation_required": bool(cint(doc.get("custom_ledgix_fbr_reconciliation_required"))),
    }


def _get_status(reference_doctype: str, reference_name: str) -> dict:
    return _status_fields(_reference(reference_doctype, reference_name))


@frappe.whitelist()
def get_native_fbr_status(reference_doctype, reference_name):
    _require_role("view")
    return _get_status(reference_doctype, reference_name)


def mark_native_fbr_status(
    reference_doctype: str,
    reference_name: str,
    status: str,
    *,
    fbr_invoice_number=None,
    fbr_qr_code=None,
    fbr_upload_due_at=None,
    error_code=None,
    error_message=None,
    log_name=None,
    submit_trigger=None,
) -> dict:
    erpnext_phase9_extensions.sync_all()
    doc = _reference(reference_doctype, reference_name)
    values = {
        "custom_ledgix_fbr_status": status,
        "custom_ledgix_fbr_reconciliation_required": 1 if status == RECONCILIATION_REQUIRED else 0,
    }
    if fbr_invoice_number is not None:
        values["custom_ledgix_fbr_invoice_number"] = fbr_invoice_number
        values["custom_ledgix_fbr_reference"] = fbr_invoice_number
    if fbr_qr_code is not None:
        values["custom_ledgix_fbr_qr_code"] = fbr_qr_code
    if fbr_upload_due_at is not None:
        values["custom_ledgix_fbr_upload_due_at"] = fbr_upload_due_at
    if error_code is not None:
        values["custom_ledgix_fbr_error_code"] = error_code
    if error_message is not None:
        values["custom_ledgix_fbr_error_message"] = str(error_message or "")[:1000]
    if log_name is not None:
        values["custom_ledgix_fbr_submission_log"] = log_name
    if submit_trigger is not None:
        values["custom_ledgix_fbr_submit_trigger"] = submit_trigger
    if status in {"Validated", "Submitted"}:
        values["custom_ledgix_fbr_submitted_at"] = now_datetime()
    if status in {"Submitted", RECONCILIATION_REQUIRED}:
        values["custom_ledgix_fbr_upload_due_at"] = None
    frappe.db.set_value(doc.doctype, doc.name, values, update_modified=False)
    return _get_status(doc.doctype, doc.name)


def _create_log(doc, status: str, *, payload=None, response=None, error_code=None, error_message=None, invoice_number=None):
    from ledgix_saas.api.fbr_submission import create_submission_log

    return create_submission_log(
        doc.doctype,
        doc.name,
        "Credit Note" if cint(doc.get("is_return")) else "Sale Invoice",
        status,
        request_json=payload,
        response_json=response,
        error_code=error_code,
        error_message=error_message,
        fbr_invoice_number=invoice_number,
        attempt_count=1 if response else 0,
    )


def _not_ready(doc, validation: dict, message: str) -> dict:
    return {
        "network_call": False,
        "status": "Not Ready",
        "reference_status": _get_status(doc.doctype, doc.name),
        "validation": validation,
        "response": None,
        "fbr_invoice_number": "",
        "fbr_qr_code": "",
        "error_code": "",
        "error_message": message,
    }


def _ready_payload(doc):
    result = build_native_payload_internal(doc.doctype, doc.name)
    validation = result.get("validation") or {}
    payload = result.get("payload")
    if not validation.get("valid"):
        return payload, validation, "Payload readiness failed."
    if not payload:
        validation.setdefault("errors", []).append("FBR payload could not be built.")
        validation["valid"] = False
        return payload, validation, "FBR payload could not be built."
    return payload, validation, ""


def _configured_for_network(settings: dict) -> str:
    if not settings.get("enabled"):
        return "FBR Settings must be enabled for submission."
    mode = settings.get("mode")
    if mode not in {"Sandbox", "Production"}:
        return "FBR mode must be Sandbox or Production for submission."
    if mode == "Sandbox" and not settings.get("sandbox_token_configured"):
        return "Sandbox token is not configured."
    if mode == "Production" and not settings.get("production_token_configured"):
        return "Production token is not configured."
    if mode == "Production" and not settings.get("production_post_armed"):
        return "Production posting is not armed."
    return ""


def _lock(doc):
    from ledgix_saas.api.fbr_submission import _submission_lock

    return _submission_lock(f"{doc.doctype}:{doc.name}")


def _already_submitted(status: dict) -> dict | None:
    if status.get("fbr_status") == RECONCILIATION_REQUIRED:
        return {
            "network_call": False,
            "status": RECONCILIATION_REQUIRED,
            "reference_status": status,
            "validation": {"valid": False, "errors": [RECONCILIATION_MESSAGE], "warnings": []},
            "response": None,
            "fbr_invoice_number": status.get("fbr_invoice_number") or "",
            "fbr_qr_code": status.get("fbr_qr_code") or "",
            "error_message": status.get("fbr_error_message") or RECONCILIATION_MESSAGE,
        }
    if status.get("fbr_invoice_number"):
        return {
            "network_call": False,
            "status": "Already Submitted",
            "reference_status": status,
            "validation": {"valid": True, "errors": [], "warnings": []},
            "response": None,
            "fbr_invoice_number": status.get("fbr_invoice_number"),
            "fbr_qr_code": status.get("fbr_qr_code") or "",
            "error_code": "",
            "error_message": "",
        }
    return None


def validate_native_with_fbr_internal(reference_doctype: str, reference_name: str, mode: str | None = None) -> dict:
    from ledgix_saas.api.fbr_submission import parse_fbr_response

    doc = _reference(reference_doctype, reference_name)
    if not is_native_fbr_source(doc):
        frappe.throw("FBR validation requires a submitted ERPNext source invoice, not a consolidated POS accounting invoice.")
    payload, validation, readiness_error = _ready_payload(doc)
    if readiness_error:
        log_name = _create_log(doc, "Failed", payload=payload, error_message=readiness_error)
        status = mark_native_fbr_status(doc.doctype, doc.name, "Failed", error_message=readiness_error, log_name=log_name)
        return {
            "network_call": False,
            "status": "Failed",
            "reference_status": status,
            "validation": validation,
            "response": None,
            "error_message": readiness_error,
        }
    settings = get_fbr_settings_internal()
    actual_mode = mode or settings.get("mode")
    if actual_mode not in {"Sandbox", "Production"}:
        actual_mode = "Sandbox"
    client_result = fbr_client.validate_invoice(payload, mode=actual_mode)
    if not client_result.get("network_call"):
        return _not_ready(doc, validation, client_result.get("error") or "FBR validation was not sent.")
    parsed = parse_fbr_response(client_result)
    if not client_result.get("success"):
        parsed["valid"] = False
    status_name = "Validated" if parsed.get("valid") else "Failed"
    error_code = "" if parsed.get("valid") else parsed.get("error_code") or ""
    error_message = "" if parsed.get("valid") else parsed.get("error_message") or client_result.get("error") or "FBR validation failed."
    log_name = _create_log(
        doc,
        status_name,
        payload=payload,
        response=client_result,
        error_code=error_code,
        error_message=error_message,
    )
    status = mark_native_fbr_status(
        doc.doctype,
        doc.name,
        status_name,
        fbr_qr_code=parsed.get("qr_code") or "",
        error_code=error_code,
        error_message=error_message,
        log_name=log_name,
    )
    return {
        "network_call": True,
        "status": status_name,
        "reference_status": status,
        "validation": validation,
        "response": client_result,
        "fbr_invoice_number": "",
        "fbr_qr_code": parsed.get("qr_code") or "",
        "error_code": error_code,
        "error_message": error_message,
    }


@frappe.whitelist()
def validate_native_with_fbr(reference_doctype, reference_name):
    _require_role("validate")
    return validate_native_with_fbr_internal(reference_doctype, reference_name)


def submit_native_to_fbr_internal(reference_doctype: str, reference_name: str) -> dict:
    from ledgix_saas.api.fbr_submission import (
        _is_ambiguous_production_post,
        _resolve_submission_status,
        parse_fbr_response,
    )

    doc = _reference(reference_doctype, reference_name)
    if not is_native_fbr_source(doc):
        frappe.throw("FBR submission requires a submitted ERPNext source invoice, not a consolidated POS accounting invoice.")
    current = _get_status(doc.doctype, doc.name)
    already = _already_submitted(current)
    if already:
        return already
    settings = get_fbr_settings_internal()
    config_error = _configured_for_network(settings)
    if config_error:
        return _not_ready(doc, {"valid": False, "errors": [config_error], "warnings": []}, config_error)

    with _lock(doc):
        current = _get_status(doc.doctype, doc.name)
        already = _already_submitted(current)
        if already:
            return already
        payload, validation, readiness_error = _ready_payload(doc)
        if readiness_error:
            log_name = _create_log(doc, "Failed", payload=payload, error_message=readiness_error)
            status = mark_native_fbr_status(doc.doctype, doc.name, "Failed", error_message=readiness_error, log_name=log_name)
            return {
                "network_call": False,
                "status": "Failed",
                "reference_status": status,
                "validation": validation,
                "response": None,
                "error_message": readiness_error,
            }

        mode = settings.get("mode")
        client_result = fbr_client.post_invoice(payload, mode=mode)
        if not client_result.get("network_call"):
            return _not_ready(doc, validation, client_result.get("error") or "FBR post was not sent.")
        parsed = parse_fbr_response(client_result, require_invoice_number=(mode == "Production"))
        if not client_result.get("success"):
            parsed["valid"] = False
            parsed["error_code"] = parsed.get("error_code") or str(client_result.get("http_status") or "")
            parsed["error_message"] = parsed.get("error_message") or client_result.get("error") or "FBR post failed."
        status_name, invoice_number = _resolve_submission_status(mode, parsed)
        qr_code = parsed.get("qr_code") or ""
        if _is_ambiguous_production_post(mode, client_result):
            status_name = RECONCILIATION_REQUIRED
            invoice_number = ""
            parsed["error_message"] = client_result.get("error") or RECONCILIATION_MESSAGE

        success_status = status_name in {"Submitted", "Validated"}
        error_code = "" if success_status else parsed.get("error_code") or ""
        error_message = "" if success_status else parsed.get("error_message") or ""
        log_name = _create_log(
            doc,
            status_name,
            payload=payload,
            response=client_result,
            error_code=error_code,
            error_message=error_message,
            invoice_number=invoice_number,
        )
        status = mark_native_fbr_status(
            doc.doctype,
            doc.name,
            status_name,
            fbr_invoice_number=invoice_number if invoice_number else None,
            fbr_qr_code=qr_code if qr_code else None,
            error_code=error_code,
            error_message=error_message,
            log_name=log_name,
        )
        return {
            "network_call": True,
            "status": status_name,
            "log_name": log_name,
            "reference_status": status,
            "validation": validation,
            "response": client_result,
            "fbr_invoice_number": invoice_number,
            "fbr_qr_code": qr_code,
            "error_code": error_code,
            "error_message": error_message,
        }


@frappe.whitelist()
def submit_native_to_fbr(reference_doctype, reference_name):
    _require_role("submit", submit=True)
    return submit_native_to_fbr_internal(reference_doctype, reference_name)


def _after_commit_submit(doctype: str, name: str) -> None:
    def _run():
        try:
            submit_native_to_fbr_internal(doctype, name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Ledgix native FBR after-commit submit failed for {doctype} {name}")

    frappe.db.after_commit.add(_run)


def queue_native_for_fbr(reference_doctype: str, reference_name: str, reason: str | None = None) -> dict:
    doc = _reference(reference_doctype, reference_name)
    if not is_native_fbr_source(doc):
        return {
            "queued": False,
            "status": "Not Required",
            "reason": "Consolidated/draft/cancelled ERPNext document is not an FBR source.",
            "reference_status": _status_fields(doc),
        }
    current = _get_status(doc.doctype, doc.name)
    already = _already_submitted(current)
    if already:
        already["queued"] = False
        return already

    settings = get_fbr_settings_internal()
    control = get_fbr_control_state_internal()
    mode = control.get("mode") or settings.get("mode") or "Disabled"
    submit_trigger = control.get("submit_trigger") or settings.get("submit_trigger") or "Manual"
    if mode == "Disabled" or (not settings.get("enabled") and mode not in {"Paused", "Manual Only"}):
        status = mark_native_fbr_status(doc.doctype, doc.name, "Not Required", submit_trigger=submit_trigger)
        return {"queued": False, "status": "Not Required", "reason": "FBR disabled", "reference_status": status}

    payload, validation, readiness_error = _ready_payload(doc)
    if mode == "Paused":
        log_name = _create_log(doc, "Paused", payload=payload, error_message=reason or control.get("reason") or "FBR paused")
        status = mark_native_fbr_status(
            doc.doctype,
            doc.name,
            "Paused",
            error_message=reason or control.get("reason") or "FBR paused",
            log_name=log_name,
            submit_trigger=submit_trigger,
        )
        return {"queued": False, "status": "Paused", "log_name": log_name, "validation": validation, "reference_status": status}
    if readiness_error:
        log_name = _create_log(doc, "Failed", payload=payload, error_message=readiness_error)
        status = mark_native_fbr_status(
            doc.doctype,
            doc.name,
            "Failed",
            error_message=readiness_error,
            log_name=log_name,
            submit_trigger=submit_trigger,
        )
        return {"queued": False, "status": "Failed", "reason": readiness_error, "log_name": log_name, "validation": validation, "reference_status": status}

    log_name = _create_log(doc, "Pending", payload=payload, error_message=reason)
    status = mark_native_fbr_status(
        doc.doctype,
        doc.name,
        "Pending",
        error_message=reason or "",
        log_name=log_name,
        submit_trigger=submit_trigger,
    )
    if mode == "Manual Only" or submit_trigger == "Manual":
        return {"queued": True, "status": "Pending", "reason": "Manual FBR submission required", "log_name": log_name, "validation": validation, "reference_status": status}
    if submit_trigger == "Validate Only":
        result = validate_native_with_fbr_internal(doc.doctype, doc.name, mode if mode in {"Sandbox", "Production"} else "Sandbox")
        result.update({"queued": True, "reason": "Validate Only flow completed"})
        return result
    if submit_trigger == "On Submit" and mode in {"Sandbox", "Production"}:
        if mode == "Production" or settings.get("sandbox_post_on_submit"):
            _after_commit_submit(doc.doctype, doc.name)
            return {"queued": True, "status": "Pending", "reason": f"{mode} FBR post queued after commit", "log_name": log_name, "validation": validation, "reference_status": status}
        result = validate_native_with_fbr_internal(doc.doctype, doc.name, "Sandbox")
        result.update({"queued": True, "reason": "Sandbox validation completed"})
        return result
    return {"queued": True, "status": "Pending", "reason": "FBR submission queued", "log_name": log_name, "validation": validation, "reference_status": status}


def on_native_invoice_submit(doc, method=None) -> None:
    if not doc or doc.doctype not in SUPPORTED_DOCTYPES or cint(doc.docstatus) != 1:
        return
    if _is_consolidated_pos_sales_invoice(doc):
        return
    queue_native_for_fbr(doc.doctype, doc.name, reason="ERPNext native invoice submitted")


def block_cancel_after_fbr_submission(doc, method=None) -> None:
    if not doc or doc.doctype not in SUPPORTED_DOCTYPES:
        return
    status = _status_fields(doc)
    if status.get("fbr_invoice_number") or status.get("fbr_status") == RECONCILIATION_REQUIRED:
        frappe.throw(
            _("This ERPNext invoice has FBR submission history. Use a native return/Credit Note or FBR correction workflow instead of cancellation.")
        )


@frappe.whitelist()
def release_native_after_fbr_reconciliation(reference_doctype, reference_name, confirmation):
    _require_role("release a reconciled invoice", submit=True)
    if str(confirmation or "").strip() != RECONCILIATION_CONFIRMATION:
        frappe.throw(f"Confirmation must be exactly: {RECONCILIATION_CONFIRMATION}")
    doc = _reference(reference_doctype, reference_name)
    current = _get_status(doc.doctype, doc.name)
    if current.get("fbr_status") != RECONCILIATION_REQUIRED:
        frappe.throw("ERPNext invoice is not awaiting FBR reconciliation.")
    message = "External FBR/PRAL reconciliation confirmed this invoice was not received. Manual retry is now permitted."
    log_name = _create_log(doc, "Pending", error_message=message)
    status = mark_native_fbr_status(
        doc.doctype,
        doc.name,
        "Pending",
        error_code="",
        error_message=message,
        log_name=log_name,
    )
    return {"released": True, "network_call": False, "status": "Pending", "reference_status": status, "log_name": log_name}
