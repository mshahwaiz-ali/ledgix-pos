"""Configuration evidence checks shared by invoice and operator readiness."""
import frappe
from frappe.utils import cint
from fbr_v1.services.pos_identity import profile_active
from fbr_v1.services.pos_service_fee import service_fee_configuration_blockers


def get_device_compliance_state(device_name, *, include_production=False):
    """Read current evidence without loading a controller or changing fiscal identity."""
    fields = ["active", "operational_state"]
    if include_production:
        fields += ["ims_package_name", "ims_package_version",
                   "ims_installation_reference", "ims_installation_evidence"]
    return frappe.db.get_value("Ledgix FBR POS Device", device_name, fields, as_dict=True) or {}


def configuration_blockers(profile, device, mode):
    errors = []
    if mode not in {"Sandbox", "Production"}:
        errors.append("Select Sandbox or Production mode before transport.")
    if not profile_active(profile) or profile.get("mode") != mode:
        errors.append("An active Federal V1 profile in " + mode + " mode is required.")
    if not profile:
        return errors
    if not cint(profile.get("transport_enabled")):
        errors.append("Transport is disabled.")
    if profile.get("provider_type") not in {"PRAL", "Licensed Integrator", "Other"}:
        errors.append("A valid provider type is required.")
    if profile.get("provider_type") == "Licensed Integrator" and not profile.get("licensed_integrator_name"):
        errors.append("Licensed integrator name is required.")
    if mode == "Production":
        if profile.get("submit_trigger") != "On Submit":
            errors.append("Production profile must use the On Submit trigger.")
        if cint(profile.get("block_print_without_fiscal_result")) != 1:
            errors.append("Production profile must block printing until a fiscal result exists.")
        if not cint(profile.get("production_post_armed")):
            errors.append("Production posting is not armed.")
        errors.extend(service_fee_configuration_blockers(profile))
    if not device:
        return errors + ["Select an active POS device for " + mode + "."]
    if device.get("company") != profile.get("company") or not cint(device.get("active")):
        errors.append("POS device must be active and belong to the profile company.")
    if device.get("pos_profile") and frappe.db.get_value("POS Profile", device.get("pos_profile"), "company") != profile.get("company"):
        errors.append("Device POS Profile must belong to the same company.")
    if device.get("environment") != mode:
        errors.append("POS device environment must be " + mode + ".")
    if device.get("operational_state") != "Operational":
        errors.append("POS device is not operational.")
    pos_id = str(device.get("pos_id") or "")
    if not pos_id.isascii() or not pos_id.isdigit() or not 0 < int(pos_id) <= 9223372036854775807:
        errors.append("A positive bigint POSID is required.")
    if mode == "Production" and not device.get("software_registration_number"):
        errors.append("POS device software registration number is required.")
    topology = device.get("transport_topology")
    if topology not in {"Cloud API", "Local IMS - Server Reachable"}:
        errors.append("POS device topology is unsupported.")
    if topology == "Cloud API":
        field = "v1_production_token" if mode == "Production" else "v1_sandbox_token"
        try:
            configured = bool(profile.get_password(field, raise_exception=False))
        except Exception:
            configured = False
        if not configured:
            errors.append("Distinct " + mode + " V1 cloud credential is missing or unavailable.")
    if mode == "Production" and topology == "Local IMS - Server Reachable":
        for key in ("ims_package_name", "ims_package_version", "ims_installation_reference", "ims_installation_evidence"):
            if not device.get(key):
                errors.append("Production local IMS requires " + key.replace("_", " ") + ".")
    return errors
