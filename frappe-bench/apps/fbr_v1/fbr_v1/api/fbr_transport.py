"""Retired DI/V2 compatibility endpoints. Historical records are preserved."""
import frappe

@frappe.whitelist()
def retired(*args, **kwargs):
    frappe.throw("DI/V2 runtime is retired in FBR V1. Use Federal V1 Center and fiscalization APIs.")

requests_available = retired
ensure_requests_available = retired
safe_error = retired
get_json = retired
post_json = retired
