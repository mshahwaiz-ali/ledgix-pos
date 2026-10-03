"""Retired Ledgix V2 runtime. Historical implementation remains in Git history.

Only compatibility rejection is executable; never reads credentials or fiscal state.
"""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
ACTIVE_MODES = {"Sandbox", "Production"}


def assert_fbr_v2_view_permission(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _setup_company(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def get_fbr_v2_status_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
