"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _roles(*args, **kwargs):
    return reject()

def _require_view(*args, **kwargs):
    return reject()

def _is_admin(*args, **kwargs):
    return reject()

def _count(*args, **kwargs):
    return reject()

def _missing_count(*args, **kwargs):
    return reject()

def _profiles(*args, **kwargs):
    return reject()

def _reference_summary(*args, **kwargs):
    return reject()

def _certification_summary(*args, **kwargs):
    return reject()

def _erpnext_tax_summary(*args, **kwargs):
    return reject()

def _v2_mapping_summary(*args, **kwargs):
    return reject()

def get_v2_center_boot(*args, **kwargs):
    return reject()

def get_v2_item_mappings(*args, **kwargs):
    return reject()

def evaluate_v2_invoice_readiness(*args, **kwargs):
    return reject()

def get_fbr_readiness(*args, **kwargs):
    return reject()
