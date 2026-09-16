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
]
web_include_css = ["/assets/ledgix_saas/css/ledgix_brand.css"]
web_include_js = ["/assets/ledgix_saas/js/ledgix_brand.js"]

role_home_page = {
	"Ledgix Cashier": "ledgix-pos",
	"Ledgix Manager": "Ledgix",
	"Ledgix Admin": "Ledgix",
}

jinja = {
	"methods": [
		"ledgix_saas.api.brand.get_splash_logo_url",
		"ledgix_saas.api.brand.get_print_logo_url",
		"ledgix_saas.api.printing.get_fbr_qr_data_uri",
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
	"ledgix_saas.setup.fast_permissions.after_migrate",
]

extend_bootinfo = ["ledgix_saas.api.brand.extend_bootinfo"]
update_website_context = ["ledgix_saas.api.brand.update_website_context"]

# Keep the Ledgix screen/RPC contracts stable while ERPNext owns the business
# engine underneath them. Phase 8 routes retail POS boot, catalog, pricing,
# checkout, shifts, holds and returns through native ERPNext POS documents.
# B2B continues through the Phase 6 native Sales Invoice compatibility path.
override_whitelisted_methods = {
	"ledgix_saas.api.tax_center.get_fbr_readiness": "ledgix_saas.api.fbr_preflight.get_fbr_readiness",

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
