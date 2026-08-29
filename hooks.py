app_name = "ledgix_saas"
app_title = "Ledgix"
app_publisher = "Ali"
app_description = "POS and inventory platform for retail shops"
app_email = "alishahwaiz96@gmail.com"
app_license = "mit"

# Keep the global Desk layer deliberately small. Workflow-specific CSS/JS belongs
# to its Page so native Frappe Lists, Forms and Workspaces retain normal behavior.
app_include_css = [
	"/assets/ledgix_saas/css/ledgix_brand.css",
	"/assets/ledgix_saas/css/ledgix_v2_tokens.css",
	"/assets/ledgix_saas/css/ledgix_modal_forms.css",
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
	],
}

after_migrate = ["ledgix_saas.setup.permissions.after_migrate"]

extend_bootinfo = [
	"ledgix_saas.api.brand.extend_bootinfo",
]

update_website_context = [
	"ledgix_saas.api.brand.update_website_context",
]

scheduler_events = {
	"cron": {
		"*/15 * * * *": [
			"ledgix_saas.api.fbr_submission.process_fbr_retry_queue"
		],
		"0 * * * *": [
			"ledgix_saas.api.fbr_submission.process_fbr_offline_upload_queue"
		],
	}
}

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
