from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]


class TestFBRClientCertificationHandoffContract(unittest.TestCase):
    def text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_known_offline_desk_surface(self):
        source = self.text(APP_ROOT / "ledgix" / "page" / "ledgix_tax_center" / "ledgix_tax_center.js")
        for token in (
            "ledgix_saas.api.fbr_offline.get_offline_queue",
            "ledgix_saas.api.fbr_offline.declare_known_offline",
            "ledgix_saas.api.fbr_offline.upload_offline_invoice",
            "DECLARE KNOWN OFFLINE",
            "UPLOAD OFFLINE INVOICE",
            "Known Offline operations",
        ):
            self.assertIn(token, source)

    def test_authoritative_di_logo_path(self):
        schema = json.loads(self.text(APP_ROOT / "ledgix" / "doctype" / "ledgix_fbr_integration_profile" / "ledgix_fbr_integration_profile.json"))
        fields = {r.get("fieldname"): r for r in schema.get("fields") or [] if r.get("fieldname")}
        self.assertEqual(fields["digital_invoicing_logo"]["fieldtype"], "Attach Image")
        self.assertIn("authoritative FBR Digital Invoicing System logo", fields["digital_invoicing_logo"]["description"])

        printing = self.text(APP_ROOT / "api" / "printing.py")
        self.assertIn('["name", "software_registration_number", "digital_invoicing_logo"]', printing)
        self.assertIn("row.digital_invoicing_logo", printing)

    def test_production_blocks_missing_logo(self):
        activation = self.text(APP_ROOT / "api" / "fbr_activation.py")
        self.assertIn('"digital_invoicing_logo_configured"', activation)
        self.assertIn('_check("digital_invoicing_logo_configured"', activation)
        self.assertIn('category="Print compliance"', activation)

    def test_optional_profile_none_values_are_not_configured(self):
        activation = self.text(APP_ROOT / "api" / "fbr_activation.py")
        self.assertIn("def _configured(value) -> bool:", activation)
        self.assertIn('return bool(str(value or "").strip())', activation)
        self.assertIn(
            '"software_registration_number_configured": _configured(',
            activation,
        )
        self.assertIn(
            '"digital_invoicing_logo_configured": _configured(',
            activation,
        )

    def test_return_note_still_fail_closed(self):
        self.assertIn(
            "return payload is not activated until Debit/Credit Note semantics",
            self.text(APP_ROOT / "services" / "fbr_v2_payload_builder.py"),
        )

    def test_docs_current(self):
        plan = self.text(REPO_ROOT / "docs" / "fbr" / "FBR_ERPNext_NATIVE_REDESIGN_PLAN.md")
        runbook = self.text(REPO_ROOT / "docs" / "production" / "fbr_sandbox_production_activation.md")
        self.assertIn("READY FOR CLIENT CERTIFICATION", plan)
        self.assertNotIn("LEGACY FBR RETIREMENT IN PROGRESS", plan)
        self.assertNotIn("true offline issuance/upload is not implemented", plan)
        self.assertNotIn("### 4.10 Return payload is currently hardcoded as Credit Note", plan)
        self.assertNotIn("Ledgix FBR Settings", runbook)

    def test_handoff_assets_exist(self):
        for rel in (
            "docs/fbr/FBR_PHASE7_KNOWN_OFFLINE_LIFECYCLE.md",
            "docs/fbr/FBR_PHASE8_PRINT_CORRECTION_FOUNDATION.md",
            "docs/fbr/FBR_CLIENT_CERTIFICATION_HANDOFF.md",
            "scripts/run_fbr_client_certification_handoff_gate.sh",
        ):
            self.assertTrue((REPO_ROOT / rel).exists(), rel)

    def test_handoff_gate_read_only_labels(self):
        gate = self.text(REPO_ROOT / "scripts" / "run_fbr_client_certification_handoff_gate.sh")
        for token in (
            "software_ready_for_client_certification=true",
            "sandbox_certified=false",
            "production_ready=false",
            "fbr_client_certification_handoff_gate_complete=true",
        ):
            self.assertIn(token, gate)
        for forbidden in (
            "production_post_armed = 1",
            "frappe.db.commit",
            "get_decrypted_password",
        ):
            self.assertNotIn(forbidden, gate)


if __name__ == "__main__":
    unittest.main()
