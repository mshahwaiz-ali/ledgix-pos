"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _text(*args, **kwargs):
    return reject()

def _money(*args, **kwargs):
    return reject()

def _quantity(*args, **kwargs):
    return reject()

def _identifier(*args, **kwargs):
    return reject()

def _is_consolidated_pos_sales_invoice(*args, **kwargs):
    return reject()

def _raise_readiness(*args, **kwargs):
    return reject()

def _line_item_payload(*args, **kwargs):
    return reject()

def build_payload_candidate(*args, **kwargs):
    return reject()
