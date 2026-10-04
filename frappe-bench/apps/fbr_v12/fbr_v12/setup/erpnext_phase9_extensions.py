"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _cf(*args, **kwargs):
    return reject()

def _fbr_runtime_fields(*args, **kwargs):
    return reject()

def _sync_status_options(*args, **kwargs):
    return reject()

def sync_all(*args, **kwargs):
    return reject()

def after_migrate(*args, **kwargs):
    return reject()
