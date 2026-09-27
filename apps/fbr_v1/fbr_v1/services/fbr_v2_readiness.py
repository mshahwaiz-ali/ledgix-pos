"""Retired DI/V2 entry points. Historical schema and records are preserved."""
import frappe


def retired(*args, **kwargs):
    frappe.throw("DI/V2 service is retired. Use Federal POS/IMS V1; historical data is not reinterpreted.")


_text = retired
_profile = retired
_token_configured = retired
_cached_reference_rows = retired
_reference_match = retired
_context_key = retired
_profile_state = retired
_sandbox_certification = retired
get_company_profile_state = retired
_check_identity_references = retired
_check_line_references = retired
_persisted_snapshot_candidate = retired
_classify_tax_rows = retired
evaluate_invoice_readiness = retired
