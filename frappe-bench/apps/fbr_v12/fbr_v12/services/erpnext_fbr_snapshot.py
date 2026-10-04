"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _row_key(*args, **kwargs):
    return reject()

def _assert_capture_supported(*args, **kwargs):
    return reject()

def _active_component_mappings(*args, **kwargs):
    return reject()

def _collect_non_posting_withheld_rows(*args, **kwargs):
    return reject()

def _matching_item_mapping(*args, **kwargs):
    return reject()

def _reconcile_mapped_tax_rows(*args, **kwargs):
    return reject()

def collect_native_tax_breakdown(*args, **kwargs):
    return reject()

def build_snapshot_candidate(*args, **kwargs):
    return reject()
