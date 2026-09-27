"""Retired DI/V2 compatibility endpoints. Historical records are preserved."""
import frappe

@frappe.whitelist()
def retired(*args, **kwargs):
    frappe.throw("DI/V2 runtime is retired in FBR V1. Use Federal V1 Center and fiscalization APIs.")

sync_reference_family_internal = retired
sync_reference_family = retired
sync_core_reference_data = retired
sync_rates = retired
sync_hs_uoms = retired
sync_sro_schedules = retired
sync_sro_items = retired
lookup_sales_tax_registration_status = retired
lookup_registration_type = retired
get_cached_reference_data = retired
get_cached_contextual_reference_data = retired
