from __future__ import annotations

import re

import frappe

from ledgix_saas.api import fbr_client
from ledgix_saas.api.fbr_settings import (
    assert_fbr_view_permission,
    get_active_fbr_token,
    get_fbr_settings_internal,
)


# FBR Digital Invoicing Technical Specification v1.12 reference APIs.
PROVINCES_URL = "https://gw.fbr.gov.pk/pdi/v1/provinces"
DOCUMENT_TYPES_URL = "https://gw.fbr.gov.pk/pdi/v1/doctypecode"
TRANSACTION_TYPES_URL = "https://gw.fbr.gov.pk/pdi/v1/transtypecode"
UOM_URL = "https://gw.fbr.gov.pk/pdi/v1/uom"
SRO_SCHEDULE_URL = "https://gw.fbr.gov.pk/pdi/v1/SroSchedule"
RATE_URL = "https://gw.fbr.gov.pk/pdi/v2/SaleTypeToRate"
HS_UOM_URL = "https://gw.fbr.gov.pk/pdi/v2/HS_UOM"
SRO_ITEM_URL = "https://gw.fbr.gov.pk/pdi/v2/SROItem"
STATL_URL = "https://gw.fbr.gov.pk/dist/v1/statl"
REGISTRATION_TYPE_URL = "https://gw.fbr.gov.pk/dist/v1/Get_Reg_Type"


def _safe_error(exc):
    text = str(exc or "")
    text = re.sub(r"Bearer\s+[^\s,;]+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
    return text or "FBR reference request failed."


def _active_mode_and_token():
    settings = get_fbr_settings_internal()
    mode = settings.get("mode")
    if not settings.get("enabled") or mode not in {"Sandbox", "Production"}:
        frappe.throw("Enable FBR in Sandbox or Production mode before using FBR reference APIs.")

    token = get_active_fbr_token(mode)
    if not token:
        frappe.throw(f"{mode} FBR token is not configured.")
    return mode, token


def _get_reference(url, params=None):
    assert_fbr_view_permission()
    if not fbr_client.requests_available():
        frappe.throw("Python requests is required for FBR reference APIs.")

    mode, token = _active_mode_and_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        response = fbr_client.requests.get(url, params=params or {}, headers=headers, timeout=30)
        try:
            data = response.json()
        except Exception:
            data = None

        if not (200 <= response.status_code < 300):
            frappe.throw(f"FBR reference API returned HTTP {response.status_code}.")
        if data is None:
            frappe.throw("FBR reference API returned a non-JSON response.")

        return {
            "mode": mode,
            "network_call": True,
            "http_status": response.status_code,
            "data": data,
        }
    except frappe.ValidationError:
        raise
    except Exception as exc:
        frappe.throw(_safe_error(exc))


def _required_text(value, label):
    text = str(value or "").strip()
    if not text:
        frappe.throw(f"{label} is required.")
    return text


@frappe.whitelist()
def get_provinces():
    """Official province descriptions used by sellerProvince/buyerProvince."""
    return _get_reference(PROVINCES_URL)


@frappe.whitelist()
def get_document_types():
    """Official FBR invoice/document types."""
    return _get_reference(DOCUMENT_TYPES_URL)


@frappe.whitelist()
def get_transaction_types():
    """Official transaction/sale types used when resolving FBR rates."""
    return _get_reference(TRANSACTION_TYPES_URL)


@frappe.whitelist()
def get_uoms():
    """Official FBR units of measurement."""
    return _get_reference(UOM_URL)


@frappe.whitelist()
def get_rates(posting_date, transaction_type_id, origination_supplier):
    """Resolve ratE_DESC/ratE_VALUE from FBR SaleTypeToRate (spec section 5.8)."""
    if not posting_date or not transaction_type_id or not origination_supplier:
        frappe.throw("posting_date, transaction_type_id, and origination_supplier are required.")
    return _get_reference(
        RATE_URL,
        {
            "date": posting_date,
            "transTypeId": transaction_type_id,
            "originationSupplier": origination_supplier,
        },
    )


@frappe.whitelist()
def get_hs_uoms(hs_code, annexure_id=3):
    """Resolve allowed UOMs for an HS code (spec section 5.9)."""
    if not str(hs_code or "").strip():
        frappe.throw("hs_code is required.")
    return _get_reference(
        HS_UOM_URL,
        {"hs_code": str(hs_code).strip(), "annexure_id": annexure_id},
    )


@frappe.whitelist()
def get_sro_schedules(rate_id, posting_date, origination_supplier_csv):
    """Resolve SRO schedules for a rate/date/supplier province (spec section 5.7)."""
    if not rate_id or not posting_date or not origination_supplier_csv:
        frappe.throw("rate_id, posting_date, and origination_supplier_csv are required.")
    return _get_reference(
        SRO_SCHEDULE_URL,
        {
            "rate_id": rate_id,
            "date": posting_date,
            "origination_supplier_csv": origination_supplier_csv,
        },
    )


@frappe.whitelist()
def get_sro_items(posting_date, sro_id):
    """Resolve item serials for an FBR SRO schedule (spec section 5.10)."""
    if not posting_date or not sro_id:
        frappe.throw("posting_date and sro_id are required.")
    return _get_reference(SRO_ITEM_URL, {"date": posting_date, "sro_id": sro_id})


@frappe.whitelist()
def get_sales_tax_registration_status(registration_no, posting_date):
    """Check FBR STATL status using the v1.12 regno/date request contract."""
    registration_no = _required_text(registration_no, "registration_no")
    posting_date = _required_text(posting_date, "posting_date")
    return _get_reference(
        STATL_URL,
        {
            "regno": registration_no,
            "date": posting_date,
        },
    )


@frappe.whitelist()
def get_registration_type(registration_no):
    """Resolve Registered/unregistered using FBR Get_Reg_Type (spec section 5.12)."""
    registration_no = _required_text(registration_no, "registration_no")
    return _get_reference(
        REGISTRATION_TYPE_URL,
        {"Registration_No": registration_no},
    )
