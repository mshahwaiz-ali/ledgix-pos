"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _text(*args, **kwargs):
    return reject()

def _address_name_for_company(*args, **kwargs):
    return reject()

def _address_name_for_customer(*args, **kwargs):
    return reject()

def _address_values(*args, **kwargs):
    return reject()

def resolve_company_seller_identity(*args, **kwargs):
    return reject()

def _buyer_registration_type(*args, **kwargs):
    return reject()

def resolve_invoice_identity(*args, **kwargs):
    return reject()

def build_identity_candidate(*args, **kwargs):
    return reject()
