"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def sync_native_print_formats(*args, **kwargs):
    return reject()

def after_migrate(*args, **kwargs):
    return reject()
