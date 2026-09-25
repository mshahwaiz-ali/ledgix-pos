from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

class TestFBRPhase8PrintCorrectionContract(unittest.TestCase):
    def _text(self, relative: str) -> str:
        return (APP_ROOT / relative).read_text(encoding="utf-8")

    def test_active_printing_uses_neutral_return_label(self):
        printing = self._text("api/printing.py")
        tax_format = self._text("ledgix/print_format/ledgix_erpnext_tax_invoice/ledgix_erpnext_tax_invoice.json")
        pos_format = self._text("ledgix/print_format/ledgix_erpnext_pos_receipt/ledgix_erpnext_pos_receipt.json")
        self.assertIn('"RETURN / ADJUSTMENT" if is_return', printing)
        self.assertNotIn('"CREDIT NOTE" if is_return', printing)
        self.assertNotIn("POS RETURN / CREDIT NOTE", pos_format)
        self.assertNotIn("Credit Total", tax_format)
        self.assertIn("Return Total", tax_format)
        self.assertIn("{{ p.title }}", pos_format)

    def test_return_network_payload_remains_fail_closed(self):
        builder = self._text("services/fbr_v2_payload_builder.py")
        native = self._text("api/fbr_native.py")
        self.assertIn("return payload is not activated until Debit/Credit Note semantics", builder)
        self.assertIn("return payload is not activated until Debit/Credit Note", native)
        self.assertNotIn('"invoiceType": "Debit Note"', builder)
        self.assertIn('"Return" if cint(doc.get("is_return")) else "Sale Invoice"', native)

    def test_offline_pending_is_printed_without_fabricating_fbr_identity(self):
        printing = self._text("api/printing.py")
        tax_format = self._text("ledgix/print_format/ledgix_erpnext_tax_invoice/ledgix_erpnext_tax_invoice.json")
        pos_format = self._text("ledgix/print_format/ledgix_erpnext_pos_receipt/ledgix_erpnext_pos_receipt.json")
        for field in ("custom_ledgix_fbr_offline_issued_at", "custom_ledgix_fbr_upload_due_at", "custom_ledgix_fbr_offline_reason"):
            self.assertIn(field, printing)
        self.assertIn("FBR OFFLINE PENDING", tax_format)
        self.assertIn("FBR OFFLINE PENDING", pos_format)
        self.assertIn("'Offline Pending'", tax_format)
        self.assertIn("'Offline Pending'", pos_format)
        self.assertIn("get_fbr_qr_data_uri(fbr_invoice_number)", printing)

    def test_pos_print_includes_software_registration_number_when_configured(self):
        pos_format = self._text("ledgix/print_format/ledgix_erpnext_pos_receipt/ledgix_erpnext_pos_receipt.json")
        self.assertIn("software_registration_number", pos_format)
        self.assertIn("Software Reg.", pos_format)

    def test_official_fbr_generation_time_is_persisted_for_accepted_post(self):
        extensions = self._text("setup/erpnext_phase9_extensions.py")
        native = self._text("api/fbr_native.py")
        self.assertIn("custom_ledgix_fbr_generated_at", extensions)
        self.assertIn("fbr_generated_at=None", native)
        self.assertIn('values["custom_ledgix_fbr_generated_at"] = fbr_generated_at', native)
        self.assertIn('parsed.get("dated")', native)
        self.assertIn('status_name == "Submitted" and invoice_number', native)

    def test_correction_completion_requires_external_evidence(self):
        schema = json.loads(self._text("ledgix/doctype/ledgix_fbr_correction_request/ledgix_fbr_correction_request.json"))
        controller = self._text("ledgix/doctype/ledgix_fbr_correction_request/ledgix_fbr_correction_request.py")
        fields = {row.get("fieldname"): row for row in schema.get("fields") or [] if row.get("fieldname")}
        self.assertEqual(fields["external_evidence"]["fieldtype"], "Attach")
        self.assertIn("External Completion Evidence is required", controller)
        self.assertIn("custom_ledgix_fbr_generated_at", controller)
        self.assertNotIn('"generated_at": doc.get("custom_ledgix_fbr_submitted_at")', controller)
        self.assertIn("hours=72", controller)
        self.assertIn("Commissioner Approval Reference is required", controller)

    def test_di_logo_remains_unfabricated_until_authoritative_asset_is_configured(self):
        printing = self._text("api/printing.py")
        self.assertIn('"digital_invoicing_logo": ""', printing)
        self.assertIn("fabricate official artwork", printing)

if __name__ == "__main__":
    unittest.main()
