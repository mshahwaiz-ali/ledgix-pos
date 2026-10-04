"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _effective_mapping(*args, **kwargs):
    return reject()

def _source_return_row(*args, **kwargs):
    return reject()

def _stamp_notified_value(*args, **kwargs):
    return reject()

def _preserve_return_basis(*args, **kwargs):
    return reject()

def stamp_fbr_taxable_base_inputs(*args, **kwargs):
    return reject()

def resolve_notified_retail_price(*args, **kwargs):
    return reject()
