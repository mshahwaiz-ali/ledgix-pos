"""Read-only Federal V1 setup summary; no DI cache or certification authority."""
import frappe
from fbr_v1.services.pos_identity import get_profile, profile_active, PROTOCOL
from fbr_v1.services.fbr_v1_readiness import UNRESOLVED
from fbr_v1.protocol import transport

@frappe.whitelist()
def get_client_readiness(company):
    frappe.get_doc("Company", company).check_permission("read")
    profile = get_profile(company)
    if profile:
        profile.check_permission("read")
    return {"protocol": PROTOCOL, "profile": profile.name if profile else None,
            "enabled": profile_active(profile), "mode": profile.get("mode") if profile else "Disabled",
            "network_cutover_active": transport.V1_NETWORK_CUTOVER_ACTIVE,
            "production_ready": False, "unresolved_contracts": UNRESOLVED,
            "network_call": False}
