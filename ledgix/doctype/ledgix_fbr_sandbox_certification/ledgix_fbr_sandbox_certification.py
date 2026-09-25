from __future__ import annotations

import frappe
from frappe.model.document import Document

from ledgix_saas.services import fbr_v2_readiness


class LedgixFBRSandboxCertification(Document):
    def validate(self):
        if not self.integration_profile or not frappe.db.exists(
            "Ledgix FBR Integration Profile", self.integration_profile
        ):
            frappe.throw("Select a valid FBR Integration Profile.")

        profile = frappe.get_doc(
            "Ledgix FBR Integration Profile", self.integration_profile
        )
        profile_company = profile.get("company")
        if self.company and self.company != profile_company:
            frappe.throw(
                "Sandbox Certification Company must match its FBR Integration Profile."
            )
        self.company = profile_company

        evidence = fbr_v2_readiness.sandbox_certification_evidence(profile, self)
        scenario_evidence = list(evidence.get("scenarios") or [])

        for row, proof in zip(self.scenarios or [], scenario_evidence):
            validate_proof = proof.get("validate") or {}
            post_proof = proof.get("post") or {}

            row.validate_status = "Validated" if validate_proof.get("proven") else "Pending"
            row.validation_log = validate_proof.get("log_name") or ""
            row.post_status = "Submitted" if post_proof.get("proven") else "Pending"
            row.post_log = post_proof.get("log_name") or ""
            row.fbr_invoice_number = post_proof.get("fbr_invoice_number") or ""
            row.completed_at = (
                post_proof.get("submitted_at") if proof.get("complete") else None
            )

            missing = []
            if not validate_proof.get("proven"):
                missing.append(
                    validate_proof.get("reason") or "Sandbox validation proof missing."
                )
            if not post_proof.get("proven"):
                missing.append(
                    post_proof.get("reason") or "Sandbox POST proof missing."
                )
            row.last_error = " ".join(item for item in missing if item)

        self.evidence_complete = 1 if evidence.get("evidence_complete") else 0

        if self.status == "Complete":
            if not evidence.get("required_count"):
                frappe.throw(
                    "At least one required Sandbox scenario is needed before certification can be Complete."
                )

            incomplete = [
                row.get("scenario_id") or "(unnamed scenario)"
                for row in scenario_evidence
                if row.get("required") and not row.get("complete")
            ]
            if incomplete:
                frappe.throw(
                    "Required Sandbox scenarios do not have matching persisted "
                    "Sandbox validation and POST evidence: "
                    + ", ".join(incomplete)
                )
