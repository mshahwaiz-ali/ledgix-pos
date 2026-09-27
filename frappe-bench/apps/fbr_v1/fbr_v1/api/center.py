import frappe
from frappe.utils import cint

from fbr_v1.api.client_readiness import get_client_readiness


PAYMENT_CODES = ["1 - Cash", "2 - Card", "3 - Gift Voucher", "4 - Loyalty Card", "6 - Cheque"]
DEVICE_FIELDS = [
    "name",
    "display_label",
    "pos_id",
    "environment",
    "operational_state",
    "transport_topology",
    "pos_profile",
    "outlet_address",
    "active",
]
SUBMISSION_SUMMARY_FIELDS = [
    "name",
    "reference_doctype",
    "reference_name",
    "fbr_status",
    "fbr_invoice_number",
    "attempt_count",
    "attempt_id",
    "source_snapshot_hash",
    "request_hash",
    "transport_started_at",
    "transport_finished_at",
    "transport_outcome",
    "reconciliation_required",
    "error_code",
    "error_message",
    "modified",
]


def _cutover_bool(value):
    value = str(value).strip().lower()
    if value not in {"0", "1", "false", "true"}:
        frappe.throw("Network cutover value must be 0 or 1.")
    return value in {"1", "true"}


def _require_cutover_manager():
    if "System Manager" not in set(frappe.get_roles()):
        frappe.throw(
            "System Manager permission is required to change the Sandbox network gate.",
            frappe.PermissionError,
        )


def _raw_site_gate_enabled(key):
    value = frappe.conf.get(key, 0)
    return (
        value is True
        or (type(value) is int and value == 1)
        or str(value).strip() == "1"
    )


def _write_site_gate(key, enabled):
    from frappe.installer import update_site_config

    value = 1 if enabled else 0
    update_site_config(key, value)

    # Keep this request's configuration projection synchronized with disk.
    frappe.local.conf[key] = value


@frappe.whitelist(methods=["POST"])
def set_sandbox_network_cutover(company, enabled):
    """Change only the general V1 network gate for controlled Sandbox testing.

    This endpoint never changes Production cutover, profile mode, credentials,
    submit trigger, or Production posting arm state.
    """
    from fbr_v1.protocol import transport
    from fbr_v1.services.pos_identity import get_profile, profile_active

    _require_cutover_manager()
    enable = _cutover_bool(enabled)

    # Disabling must always remain possible for an authorized operator.
    if not enable:
        _write_site_gate("fbr_v1_network_cutover_active", False)
        return {
            "network_cutover_active": transport.network_cutover_active(),
            "production_cutover_active": transport.production_cutover_active(),
            "network_call": False,
        }

    frappe.get_doc("Company", company).check_permission("read")

    profile = get_profile(company)
    if not profile:
        frappe.throw("Federal V1 Integration Profile is required.")

    profile.check_permission("read")

    if not profile_active(profile) or profile.get("mode") != "Sandbox":
        frappe.throw("Sandbox network cutover requires an enabled Sandbox profile.")

    if profile.get("submit_trigger") != "Manual":
        frappe.throw("Sandbox network cutover requires Submit Trigger = Manual.")

    if not cint(profile.get("transport_enabled")):
        frappe.throw("Sandbox network cutover requires Transport Enabled.")

    if cint(profile.get("production_post_armed")):
        frappe.throw("Production Posting must remain disarmed.")

    # Check the raw Production config because production_cutover_active()
    # is intentionally masked while the general gate is OFF.
    if _raw_site_gate_enabled("fbr_v1_production_cutover_active"):
        frappe.throw(
            "Production cutover is configured ON. "
            "Refusing to enable the Sandbox network gate."
        )

    # The general gate is site-wide. Prevent any enabled Sandbox profile
    # from becoming an automatic sender when this gate is opened.
    automatic_profiles = frappe.get_all(
        "Ledgix FBR Integration Profile",
        filters={
            "enabled": 1,
            "mode": "Sandbox",
            "submit_trigger": "On Submit",
        },
        pluck="name",
        limit_page_length=0,
    )
    if automatic_profiles:
        frappe.throw(
            "Sandbox network cutover requires Manual submit on every "
            "enabled Sandbox profile."
        )

    _write_site_gate("fbr_v1_network_cutover_active", True)

    # Final defense in depth: this Sandbox-only operation must never
    # result in Production transport becoming active.
    if transport.production_cutover_active():
        _write_site_gate("fbr_v1_network_cutover_active", False)
        frappe.throw(
            "Safety interlock stopped the operation because "
            "Production transport became active."
        )

    return {
        "network_cutover_active": transport.network_cutover_active(),
        "production_cutover_active": transport.production_cutover_active(),
        "network_call": False,
    }


def _mapping_summary(company):
    item_rows = frappe.get_list(
        "Ledgix FBR Item Mapping",
        filters={"company": company, "active": 1},
        fields=["name", "needs_review"],
        limit_page_length=0,
    )
    tax_rows = frappe.get_list(
        "Ledgix FBR Tax Component Mapping",
        filters={"company": company, "active": 1},
        fields=["name", "component", "account_head"],
        limit_page_length=0,
    )
    payment_rows = frappe.get_list(
        "Mode of Payment",
        filters={"custom_ledgix_fbr_v1_payment_mode": ["in", PAYMENT_CODES]},
        fields=["name", "custom_ledgix_fbr_v1_payment_mode"],
        limit_page_length=0,
    )
    return {
        "active_item_mappings": len(item_rows),
        "reviewed_item_mappings": sum(not cint(row.get("needs_review")) for row in item_rows),
        "active_tax_component_mappings": len(tax_rows),
        "payment_mappings": len(payment_rows),
        "payment_modes": payment_rows,
    }


def _latest_submission_summary(devices):
    device_names = [row.get("name") for row in (devices or []) if row.get("name")]
    if not device_names:
        return None

    rows = frappe.get_list(
        "Ledgix FBR Submission Log",
        filters={"pos_device": ["in", device_names]},
        fields=SUBMISSION_SUMMARY_FIELDS,
        order_by="modified desc",
        limit_page_length=1,
    )
    return rows[0] if rows else None


@frappe.whitelist()
def get_center_boot(company=None):
    companies = frappe.get_list("Company", pluck="name", limit_page_length=0)
    company = company or (companies[0] if companies else None)
    if company not in companies:
        frappe.throw("Select a permitted company.", frappe.PermissionError)

    devices = frappe.get_list(
        "Ledgix FBR POS Device",
        filters={"company": company},
        fields=DEVICE_FIELDS,
        limit_page_length=0,
    )

    return {
        "companies": companies,
        "company": company,
        "readiness": get_client_readiness(company),
        "devices": devices,
        "mapping_summary": _mapping_summary(company),
        "latest_submission": _latest_submission_summary(devices),
        "network_call": False,
    }


@frappe.whitelist(methods=["POST"])
def test_local_ims_health(pos_device):
    from fbr_v1.api.fiscalization import require_operator
    from fbr_v1.protocol import transport

    require_operator()
    device = frappe.get_doc("Ledgix FBR POS Device", pos_device)
    device.check_permission("write")
    if device.transport_topology != "Local IMS - Server Reachable":
        frappe.throw("Health testing supports only Local IMS - Server Reachable.")
    if not transport.network_cutover_active():
        frappe.throw("General V1 network cutover is disabled.")
    try:
        result = transport.health_local()
    except Exception:
        return {
            "ok": False,
            "network_call": True,
            "error": "IMS health check unavailable; inspect the local service.",
        }
    # Service bodies and exception details are deliberately not returned to browsers.
    return {
        "ok": result["ok"],
        "http_status": result["http_status"],
        "network_call": True,
    }
