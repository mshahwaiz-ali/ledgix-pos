"""Retired Ledgix V2 compatibility surface; execution fails closed."""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

@frappe.whitelist()
def get_fbr_readiness(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
