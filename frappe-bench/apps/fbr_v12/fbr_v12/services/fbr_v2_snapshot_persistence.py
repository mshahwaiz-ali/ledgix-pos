"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _canonical_json(*args, **kwargs):
    return reject()

def _digest_json(*args, **kwargs):
    return reject()

def _profile_active(*args, **kwargs):
    return reject()

def _assert_snapshot_fields(*args, **kwargs):
    return reject()

def _build_snapshot_payloads(*args, **kwargs):
    return reject()

def _item_by_snapshot_key(*args, **kwargs):
    return reject()

def _assert_existing_snapshot_matches(*args, **kwargs):
    return reject()

def capture_v2_snapshot(*args, **kwargs):
    return reject()

def before_submit_capture(*args, **kwargs):
    return reject()

def read_persisted_v2_snapshot(*args, **kwargs):
    return reject()
