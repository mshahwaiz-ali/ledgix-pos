"""Optional Federal POS/IMS V1 extension boundary; no import-time dependency."""
import frappe


def is_fbr_v1_installed():
    return "fbr_v1" in frappe.get_installed_apps()


def _missing(company, message="Federal FBR V1 app is required for Federal POS/IMS V1 configuration."):
    return {"company": company, "ready": False, "profile": None,
            "source_accounting_ready": False, "setup_ready": False,
            "tax_configuration_ready": False, "errors": [message],
            "setup_blockers": [message], "blockers": [message],
            "database_write": False, "fbr_network_call": False}


def get_company_readiness(company):
    if not is_fbr_v1_installed():
        return _missing(company)
    if not company:
        return _missing(company, "Select an existing ERPNext Company.")
    return frappe.get_attr("fbr_v1.api.client_readiness.get_client_readiness")(company)


def get_company_seller_identity(company):
    if not is_fbr_v1_installed():
        return _missing(company)
    if not company:
        return _missing(company, "Select an existing ERPNext Company.")
    return frappe.get_attr("fbr_v1.services.erpnext_fbr_identity.resolve_company_seller_identity")(company)


def stamp_taxable_base_inputs(doc):
    if is_fbr_v1_installed():
        return frappe.get_attr("fbr_v1.services.erpnext_taxable_base.stamp_fbr_taxable_base_inputs")(doc)
