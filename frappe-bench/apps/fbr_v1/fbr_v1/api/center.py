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


@frappe.whitelist()
def get_center_boot(company=None):
    companies = frappe.get_list("Company", pluck="name", limit_page_length=0)
    company = company or (companies[0] if companies else None)
    if company not in companies:
        frappe.throw("Select a permitted company.", frappe.PermissionError)

    return {
        "companies": companies,
        "company": company,
        "readiness": get_client_readiness(company),
        "devices": frappe.get_list(
            "Ledgix FBR POS Device",
            filters={"company": company},
            fields=DEVICE_FIELDS,
            limit_page_length=0,
        ),
        "mapping_summary": _mapping_summary(company),
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
        return {"ok": False, "network_call": True, "error": "IMS health check unavailable; inspect the local service."}
    # Service bodies and exception details are deliberately not returned to browsers.
    return {"ok": result["ok"], "http_status": result["http_status"], "network_call": True}
