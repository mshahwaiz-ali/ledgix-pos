"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def requests_available(*args, **kwargs):
    return reject()

def ensure_requests_available(*args, **kwargs):
    return reject()

def safe_error(*args, **kwargs):
    return reject()

def get_json(*args, **kwargs):
    return reject()

def post_json(*args, **kwargs):
    return reject()
