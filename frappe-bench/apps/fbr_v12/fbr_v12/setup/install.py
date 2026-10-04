"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def sync_all(*args, **kwargs):
    return reject()

def after_install(*args, **kwargs):
    return reject()

def after_migrate(*args, **kwargs):
    return reject()
