app_name = "ledgix_saas"
app_title = "Ledgix"
app_publisher = "Ali"
app_description = "POS and inventory platform for retail shops"
app_email = "alishahwaiz96@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]
app_logo_url = "/assets/ledgix_saas/images/brand/ledgix-symbol.svg"

app_include_css = [
	"/assets/ledgix_saas/css/ledgix_brand.css",
	"/assets/ledgix_saas/css/ledgix_v2_tokens.css",
]
app_include_js = [
	"/assets/ledgix_saas/js/ledgix_brand.js",
	"/assets/ledgix_saas/js/ledgix_sidebar_brand.js",
	"/assets/ledgix_saas/js/ledgix_fbr_native_center.js",
	"/assets/ledgix_saas/js/ledgix_phase10_native_surfaces.js",
	"/assets/ledgix_saas/js/ledgix_phase11_product_shell.js",
]
web_include_css = ["/assets/ledgix_saas/css/ledgix_brand.css"]
web_include_js = ["/assets/ledgix_saas/js/ledgix_brand.js"]

# Desk landing is profile-aware in Phase 11. A static role_home_page hook would
# incorrectly send Invoice-only/B2B Cashiers into POS when POS is disabled.

jinja = {
	"methods": [
		"ledgix_saas.api.brand.get_splash_logo_url",
		"ledgix_saas.api.brand.get_print_logo_url",
		"ledgix_saas.api.printing.get_fbr_qr_data_uri",
		"ledgix_saas.api.printing.get_native_invoice_print_context",
	],
}

after_migrate = [
	"ledgix_saas.setup.erpnext_extensions.after_migrate",
	"ledgix_saas.setup.erpnext_tax_foundation.after_migrate",
	"ledgix_saas.setup.erpnext_phase5_extensions.after_migrate",
	"ledgix_saas.setup.erpnext_phase6_extensions.after_migrate",
	"ledgix_saas.setup.erpnext_phase7_extensions.after_migrate",
	"ledgix_saas.setup.erpnext_phase8_extensions.after_migrate",
	"ledgix_saas.setup.erpnext_phase9_extensions.after_migrate",
	"ledgix_saas.setup.erpnext_phase10_print_formats.after_migrate",
	"ledgix_saas.setup.fast_permissions.after_migrate",
	"ledgix_saas.setup.erpnext_phase11_product_shell.after_migrate",
	# This runs after the normal permission policy so a previously frozen site
	# always finishes migrate with legacy business DocTypes read-only again.
	"ledgix_saas.setup.erpnext_phase12_legacy_retirement.after_migrate",
]

extend_bootinfo = [
	"ledgix_saas.api.brand.extend_bootinfo",
	"ledgix_saas.api.product_shell.extend_bootinfo",
]
update_website_context = ["ledgix_saas.api.brand.update_website_context"]

# Keep Ledgix screen/RPC contracts stable while ERPNext owns the business engine.
override_whitelisted_methods = {
	"ledgix_saas.api.tax_center.get_fbr_readiness": "ledgix_saas.api.fbr_preflight.get_fbr_readiness",
	"ledgix_saas.api.inventory_intelligence.get_inventory_intelligence_data": "ledgix_saas.api.inventory_intelligence_native.get_inventory_intelligence_data",
	# The original 79KB BI engine remains historical source code only. Any old RPC
	# client now receives the same ERPNext-native intelligence result as Phase 10.
	"ledgix_saas.api.business_intelligence.get_business_intelligence_data": "ledgix_saas.api.inventory_intelligence_native.get_inventory_intelligence_data",

	"ledgix_saas.api.v2_pos.get_pos_v2_boot": "ledgix_saas.api.pos_compat.get_pos_v2_boot",
	"ledgix_saas.api.v2_pos.search_pos_v2_items": "ledgix_saas.api.pos_compat.search_pos_v2_items",
	"ledgix_saas.api.v2_pos.complete_pos_v2_sale": "ledgix_saas.api.pos_compat.complete_pos_v2_sale",
	"ledgix_saas.api.v2_pos.preview_pos_v2_checkout": "ledgix_saas.api.pos_compat.preview_pos_v2_checkout",
	"ledgix_saas.api.v2_pos.get_pos_v2_customer_context": "ledgix_saas.api.pos_compat.get_pos_v2_customer_context",

	"ledgix_saas.api.v2_returns.get_pos_v2_return_context": "ledgix_saas.api.pos_compat.get_pos_v2_return_context",
	"ledgix_saas.api.v2_returns.create_pos_v2_return": "ledgix_saas.api.pos_compat.create_pos_v2_return",

	"ledgix_saas.api.v2_holds.hold_pos_v2_sale": "ledgix_saas.api.pos_compat.hold_pos_v2_sale",
	"ledgix_saas.api.v2_holds.get_pos_v2_holds": "ledgix_saas.api.pos_compat.get_pos_v2_holds",
	"ledgix_saas.api.v2_holds.resume_pos_v2_hold": "ledgix_saas.api.pos_compat.resume_pos_v2_hold",
	"ledgix_saas.api.v2_holds.cancel_pos_v2_hold": "ledgix_saas.api.pos_compat.cancel_pos_v2_hold",

	"ledgix_saas.api.shifts.get_active_shift_info": "ledgix_saas.api.pos_compat.get_active_shift_info",
	"ledgix_saas.api.shifts.open_pos_shift": "ledgix_saas.api.pos_compat.open_pos_shift",
	"ledgix_saas.api.shifts.close_pos_shift": "ledgix_saas.api.pos_compat.close_pos_shift",
	"ledgix_saas.api.api.get_active_shift_info": "ledgix_saas.api.pos_compat.get_active_shift_info",
	"ledgix_saas.api.api.open_pos_shift": "ledgix_saas.api.pos_compat.open_pos_shift",
	"ledgix_saas.api.api.close_pos_shift": "ledgix_saas.api.pos_compat.close_pos_shift",

	"ledgix_saas.api.selling.preview_b2b_invoice": "ledgix_saas.api.selling_compat.preview_b2b_invoice",
	"ledgix_saas.api.selling.create_b2b_invoice": "ledgix_saas.api.selling_compat.create_b2b_invoice",
	"ledgix_saas.api.selling.complete_b2b_sale": "ledgix_saas.api.selling_compat.complete_b2b_sale",
	"ledgix_saas.api.selling.create_exchange": "ledgix_saas.api.selling_compat.create_exchange",

	# Phase 9 is a hard source cutover. Historical legacy sales stay readable but
	# can no longer issue a new official FBR invoice through the old POST endpoint.
	"ledgix_saas.api.fbr_submission.submit_sale_to_fbr": "ledgix_saas.api.fbr_legacy_guard.reject_legacy_sale_submission",
}

doc_events = {
	"Payment Entry": {
		"validate": "ledgix_saas.services.erpnext_payment_policy.validate_ledgix_payment_entry",
	},
	"Sales Invoice": {
		"on_submit": "ledgix_saas.api.fbr_native.on_native_invoice_submit",
		"before_cancel": "ledgix_saas.api.fbr_native.block_cancel_after_fbr_submission",
	},
	"POS Invoice": {
		"on_submit": "ledgix_saas.api.fbr_native.on_native_invoice_submit",
		"before_cancel": "ledgix_saas.api.fbr_native.block_cancel_after_fbr_submission",
	},
}

# Phase 12 keeps historical rows physically present but immutable once the
# retirement state is explicitly Frozen.  The guard is state-aware, so merely
# installing/migrating Phase 12 does not trap an unresolved legacy draft.
_legacy_retired_business_doctypes = (
	"Ledgix Item",
	"Ledgix Category",
	"Ledgix Customer",
	"Ledgix Supplier",
	"Ledgix Price List",
	"Ledgix Item Price",
	"Ledgix Payment Method",
	"Ledgix Sale",
	"Ledgix Purchase",
	"Ledgix Sales Return",
	"Ledgix POS Shift",
	"Ledgix POS Hold",
	"Ledgix Payment",
	"Ledgix Stock Movement",
	"Ledgix Stock Lot",
	"Ledgix Stock Serial",
)
_legacy_freeze_events = {
	"before_insert": "ledgix_saas.api.legacy_retirement.guard_legacy_write",
	"before_save": "ledgix_saas.api.legacy_retirement.guard_legacy_write",
	"before_submit": "ledgix_saas.api.legacy_retirement.guard_legacy_write",
	"before_cancel": "ledgix_saas.api.legacy_retirement.guard_legacy_write",
	"on_trash": "ledgix_saas.api.legacy_retirement.guard_legacy_write",
}
for _legacy_doctype in _legacy_retired_business_doctypes:
	doc_events[_legacy_doctype] = _legacy_freeze_events

# Retransmission remains fail-closed. A production POST with an ambiguous outcome
# must be externally reconciled before any manual retry; no blind scheduler retry.
scheduler_events = {}

fixtures = [
	{
		"doctype": "Role",
		"filters": [["name", "in", ["Ledgix Admin", "Ledgix Manager", "Ledgix Cashier"]]],
	},
	{"doctype": "Workspace", "filters": [["name", "=", "Ledgix"]]},
	{"doctype": "Custom Field", "filters": [["module", "=", "Ledgix"]]},
	{"doctype": "Property Setter", "filters": [["module", "=", "Ledgix"]]},
]
