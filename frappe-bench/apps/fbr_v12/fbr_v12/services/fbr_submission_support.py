"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def serialize_json(*args, **kwargs):
    return reject()

def normalize_fbr_status(*args, **kwargs):
    return reject()

def _safe_message(*args, **kwargs):
    return reject()

def _extract_fbr_qr_code(*args, **kwargs):
    return reject()

def resolve_submission_status(*args, **kwargs):
    return reject()

def parse_fbr_response(*args, **kwargs):
    return reject()

def create_submission_log(*args, **kwargs):
    return reject()

def submission_lock(*args, **kwargs):
    return reject()
