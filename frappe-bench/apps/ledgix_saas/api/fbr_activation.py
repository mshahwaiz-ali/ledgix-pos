"""Retired Ledgix V2 compatibility surface; execution fails closed."""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

def get_v2_configuration_summary_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

def evaluate_fbr_activation_readiness(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def get_fbr_activation_readiness(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)

@frappe.whitelist()
def generate_fbr_activation_evidence(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
