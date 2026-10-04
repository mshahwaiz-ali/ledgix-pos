from __future__ import annotations

from pathlib import Path
import unittest
import ast
import importlib
from unittest.mock import patch

import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest
from ledgix_saas.api.fbr_legacy_guard import LEGACY_V2_RETIRED_MESSAGE

APP = Path(__file__).resolve().parents[1]
NATIVE = (APP / "api" / "fbr_native.py").read_text(encoding="utf-8")
SUPPORT = (APP / "services" / "fbr_submission_support.py").read_text(encoding="utf-8")
GATE = (APP / "migration" / "fbr_native_legacy_dependency_retirement_gate.py").read_text(encoding="utf-8")


class TestFBRNativeLegacyDependencyRetirementContract(unittest.TestCase):
    def test_native_no_longer_imports_legacy_payload_or_submission_modules(self):
        for forbidden in (
            "from ledgix_saas.api import fbr_payload",
            "ledgix_saas.api.fbr_submission",
            "fbr_payload.",
        ):
            self.assertNotIn(forbidden, NATIVE)

    def test_native_dead_legacy_payload_helper_chain_is_removed(self):
        for forbidden in (
            "def _seller_block(", "def _buyer_block(", "def _line_snapshot(",
            "def _tax_rows(", "def _original_for_return(",
        ):
            self.assertNotIn(forbidden, NATIVE)

    def test_native_has_no_transport_or_submission_support_imports(self):
        for forbidden in ('fbr_v2_transport', 'fbr_v2_payload_builder', 'fbr_v2_readiness',
                          'fbr_submission_support', 'frappe.db', 'enqueue', 'requests'):
            self.assertNotIn(forbidden, NATIVE)
        self.assertIn('reject_legacy_v2_action', NATIVE)

    def test_support_is_transport_settings_and_payload_agnostic(self):
        for forbidden in (
            "fbr_client", "fbr_settings", "fbr_payload", "fbr_submission",
            "requests.", "get_fbr_settings_internal", "get_active_fbr_token",
            "fbr_v2_transport",
        ):
            self.assertNotIn(forbidden, SUPPORT)

    def test_support_only_contains_neutral_primitives(self):
        for required in (
            "def parse_fbr_response(", "def resolve_submission_status(",
            "def create_submission_log(", "class _SubmissionLock:",
            "def submission_lock(", 'frappe.new_doc("Ledgix FBR Submission Log")',
        ):
            self.assertIn(required, SUPPORT)

    def test_gate_compares_neutral_parser_and_resolver_to_legacy_behavior(self):
        self.assertIn("support.parse_fbr_response", GATE)
        self.assertIn("legacy.parse_fbr_response", GATE)
        self.assertIn("support.resolve_submission_status", GATE)
        self.assertIn("legacy._resolve_submission_status", GATE)

    def test_gate_exercises_log_and_lock_without_network(self):
        self.assertIn("support.create_submission_log(", GATE)
        self.assertIn("with support.submission_lock(", GATE)
        self.assertIn('"real_fbr_network_calls": 0', GATE)
        self.assertNotIn("requests.", GATE)

    def test_gate_is_rollback_safe_and_cutover_stays_false(self):
        self.assertIn("frappe.db.rollback()", GATE)
        self.assertIn("frappe.db.commit = _no_commit", GATE)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE", GATE)
        self.assertIn('"rollback_clean"', GATE)


class TestRetiredV2Endpoints(NoNetworkTest):
    def test_every_compatibility_function_rejects_before_db_or_transport(self):
        count = 0
        for name in ('fbr_activation', 'fbr_client', 'fbr_health', 'fbr_native', 'fbr_native_ui', 'fbr_offline', 'fbr_preflight'):
            source = (APP / 'api' / (name + '.py')).read_text()
            tree = ast.parse(source)
            module = importlib.import_module('ledgix_saas.api.' + name)
            imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
            self.assertEqual(len(imports), 2)
            self.assertEqual(imports[0], 'import frappe')
            self.assertIn('fbr_legacy_guard', imports[1])
            with patch.object(frappe, 'get_doc', side_effect=AssertionError('Document mutation forbidden')), \
                 patch.object(frappe, 'get_all', side_effect=AssertionError('DB work forbidden')):
                for node in tree.body:
                    if isinstance(node, ast.FunctionDef):
                        with self.subTest(module=name, endpoint=node.name):
                            with self.assertRaisesRegex(frappe.ValidationError, 'Historical Digital Invoicing') as error:
                                getattr(module, node.name)('ignored', arbitrary='input')
                            self.assertEqual(str(error.exception), LEGACY_V2_RETIRED_MESSAGE)
                            count += 1
            for method in ('set_value', 'sql', 'commit', 'insert'):
                getattr(self.db, method).assert_not_called()
        self.assertEqual(count, 34)

    def test_current_release_acceptance_uses_v1_bridge(self):
        source = (APP / 'api/release_acceptance.py').read_text()
        self.assertNotIn('fbr_activation', source)
        self.assertIn('fbr_v1_bridge.get_company_readiness', source)
        self.assertIn('sandbox_transport_acceptance_complete', source)

    def test_current_desk_bindings_do_not_load_retired_apis(self):
        hooks = (APP / 'hooks.py').read_text()
        for name in ('fbr_activation', 'fbr_client', 'fbr_health', 'fbr_native', 'fbr_native_ui', 'fbr_offline', 'fbr_preflight'):
            self.assertNotIn('ledgix_saas.api.' + name + '.', hooks)
        self.assertNotIn('ledgix_fbr_native_center.js', hooks)


if __name__ == "__main__":
    unittest.main()
