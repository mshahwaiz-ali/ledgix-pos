"""Retired Ledgix V2 compatibility surface; execution fails closed."""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

def declare_known_offline_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def declare_known_offline(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def list_offline_queue_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def get_offline_queue(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def upload_offline_native_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def upload_offline_invoice(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
