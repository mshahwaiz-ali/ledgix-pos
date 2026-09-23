from __future__ import annotations

"""FBR V2 reference-data synchronization.

This module is additive during the redesign. It performs authenticated GET
requests only and persists official reference values into Ledgix FBR Reference
Data. It never validates/posts invoices, changes accounting or arms Production.
"""

import hashlib
import json
from typing import Any

import frappe
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password

from ledgix_saas.api import fbr_transport


PROVINCES_URL = "https://gw.fbr.gov.pk/pdi/v1/provinces"
DOCUMENT_TYPES_URL = "https://gw.fbr.gov.pk/pdi/v1/doctypecode"
TRANSACTION_TYPES_URL = "https://gw.fbr.gov.pk/pdi/v1/transtypecode"
UOM_URL = "https://gw.fbr.gov.pk/pdi/v1/uom"
SRO_SCHEDULE_URL = "https://gw.fbr.gov.pk/pdi/v1/SroSchedule"
RATE_URL = "https://gw.fbr.gov.pk/pdi/v2/SaleTypeToRate"
HS_UOM_URL = "https://gw.fbr.gov.pk/pdi/v2/HS_UOM"
SRO_ITEM_URL = "https://gw.fbr.gov.pk/pdi/v2/SROItem"

PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
REFERENCE_DOCTYPE = "Ledgix FBR Reference Data"
DEFAULT_PROTOCOL_VERSION = "DI API V1.12"
GLOBAL_CONTEXT_KEY = "GLOBAL"

FBR_VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
FBR_ADMIN_ROLES = {"System Manager", "Ledgix Admin"}

STATIC_REFERENCE_FAMILIES = {
    "Province": {
        "url": PROVINCES_URL,
        "id_keys": ("stateProvinceCode",),
        "description_keys": ("stateProvinceDesc",),
    },
    "Document Type": {
        "url": DOCUMENT_TYPES_URL,
        "id_keys": ("docTypeId",),
        "description_keys": ("docDescription",),
    },
    "Transaction Type": {
        "url": TRANSACTION_TYPES_URL,
        "id_keys": ("transactiON_TYPE_ID", "transaction_type_id"),
        "description_keys": ("transactiON_DESC", "transaction_desc"),
    },
    "UOM": {
        "url": UOM_URL,
        "id_keys": ("uoM_ID", "uom_id"),
        "description_keys": ("description",),
    },
}

PARAMETERIZED_REFERENCE_FAMILIES = {
    "Rate": {
        "url": RATE_URL,
        "id_keys": ("ratE_ID", "rate_id"),
        "description_keys": ("ratE_DESC", "rate_desc"),
    },
    "HS-UOM": {
        "url": HS_UOM_URL,
        "id_keys": ("uoM_ID", "uom_id"),
        "description_keys": ("description",),
    },
    "SRO Schedule": {
        "url": SRO_SCHEDULE_URL,
        "id_keys": ("srO_ID", "sro_id"),
        "description_keys": ("srO_DESC", "sro_desc"),
    },
    "SRO Item": {
        "url": SRO_ITEM_URL,
        "id_keys": ("srO_ITEM_ID", "sro_item_id"),
        "description_keys": ("srO_ITEM_DESC", "sro_item_desc"),
    },
}


def _assert_view_permission() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(FBR_VIEW_ROLES):
        frappe.throw(
            "You do not have permission to view FBR reference data.",
            frappe.PermissionError,
        )


def _assert_admin_permission() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(FBR_ADMIN_ROLES):
        frappe.throw(
            "Only System Manager or Ledgix Admin can synchronize FBR reference data.",
            frappe.PermissionError,
        )


def _safe_error(exc: Exception) -> str:
    return fbr_transport.safe_error(exc)


def _required_text(value, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        frappe.throw(f"{label} is required.")
    return text


def _profile(profile_name: str):
    profile_name = str(profile_name or "").strip()
    if not profile_name or not frappe.db.exists(PROFILE_DOCTYPE, profile_name):
        frappe.throw("Select a valid Ledgix FBR Integration Profile.")
    return frappe.get_doc(PROFILE_DOCTYPE, profile_name)


def _profile_token(profile) -> tuple[str, str]:
    if not profile.get("enabled"):
        frappe.throw("FBR Integration Profile must be enabled before reference synchronization.")

    mode = str(profile.get("mode") or "Disabled")
    if mode not in {"Sandbox", "Production"}:
        frappe.throw("Reference synchronization requires Sandbox or Production mode.")

    fieldname = "sandbox_token" if mode == "Sandbox" else "production_token"
    token = get_decrypted_password(
        PROFILE_DOCTYPE,
        profile.name,
        fieldname,
        raise_exception=False,
    )
    if not token:
        frappe.throw(f"{mode} token is not configured on the FBR Integration Profile.")

    return mode, token


def _reference_get(profile, url: str, params: dict | None = None) -> dict:
    mode, token = _profile_token(profile)
    response = fbr_transport.get_json(
        url=url,
        token=token,
        params=params or {},
        timeout=30,
    )
    return {
        "mode": mode,
        "http_status": response["http_status"],
        "payload": response["payload"],
    }


def _casefold_row(row: dict) -> dict:
    return {str(key).casefold(): value for key, value in row.items()}


def _value(row: dict, keys: tuple[str, ...]):
    folded = _casefold_row(row)
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
        value = folded.get(str(key).casefold())
        if value not in (None, ""):
            return value
    return None


def _normalize_rows(reference_type: str, payload: Any, spec: dict) -> list[dict]:
    if not isinstance(payload, list):
        frappe.throw(
            f"FBR {reference_type} reference API returned an unexpected non-list payload."
        )

    normalized = []
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            frappe.throw(f"FBR {reference_type} row {index} is not a JSON object.")

        fbr_id = _value(raw, spec["id_keys"])
        description = _value(raw, spec["description_keys"])
        if fbr_id in (None, "") or description in (None, ""):
            frappe.throw(
                f"FBR {reference_type} row {index} does not match the documented v1.12 response shape."
            )

        normalized.append(
            {
                "fbr_id": str(fbr_id).strip(),
                "description": str(description).strip(),
                "payload_json": json.dumps(
                    raw,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
            }
        )

    return normalized


def _canonical_context(context: dict | None) -> tuple[str, str]:
    context = dict(context or {})
    if not context:
        return GLOBAL_CONTEXT_KEY, "{}"

    canonical = json.dumps(
        context,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest, canonical


def _protocol_version(profile) -> str:
    return (
        str(profile.get("protocol_version") or DEFAULT_PROTOCOL_VERSION).strip()
        or DEFAULT_PROTOCOL_VERSION
    )


def _context_existing_names(
    *,
    reference_type: str,
    protocol_version: str,
    context_key: str,
) -> list[str]:
    rows = frappe.get_all(
        REFERENCE_DOCTYPE,
        filters={
            "reference_type": reference_type,
            "protocol_version": protocol_version,
        },
        fields=["name", "context_key"],
        limit_page_length=0,
    )
    names = []
    for row in rows:
        row_context = str(row.get("context_key") or "").strip()
        if context_key == GLOBAL_CONTEXT_KEY:
            if row_context in {"", GLOBAL_CONTEXT_KEY}:
                names.append(row["name"])
        elif row_context == context_key:
            names.append(row["name"])
    return names


def _existing_reference_name(
    *,
    reference_type: str,
    fbr_id: str,
    protocol_version: str,
    context_key: str,
) -> str | None:
    exact = frappe.db.get_value(
        REFERENCE_DOCTYPE,
        {
            "reference_type": reference_type,
            "fbr_id": fbr_id,
            "protocol_version": protocol_version,
            "context_key": context_key,
        },
        "name",
    )
    if exact or context_key != GLOBAL_CONTEXT_KEY:
        return exact

    # Compatibility for rows written before contextual cache keys existed.
    rows = frappe.get_all(
        REFERENCE_DOCTYPE,
        filters={
            "reference_type": reference_type,
            "fbr_id": fbr_id,
            "protocol_version": protocol_version,
        },
        fields=["name", "context_key"],
        limit_page_length=0,
    )
    for row in rows:
        if not str(row.get("context_key") or "").strip():
            return row["name"]
    return None


def _upsert_family(
    *,
    reference_type: str,
    protocol_version: str,
    source_endpoint: str,
    rows: list[dict],
    context: dict | None = None,
) -> dict:
    fetched_at = now_datetime()
    context_key, context_json = _canonical_context(context)

    existing = _context_existing_names(
        reference_type=reference_type,
        protocol_version=protocol_version,
        context_key=context_key,
    )
    for name in existing:
        frappe.db.set_value(
            REFERENCE_DOCTYPE,
            name,
            "stale",
            1,
            update_modified=False,
        )

    created = 0
    updated = 0
    for row in rows:
        name = _existing_reference_name(
            reference_type=reference_type,
            fbr_id=row["fbr_id"],
            protocol_version=protocol_version,
            context_key=context_key,
        )
        values = {
            "description": row["description"],
            "context_key": context_key,
            "context_json": context_json,
            "active": 1,
            "stale": 0,
            "source_endpoint": source_endpoint,
            "fetched_at": fetched_at,
            "payload_json": row["payload_json"],
        }
        if name:
            frappe.db.set_value(
                REFERENCE_DOCTYPE,
                name,
                values,
                update_modified=True,
            )
            updated += 1
        else:
            doc = frappe.get_doc(
                {
                    "doctype": REFERENCE_DOCTYPE,
                    "reference_type": reference_type,
                    "fbr_id": row["fbr_id"],
                    "description": row["description"],
                    "protocol_version": protocol_version,
                    **values,
                }
            )
            doc.insert(ignore_permissions=True)
            created += 1

    stale_count = len(
        [
            name
            for name in _context_existing_names(
                reference_type=reference_type,
                protocol_version=protocol_version,
                context_key=context_key,
            )
            if frappe.db.get_value(REFERENCE_DOCTYPE, name, "stale")
        ]
    )

    return {
        "reference_type": reference_type,
        "context_key": context_key,
        "context_json": context_json,
        "fetched": len(rows),
        "created": created,
        "updated": updated,
        "stale": stale_count,
        "source_endpoint": source_endpoint,
    }


def _sync_reference(
    *,
    profile,
    reference_type: str,
    spec: dict,
    params: dict | None = None,
    context: dict | None = None,
) -> dict:
    response = _reference_get(profile, spec["url"], params=params)
    rows = _normalize_rows(reference_type, response["payload"], spec)
    result = _upsert_family(
        reference_type=reference_type,
        protocol_version=_protocol_version(profile),
        source_endpoint=spec["url"],
        rows=rows,
        context=context,
    )
    result.update(
        {
            "mode": response["mode"],
            "http_status": response["http_status"],
            "protocol_version": _protocol_version(profile),
            "network_call": True,
            "invoice_network_call": False,
            "production_post_armed_changed": False,
            "contains_secrets": False,
        }
    )
    return result


def sync_reference_family_internal(profile_name: str, reference_type: str) -> dict:
    profile = _profile(profile_name)
    spec = STATIC_REFERENCE_FAMILIES.get(reference_type)
    if not spec:
        frappe.throw(
            "Only Province, Document Type, Transaction Type and UOM are supported "
            "by the parameter-free Phase 3 sync foundation."
        )
    return _sync_reference(
        profile=profile,
        reference_type=reference_type,
        spec=spec,
    )


def _sync_parameterized(
    *,
    profile_name: str,
    reference_type: str,
    params: dict,
    context: dict,
) -> dict:
    profile = _profile(profile_name)
    spec = PARAMETERIZED_REFERENCE_FAMILIES.get(reference_type)
    if not spec:
        frappe.throw(f"Unsupported parameterized FBR reference family: {reference_type}.")
    return _sync_reference(
        profile=profile,
        reference_type=reference_type,
        spec=spec,
        params=params,
        context=context,
    )


@frappe.whitelist()
def sync_reference_family(profile_name, reference_type):
    _assert_admin_permission()
    return sync_reference_family_internal(profile_name, reference_type)


@frappe.whitelist()
def sync_core_reference_data(profile_name):
    """Synchronize only parameter-free official DI reference families."""

    _assert_admin_permission()
    profile = _profile(profile_name)
    results = []
    errors = []

    for index, reference_type in enumerate(STATIC_REFERENCE_FAMILIES, start=1):
        savepoint = f"fbr_reference_family_{index}"
        frappe.db.savepoint(savepoint)
        try:
            results.append(
                sync_reference_family_internal(profile.name, reference_type)
            )
        except Exception as exc:
            frappe.db.rollback(save_point=savepoint)
            errors.append(
                {
                    "reference_type": reference_type,
                    "error": _safe_error(exc),
                }
            )

    status = "Failed" if errors else "Current"
    protocol_version = _protocol_version(profile)
    frappe.db.set_value(
        PROFILE_DOCTYPE,
        profile.name,
        {
            "reference_sync_status": status,
            "last_reference_sync_at": now_datetime(),
            "reference_version": protocol_version,
        },
        update_modified=True,
    )

    return {
        "profile": profile.name,
        "company": profile.company,
        "protocol_version": protocol_version,
        "status": status,
        "families": results,
        "errors": errors,
        "invoice_network_call": False,
        "production_post_armed_changed": False,
        "contains_secrets": False,
    }


@frappe.whitelist()
def sync_rates(profile_name, posting_date, transaction_type_id, origination_supplier):
    _assert_admin_permission()
    posting_date = _required_text(posting_date, "posting_date")
    transaction_type_id = _required_text(transaction_type_id, "transaction_type_id")
    origination_supplier = _required_text(origination_supplier, "origination_supplier")
    context = {
        "date": posting_date,
        "transTypeId": transaction_type_id,
        "originationSupplier": origination_supplier,
    }
    return _sync_parameterized(
        profile_name=profile_name,
        reference_type="Rate",
        params=context,
        context=context,
    )


@frappe.whitelist()
def sync_hs_uoms(profile_name, hs_code, annexure_id=3):
    _assert_admin_permission()
    hs_code = _required_text(hs_code, "hs_code")
    annexure_id = _required_text(annexure_id, "annexure_id")
    context = {
        "hs_code": hs_code,
        "annexure_id": annexure_id,
    }
    return _sync_parameterized(
        profile_name=profile_name,
        reference_type="HS-UOM",
        params=context,
        context=context,
    )


@frappe.whitelist()
def sync_sro_schedules(profile_name, rate_id, posting_date, origination_supplier_csv):
    _assert_admin_permission()
    rate_id = _required_text(rate_id, "rate_id")
    posting_date = _required_text(posting_date, "posting_date")
    origination_supplier_csv = _required_text(
        origination_supplier_csv,
        "origination_supplier_csv",
    )
    params = {
        "rate_id": rate_id,
        "date": posting_date,
        "origination_supplier_csv": origination_supplier_csv,
    }
    return _sync_parameterized(
        profile_name=profile_name,
        reference_type="SRO Schedule",
        params=params,
        context=params,
    )


@frappe.whitelist()
def sync_sro_items(profile_name, posting_date, sro_id):
    _assert_admin_permission()
    posting_date = _required_text(posting_date, "posting_date")
    sro_id = _required_text(sro_id, "sro_id")
    params = {
        "date": posting_date,
        "sro_id": sro_id,
    }
    return _sync_parameterized(
        profile_name=profile_name,
        reference_type="SRO Item",
        params=params,
        context=params,
    )


def _cached_rows(filters: dict) -> list[dict]:
    return frappe.get_all(
        REFERENCE_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "reference_type",
            "fbr_id",
            "description",
            "protocol_version",
            "context_key",
            "context_json",
            "fetched_at",
            "source_endpoint",
            "payload_json",
        ],
        order_by="description asc, fbr_id asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def get_cached_reference_data(reference_type, protocol_version=None):
    _assert_view_permission()
    reference_type = str(reference_type or "").strip()
    if reference_type not in STATIC_REFERENCE_FAMILIES:
        frappe.throw("Unsupported cached static FBR reference family.")

    filters = {
        "reference_type": reference_type,
        "active": 1,
        "stale": 0,
        "context_key": GLOBAL_CONTEXT_KEY,
    }
    if protocol_version:
        filters["protocol_version"] = str(protocol_version).strip()

    rows = _cached_rows(filters)
    if rows:
        return rows

    # Compatibility for rows written before contextual cache keys existed.
    filters["context_key"] = ["in", ["", None]]
    return _cached_rows(filters)


@frappe.whitelist()
def get_cached_contextual_reference_data(reference_type, context_key, protocol_version=None):
    _assert_view_permission()
    reference_type = str(reference_type or "").strip()
    context_key = _required_text(context_key, "context_key")
    if reference_type not in PARAMETERIZED_REFERENCE_FAMILIES:
        frappe.throw("Unsupported cached parameterized FBR reference family.")

    filters = {
        "reference_type": reference_type,
        "active": 1,
        "stale": 0,
        "context_key": context_key,
    }
    if protocol_version:
        filters["protocol_version"] = str(protocol_version).strip()
    return _cached_rows(filters)
