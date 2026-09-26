app_name = "fbr_v12"
app_title = "FBR V1.2"
app_publisher = "Ledgix"
app_description = "ERPNext integration for FBR Digital Invoicing V1.2"
app_email = "alishahwaiz96@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

after_install = "fbr_v12.setup.install.after_install"
after_migrate = ["fbr_v12.setup.install.after_migrate"]

jinja = {
    "methods": [
        "fbr_v12.api.printing.get_fbr_qr_data_uri",
        "fbr_v12.api.printing.get_native_invoice_print_context",
    ],
}

erpnext_taxable_base_resolvers = {
    "On Notified Retail Price": "fbr_v12.services.erpnext_taxable_base.resolve_notified_retail_price",
}

doc_events = {
    "Sales Invoice": {
        "before_validate": "fbr_v12.services.erpnext_taxable_base.stamp_fbr_taxable_base_inputs",
        "before_submit": "fbr_v12.services.fbr_v2_snapshot_persistence.before_submit_capture",
        "on_submit": "fbr_v12.api.fbr_native.on_native_invoice_submit",
        "before_cancel": "fbr_v12.api.fbr_native.block_cancel_after_fbr_submission",
    },
    "POS Invoice": {
        "before_validate": "fbr_v12.services.erpnext_taxable_base.stamp_fbr_taxable_base_inputs",
        "before_submit": "fbr_v12.services.fbr_v2_snapshot_persistence.before_submit_capture",
        "on_submit": "fbr_v12.api.fbr_native.on_native_invoice_submit",
        "before_cancel": "fbr_v12.api.fbr_native.block_cancel_after_fbr_submission",
    },
}

# Production retransmission remains fail-closed. No automatic retry scheduler.
scheduler_events = {}
