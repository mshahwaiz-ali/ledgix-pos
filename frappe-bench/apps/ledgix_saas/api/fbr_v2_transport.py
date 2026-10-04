"""Retired Ledgix V2 runtime. Historical implementation remains in Git history.

Only compatibility rejection is executable; never reads credentials or fiscal state.
"""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
CERTIFICATION_DOCTYPE = "Ledgix FBR Sandbox Certification"


def _text(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _not_sent(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _profile_for_company(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _token(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _production_certification(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _transport_context(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _fbr_body_state(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _fbr_body_is_valid(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _invoice_number(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _production_post_is_ambiguous(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _endpoint(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _send(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def validate_invoice(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def post_invoice(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
