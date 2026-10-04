"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _require_admin(*args, **kwargs):
    return reject()

def _check(*args, **kwargs):
    return reject()

def _configured(*args, **kwargs):
    return reject()

def _safe_json(*args, **kwargs):
    return reject()

def _seller_identity_summary(*args, **kwargs):
    return reject()

def get_v2_configuration_summary_internal(*args, **kwargs):
    return reject()

def _native_reference_is_return(*args, **kwargs):
    return reject()

def _sandbox_proof_summary(*args, **kwargs):
    return reject()

def _reconciliation_summary(*args, **kwargs):
    return reject()

def _backup_summary(*args, **kwargs):
    return reject()

def evaluate_fbr_activation_readiness(*args, **kwargs):
    return reject()

def get_fbr_activation_readiness(*args, **kwargs):
    return reject()

def generate_fbr_activation_evidence(*args, **kwargs):
    return reject()
