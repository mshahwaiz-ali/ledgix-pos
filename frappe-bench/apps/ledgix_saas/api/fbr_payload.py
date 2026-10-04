"""Retired payload generation. Historical snapshots are read strictly, never rebuilt."""
import frappe
from ledgix_saas.api import fbr_legacy_guard
from ledgix_saas.services.historical_fbr_evidence import read_persisted_v2_snapshot

LEGACY_PAYLOAD_AUTHORITY = "Historical Persisted Evidence Only"

def get_sale_for_fbr(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def get_customer_for_fbr(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def get_invoice_tax_rows_for_fbr(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def get_return_for_fbr(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def get_return_tax_rows_for_fbr(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _clean_text(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _clean_identifier(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _clean_hs_code(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _is_digits(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _is_valid_hs_code(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _is_missing(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _money(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _format_invoice_date(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _format_tax_rate(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _fbr_rate_description(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _charged_tax_amount(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _add_required_error(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _get_tax_profile_defaults(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _normalize_buyer_registration_type(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _customer_address_fallback(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _validate_ntn_cnic(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _validate_province(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _validate_sro_fields(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _historical_settings(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _historical_control_state(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _require_fbr_view_permission(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _settings_summary(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _sale_summary(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _return_summary(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def build_fbr_seller_block(*args, **kwargs):
    frappe.throw("Historical fiscal evidence unavailable: legacy sale identity is unverified.")

def build_fbr_seller_block_from_sale(*args, **kwargs):
    frappe.throw("Historical fiscal evidence unavailable: legacy sale identity is unverified.")

def build_fbr_buyer_block(*args, **kwargs):
    frappe.throw("Historical fiscal evidence unavailable: legacy sale identity is unverified.")

def build_fbr_buyer_block_from_sale(*args, **kwargs):
    frappe.throw("Historical fiscal evidence unavailable: legacy sale identity is unverified.")

def _validate_tax_rows(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _validate_seller_block(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _validate_buyer_block(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _unique_scenario_ids(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _validate_single_sandbox_scenario(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _validate_sale_fbr_readiness_internal(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def validate_sale_fbr_readiness(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _item_description(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def build_fbr_item_rows(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _payload_totals(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def build_internal_fbr_payload(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _official_item_payload(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def build_official_sale_invoice_payload(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _build_sale_invoice_payload_internal(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def build_sale_invoice_payload(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _validate_return_fbr_readiness_internal(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def build_official_return_invoice_payload(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def _build_return_invoice_payload_internal(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()

def build_return_invoice_payload(*args, **kwargs):
    return fbr_legacy_guard.reject_legacy_fbr_action()
