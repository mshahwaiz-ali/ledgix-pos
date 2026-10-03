"""Read-only configuration readiness; invoice readiness remains a separate gate."""
import frappe
from fbr_v1.services.pos_identity import get_profile, profile_active, PROTOCOL
from fbr_v1.services.fbr_v1_readiness import UNRESOLVED
from fbr_v1.services.v1_configuration import configuration_blockers
from fbr_v1.services.erpnext_fbr_identity import resolve_company_seller_identity
from fbr_v1.protocol import transport
from fbr_v1.services import erpnext_tax_readiness


PROFILE_STATE_FIELDS = (
    "protocol_version",
    "enabled",
    "mode",
    "provider_type",
    "default_pos_device",
    "transport_enabled",
    "production_post_armed",
    "submit_trigger",
    "offline_policy",
    "block_print_without_fiscal_result",
    "authority_status",
    "ip_whitelist_status",
)


@frappe.whitelist()
def get_client_readiness(company):
    frappe.get_doc("Company", company).check_permission("read")
    profile = get_profile(company)
    if profile:
        profile.check_permission("read")
    source = resolve_company_seller_identity(company)
    devices = [frappe.get_doc("Ledgix FBR POS Device", name) for name in frappe.get_list(
        "Ledgix FBR POS Device", filters={"company": company, "active": 1}, pluck="name", limit_page_length=0)]
    states = {}
    for mode in ("Sandbox", "Production"):
        candidates = [d for d in devices if d.environment == mode]
        checks = [{"device": d.name, "blockers": configuration_blockers(profile, d, mode)} for d in candidates]
        ready = source["ready"] and any(not c["blockers"] for c in checks)
        states[mode.lower()] = {"ready": bool(ready), "devices": checks,
            "blockers": source["errors"] + ([] if ready else sorted(set(
                e for c in checks for e in c["blockers"]))) + (
                configuration_blockers(profile, None, mode) if not candidates else [])}
    tax_configuration = erpnext_tax_readiness.get_company_tax_readiness(company)
    setup_blockers = list(source["errors"]) + tax_configuration["blockers"]
    if not profile_active(profile) or profile.get("mode") == "Paused":
        setup_blockers.append("An active, unpaused Federal V1 profile is required.")
    if not devices:
        setup_blockers.append("An active POS device is required.")
    for dt, label in (("Ledgix FBR Item Mapping", "Item Mapping"), ("Ledgix FBR Tax Component Mapping", "Tax Component Mapping")):
        filters = {"company": company, "active": 1}
        if dt == "Ledgix FBR Item Mapping":
            filters["needs_review"] = 0
        if not frappe.db.exists(dt, filters):
            setup_blockers.append(label + " configuration is missing.")
    if not frappe.db.exists("Mode of Payment", {"custom_ledgix_fbr_v1_payment_mode": ["in", ["1 - Cash", "2 - Card", "3 - Gift Voucher", "4 - Loyalty Card", "6 - Cheque"]]}):
        setup_blockers.append("A V1 payment mapping is required.")
    for state in states.values():
        state["ready"] = state["ready"] and not setup_blockers
        state["blockers"] = list(dict.fromkeys(state["blockers"] + setup_blockers))
    mode = profile.get("mode") if profile else "Disabled"
    blockers = list(states.get(mode.lower(), {}).get("blockers", setup_blockers))
    if not transport.network_cutover_active():
        blockers.append("General network cutover is disabled.")
    if mode == "Production" and not transport.production_cutover_active():
        blockers.append("Production network cutover is disabled.")
    profile_state = {field: profile.get(field) for field in PROFILE_STATE_FIELDS} if profile else None
    seller = source.get("seller") or {}
    seller_identity = {key: seller.get(key) for key in (
        "ntn_cnic", "business_name", "province", "address", "address_name",
    )}
    return {"protocol": PROTOCOL, "profile": profile.name if profile else None,
            "profile_state": profile_state, "seller_identity": seller_identity,
            "enabled": profile_active(profile), "mode": mode,
            "source_accounting_ready": source["ready"], "source_blockers": source["errors"],
            "tax_configuration": tax_configuration,
            "tax_configuration_ready": tax_configuration["ready"],
            "database_write": False, "fbr_network_call": False,
            "setup_ready": not setup_blockers, "setup_blockers": setup_blockers,
            "sandbox_configuration_ready": states["sandbox"]["ready"],
            "production_configuration_ready": states["production"]["ready"],
            "configuration": states,
            "network_cutover_active": transport.network_cutover_active(),
            "production_cutover_active": transport.production_cutover_active(),
            "production_ready": not setup_blockers and states["production"]["ready"] and transport.production_cutover_active(),
            "invoice_readiness_required": True, "blockers": blockers,
            "unresolved_contracts": UNRESOLVED, "external_closing_status": "Unresolved", "network_call": False}
