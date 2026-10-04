"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _sandbox_network_exercise_allowed(*args, **kwargs):
    return reject()

def _require_role(*args, **kwargs):
    return reject()

def _reference(*args, **kwargs):
    return reject()

def _is_consolidated_pos_sales_invoice(*args, **kwargs):
    return reject()

def is_native_fbr_source(*args, **kwargs):
    return reject()

def _summary(*args, **kwargs):
    return reject()

def validate_native_readiness_internal(*args, **kwargs):
    return reject()

def build_native_payload_internal(*args, **kwargs):
    return reject()

def build_native_invoice_payload(*args, **kwargs):
    return reject()

def _status_fields(*args, **kwargs):
    return reject()

def _get_status(*args, **kwargs):
    return reject()

def get_native_fbr_status(*args, **kwargs):
    return reject()

def mark_native_fbr_status(*args, **kwargs):
    return reject()

def _create_log(*args, **kwargs):
    return reject()

def _not_ready(*args, **kwargs):
    return reject()

def _ready_payload(*args, **kwargs):
    return reject()

def _configured_for_network(*args, **kwargs):
    return reject()

def _lock(*args, **kwargs):
    return reject()

def _already_submitted(*args, **kwargs):
    return reject()

def validate_native_with_fbr_internal(*args, **kwargs):
    return reject()

def validate_native_with_fbr(*args, **kwargs):
    return reject()

def submit_native_to_fbr_internal(*args, **kwargs):
    return reject()

def submit_native_to_fbr(*args, **kwargs):
    return reject()

def _after_commit_submit(*args, **kwargs):
    return reject()

def queue_native_for_fbr(*args, **kwargs):
    return reject()

def on_native_invoice_submit(*args, **kwargs):
    return reject()

def block_cancel_after_fbr_submission(*args, **kwargs):
    return reject()

def release_native_after_fbr_reconciliation(*args, **kwargs):
    return reject()
