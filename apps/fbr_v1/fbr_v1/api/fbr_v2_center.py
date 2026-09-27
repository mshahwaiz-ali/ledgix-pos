"""Retired DI/V2 compatibility endpoints. Historical records are preserved."""
import frappe

@frappe.whitelist()
def retired(*args, **kwargs):
    frappe.throw("DI/V2 runtime is retired in FBR V1. Use Federal V1 Center and fiscalization APIs.")

get_v2_center_boot = retired
get_v2_item_mappings = retired
evaluate_v2_invoice_readiness = retired
get_fbr_readiness = retired
