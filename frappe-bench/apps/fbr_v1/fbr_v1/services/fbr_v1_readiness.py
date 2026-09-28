"""V1 internal readiness is distinct from authorization to send."""
import frappe
from frappe.utils import cint
from fbr_v1.services.pos_identity import get_profile, profile_active, resolve_device, is_consolidated
from fbr_v1.services.fbr_v1_snapshot_persistence import read_persisted_v1_snapshot
from fbr_v1.services.fbr_v1_payload_builder import build_invoice
from fbr_v1.protocol import transport
from fbr_v1.services.v1_configuration import configuration_blockers, get_device_compliance_state

UNRESOLVED = [
    "Item-level Debit behavior", "Complete error-code catalogue", "Server duplicate-USIN behavior",
    "Current client POSID/token acquisition workflow",
    "Separate offline batch-upload endpoint/schema", "External daily/weekly/monthly closing endpoint/schema",
    "Undocumented digital-signature algorithm",
    "External outage-reporting API", "External alert-message API",
    "V1 wire fields for Extra Tax, FED Payable and Sales Tax Withheld at Source",
    "Foreign-currency and inclusive-tax discount wire semantics",
]


def inspect_invoice(doc):
    errors = []
    snapshot = invoice = device = None
    profile = get_profile(doc.company)
    if not profile_active(profile) or profile.get("mode") == "Paused":
        errors.append("Federal V1 profile is disabled, legacy, missing or paused.")
    if cint(doc.docstatus) != 1 or is_consolidated(doc):
        errors.append("A submitted native source invoice is required; POS consolidation is suppressed.")
    try:
        snapshot = read_persisted_v1_snapshot(doc.doctype, doc.name)
        invoice = build_invoice(snapshot)
        if profile_active(profile):
            device = resolve_device(doc, profile)
            if device != snapshot["header"]["pos_device"]:
                errors.append("Current device identity differs from immutable submission evidence.")
    except (ValueError, frappe.ValidationError) as exc:
        errors.append(str(exc))
    if doc.get("custom_ledgix_fbr_reconciliation_required") or doc.get("custom_ledgix_fbr_status") == "Reconciliation Required":
        errors.append("Reconciliation Required; automatic retransmission is prohibited.")
    if doc.get("custom_ledgix_fbr_status") == "Offline Pending":
        errors.append("Separate offline-upload contract is unresolved.")
    network_errors = []
    if not transport.network_cutover_active():
        network_errors.append("General V1 network cutover is disabled.")
    mode = profile.get("mode") if profile else "Disabled"
    current_device = None
    if device and mode in {"Sandbox", "Production"}:
        compliance = get_device_compliance_state(device["name"], include_production=mode == "Production")
        # Merge only for current readiness, never into the persisted identity or its comparison.
        current_device = {**device, **compliance}
    network_errors.extend(configuration_blockers(profile, current_device, mode))
    if mode == "Production" and not transport.production_cutover_active():
        network_errors.append("Production network cutover is disabled.")
    return {"ready": not errors, "network_ready": not errors and not network_errors,
            "errors": errors, "network_blockers": network_errors, "unresolved_contracts": UNRESOLVED,
            "snapshot": snapshot, "invoice": invoice, "profile": profile, "device": device}
