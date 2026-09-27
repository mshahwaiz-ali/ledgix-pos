"""V1 internal readiness is distinct from authorization to send."""
import frappe
from frappe.utils import cint
from fbr_v1.services.pos_identity import get_profile, profile_active, resolve_device, is_consolidated
from fbr_v1.services.fbr_v1_snapshot_persistence import read_persisted_v1_snapshot
from fbr_v1.services.fbr_v1_payload_builder import build_invoice
from fbr_v1.protocol import transport

UNRESOLVED = [
    "Item-level Debit behavior", "Complete error-code catalogue", "Server duplicate-USIN behavior",
    "Current IMS installer/package version", "Current client POSID/token acquisition workflow",
    "Separate offline batch-upload endpoint/schema", "External daily/weekly/monthly closing endpoint/schema",
    "Exact QR verification/encoded payload beyond the returned fiscal number",
    "Federal digital-signature machine implementation", "External outage-reporting API",
    "V1 wire fields for Extra Tax, FED Payable and Sales Tax Withheld at Source",
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
    if not transport.V1_NETWORK_CUTOVER_ACTIVE:
        network_errors.append("V1_NETWORK_CUTOVER_ACTIVE is False.")
    if not profile or not cint(profile.get("transport_enabled")):
        network_errors.append("Transport is disabled.")
    if profile and profile.get("mode") == "Production":
        if not cint(profile.get("production_post_armed")):
            network_errors.append("Production posting is not armed.")
        if not profile.get("activation_reference") or not profile.get("activation_evidence"):
            network_errors.append("Production activation authority evidence is required.")
        network_errors.extend(["Production QR verification contract is unresolved.",
                               "Production digital-signature implementation is unresolved."])
    if device and frappe.db.get_value("Ledgix FBR POS Device", device["name"], "operational_state") != "Operational":
        network_errors.append("POS Device is not operational.")
    if device and device.get("transport_topology") == "Cloud API" and profile:
        field = "v1_production_token" if profile.get("mode") == "Production" else "v1_sandbox_token"
        if not profile.get_password(field, raise_exception=False):
            network_errors.append("Distinct V1 cloud credential is missing.")
    return {"ready": not errors, "network_ready": not errors and not network_errors,
            "errors": errors, "network_blockers": network_errors, "unresolved_contracts": UNRESOLVED,
            "snapshot": snapshot, "invoice": invoice, "profile": profile, "device": device}
