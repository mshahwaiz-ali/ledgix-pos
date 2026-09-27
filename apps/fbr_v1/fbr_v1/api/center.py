import frappe
from fbr_v1.api.client_readiness import get_client_readiness

@frappe.whitelist()
def get_center_boot(company=None):
    companies = frappe.get_list("Company", pluck="name", limit_page_length=0)
    company = company or (companies[0] if companies else None)
    if company not in companies:
        frappe.throw("Select a permitted company.", frappe.PermissionError)
    return {"companies": companies, "company": company, "readiness": get_client_readiness(company),
            "devices": frappe.get_list("Ledgix FBR POS Device", filters={"company": company},
                fields=["name", "display_label", "pos_id", "environment", "operational_state"], limit_page_length=0)}


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
