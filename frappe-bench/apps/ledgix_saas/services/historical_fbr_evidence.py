"""Historical V2 evidence verification for printing only. No capture or fiscal runtime.

Reads stored evidence unchanged; never rebuilds, reclassifies, or persists it.
"""

import hashlib

import json

import frappe

from frappe.utils import cint

SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}

SNAPSHOT_VERSION = 2

HEADER_VERSION_FIELD = "custom_ledgix_fbr_v2_snapshot_version"

HEADER_HASH_FIELD = "custom_ledgix_fbr_v2_snapshot_hash"

HEADER_CAPTURED_AT_FIELD = "custom_ledgix_fbr_v2_snapshot_captured_at"

HEADER_JSON_FIELD = "custom_ledgix_fbr_v2_snapshot_json"

LINE_VERSION_FIELD = "custom_ledgix_fbr_v2_snapshot_version"

LINE_HASH_FIELD = "custom_ledgix_fbr_v2_snapshot_hash"

LINE_JSON_FIELD = "custom_ledgix_fbr_v2_snapshot_json"

def _canonical_json(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )

def _digest_json(value) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()

def _assert_snapshot_fields(doc) -> None:
    for fieldname in (
        HEADER_VERSION_FIELD,
        HEADER_HASH_FIELD,
        HEADER_CAPTURED_AT_FIELD,
        HEADER_JSON_FIELD,
    ):
        if not doc.meta.has_field(fieldname):
            frappe.throw(
                f"{doc.doctype} is missing required FBR V2 snapshot field "
                f"{fieldname}. Run the Ledgix extension schema sync first."
            )

    for item in doc.get("items") or []:
        for fieldname in (
            LINE_VERSION_FIELD,
            LINE_HASH_FIELD,
            LINE_JSON_FIELD,
        ):
            if not item.meta.has_field(fieldname):
                frappe.throw(
                    f"{item.doctype} is missing required FBR V2 snapshot field "
                    f"{fieldname}. Run the Ledgix extension schema sync first."
                )

def _item_by_snapshot_key(doc) -> dict[str, object]:
    rows = {}
    for item in doc.get("items") or []:
        key = str(item.get("name") or f"item-{item.get('idx') or 0}")
        if key in rows:
            frappe.throw(f"Duplicate ERPNext invoice item row identity: {key}.")
        rows[key] = item
    return rows

def read_persisted_v2_snapshot(
    reference_doctype: str,
    reference_name: str,
) -> dict:
    reference_doctype = str(reference_doctype or "").strip()
    reference_name = str(reference_name or "").strip()

    if reference_doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("reference_doctype must be Sales Invoice or POS Invoice.")
    if not reference_name or not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw("Select an existing ERPNext invoice.")

    doc = frappe.get_doc(reference_doctype, reference_name)
    _assert_snapshot_fields(doc)

    if cint(doc.get(HEADER_VERSION_FIELD)) != SNAPSHOT_VERSION:
        frappe.throw("ERPNext invoice has no valid FBR V2 immutable snapshot version.")

    raw_header = str(doc.get(HEADER_JSON_FIELD) or "")
    stored_header_hash = str(doc.get(HEADER_HASH_FIELD) or "")
    if not raw_header or not stored_header_hash:
        frappe.throw("ERPNext invoice has incomplete FBR V2 immutable header evidence.")

    try:
        header = json.loads(raw_header)
    except Exception as exc:
        frappe.throw(f"Invalid FBR V2 immutable header JSON: {exc}")

    if _digest_json(header) != stored_header_hash:
        frappe.throw("FBR V2 immutable header snapshot hash verification failed.")

    items = _item_by_snapshot_key(doc)
    lines = {}
    actual_line_hashes = []

    for key, item in items.items():
        if cint(item.get(LINE_VERSION_FIELD)) != SNAPSHOT_VERSION:
            frappe.throw(
                f"ERPNext invoice row {key} has no valid FBR V2 snapshot version."
            )

        raw_line = str(item.get(LINE_JSON_FIELD) or "")
        stored_line_hash = str(item.get(LINE_HASH_FIELD) or "")
        if not raw_line or not stored_line_hash:
            frappe.throw(
                f"ERPNext invoice row {key} has incomplete FBR V2 immutable evidence."
            )

        try:
            payload = json.loads(raw_line)
        except Exception as exc:
            frappe.throw(f"Invalid FBR V2 immutable line JSON for {key}: {exc}")

        if _digest_json(payload) != stored_line_hash:
            frappe.throw(
                f"FBR V2 immutable line snapshot hash verification failed for {key}."
            )

        lines[key] = payload
        actual_line_hashes.append(
            {
                "item_row": key,
                "sha256": stored_line_hash,
            }
        )

    expected_line_hashes = header.get("line_hashes") or []
    if actual_line_hashes != expected_line_hashes:
        frappe.throw(
            "FBR V2 immutable header/line snapshot hash manifest does not match."
        )

    if cint(header.get("line_count")) != len(lines):
        frappe.throw("FBR V2 immutable snapshot line count does not match invoice rows.")

    return {
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "snapshot_version": SNAPSHOT_VERSION,
        "snapshot_hash": stored_header_hash,
        "header": header,
        "lines": lines,
        "hash_verified": True,
        "fbr_network_call": False,
    }
