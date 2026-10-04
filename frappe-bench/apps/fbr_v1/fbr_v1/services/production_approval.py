"""Internal evidence of explicit external approval, never an FBR API."""
import frappe
from frappe.utils import now_datetime
from fbr_v1.api.compliance_evidence import require_external_evidence

FIELDS = ("production_approval_reference", "production_approval_evidence")

def validate_approval(doc, old):
    verified = doc.get("production_approval_status") == "Verified"
    unchanged = old and old.get("production_approval_status") == "Verified" and all(doc.get(f) == old.get(f) for f in FIELDS)
    if not verified:
        doc.production_approval_verified_at = doc.production_approval_verified_by = None
        return
    require_external_evidence(doc.get(FIELDS[0]), doc.get(FIELDS[1]))
    if unchanged:
        doc.production_approval_verified_at = old.get("production_approval_verified_at")
        doc.production_approval_verified_by = old.get("production_approval_verified_by")
    else:
        if "System Manager" not in frappe.get_roles():
            frappe.throw("Only System Manager may verify external Production approval.", frappe.PermissionError)
        doc.production_approval_verified_at = now_datetime()
        doc.production_approval_verified_by = frappe.session.user

def approval_complete(profile):
    if not profile or profile.get("production_approval_status") != "Verified":
        return False
    if not all(profile.get(f) for f in (*FIELDS, "production_approval_verified_at", "production_approval_verified_by")):
        return False
    try:
        require_external_evidence(profile.get(FIELDS[0]), profile.get(FIELDS[1]))
    except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError):
        return False
    return True
