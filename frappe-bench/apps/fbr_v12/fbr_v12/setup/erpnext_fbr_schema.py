"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _cf(*args, **kwargs):
    return reject()

def _invoice_fbr_fields(*args, **kwargs):
    return reject()

def _invoice_item_fbr_fields(*args, **kwargs):
    return reject()

def _invoice_fbr_v2_snapshot_fields(*args, **kwargs):
    return reject()

def _invoice_item_fbr_v2_snapshot_fields(*args, **kwargs):
    return reject()

def sync_sales_tax_charge_type_extension(*args, **kwargs):
    return reject()

def sync_custom_fields(*args, **kwargs):
    return reject()

def sync_all(*args, **kwargs):
    return reject()

def after_migrate(*args, **kwargs):
    return reject()
