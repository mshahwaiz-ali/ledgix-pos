"""Retired DI/V2 entry points. Historical schema and records are preserved."""
import frappe


def retired(*args, **kwargs):
    frappe.throw("DI/V2 service is retired. Use Federal POS/IMS V1; historical data is not reinterpreted.")


_normalize_plan = retired
_account_state = retired
preview_component_mappings = retired
provision_component_mappings = retired
