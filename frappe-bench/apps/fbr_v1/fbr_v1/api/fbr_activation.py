"""Retired DI/V2 compatibility endpoints. Historical records are preserved."""
import frappe

@frappe.whitelist()
def retired(*args, **kwargs):
    frappe.throw("DI/V2 runtime is retired in FBR V1. Use Federal V1 Center and fiscalization APIs.")

get_v2_configuration_summary_internal = retired
evaluate_fbr_activation_readiness = retired
get_fbr_activation_readiness = retired
generate_fbr_activation_evidence = retired
