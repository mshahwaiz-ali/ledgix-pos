"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _normalize_plan(*args, **kwargs):
    return reject()

def _account_state(*args, **kwargs):
    return reject()

def preview_component_mappings(*args, **kwargs):
    return reject()

def provision_component_mappings(*args, **kwargs):
    return reject()
