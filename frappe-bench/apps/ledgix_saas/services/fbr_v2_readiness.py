"""Retired Ledgix V2 runtime. Historical implementation remains in Git history.

Only compatibility rejection is executable; never reads credentials or fiscal state.
"""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}
PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
CERTIFICATION_DOCTYPE = "Ledgix FBR Sandbox Certification"
REFERENCE_DOCTYPE = "Ledgix FBR Reference Data"
MONEY_TOLERANCE = 0.011


def _text(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _profile(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _token_configured(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _cached_reference_rows(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _reference_match(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _context_key(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _profile_state(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _sandbox_certification(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def get_company_profile_state(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _check_identity_references(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _check_line_references(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _persisted_snapshot_candidate(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _classify_tax_rows(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def evaluate_invoice_readiness(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
