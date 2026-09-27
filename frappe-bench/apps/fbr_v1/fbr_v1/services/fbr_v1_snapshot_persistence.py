from __future__ import annotations

import hashlib
import json

import frappe
from frappe.utils import cint, now_datetime

from fbr_v1.services import erpnext_fbr_identity
from fbr_v1.services.pos_identity import PROTOCOL, get_profile, profile_active, resolve_device, is_consolidated
from fbr_v1.services.payment_snapshot import capture_payment
from fbr_v1.services.erpnext_fbr_snapshot import (
    SUPPORTED_DOCTYPES,
    collect_native_tax_breakdown,
)


PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
SNAPSHOT_VERSION = 1

HEADER_VERSION_FIELD = "custom_ledgix_fbr_snapshot_version"
HEADER_HASH_FIELD = "custom_ledgix_fbr_snapshot_hash"
HEADER_CAPTURED_AT_FIELD = "custom_ledgix_fbr_snapshot_captured_at"
HEADER_JSON_FIELD = "custom_ledgix_fbr_snapshot_json"

LINE_VERSION_FIELD = "custom_ledgix_fbr_snapshot_version"
LINE_HASH_FIELD = "custom_ledgix_fbr_snapshot_hash"
LINE_JSON_FIELD = "custom_ledgix_fbr_snapshot_json"


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


def _profile_active(company):
    return profile_active(get_profile(company))


def _assert_snapshot_fields(doc) -> None:
    for fieldname in (
        "custom_ledgix_fbr_snapshot_protocol",
        HEADER_VERSION_FIELD,
        HEADER_HASH_FIELD,
        HEADER_CAPTURED_AT_FIELD,
        HEADER_JSON_FIELD,
    ):
        if not doc.meta.has_field(fieldname):
            frappe.throw(
                f"{doc.doctype} is missing required FBR V1 snapshot field "
                f"{fieldname}. Run the Ledgix extension schema sync first."
            )

    for item in doc.get("items") or []:
        for fieldname in (
            "custom_ledgix_fbr_snapshot_protocol",
            LINE_VERSION_FIELD,
            LINE_HASH_FIELD,
            LINE_JSON_FIELD,
        ):
            if not item.meta.has_field(fieldname):
                frappe.throw(
                    f"{item.doctype} is missing required FBR V1 snapshot field "
                    f"{fieldname}. Run the Ledgix extension schema sync first."
                )


def _build_snapshot_payloads(doc) -> tuple[dict, dict[str, dict]]:
    profile = get_profile(doc.company)
    if not profile_active(profile) or profile.get("mode") == "Paused":
        frappe.throw("An enabled, unpaused Federal V1 profile is required.")
    device = resolve_device(doc, profile)
    payment = capture_payment(doc)
    usin = str(doc.name or "")
    if not usin or len(usin) > 50:
        frappe.throw("ERPNext invoice name must be a stable USIN of at most 50 characters.")
    ref_usin = ""
    if cint(doc.get("is_return")):
        if not doc.get("return_against"):
            frappe.throw("Credit requires the original ERPNext invoice.")
        original = read_persisted_v1_snapshot(doc.doctype, doc.get("return_against"))
        if original["header"]["company"] != doc.company or original["header"].get("is_return"):
            frappe.throw("Credit source must be an original sale in the same company.")
        ref_usin = original["header"]["usin"]
    clone = frappe.get_doc(doc.as_dict())
    candidate = collect_native_tax_breakdown(clone)
    identity = erpnext_fbr_identity.resolve_invoice_identity(doc)
    seller = identity.get("seller") or {}
    if any(not seller.get(k) for k in ("ntn_cnic", "business_name", "address")):
        frappe.throw("ERPNext seller tax identity, name and address are required.")
    if identity.get("errors"):
        frappe.throw("; ".join(identity["errors"]))
    # Recalculation is a detached ERPNext collector, never a replacement authority.
    from decimal import Decimal
    for key in ("net_total", "total_taxes_and_charges", "grand_total"):
        if abs(Decimal(str(candidate[key])) - Decimal(str(doc.get(key) or 0))) > Decimal("0.011"):
            frappe.throw("Native collector differs from source invoice " + key)


    line_payloads: dict[str, dict] = {}
    line_hashes = []

    for line in candidate.get("lines") or []:
        item_row = str(line.get("item_row") or "").strip()
        if not item_row:
            frappe.throw("FBR V1 collector returned a line without stable row identity.")
        if item_row in line_payloads:
            frappe.throw(f"Duplicate FBR V1 collector row identity: {item_row}.")

        payload = {
            "snapshot_version": SNAPSHOT_VERSION,
            "protocol": PROTOCOL,
            "authority": "ERPNext Native",
            "source_doctype": doc.doctype,
            "source_name": doc.name or "",
            "company": doc.company,
            "posting_date": candidate.get("posting_date"),
            "is_return": bool(cint(doc.get("is_return"))),
            "return_against": str(doc.get("return_against") or ""),
            "line": line,
        }
        line_payloads[item_row] = payload
        line_hashes.append(
            {
                "item_row": item_row,
                "sha256": _digest_json(payload),
            }
        )

    header = {
        "snapshot_version": SNAPSHOT_VERSION,
        "protocol": PROTOCOL,
        "authority": "ERPNext Native",
        "source_doctype": doc.doctype,
        "source_name": doc.name or "",
        "company": doc.company,
        "posting_date": candidate.get("posting_date"),
        "currency": candidate.get("currency") or "",
        "is_return": bool(cint(doc.get("is_return"))),
        "return_against": str(doc.get("return_against") or ""),
        "net_total": candidate.get("net_total"),
        "total_taxes_and_charges": candidate.get("total_taxes_and_charges"),
        "grand_total": candidate.get("grand_total"),
        "identity": identity,
        "pos_device": device,
        "payment": payment,
        "usin": usin,
        "ref_usin": ref_usin,
        "posting_time": str(doc.get("posting_time") or "00:00:00"),
        "note_type": doc.get("custom_ledgix_fbr_note_type") or "New",
        "discount_amount": doc.get("discount_amount") or 0,
        "apply_discount_on": doc.get("apply_discount_on") or "",
        "rounded_total": doc.get("rounded_total"),
        "rounding_adjustment": doc.get("rounding_adjustment"),
        "native_tax_rows": [
            {key: row.get(key) for key in ("name", "idx", "account_head", "charge_type", "rate",
                "tax_amount", "tax_amount_after_discount_amount", "included_in_print_rate", "add_deduct_tax")}
            for row in doc.get("taxes") or []
        ],
        "component_mappings": candidate.get("component_mappings") or {},
        "reconciliation": candidate.get("reconciliation") or {},
        "line_count": candidate.get("line_count") or 0,
        "line_hashes": line_hashes,
    }

    from fbr_v1.services.fbr_v1_payload_builder import build_invoice
    build_invoice({"header": header, "lines": line_payloads, "snapshot_hash": _digest_json(header)})
    return header, line_payloads


def _item_by_snapshot_key(doc) -> dict[str, object]:
    rows = {}
    for item in doc.get("items") or []:
        key = str(item.get("name") or f"item-{item.get('idx') or 0}")
        if key in rows:
            frappe.throw(f"Duplicate ERPNext invoice item row identity: {key}.")
        rows[key] = item
    return rows


def _assert_existing_snapshot_matches(
    doc,
    header_payload: dict,
    line_payloads: dict[str, dict],
) -> None:
    expected_header_json = _canonical_json(header_payload)
    expected_header_hash = _digest_json(header_payload)

    stored_version = cint(doc.get(HEADER_VERSION_FIELD))
    stored_json = str(doc.get(HEADER_JSON_FIELD) or "")
    stored_hash = str(doc.get(HEADER_HASH_FIELD) or "")

    if (
        stored_version != SNAPSHOT_VERSION
        or stored_json != expected_header_json
        or stored_hash != expected_header_hash
    ):
        frappe.throw(
            "ERPNext invoice already contains a different FBR V1 immutable snapshot. "
            "Refusing to overwrite legal evidence."
        )

    items = _item_by_snapshot_key(doc)
    if set(items) != set(line_payloads):
        frappe.throw(
            "ERPNext invoice item identities differ from the existing FBR V1 snapshot."
        )

    for key, payload in line_payloads.items():
        item = items[key]
        if (
            cint(item.get(LINE_VERSION_FIELD)) != SNAPSHOT_VERSION
            or str(item.get(LINE_JSON_FIELD) or "") != _canonical_json(payload)
            or str(item.get(LINE_HASH_FIELD) or "") != _digest_json(payload)
        ):
            frappe.throw(
                f"ERPNext invoice row {key} already contains a different FBR V1 "
                "immutable snapshot."
            )


def capture_v1_snapshot(doc, *, force: bool = False) -> dict:
    if not doc or doc.doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("FBR V1 snapshot capture requires Sales Invoice or POS Invoice.")

    # Frappe sets docstatus=1 before save() invokes before_submit.
    # _action="submit" distinguishes that in-flight transition from a
    # document that was already submitted earlier.
    if cint(doc.docstatus) != 1 or str(getattr(doc, "_action", "") or "") != "submit":
        frappe.throw(
            "FBR V1 immutable snapshot may only be captured during the native "
            "before_submit transition."
        )

    if is_consolidated(doc) or (not force and not _profile_active(doc.company)):
        return {
            "captured": False,
            "reason": "FBR V1 Integration Profile is not active.",
            "database_write": False,
            "fbr_network_call": False,
        }

    _assert_snapshot_fields(doc)

    header_payload, line_payloads = _build_snapshot_payloads(doc)

    existing_markers = (
        cint(doc.get(HEADER_VERSION_FIELD)),
        str(doc.get(HEADER_HASH_FIELD) or ""),
        str(doc.get(HEADER_JSON_FIELD) or ""),
    )
    if any(existing_markers):
        _assert_existing_snapshot_matches(doc, header_payload, line_payloads)
        return {
            "captured": True,
            "reused_existing": True,
            "snapshot_version": SNAPSHOT_VERSION,
            "snapshot_hash": _digest_json(header_payload),
            "line_count": len(line_payloads),
            "database_write": False,
            "fbr_network_call": False,
        }

    items = _item_by_snapshot_key(doc)
    if set(items) != set(line_payloads):
        frappe.throw(
            "FBR V1 collector line identities do not match ERPNext invoice item rows."
        )

    header_json = _canonical_json(header_payload)
    header_hash = _digest_json(header_payload)

    doc.set("custom_ledgix_fbr_snapshot_protocol", PROTOCOL)
    doc.set("custom_ledgix_fbr_pos_device", header_payload["pos_device"]["name"])
    doc.set(HEADER_VERSION_FIELD, SNAPSHOT_VERSION)
    doc.set(HEADER_HASH_FIELD, header_hash)
    doc.set(HEADER_CAPTURED_AT_FIELD, now_datetime())
    doc.set(HEADER_JSON_FIELD, header_json)

    for key, payload in line_payloads.items():
        item = items[key]
        item.set("custom_ledgix_fbr_snapshot_protocol", PROTOCOL)
        item.set(LINE_VERSION_FIELD, SNAPSHOT_VERSION)
        item.set(LINE_HASH_FIELD, _digest_json(payload))
        item.set(LINE_JSON_FIELD, _canonical_json(payload))

    return {
        "captured": True,
        "reused_existing": False,
        "snapshot_version": SNAPSHOT_VERSION,
        "snapshot_hash": header_hash,
        "line_count": len(line_payloads),
        "database_write": False,
        "document_mutated_for_normal_submit": True,
        "fbr_network_call": False,
    }


def before_submit_capture(doc, method=None):
    return capture_v1_snapshot(doc, force=False)


def read_persisted_v1_snapshot(
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
    if cint(doc.docstatus) != 1 or doc.get("custom_ledgix_fbr_snapshot_protocol") != PROTOCOL:
        frappe.throw("A submitted invoice with Federal V1 evidence is required.")

    if cint(doc.get(HEADER_VERSION_FIELD)) != SNAPSHOT_VERSION:
        frappe.throw("ERPNext invoice has no valid FBR V1 immutable snapshot version.")

    raw_header = str(doc.get(HEADER_JSON_FIELD) or "")
    stored_header_hash = str(doc.get(HEADER_HASH_FIELD) or "")
    if not raw_header or not stored_header_hash:
        frappe.throw("ERPNext invoice has incomplete FBR V1 immutable header evidence.")

    try:
        header = json.loads(raw_header)
    except Exception as exc:
        frappe.throw(f"Invalid FBR V1 immutable header JSON: {exc}")

    if _digest_json(header) != stored_header_hash:
        frappe.throw("FBR V1 immutable header snapshot hash verification failed.")

    if (header.get("protocol") != PROTOCOL or header.get("source_doctype") != doc.doctype
            or header.get("source_name") != doc.name or header.get("company") != doc.company):
        frappe.throw("V1 snapshot source identity mismatch.")
    items = _item_by_snapshot_key(doc)
    lines = {}
    actual_line_hashes = []

    for key, item in items.items():
        if cint(item.get(LINE_VERSION_FIELD)) != SNAPSHOT_VERSION:
            frappe.throw(
                f"ERPNext invoice row {key} has no valid FBR V1 snapshot version."
            )

        raw_line = str(item.get(LINE_JSON_FIELD) or "")
        stored_line_hash = str(item.get(LINE_HASH_FIELD) or "")
        if not raw_line or not stored_line_hash:
            frappe.throw(
                f"ERPNext invoice row {key} has incomplete FBR V1 immutable evidence."
            )

        try:
            payload = json.loads(raw_line)
        except Exception as exc:
            frappe.throw(f"Invalid FBR V1 immutable line JSON for {key}: {exc}")

        if _digest_json(payload) != stored_line_hash:
            frappe.throw(
                f"FBR V1 immutable line snapshot hash verification failed for {key}."
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
            "FBR V1 immutable header/line snapshot hash manifest does not match."
        )

    if cint(header.get("line_count")) != len(lines):
        frappe.throw("FBR V1 immutable snapshot line count does not match invoice rows.")

    from fbr_v1.services.fbr_v1_payload_builder import verify_snapshot
    verify_snapshot({"header": header, "lines": lines, "snapshot_hash": stored_header_hash})
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
