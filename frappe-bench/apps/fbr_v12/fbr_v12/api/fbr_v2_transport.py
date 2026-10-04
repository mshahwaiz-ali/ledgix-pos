"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _text(*args, **kwargs):
    return reject()

def _not_sent(*args, **kwargs):
    return reject()

def _profile_for_company(*args, **kwargs):
    return reject()

def _token(*args, **kwargs):
    return reject()

def _production_certification(*args, **kwargs):
    return reject()

def _transport_context(*args, **kwargs):
    return reject()

def _fbr_body_state(*args, **kwargs):
    return reject()

def _fbr_body_is_valid(*args, **kwargs):
    return reject()

def _invoice_number(*args, **kwargs):
    return reject()

def _production_post_is_ambiguous(*args, **kwargs):
    return reject()

def _endpoint(*args, **kwargs):
    return reject()

def _send(*args, **kwargs):
    return reject()

def validate_invoice(*args, **kwargs):
    return reject()

def post_invoice(*args, **kwargs):
    return reject()
