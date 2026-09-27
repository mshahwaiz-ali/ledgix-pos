"""Retired DI/V2 entry points. Historical schema and records are preserved."""
import frappe


def retired(*args, **kwargs):
    frappe.throw("DI/V2 service is retired. Use Federal POS/IMS V1; historical data is not reinterpreted.")


_canonical_json = retired
_digest_json = retired
_profile_active = retired
_assert_snapshot_fields = retired
_build_snapshot_payloads = retired
_item_by_snapshot_key = retired
_assert_existing_snapshot_matches = retired
capture_v2_snapshot = retired
before_submit_capture = retired
read_persisted_v2_snapshot = retired
