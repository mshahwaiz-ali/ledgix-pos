app_name = "fbr_v1"
app_title = "FBR V1"
app_publisher = "Ledgix"
app_description = "Bootstrap ERPNext integration for FBR V1 / Tier-1 POS redesign"
app_email = "alishahwaiz96@gmail.com"
app_license = "mit"

required_apps = ["erpnext", "ledgix_saas"]

app_include_js = ["/assets/fbr_v1/js/fbr_v1_taxable_base.js"]

after_install = "fbr_v1.setup.install.after_install"
after_migrate = ["fbr_v1.setup.install.after_migrate"]

jinja = {
    "methods": [
        "fbr_v1.api.printing.get_fbr_qr_data_uri",
        "fbr_v1.api.printing.get_native_invoice_print_context",
    ],
}

erpnext_taxable_base_resolvers = {
    "On Notified Retail Price": "fbr_v1.services.erpnext_taxable_base.resolve_notified_retail_price",
}

doc_events = {
    "Sales Invoice": {
        "before_validate": "fbr_v1.services.erpnext_taxable_base.stamp_fbr_taxable_base_inputs",
        "before_submit": "fbr_v1.services.fbr_v1_snapshot_persistence.before_submit_capture",
        "on_submit": "fbr_v1.api.fiscalization.on_native_invoice_submit",
        "before_cancel": "fbr_v1.api.fiscalization.block_cancel_after_fbr_submission",
    },
    "POS Invoice": {
        "before_validate": "fbr_v1.services.erpnext_taxable_base.stamp_fbr_taxable_base_inputs",
        "before_submit": "fbr_v1.services.fbr_v1_snapshot_persistence.before_submit_capture",
        "on_submit": "fbr_v1.api.fiscalization.on_native_invoice_submit",
        "before_cancel": "fbr_v1.api.fiscalization.block_cancel_after_fbr_submission",
    },
}

# Production retransmission remains fail-closed. No automatic retry scheduler.
scheduler_events = {}
