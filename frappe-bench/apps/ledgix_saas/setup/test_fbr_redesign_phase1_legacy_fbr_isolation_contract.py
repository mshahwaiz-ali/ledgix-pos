from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPhase1LegacyFBRIsolationContract(unittest.TestCase):
    def test_legacy_rpc_surfaces_fail_closed(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        target = "ledgix_saas.api.fbr_legacy_guard.reject_legacy_fbr_action"
        retired = (
            "ledgix_saas.api.fbr_preview.get_fbr_sale_preview",
            "ledgix_saas.api.fbr_payload.validate_sale_fbr_readiness",
            "ledgix_saas.api.fbr_payload.build_sale_invoice_payload",
            "ledgix_saas.api.fbr_payload.build_return_invoice_payload",
            "ledgix_saas.api.fbr_submission.dry_run_sale_fbr_payload",
            "ledgix_saas.api.fbr_submission.validate_sale_with_fbr",
            "ledgix_saas.api.fbr_submission.validate_sale_with_fbr_production",
            "ledgix_saas.api.fbr_submission.release_sale_after_fbr_reconciliation",
            "ledgix_saas.api.fbr_submission.submit_return_to_fbr",
            "ledgix_saas.api.fbr_submission.release_return_after_fbr_reconciliation",
        )
        for method in retired:
            self.assertIn(f'"{method}": "{target}"', hooks)
        self.assertIn(
            '"ledgix_saas.api.fbr_submission.submit_sale_to_fbr": "ledgix_saas.api.fbr_legacy_guard.reject_legacy_sale_submission"',
            hooks,
        )

    def test_legacy_controllers_cannot_auto_queue_fbr(self):
        sale = (APP_ROOT / "ledgix" / "doctype" / "ledgix_sale" / "ledgix_sale.py").read_text(encoding="utf-8")
        sales_return = (APP_ROOT / "ledgix" / "doctype" / "ledgix_sales_return" / "ledgix_sales_return.py").read_text(encoding="utf-8")
        self.assertNotIn("queue_sale_for_fbr", sale)
        self.assertNotIn("_validate_sale_fbr_readiness_internal", sale)
        self.assertNotIn("queue_return_for_fbr", sales_return)
        self.assertIn("Legacy Sale FBR issuance is retired", sale)
        self.assertIn("Legacy Sales Return FBR issuance is retired", sales_return)

    def test_native_shared_helpers_are_preserved(self):
        native = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        submission = (APP_ROOT / "api" / "fbr_submission.py").read_text(encoding="utf-8")
        for helper in ("create_submission_log", "_submission_lock", "parse_fbr_response"):
            self.assertIn(helper, native)
            self.assertIn(f"def {helper}", submission)
        self.assertIn("scheduler_events = {}", (APP_ROOT / "hooks.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
