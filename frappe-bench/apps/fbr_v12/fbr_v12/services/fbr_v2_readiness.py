"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _text(*args, **kwargs):
    return reject()

def _profile(*args, **kwargs):
    return reject()

def _token_configured(*args, **kwargs):
    return reject()

def _cached_reference_rows(*args, **kwargs):
    return reject()

def _reference_match(*args, **kwargs):
    return reject()

def _context_key(*args, **kwargs):
    return reject()

def _profile_state(*args, **kwargs):
    return reject()

def _sandbox_certification(*args, **kwargs):
    return reject()

def get_company_profile_state(*args, **kwargs):
    return reject()

def _check_identity_references(*args, **kwargs):
    return reject()

def _check_line_references(*args, **kwargs):
    return reject()

def _persisted_snapshot_candidate(*args, **kwargs):
    return reject()

def _classify_tax_rows(*args, **kwargs):
    return reject()

def evaluate_invoice_readiness(*args, **kwargs):
    return reject()
