"""Retired Digital Invoicing compatibility shell."""
from fbr_v12.retired import reject

def _text(*args, **kwargs):
    return reject()

def _require_roles(*args, **kwargs):
    return reject()

def _profile_runtime(*args, **kwargs):
    return reject()

def _offline_policy(*args, **kwargs):
    return reject()

def _response_json(*args, **kwargs):
    return reject()

def _prior_production_post_attempts(*args, **kwargs):
    return reject()

def _source(*args, **kwargs):
    return reject()

def declare_known_offline_internal(*args, **kwargs):
    return reject()

def declare_known_offline(*args, **kwargs):
    return reject()

def list_offline_queue_internal(*args, **kwargs):
    return reject()

def get_offline_queue(*args, **kwargs):
    return reject()

def upload_offline_native_internal(*args, **kwargs):
    return reject()

def upload_offline_invoice(*args, **kwargs):
    return reject()
