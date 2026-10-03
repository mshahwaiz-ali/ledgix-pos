"""Retired Ledgix V2 runtime. Historical implementation remains in Git history.

Only compatibility rejection is executable; never reads credentials or fiscal state.
"""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
ADMIN_ROLES = {"System Manager", "Ledgix Admin"}
PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
ITEM_MAPPING_DOCTYPE = "Ledgix FBR Item Mapping"
COMPONENT_MAPPING_DOCTYPE = "Ledgix FBR Tax Component Mapping"
REFERENCE_DOCTYPE = "Ledgix FBR Reference Data"
CERTIFICATION_DOCTYPE = "Ledgix FBR Sandbox Certification"


def _roles(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _require_view(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _is_admin(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _count(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _missing_count(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _profiles(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _reference_summary(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _certification_summary(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _erpnext_tax_summary(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _v2_mapping_summary(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def get_v2_center_boot(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def get_v2_item_mappings(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def evaluate_v2_invoice_readiness(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def get_fbr_readiness(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
