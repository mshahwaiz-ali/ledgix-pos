app_name = "ledgix_saas"
app_title = "Ledgix"
app_publisher = "Ali"
app_description = "POS and inventory platform for retail shops"
app_email = "alishahwaiz96@gmail.com"
app_license = "mit"

# Keep the global Desk layer deliberately small. Workflow-specific styling belongs
# to its Page so native Frappe Lists, Forms, Workspaces and dialogs retain normal behavior.
app_include_css = [
	"/assets/ledgix_saas/css/ledgix_brand.css",
	"/assets/ledgix_saas/css/ledgix_v2_tokens.css",
]

app_include_js = [
	"/assets/ledgix_saas/js/ledgix_brand.js",
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
	"ledgix_saas.setup.fast_permissions.after_migrate",
]

extend_bootinfo = [
	"ledgix_saas.api.brand.extend_bootinfo",
]

update_website_context = [
	"ledgix_saas.api.brand.update_website_context",
]

# Keep the existing Tax Center API contract stable while routing FBR readiness
# through the environment-aware preflight service.
override_whitelisted_methods = {
	"ledgix_saas.api.tax_center.get_fbr_readiness": "ledgix_saas.api.fbr_preflight.get_fbr_readiness",
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
