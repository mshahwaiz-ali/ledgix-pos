"""Deterministic company/POS Profile device selection; no network."""
import frappe
from frappe.utils import cint

PROTOCOL = "Federal POS/IMS V1"
PROFILE = "Ledgix FBR Integration Profile"
DEVICE = "Ledgix FBR POS Device"


def get_profile(company):
    rows = frappe.get_all(PROFILE, filters={"company": company}, pluck="name", limit_page_length=2)
    if len(rows) > 1:
        frappe.throw("Multiple Integration Profiles exist for this company.")
    return frappe.get_doc(PROFILE, rows[0]) if rows else None


def profile_active(profile):
    return bool(profile and profile.get("protocol_version") == PROTOCOL
                and cint(profile.get("enabled")) and profile.get("mode") != "Disabled")


def is_consolidated(doc):
    if doc.doctype != "Sales Invoice":
        return False
    # ERPNext marks POS consolidation before linked POS invoices are updated.
    return bool(cint(doc.get("is_consolidated")) or frappe.db.exists(
        "POS Invoice", {"consolidated_invoice": doc.name, "docstatus": 1}))


def resolve_device(doc, profile):
    selected = doc.get("custom_ledgix_fbr_pos_device")
    if not selected and doc.doctype == "Sales Invoice":
        selected = profile.get("default_pos_device")
    if not selected:
        filters = {"company": doc.company, "active": 1, "environment": profile.get("mode")}
        if doc.doctype == "POS Invoice":
            if not doc.get("pos_profile"):
                frappe.throw("POS Invoice requires an explicit device or POS Profile.")
            filters["pos_profile"] = doc.get("pos_profile")
        matches = frappe.get_all(DEVICE, filters=filters, pluck="name", limit_page_length=2)
        if len(matches) != 1:
            frappe.throw("Select a deterministic FBR POS Device; zero or multiple eligible devices found.")
        selected = matches[0]
    device = frappe.get_doc(DEVICE, selected)
    if device.company != doc.company or not cint(device.get("active")):
        frappe.throw("FBR POS Device must be active and belong to the invoice company.")
    if device.get("environment") != profile.get("mode"):
        frappe.throw("POS Device environment differs from the Integration Profile mode.")
    if doc.doctype == "POS Invoice" and device.get("pos_profile") and device.get("pos_profile") != doc.get("pos_profile"):
        frappe.throw("POS Device belongs to another POS Profile.")
    pos_id = str(device.get("pos_id") or "")
    if not pos_id.isascii() or not pos_id.isdigit() or not 0 < int(pos_id) <= 9223372036854775807:
        frappe.throw("POSID must be a positive bigint registration number.")
    if device.get("transport_topology") not in {"Cloud API", "Local IMS - Server Reachable"}:
        frappe.throw("POS Device transport topology is unresolved or unsupported.")
    return {key: device.get(key) for key in (
        "name", "company", "pos_profile", "pos_id", "environment", "transport_topology",
        "software_registration_number", "outlet_address", "onboarding_reference")}
