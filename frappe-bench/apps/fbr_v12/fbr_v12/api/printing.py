"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _asset_url(*args, **kwargs):
    return reject()

def _print_brand(*args, **kwargs):
    return reject()

def get_fbr_qr_data_uri(*args, **kwargs):
    return reject()

def _json(*args, **kwargs):
    return reject()

def _v2_profile_public(*args, **kwargs):
    return reject()

def _identity_for_print(*args, **kwargs):
    return reject()

def _buyer(*args, **kwargs):
    return reject()

def _seller(*args, **kwargs):
    return reject()

def _line_context(*args, **kwargs):
    return reject()

def get_native_invoice_print_context(*args, **kwargs):
    return reject()
