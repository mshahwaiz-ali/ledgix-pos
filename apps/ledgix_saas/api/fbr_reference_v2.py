from __future__ import annotations

"""FBR V2 reference-data synchronization.

This module is additive during the redesign. It performs authenticated GET
requests only and persists official reference values into Ledgix FBR Reference
Data. It never validates/posts invoices, changes accounting or arms Production.
"""

import json
import re
from typing import Any

import frappe
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password

from ledgix_saas.api import fbr_client


PROVINCES_URL = "https://gw.fbr.gov.pk/pdi/v1/provinces"
DOCUMENT_TYPES_URL = "https://gw.fbr.gov.pk/pdi/v1/doctypecode"
TRANSACTION_TYPES_URL = "https://gw.fbr.gov.pk/pdi/v1/transtypecode"
UOM_URL = "https://gw.fbr.gov.pk/pdi/v1/uom"

PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
REFERENCE_DOCTYPE = "Ledgix FBR Reference Data"
DEFAULT_PROTOCOL_VERSION = "DI API V1.12"

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
    value = str(exc or "")
    value = re.sub(
        r"Bearer\s+[^\s,;]+",
        "Bearer [REDACTED]",
        value,
        flags=re.IGNORECASE,
    )
    return value or "FBR reference request failed."


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


def _reference_get(profile, url: str) -> dict:
    fbr_client.ensure_requests_available()
    mode, token = _profile_token(profile)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        response = fbr_client.requests.get(url, headers=headers, timeout=30)
        if not (200 <= response.status_code < 300):
            frappe.throw(f"FBR reference API returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except Exception:
            frappe.throw("FBR reference API returned a non-JSON response.")
    except frappe.ValidationError:
        raise
    except Exception as exc:
        frappe.throw(_safe_error(exc))

    return {
        "mode": mode,
        "http_status": response.status_code,
        "payload": payload,
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


def _normalize_rows(reference_type: str, payload: Any) -> list[dict]:
    spec = STATIC_REFERENCE_FAMILIES.get(reference_type)
    if not spec:
        frappe.throw(f"Unsupported static FBR reference family: {reference_type}.")

    if not isinstance(payload, list):
        frappe.throw(
            f"FBR {reference_type} reference API returned an unexpected non-list payload."
        )

    normalized = []
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            frappe.throw(
                f"FBR {reference_type} row {index} is not a JSON object."
            )

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


def _upsert_family(
    *,
    reference_type: str,
    protocol_version: str,
    source_endpoint: str,
    rows: list[dict],
) -> dict:
    fetched_at = now_datetime()

    existing = frappe.get_all(
        REFERENCE_DOCTYPE,
        filters={
            "reference_type": reference_type,
            "protocol_version": protocol_version,
        },
        pluck="name",
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
        name = frappe.db.get_value(
            REFERENCE_DOCTYPE,
            {
                "reference_type": reference_type,
                "fbr_id": row["fbr_id"],
                "protocol_version": protocol_version,
            },
            "name",
        )
        values = {
            "description": row["description"],
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
                    "active": 1,
                    "stale": 0,
                    "source_endpoint": source_endpoint,
                    "fetched_at": fetched_at,
                    "payload_json": row["payload_json"],
                }
            )
            doc.insert(ignore_permissions=True)
            created += 1

    stale_count = frappe.db.count(
        REFERENCE_DOCTYPE,
        {
            "reference_type": reference_type,
            "protocol_version": protocol_version,
            "stale": 1,
        },
    )
    return {
        "reference_type": reference_type,
        "fetched": len(rows),
        "created": created,
        "updated": updated,
        "stale": stale_count,
        "source_endpoint": source_endpoint,
    }


def sync_reference_family_internal(profile_name: str, reference_type: str) -> dict:
    profile = _profile(profile_name)
    spec = STATIC_REFERENCE_FAMILIES.get(reference_type)
    if not spec:
        frappe.throw(
            "Only Province, Document Type, Transaction Type and UOM are supported "
            "by the parameter-free Phase 3 sync foundation."
        )

    response = _reference_get(profile, spec["url"])
    rows = _normalize_rows(reference_type, response["payload"])
    protocol_version = (
        str(profile.get("protocol_version") or DEFAULT_PROTOCOL_VERSION).strip()
        or DEFAULT_PROTOCOL_VERSION
    )
    result = _upsert_family(
        reference_type=reference_type,
        protocol_version=protocol_version,
        source_endpoint=spec["url"],
        rows=rows,
    )
    result.update(
        {
            "mode": response["mode"],
            "http_status": response["http_status"],
            "protocol_version": protocol_version,
            "network_call": True,
            "invoice_network_call": False,
        }
    )
    return result


@frappe.whitelist()
def sync_reference_family(profile_name, reference_type):
    _assert_admin_permission()
    return sync_reference_family_internal(profile_name, reference_type)


@frappe.whitelist()
def sync_core_reference_data(profile_name):
    """Synchronize only parameter-free official DI reference families.

    This method performs authenticated GET requests only. It never validates or
    posts an invoice and never changes Production arming.
    """

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
    protocol_version = (
        str(profile.get("protocol_version") or DEFAULT_PROTOCOL_VERSION).strip()
        or DEFAULT_PROTOCOL_VERSION
    )
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
def get_cached_reference_data(reference_type, protocol_version=None):
    _assert_view_permission()
    reference_type = str(reference_type or "").strip()
    if reference_type not in STATIC_REFERENCE_FAMILIES:
        frappe.throw("Unsupported cached FBR reference family.")

    filters = {
        "reference_type": reference_type,
        "active": 1,
        "stale": 0,
    }
    if protocol_version:
        filters["protocol_version"] = str(protocol_version).strip()

    return frappe.get_all(
        REFERENCE_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "reference_type",
            "fbr_id",
            "description",
            "protocol_version",
            "fetched_at",
            "source_endpoint",
        ],
        order_by="description asc, fbr_id asc",
        limit_page_length=0,
    )
