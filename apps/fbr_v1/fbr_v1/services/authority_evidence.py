"""Controlled operator attestations, independent of undocumented machine contracts."""
import frappe
from frappe.utils import now_datetime

AUTHORITY_STATES = {"Existing Tier-1 Registration", "FBR / PRAL Directed", "Licensed Integrator Authorized"}


def stamp_verification(doc, status_field, reference_field, evidence_field, at_field, by_field, verified_states, *, context_fields=()):
    old = doc.get_doc_before_save()
    state = doc.get(status_field) or "Unverified"
    if state not in verified_states | {"Unverified"}:
        frappe.throw("Unsupported verification status.")
    context_changed = bool(old and any(doc.get(k) != old.get(k) for k in context_fields))
    evidence_changed = bool(old and any(doc.get(k) != old.get(k) for k in (reference_field, evidence_field)))
    if context_changed and state in verified_states and old.get(status_field) in verified_states and not evidence_changed:
        frappe.throw("Verified identity or package changed. Set verification to Unverified or supply renewed authority reference/evidence.")
    changed = not old or context_changed or any(doc.get(k) != old.get(k) for k in (status_field, reference_field, evidence_field))
    if state in verified_states:
        if not str(doc.get(reference_field) or "").strip() or not doc.get(evidence_field):
            frappe.throw("Verification requires its authority reference and evidence.")
        if changed:
            from fbr_v1.api.fiscalization import require_operator
            require_operator()
            from fbr_v1.api.compliance_evidence import require_external_evidence
            require_external_evidence(doc.get(reference_field), doc.get(evidence_field))
            doc.set(at_field, now_datetime())
            doc.set(by_field, frappe.session.user)
        else:
            doc.set(at_field, old.get(at_field))
            doc.set(by_field, old.get(by_field))
    else:
        doc.set(at_field, None)
        doc.set(by_field, None)
