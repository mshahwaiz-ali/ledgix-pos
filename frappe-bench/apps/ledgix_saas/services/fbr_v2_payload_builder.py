"""Retired Ledgix V2 runtime. Historical implementation remains in Git history.

Only compatibility rejection is executable; never reads credentials or fiscal state.
"""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}
MONEY_TOLERANCE = 0.02


def _text(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _money(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _quantity(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _identifier(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _is_consolidated_pos_sales_invoice(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _raise_readiness(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _line_item_payload(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def build_payload_candidate(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
