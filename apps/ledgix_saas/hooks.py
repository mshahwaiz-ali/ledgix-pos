app_name = "ledgix_saas"
app_title = "Ledgix"
app_publisher = "Ali"
app_description = "POS and inventory platform for retail shops"
app_email = "alishahwaiz96@gmail.com"
app_license = "mit"

# Ledgix is an ERPNext extension product. Frappe installs required apps before
# installing Ledgix on a site, so ERPNext must already be available on the bench.
required_apps = ["erpnext"]

# Modern Frappe Desk shells build app_data / dock branding from the app_logo_url
# hook instead of the older top-level bootinfo.app_logo_url field. Keep the
# bundled Ledgix symbol declared here so the app logo is correct from first
# render; ledgix_brand.js can still apply a per-site Brand Settings override.
app_logo_url = "/assets/ledgix_saas/images/brand/ledgix-symbol.svg"

# Keep the global Desk layer deliberately small. Workflow-specific styling belongs
# to its Page so native Frappe Lists, Forms, Workspaces and dialogs retain normal behavior.
app_include_css = [
	"/assets/ledgix_saas/css/ledgix_brand.css",
	"/assets/ledgix_saas/css/ledgix_v2_tokens.css",
]

app_include_js = [
	"/assets/ledgix_saas/js/ledgix_brand.js",
	"/assets/ledgix_saas/js/ledgix_sidebar_brand.js",
]

web_include_css = [
	"/assets/ledgix_saas/css/ledgix_brand.css",
]
web_include_js = [
	"/assets/ledgix_saas/js/ledgix_brand.js",
]

# Homepage routing is only a UX default. Authorization remains enforced by
# Page, DocType, Report and server-side permissions.
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
	"ledgix_saas.setup.fast_permissions.after_migrate",
]

extend_bootinfo = [
	"ledgix_saas.api.brand.extend_bootinfo",
]

update_website_context = [
	"ledgix_saas.api.brand.update_website_context",
]

# Keep stable UI/API contracts while moving business authority phase-by-phase.
# Retail POS remains on the legacy backend until Phase 8; the compatibility
# functions delegate Retail calls back to the existing implementation while B2B
# and native Sales Invoice returns use ERPNext authority from Phase 6 onward.
override_whitelisted_methods = {
	"ledgix_saas.api.tax_center.get_fbr_readiness": "ledgix_saas.api.fbr_preflight.get_fbr_readiness",
	"ledgix_saas.api.v2_pos.complete_pos_v2_sale": "ledgix_saas.api.selling.complete_pos_v2_sale_compat",
	"ledgix_saas.api.v2_pos.preview_pos_v2_checkout": "ledgix_saas.api.selling.preview_pos_v2_checkout_compat",
	"ledgix_saas.api.v2_pos.get_pos_v2_customer_context": "ledgix_saas.api.selling.get_pos_v2_customer_context_compat",
	"ledgix_saas.api.v2_returns.get_pos_v2_return_context": "ledgix_saas.api.selling.get_pos_return_context_compat",
	"ledgix_saas.api.v2_returns.create_pos_v2_return": "ledgix_saas.api.selling.create_pos_return_compat",
}

# Production FBR recovery is intentionally fail-closed. An ambiguous POST/HTTP
# failure can mean FBR received the invoice even when Ledgix did not receive the
# response, so automatic retransmission is disabled until reconciliation-safe
# status checking is implemented and proven against the client Sandbox/PRAL flow.
scheduler_events = {}

# Export customizations, business roles, Workspace, and property metadata.
fixtures = [
	{
		"doctype": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Ledgix Admin",
					"Ledgix Manager",
					"Ledgix Cashier",
				],
			]
		],
	},
	{
		"doctype": "Workspace",
		"filters": [["name", "=", "Ledgix"]],
	},
	{
		"doctype": "Custom Field",
		"filters": [["module", "=", "Ledgix"]],
	},
	{
		"doctype": "Property Setter",
		"filters": [["module", "=", "Ledgix"]],
	},
]
