"""Capture exact retired stored values before model sync; never decrypt or log."""
import hashlib
import json
import frappe
from frappe.utils import now_datetime
from fbr_v1.fbr_v1.doctype.ledgix_fbr_legacy_evidence.ledgix_fbr_legacy_evidence import CONTROLLED_CAPTURE

LEGACY_FIELDS = ('business_natures', 'sector', 'onboarding_status', 'sandbox_token', 'production_token', 'block_sale_if_fbr_fails', 'offline_upload_window_hours', 'reference_sync_status', 'last_reference_sync_at', 'reference_version', 'activation_reference', 'activation_evidence')
DOCTYPE = "Ledgix FBR Legacy Evidence"
SOURCE = "Ledgix FBR Integration Profile"
VERSION = "v1-runtime-retirement-1"

def canonical_payload(values):
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

def execute():
    if not frappe.db.exists("DocType", SOURCE):
        return
    meta = frappe.get_meta(SOURCE)
    fields = [field for field in LEGACY_FIELDS if meta.has_field(field)]
    if not fields:
        return
    frappe.reload_doc("fbr_v1", "doctype", "ledgix_fbr_legacy_evidence", force=True)
    for row in frappe.get_all(SOURCE, fields=["name", "company"], order_by="name", limit_page_length=0):
        doc = frappe.get_doc(SOURCE, row.name)
        values = {field: [r.as_dict() for r in doc.get(field) or []] if field == "business_natures" else doc.get(field) for field in fields}
        # Password columns are masked by Frappe. Preserve encrypted __Auth rows,
        # never retrieve plaintext and never reuse a DI credential as V1.
        values["encrypted_credential_storage"] = frappe.db.sql(
            "SELECT fieldname, password, encrypted FROM `__Auth` WHERE doctype=%s AND name=%s AND fieldname IN (%s,%s) ORDER BY fieldname",
            (SOURCE, row.name, "sandbox_token", "production_token"), as_dict=True)
        payload = canonical_payload(values)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        existing = frappe.db.get_value(DOCTYPE, row.name, "payload_hash")
        if existing:
            if existing != digest:
                frappe.throw("Legacy profile evidence differs from captured values; schema sync blocked.")
            continue
        evidence = frappe.get_doc(dict(doctype=DOCTYPE, company=row.company,
            source_kind=SOURCE, source_name=row.name, payload_json=payload,
            payload_hash=digest, captured_at=now_datetime(), migration_version=VERSION))
        evidence.flags.legacy_evidence_capture = CONTROLLED_CAPTURE
        evidence.insert(ignore_permissions=True)
