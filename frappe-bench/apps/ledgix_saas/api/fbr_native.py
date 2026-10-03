"""Retired Ledgix V2 compatibility surface; execution fails closed."""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

V2_NETWORK_CUTOVER_ACTIVE = False

def is_native_fbr_source(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def validate_native_readiness_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def build_native_payload_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def build_native_invoice_payload(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def get_native_fbr_status(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def mark_native_fbr_status(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def validate_native_with_fbr_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def validate_native_with_fbr(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def submit_native_to_fbr_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def submit_native_to_fbr(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def queue_native_for_fbr(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def on_native_invoice_submit(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def block_cancel_after_fbr_submission(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def release_native_after_fbr_reconciliation(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
