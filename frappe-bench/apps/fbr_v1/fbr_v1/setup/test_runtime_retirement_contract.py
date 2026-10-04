"""Current architecture, upgrade history and direct-call safety contracts."""
import ast
import hashlib
import importlib
import json
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row

REPO = Path(__file__).resolve().parents[5]
APPS = REPO / 'frappe-bench/apps'
V1 = APPS / 'fbr_v1/fbr_v1'
LED = APPS / 'ledgix_saas'
V12 = APPS / 'fbr_v12/fbr_v12'
RETIRED = ('business_nature', 'reference_data', 'sandbox_certification', 'sandbox_scenario')


class TestArchitecture(NoNetworkTest):
    def test_no_executable_di_endpoint_or_alternate_http(self):
        for root in (V1, LED, V12):
            for path in root.rglob('*.py'):
                if path.name.startswith('test_'):
                    continue
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        for marker in ('di_data/v1', '/pdi/v', '/dist/v', 'validateinvoicedata', 'postinvoicedata'):
                            self.assertNotIn(marker, node.value, str(path))
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or '']
                        if root != V12:
                            self.assertFalse(any(n.startswith('fbr_v12') for n in names), str(path))
                    if path != V1 / 'protocol/transport.py' and isinstance(node, ast.Call):
                        self.assertFalse(isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == 'requests' and node.func.attr in ('get', 'post', 'request'), str(path))

    def test_tombstone_hooks_and_install_guard(self):
        from fbr_v12 import hooks, retired
        self.assertEqual(hooks.doc_events, {})
        self.assertEqual(hooks.scheduler_events, {})
        self.assertFalse(hasattr(hooks, 'after_migrate'))
        self.assertFalse(hasattr(hooks, 'after_install'))
        self.assertEqual(hooks.before_install, 'fbr_v12.retired.reject')
        with self.assertRaisesRegex(frappe.ValidationError, 'Retired'):
            retired.reject()
        self.assertFalse(list(V12.rglob('*.json')))
        self.assertFalse((REPO / '.github/workflows/fbr-v12-static.yml').exists())

    def test_every_retained_di_function_rejects_without_io(self):
        with patch.object(frappe, 'get_doc', side_effect=AssertionError('document lookup')), \
             patch('frappe.utils.password.get_decrypted_password', side_effect=AssertionError('credential lookup')):
            called = 0
            for path in V12.rglob('*.py'):
                if path.name in ('hooks.py', '__init__.py', 'retired.py'):
                    continue
                funcs = [n.name for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)]
                if not funcs:
                    continue
                module = importlib.import_module('.'.join(path.relative_to(V12.parent).with_suffix('').parts))
                for name in funcs:
                    with self.subTest(path=path, name=name), self.assertRaisesRegex(frappe.ValidationError, 'Retired'):
                        getattr(module, name)('arbitrary', unknown='argument')
                    called += 1
            self.assertGreater(called, 50)
        self.db.assert_not_called()
        self.assertEqual(self.db.mock_calls, [])

    def test_current_deploy_inventory_only_requires_active_apps(self):
        for path in (REPO / 'deploy').rglob('*.sh'):
            self.assertNotRegex(path.read_text(), r'install-app\s+fbr_v12')
        for path in (REPO / 'scripts').rglob('*.sh'):
            if 'archive' not in path.parts:
                self.assertNotRegex(path.read_text(), r'install-app\s+fbr_v12')
        source = (REPO / 'scripts/validation/validate_repo.sh').read_text()
        self.assertIn('custom_app_names = ("ledgix_saas", "fbr_v1")', source)
        self.assertNotIn('"fbr_v12"', source)

    def test_fresh_schema_and_existing_controller_resolution(self):
        for suffix in RETIRED:
            name = 'ledgix_fbr_' + suffix
            folder = V1 / 'fbr_v1/doctype' / name
            self.assertFalse((folder / (name + '.json')).exists())
            module = importlib.import_module(f'fbr_v1.fbr_v1.doctype.{name}.{name}')
            classes = [value for key, value in vars(module).items() if key.startswith('Ledgix') and isinstance(value, type)]
            self.assertEqual(len(classes), 1)
            with self.assertRaisesRegex(frappe.ValidationError, 'read-only'):
                classes[0].validate(Row())
        self.assertTrue((V1 / 'fbr_v1/doctype/ledgix_fbr_correction_request/ledgix_fbr_correction_request.json').exists())
        from fbr_v1.patches.preserve_legacy_profile_evidence import LEGACY_FIELDS
        schema = json.loads((V1 / 'fbr_v1/doctype/ledgix_fbr_integration_profile/ledgix_fbr_integration_profile.json').read_text())
        fields = {f['fieldname']: f for f in schema['fields']}
        self.assertFalse(set(LEGACY_FIELDS).intersection(fields))
        for name in ('v1_sandbox_token', 'v1_production_token'):
            self.assertEqual(fields[name]['fieldtype'], 'Password')

    def test_pinned_frappe_controller_resolvability_prevents_orphan_removal(self):
        from frappe.model import sync
        from fbr_v1.fbr_v1.doctype.ledgix_fbr_reference_data.ledgix_fbr_reference_data import LedgixFBRReferenceData
        with patch.object(frappe, 'get_all', return_value=['Ledgix FBR Reference Data']), \
             patch.object(frappe, 'get_hooks', return_value={}), \
             patch.object(sync, 'clear_controller_cache'), \
             patch.object(sync, 'get_controller', return_value=LedgixFBRReferenceData), \
             patch.object(frappe, 'delete_doc') as delete:
            sync.remove_orphan_doctypes()
            delete.assert_not_called()
        self.db.commit.assert_not_called()

    def test_archival_formats_and_pending_backfills_cannot_fabricate_evidence(self):
        for name in ('ledgix_b2b_invoice', 'ledgix_thermal_receipt'):
            html = json.loads((LED / 'ledgix/print_format' / name / (name + '.json')).read_text())['html']
            self.assertIn('Non-fiscal historical view', html)
            for forbidden in ('Brand Settings', 'get_doc', 'get_fbr_qr_data_uri', 'fbr_invoice_number', 'immutable'):
                self.assertNotIn(forbidden, html)
        for name in ('backfill_sale_seller_snapshots', 'backfill_sale_item_identity_and_sync_receipts'):
            module = importlib.import_module('ledgix_saas.patches.v1_0.' + name)
            with patch('frappe.modules.utils.reload_doc'), patch.object(module, 'reload_doc', create=True):
                module.execute()
            self.assertEqual(self.db.mock_calls, [])
        source = (LED / 'api/printing.py').read_text()
        for forbidden in ('get_brand_settings', 'resolve_invoice_identity', 'erpnext_live', '_v2_profile_public'):
            self.assertNotIn(forbidden, source)
        release = (LED / 'api/release_acceptance.py').read_text()
        self.assertNotIn('sandbox_certification_complete', release)
        self.assertNotIn('fbr_external_certification_complete', release)

    def test_pending_commerce_bootstrap_cannot_reopen_current_native_ledgers(self):
        with patch.object(frappe, 'get_installed_apps', return_value=['frappe','erpnext','ledgix_saas','fbr_v1']):
            for name in ('bootstrap_v2_commerce_contracts','normalize_v2_payment_methods'):
                importlib.import_module('ledgix_saas.patches.v1_0.' + name).execute()
        self.assertEqual(self.db.mock_calls, [])


class TestLegacyTransportAndHistoricalReads(NoNetworkTest):
    def test_direct_generic_transport_and_payload_calls_do_no_io(self):
        from ledgix_saas.api import fbr_transport, fbr_payload
        self.assertFalse(fbr_transport.requests_available())
        with patch.object(frappe, 'get_doc', side_effect=AssertionError('live master lookup')), \
             patch('frappe.utils.password.get_decrypted_password', side_effect=AssertionError('credential retrieval')):
            for method in (fbr_transport.get_json, fbr_transport.post_json, fbr_transport.ensure_requests_available):
                with self.assertRaisesRegex(frappe.ValidationError, 'retired'):
                    method()
            for method in (fbr_payload.build_fbr_seller_block_from_sale, fbr_payload.build_fbr_buyer_block_from_sale):
                with self.assertRaisesRegex(frappe.ValidationError, 'Historical fiscal evidence unavailable'):
                    method(Row())
        self.assertEqual(self.db.mock_calls, [])

    def test_verified_history_reads_and_missing_or_incomplete_evidence_blocks(self):
        from ledgix_saas.api import printing
        doc = Row(doctype='Sales Invoice', name='OLD', custom_ledgix_fbr_v2_snapshot_version=0)
        with patch.object(printing.historical_fbr_evidence, 'read_persisted_v2_snapshot') as reader:
            with self.assertRaisesRegex(frappe.ValidationError, 'unavailable'):
                printing._identity_for_print(doc)
            reader.assert_not_called()
            doc.custom_ledgix_fbr_v2_snapshot_version = printing.historical_fbr_evidence.SNAPSHOT_VERSION
            reader.return_value = dict(header=dict(identity=dict(seller=dict(business_name='Past seller', ntn_cnic='Past NTN', province='Past province', address='Past address'), buyer=dict(business_name='Past buyer'))), snapshot_hash='verified-hash')
            identity, source, digest = printing._identity_for_print(doc)
            self.assertEqual(identity['seller']['business_name'], 'Past seller')
            self.assertEqual(source, 'persisted_v2')
            self.assertEqual(digest, 'verified-hash')
            reader.return_value['header']['identity']['seller']['address'] = ''
            with self.assertRaisesRegex(frappe.ValidationError, 'incomplete'):
                printing._identity_for_print(doc)
        self.assertEqual(printing.get_fbr_qr_data_uri('unverified-number'), '')
        self.assertEqual(self.db.mock_calls, [])

    def test_current_v1_native_print_delegation(self):
        from ledgix_saas.api import printing
        doc = Row(doctype='POS Invoice', name='CURRENT', custom_ledgix_fbr_snapshot_protocol='Federal POS/IMS V1', custom_ledgix_fbr_invoice_number='RETURNED')
        with patch.object(frappe, 'get_doc', return_value=doc), \
             patch('fbr_v1.api.printing.get_native_invoice_print_context', return_value={'current': True}) as current:
            self.assertEqual(printing.get_native_invoice_print_context(doc.doctype, doc.name), {'current': True})
            current.assert_called_once_with(doc.doctype, doc.name)


class TestUpgradeEvidence(NoNetworkTest):
    def test_capture_hashes_exact_values_children_ciphertext_and_is_idempotent(self):
        from fbr_v1.patches import preserve_legacy_profile_evidence as migration
        profile = Row(name='PROFILE', company='Shop', sector='Original', sandbox_token='***', business_natures=[Row(business_nature='Past')])
        self.db.exists.return_value = True
        self.db.get_value.return_value = None
        self.db.sql.return_value = [Row(fieldname='sandbox_token', password='encrypted-placeholder', encrypted=1)]
        inserted = []
        evidence = Row(flags=Row(), insert=lambda **kwargs: inserted.append(True))
        def get_doc(*args):
            if isinstance(args[0], dict):
                evidence.update(args[0]); return evidence
            return profile
        with patch.object(frappe, 'get_meta', return_value=Mock(has_field=lambda f: f in ('sector','business_natures','sandbox_token'))), \
             patch.object(frappe, 'reload_doc') as reload, \
             patch.object(frappe, 'get_all', return_value=[Row(name='PROFILE', company='Shop')]), \
             patch.object(frappe, 'get_doc', side_effect=get_doc), \
             patch('frappe.utils.password.get_decrypted_password', side_effect=AssertionError('plaintext forbidden')) as decrypt:
            migration.execute()
            reload.assert_called_once()
            self.assertEqual(inserted, [True])
            payload = json.loads(evidence.payload_json)
            self.assertEqual(payload['sector'], 'Original')
            self.assertEqual(payload['business_natures'], [{'business_nature': 'Past'}])
            self.assertEqual(payload['encrypted_credential_storage'][0]['password'], 'encrypted-placeholder')
            self.assertEqual(evidence.payload_hash, hashlib.sha256(evidence.payload_json.encode()).hexdigest())
            self.db.get_value.return_value = evidence.payload_hash
            migration.execute()
            self.assertEqual(inserted, [True])
            decrypt.assert_not_called()
        self.db.set_value.assert_not_called()

    def test_fresh_install_patch_is_noop_and_precedes_sync(self):
        from fbr_v1.patches import preserve_legacy_profile_evidence as migration
        self.db.exists.return_value = False
        with patch.object(frappe, 'reload_doc') as reload:
            migration.execute(); reload.assert_not_called()
        patches = (V1 / 'patches.txt').read_text()
        self.assertLess(patches.index('preserve_legacy_profile_evidence'), patches.index('[post_model_sync]'))

    def test_evidence_permissions_and_immutability(self):
        schema = json.loads((V1 / 'fbr_v1/doctype/ledgix_fbr_legacy_evidence/ledgix_fbr_legacy_evidence.json').read_text())
        for permission in schema['permissions']:
            self.assertTrue(permission['read'])
            self.assertFalse(any(permission.get(f) for f in ('create','write','delete','export')))
        payload = next(f for f in schema['fields'] if f['fieldname'] == 'payload_json')
        self.assertEqual(payload['permlevel'], 1)
        from fbr_v1.fbr_v1.doctype.ledgix_fbr_legacy_evidence.ledgix_fbr_legacy_evidence import LedgixFBRLegacyEvidence
        with self.assertRaisesRegex(frappe.ValidationError, 'read-only'):
            doc = object.__new__(LedgixFBRLegacyEvidence)
            doc.is_new = lambda: False
            doc.flags = Row()
            doc.validate()

    def test_payload_is_never_serialized_even_for_privileged_document_api(self):
        from fbr_v1.fbr_v1.doctype.ledgix_fbr_legacy_evidence.ledgix_fbr_legacy_evidence import LedgixFBRLegacyEvidence
        from frappe.model.document import Document
        doc = object.__new__(LedgixFBRLegacyEvidence)
        with patch.object(Document, 'as_dict', return_value={'payload_json': 'private-preservation', 'payload_hash': 'digest'}):
            self.assertEqual(doc.as_dict(), {'payload_hash': 'digest'})


class TestArmAndApproval(NoNetworkTest):
    def profile(self, old=None, **changes):
        return Row(protocol_version='Federal POS/IMS V1', mode='Production', enabled=1,
            transport_enabled=1, production_post_armed=1, provider_type='PRAL',
            pos_service_fee_account='Fee', submit_trigger='On Submit', block_print_without_fiscal_result=1,
            offline_policy='Disabled', get_doc_before_save=lambda: old, **changes)

    def test_arm_transition_is_server_role_protected_and_disarm_allowed(self):
        from fbr_v1.fbr_v1.doctype.ledgix_fbr_integration_profile.ledgix_fbr_integration_profile import LedgixFBRIntegrationProfile as C
        for role in ('Accounts Manager','Ledgix Admin'):
            with patch.object(frappe, 'get_roles', return_value=[role]):
                with self.assertRaises(frappe.PermissionError):
                    C.validate(self.profile(Row(production_post_armed=0)))
                doc = self.profile(Row(production_post_armed=1)); doc.production_post_armed=0
                C.validate(doc)
        with patch.object(frappe, 'get_roles', return_value=['System Manager']):
            C.validate(self.profile(Row(production_post_armed=0)))
            doc = self.profile(); doc.submit_trigger='Manual'
            with self.assertRaisesRegex(frappe.ValidationError, 'On Submit'):
                C.validate(doc)

    def test_external_approval_needs_reference_file_and_server_stamped_operator(self):
        from fbr_v1.services import production_approval as approval
        doc = Row(production_approval_status='Verified', production_approval_reference='External letter', production_approval_evidence='/private/files/approval.pdf', production_approval_verified_at='forged', production_approval_verified_by='forged')
        self.db.get_value.return_value = 'FILE'
        with patch.object(frappe, 'get_doc', return_value=Row()), patch.object(frappe, 'get_roles', return_value=['Accounts Manager']):
            with self.assertRaises(frappe.PermissionError):
                approval.validate_approval(doc, None)
        with patch.object(frappe, 'get_doc', return_value=Row()), patch.object(frappe, 'get_roles', return_value=['System Manager']):
            approval.validate_approval(doc, None)
            self.assertEqual(doc.production_approval_verified_by, 'test@example.invalid')
            self.assertNotEqual(doc.production_approval_verified_at, 'forged')
            self.assertTrue(approval.approval_complete(doc))
            doc.production_approval_reference=''
            with self.assertRaises(frappe.ValidationError):
                approval.validate_approval(doc, None)
        self.db.get_value.return_value = None
        self.assertFalse(approval.approval_complete(doc))


class TestItemScope(NoNetworkTest):
    def test_retail_b2b_new_sales_reject_disabled_non_sales_templates(self):
        from ledgix_saas.services import erpnext_selling as selling
        self.db.exists.return_value = True
        for changes in ({'disabled':1},{'is_sales_item':0},{'has_variants':1}):
            item = Row(disabled=0, is_sales_item=1, has_variants=0); item.update(changes)
            self.db.get_value.return_value = item
            with self.assertRaisesRegex(frappe.ValidationError, 'New sales require'):
                selling._resolve_item('SKU')
            self.assertEqual(selling._resolve_item('SKU', new_sale=False), 'SKU')
        for variant in ('', 'TEMPLATE'):
            self.db.get_value.return_value = Row(disabled=0, is_sales_item=1, has_variants=0, variant_of=variant)
            self.assertEqual(selling._resolve_item('SKU'), 'SKU')

    def test_reachable_retail_and_b2b_builders_reject_out_of_scope_items(self):
        from ledgix_saas.services import erpnext_selling as selling, erpnext_pos as pos
        self.db.exists.return_value = True
        self.stack.enter_context(patch.object(selling.erpnext_phase6_extensions, 'sync_all'))
        self.stack.enter_context(patch.object(pos.erpnext_phase8_extensions, 'sync_all'))
        for module, name, value in ((selling,'_company','Shop'), (selling,'_resolve_customer','Customer'),
                (selling,'_resolve_price_list','Selling'), (pos,'_company','Shop'),
                (pos,'profile_for_user',Row(name='Profile')), (pos,'_profile_customer','Customer'),
                (pos,'_price_list','Selling'), (pos,'_profile_warehouse','Warehouse')):
            self.stack.enter_context(patch.object(module, name, return_value=value))
        with patch.object(selling, '_native_item_rate', side_effect=AssertionError('Pricing must follow scope check')):
            for flags in ({'disabled':1}, {'is_sales_item':0}, {'has_variants':1}):
                item = Row(disabled=0, is_sales_item=1, has_variants=0); item.update(flags)
                self.db.get_value.return_value = item
                with self.subTest(surface='B2B', flags=flags), self.assertRaisesRegex(frappe.ValidationError, 'New sales require'):
                    selling.build_sales_invoice(customer='Customer', items=[{'item_code':'SKU','qty':1}])
                with self.subTest(surface='Retail', flags=flags), self.assertRaisesRegex(frappe.ValidationError, 'New sales require'):
                    pos.build_pos_invoice(cart_items=[{'item_code':'SKU','qty':1}])

    def test_native_return_remains_source_bound_for_now_disabled_item(self):
        from ledgix_saas.services import erpnext_selling as selling
        self.db.exists.return_value = True
        self.db.get_value.return_value = Row(disabled=1, is_sales_item=0, has_variants=0)
        self.stack.enter_context(patch.object(selling, '_', side_effect=lambda message: message))
        source = SimpleNamespace(items=[Row(name='SOURCE-ROW', item_code='SKU', qty=2)])
        self.assertEqual(selling._return_request_map(source, [{'item_code':'SKU','qty':1}]),
            {'SOURCE-ROW':{'item_code':'SKU','qty':1}})
        with self.assertRaises(frappe.ValidationError):
            selling._return_request_map(source, [{'item_code':'FOREIGN','qty':1}])
        with self.assertRaises(frappe.ValidationError):
            selling._return_request_map(source, [{'item_code':'SKU','qty':3}])

    def test_direct_commerce_compatibility_uses_native_services(self):
        from ledgix_saas.api import v2_pos, v2_returns, pos_compat
        for module,name in ((v2_pos,'preview_pos_v2_checkout'),(v2_pos,'complete_pos_v2_sale'),(v2_returns,'create_pos_v2_return')):
            with patch.object(pos_compat, name, return_value={'native':True}) as native:
                self.assertEqual(getattr(module,name)(cart_items=[]), {'native':True})
                native.assert_called_once_with(cart_items=[])
