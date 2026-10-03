import ast
import json
from pathlib import Path
from unittest.mock import patch, Mock

import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest
from ledgix_saas.services import fbr_v1_bridge as bridge

ROOT = Path(__file__).resolve().parents[1]
FBR = ROOT.parent / 'fbr_v1' / 'fbr_v1'


class TestFederalV1Bridge(NoNetworkTest):
    def test_missing_extension_fails_closed(self):
        with patch.object(frappe, 'get_installed_apps', return_value=['frappe', 'erpnext', 'ledgix_saas']), patch.object(frappe, 'get_attr') as lookup:
            for call in (bridge.get_company_readiness, bridge.get_company_seller_identity):
                state = call('Shop')
                self.assertFalse(state['ready'])
                self.assertIn('Federal FBR V1 app is required', state['blockers'][0])
            bridge.stamp_taxable_base_inputs(object())
            lookup.assert_not_called()
        self.db.set_value.assert_not_called()

    def test_installed_extension_uses_runtime_lookup(self):
        target = Mock(return_value={'ready': True})
        with patch.object(frappe, 'get_installed_apps', return_value=['fbr_v1']), patch.object(frappe, 'get_attr', return_value=target) as lookup:
            for function, path in (
                (bridge.get_company_readiness, 'fbr_v1.api.client_readiness.get_client_readiness'),
                (bridge.get_company_seller_identity, 'fbr_v1.services.erpnext_fbr_identity.resolve_company_seller_identity'),
                (bridge.stamp_taxable_base_inputs, 'fbr_v1.services.erpnext_taxable_base.stamp_fbr_taxable_base_inputs'),
            ):
                self.assertEqual(function('Shop'), {'ready': True})
                lookup.assert_called_with(path)
                target.assert_called_with('Shop')
        self.db.set_value.assert_not_called()

    def test_delegate_failures_are_not_hidden(self):
        with patch.object(frappe, 'get_installed_apps', return_value=['fbr_v1']), patch.object(frappe, 'get_attr', side_effect=RuntimeError('broken extension')):
            with self.assertRaises(RuntimeError):
                bridge.get_company_readiness('Shop')

    def test_bridge_has_no_import_time_fbr_dependency(self):
        tree = ast.parse((ROOT / 'services/fbr_v1_bridge.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or '').startswith('fbr_v1'))
            if isinstance(node, ast.Import):
                self.assertFalse(any(a.name.startswith('fbr_v1') for a in node.names))

    def test_current_transaction_and_setup_paths_cannot_route_through_v2(self):
        for path in ('api/client_setup.py', 'api/client_readiness.py', 'api/pos_compat.py',
                     'api/selling.py', 'api/selling_compat.py', 'services/erpnext_tax_authority.py', 'api/tax_center.py'):
            source = (ROOT / path).read_text()
            for forbidden in ('fbr_v2_readiness', 'fbr_v2_payload_builder', 'fbr_v2_snapshot_persistence', 'fbr_v2_center'):
                self.assertNotIn(forbidden, source, path)
        for path in ('api/client_setup.py', 'api/client_readiness.py'):
            source = (ROOT / path).read_text()
            self.assertIn('fbr_v1_bridge', source)
            self.assertNotIn('V2', source)
            self.assertNotIn('official reference evidence', source)

    def test_third_schedule_has_one_browser_and_server_owner(self):
        hooks = (FBR / 'hooks.py').read_text()
        self.assertIn('erpnext_taxable_base_resolvers', hooks)
        self.assertIn('fbr_v1_taxable_base.js', hooks)
        self.assertNotIn('ledgix_taxable_base.js', (ROOT / 'hooks.py').read_text())
        self.assertFalse((ROOT / 'public/js/ledgix_taxable_base.js').exists())
        self.assertIn('notified * flt(item.qty)', (FBR / 'public/js/fbr_v1_taxable_base.js').read_text())
        self.assertNotIn('notified_value *', (ROOT / 'services/erpnext_taxable_base.py').read_text())
        self.assertNotIn('erpnext_tax_foundation.after_migrate', (ROOT / 'hooks.py').read_text())

    def test_legacy_fields_are_retained_hidden_read_only(self):
        schema = json.loads((FBR / 'fbr_v1/doctype/ledgix_fbr_item_mapping/ledgix_fbr_item_mapping.json').read_text())
        fields = {row['fieldname']: row for row in schema['fields']}
        for name in ('fbr_uom', 'sales_type', 'fbr_rate_description', 'sro_schedule_number', 'sro_item_serial_number', 'reference_version'):
            self.assertTrue(fields[name]['hidden'])
            self.assertTrue(fields[name]['read_only'])
        source = (FBR / 'services/erpnext_fbr_snapshot.py').read_text()
        query = source[source.index('def _matching_item_mapping'):source.index('def _reconcile_mapped_tax_rows')]
        for name in ('fbr_uom', 'sales_type', 'fbr_rate_description', 'sro_schedule_number', 'reference_version'):
            self.assertNotIn(name, query)

    def test_schema_ownership_is_federal_v1(self):
        source = (ROOT / 'setup/erpnext_extensions.py').read_text()
        self.assertIn('"fbr_schema_owner": "fbr_v1"', source)
        self.assertNotIn('fbr_v12', source)
        self.assertNotIn('CUSTOMER_FBR_FIELDS', source)

    def test_missing_company_is_reported_without_extension_lookup(self):
        with patch.object(frappe, 'get_installed_apps', return_value=['fbr_v1']), patch.object(frappe, 'get_attr') as lookup:
            self.assertFalse(bridge.get_company_readiness('')['setup_ready'])
            self.assertFalse(bridge.get_company_seller_identity('')['ready'])
            lookup.assert_not_called()

    def test_historical_whitelisted_surfaces_reject_before_any_work(self):
        for path in ('api/fbr_v2_center.py', 'api/fbr_reference_v2.py'):
            tree = ast.parse((ROOT / path).read_text())
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == 'whitelist' for d in node.decorator_list):
                    body = node.body
                    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                        body = body[1:]
                    first = body[0]
                    self.assertIsInstance(first, ast.Expr)
                    self.assertEqual(ast.unparse(first.value.func), 'frappe.throw')
                    self.assertIn('retired', first.value.args[0].value)
        source = (ROOT / 'api/legacy_tax_guard.py').read_text()
        self.assertNotIn('FBR V2', source)
