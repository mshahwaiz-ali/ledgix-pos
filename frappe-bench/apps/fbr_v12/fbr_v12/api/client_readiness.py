"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _require_admin(*args, **kwargs):
    return reject()

def _check(*args, **kwargs):
    return reject()

def _field_value(*args, **kwargs):
    return reject()

def _resolve_company(*args, **kwargs):
    return reject()

def _operational_user_summary(*args, **kwargs):
    return reject()

def _backup_candidates(*args, **kwargs):
    return reject()

def _evidence_checks(*args, **kwargs):
    return reject()

def evaluate_client_readiness(*args, **kwargs):
    return reject()

def get_client_readiness(*args, **kwargs):
    return reject()

def generate_client_readiness_evidence(*args, **kwargs):
    return reject()
