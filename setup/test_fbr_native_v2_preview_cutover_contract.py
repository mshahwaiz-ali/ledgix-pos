from __future__ import annotations

from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
NATIVE = APP / "api" / "fbr_native.py"


def _function_block(source: str, function_name: str, next_marker: str) -> str:
    start = source.index(f"def {function_name}(")
    end = source.index(next_marker, start)
    return source[start:end]


class TestFBRNativeV2PreviewCutoverContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = NATIVE.read_text(encoding="utf-8")

    def test_native_imports_canonical_v2_services(self):
        self.assertIn(
            "from ledgix_saas.services import fbr_v2_payload_builder, fbr_v2_readiness",
            self.native,
        )

    def test_readiness_delegates_to_v2_service(self):
        block = _function_block(
            self.native,
            "validate_native_readiness_internal",
            "\ndef build_native_payload_internal",
        )
        self.assertIn("fbr_v2_readiness.evaluate_invoice_readiness(", block)
        for forbidden in (
            "get_fbr_settings_internal(",
            "get_fbr_control_state_internal(",
            "fbr_payload.",
            "custom_ledgix_fbr_snapshot_version",
            "custom_ledgix_fbr_snapshot_json",
            "_tax_rows(",
        ):
            self.assertNotIn(forbidden, block)

    def test_preview_delegates_to_canonical_builder_only(self):
        block = _function_block(
            self.native,
            "build_native_payload_internal",
            "\n@frappe.whitelist()\ndef build_native_invoice_payload",
        )
        self.assertIn("fbr_v2_payload_builder.build_payload_candidate(", block)
        for forbidden in (
            "get_fbr_settings_internal(",
            "get_fbr_control_state_internal(",
            "fbr_payload.",
            "_seller_block(",
            "_buyer_block(",
            "_tax_rows(",
            "scenarioId",
            "custom_ledgix_fbr_snapshot",
        ):
            self.assertNotIn(forbidden, block)

    def test_invalid_preview_never_builds_partial_payload(self):
        block = _function_block(
            self.native,
            "build_native_payload_internal",
            "\n@frappe.whitelist()\ndef build_native_invoice_payload",
        )
        self.assertIn('if not validation.get("valid"):', block)
        self.assertIn('"payload": None', block)

    def test_network_cutover_is_hard_disabled(self):
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE = False", self.native)
        self.assertIn("V2_NETWORK_CUTOVER_MESSAGE", self.native)

    def test_validate_is_blocked_before_v2_transport(self):
        block = _function_block(
            self.native,
            "validate_native_with_fbr_internal",
            "\n@frappe.whitelist()\ndef validate_native_with_fbr",
        )
        guard = block.index("if not V2_NETWORK_CUTOVER_ACTIVE:")
        transport = block.index("fbr_v2_transport.validate_invoice(")
        self.assertLess(guard, transport)

    def test_submit_is_blocked_before_v2_transport(self):
        block = _function_block(
            self.native,
            "submit_native_to_fbr_internal",
            "\n@frappe.whitelist()\ndef submit_native_to_fbr",
        )
        guard = block.index("if not V2_NETWORK_CUTOVER_ACTIVE:")
        transport = block.index("fbr_v2_transport.post_invoice(")
        self.assertLess(guard, transport)
        self.assertIn('client_result.get("requires_reconciliation")', block)

    def test_submit_hook_queue_is_blocked_before_v2_queue_policy(self):
        block = _function_block(
            self.native,
            "queue_native_for_fbr",
            "\ndef on_native_invoice_submit",
        )
        guard = block.index("if not V2_NETWORK_CUTOVER_ACTIVE:")
        validation = block.index("validate_native_readiness_internal(", guard)
        self.assertLess(guard, validation)
        self.assertIn('"queued": False', block)
        self.assertIn('"status": "Not Ready"', block)

    def test_preview_source_identifies_v2_builder(self):
        block = _function_block(
            self.native,
            "build_native_payload_internal",
            "\n@frappe.whitelist()\ndef build_native_invoice_payload",
        )
        self.assertIn('"payload_builder": "FBR V2"', block)
        self.assertIn('"authority": "ERPNext Native"', block)


    def test_native_has_no_old_global_network_dependency(self):
        for forbidden in (
            "from ledgix_saas.api import fbr_client",
            "get_fbr_settings_internal",
            "get_fbr_control_state_internal",
            "fbr_client.validate_invoice(",
            "fbr_client.post_invoice(",
        ):
            self.assertNotIn(forbidden, self.native)

        self.assertIn("fbr_v2_transport.validate_invoice(", self.native)
        self.assertIn("fbr_v2_transport.post_invoice(", self.native)
        self.assertIn(
            'settings = validation.get("settings") or {}',
            self.native,
        )

if __name__ == "__main__":
    unittest.main()
