app_name = "ledgix_saas"
app_title = "Ledgix"
app_publisher = "Ali"
app_description = "POS and inventory platform for retail shops"
app_email = "alishahwaiz96@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "ledgix_saas",
# 		"logo": "/assets/ledgix_saas/logo.png",
# 		"title": "Ledgix",
# 		"route": "/ledgix_saas",
# 		"has_permission": "ledgix_saas.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ledgix_saas/css/ledgix_saas.css"
# app_include_js = "/assets/ledgix_saas/js/ledgix_saas.js"

app_include_css = [
	"/assets/ledgix_saas/css/ledgix_navigator.css",
	"/assets/ledgix_saas/css/ledgix_brand.css",
	"/assets/ledgix_saas/css/ledgix_modal_forms.css",
]

app_include_js = [
	"/assets/ledgix_saas/js/ledgix_navigator_config.js",
	"/assets/ledgix_saas/js/ledgix_navigator.js",
	"/assets/ledgix_saas/js/ledgix_brand.js",
]

# include js, css files in header of web template
web_include_css = [
	"/assets/ledgix_saas/css/ledgix_brand.css",
]
web_include_js = [
	"/assets/ledgix_saas/js/ledgix_brand.js",
]

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ledgix_saas/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ledgix_saas/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
role_home_page = {
	"Ledgix Cashier": "ledgix-pos",
	"Ledgix Manager": "ledgix_operations",
	"Ledgix Admin": "Ledgix",
}

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

jinja = {
	"methods": [
		"ledgix_saas.api.brand.get_splash_logo_url",
	],
}

# Installation
# ------------

# before_install = "ledgix_saas.install.before_install"
# after_install = "ledgix_saas.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ledgix_saas.uninstall.before_uninstall"
# after_uninstall = "ledgix_saas.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ledgix_saas.utils.before_app_install"
# after_app_install = "ledgix_saas.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ledgix_saas.utils.before_app_uninstall"
# after_app_uninstall = "ledgix_saas.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ledgix_saas.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

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
		]
	}
}

# Testing
# -------

# before_tests = "ledgix_saas.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ledgix_saas.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ledgix_saas.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ledgix_saas.utils.before_request"]
# after_request = ["ledgix_saas.utils.after_request"]

# Job Events
# ----------
# before_job = ["ledgix_saas.utils.before_job"]
# after_job = ["ledgix_saas.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ledgix_saas.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


#============================================================================
#============================================================================
#============================================================================
#============================================================================
#============================================================================




# Fixtures
# --------
# Export customizations, roles, workspaces, and permissions

fixtures = [
	{
		"doctype": "Role",
		"filters": [
			["name", "in", [
				"Ledgix Super Admin",
				"Ledgix Admin",
				"Ledgix Manager",
				"Ledgix Cashier"
			]]
		]
	},
	{
		"doctype": "Workspace",
		"filters": [
			["name", "=", "Ledgix"]
		]
	},
	{
		"doctype": "Custom Field",
		"filters": [
			["module", "=", "Ledgix"]
		]
	},
	{
		"doctype": "Property Setter",
		"filters": [
			["module", "=", "Ledgix"]
		]
	}
]
