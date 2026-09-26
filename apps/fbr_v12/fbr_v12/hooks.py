app_name = "fbr_v12"
app_title = "FBR V1.2"
app_publisher = "Ledgix"
app_description = "ERPNext integration for FBR Digital Invoicing V1.2"
app_email = "alishahwaiz96@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

# Extraction safety:
# Runtime hooks remain disabled at this checkpoint. The existing ledgix_saas
# implementation stays authoritative until FBR-owned source and schema have
# been moved and parity-tested in this app.
doc_events = {}
scheduler_events = {}
