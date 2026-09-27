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
