"""Retired Ledgix V2 runtime. Historical implementation remains in Git history.

Only compatibility rejection is executable; never reads credentials or fiscal state.
"""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
SNAPSHOT_VERSION = 2
HEADER_VERSION_FIELD = "custom_ledgix_fbr_v2_snapshot_version"
HEADER_HASH_FIELD = "custom_ledgix_fbr_v2_snapshot_hash"
HEADER_CAPTURED_AT_FIELD = "custom_ledgix_fbr_v2_snapshot_captured_at"
HEADER_JSON_FIELD = "custom_ledgix_fbr_v2_snapshot_json"
LINE_VERSION_FIELD = "custom_ledgix_fbr_v2_snapshot_version"
LINE_HASH_FIELD = "custom_ledgix_fbr_v2_snapshot_hash"
LINE_JSON_FIELD = "custom_ledgix_fbr_v2_snapshot_json"


def _canonical_json(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _digest_json(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _profile_active(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _assert_snapshot_fields(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _build_snapshot_payloads(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _item_by_snapshot_key(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _assert_existing_snapshot_matches(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def capture_v2_snapshot(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def before_submit_capture(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def read_persisted_v2_snapshot(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
