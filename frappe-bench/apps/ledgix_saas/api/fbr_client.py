"""Retired Ledgix V2 compatibility surface; execution fails closed."""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

def requests_available(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def ensure_requests_available(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def get_client_status(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def validate_invoice(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def post_invoice(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
