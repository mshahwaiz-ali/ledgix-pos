"""Retired DI/V2 compatibility endpoints. Historical records are preserved."""
import frappe

@frappe.whitelist()
def retired(*args, **kwargs):
    frappe.throw("DI/V2 runtime is retired in FBR V1. Use Federal V1 Center and fiscalization APIs.")

is_native_fbr_source = retired
validate_native_readiness_internal = retired
build_native_payload_internal = retired
build_native_invoice_payload = retired
get_native_fbr_status = retired
mark_native_fbr_status = retired
validate_native_with_fbr_internal = retired
validate_native_with_fbr = retired
submit_native_to_fbr_internal = retired
submit_native_to_fbr = retired
queue_native_for_fbr = retired
on_native_invoice_submit = retired
block_cancel_after_fbr_submission = retired
release_native_after_fbr_reconciliation = retired
