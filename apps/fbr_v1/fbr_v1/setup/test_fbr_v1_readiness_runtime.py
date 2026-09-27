from unittest.mock import patch, Mock
from contextlib import nullcontext, ExitStack
import json
from pathlib import Path
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row, fixture, rehash
from fbr_v1.services import v1_configuration as configuration
from fbr_v1.services import pos_identity as identity, fbr_v1_readiness as readiness
from fbr_v1.api import fbr_offline as offline
from fbr_v1.services import fiscal_closing as closing
from fbr_v1.api import fiscalization as fiscal
from fbr_v1.fbr_v1.doctype.ledgix_fbr_integration_profile import ledgix_fbr_integration_profile as profile_controller

class TestReadiness(NoNetworkTest):
    def test_device_ambiguity_environment_and_pos_profile(self):
        profile=Row(mode='Sandbox')
        doc=Row(doctype='POS Invoice',company='Test Company',pos_profile='Till')
        device=Row(**fixture()['header']['pos_device'],active=1)
        device.pos_profile='Till'
        with patch.object(frappe,'get_all',return_value=['D1','D2']):
            with self.assertRaisesRegex(frappe.ValidationError,'deterministic'):identity.resolve_device(doc,profile)
        with patch.object(frappe,'get_all',return_value=['DEVICE-1']),patch.object(frappe,'get_doc',return_value=device):
            self.assertEqual(identity.resolve_device(doc,profile)['pos_id'],'123')
            device.environment='Production'
            with self.assertRaisesRegex(frappe.ValidationError,'environment'):identity.resolve_device(doc,profile)

    def test_consolidation_does_not_suppress_native_pos_sales_invoice(self):
        self.db.exists.return_value=False
        self.assertFalse(identity.is_consolidated(Row(doctype='Sales Invoice',name='I',is_pos=1)))
        self.assertTrue(identity.is_consolidated(Row(doctype='Sales Invoice',name='I',is_consolidated=1)))
        self.assertTrue(identity.is_consolidated(Row(doctype='Sales Invoice',name='I',is_consolidated=1,is_return=1)))

    def test_legacy_profile_is_not_active(self):
        self.assertFalse(identity.profile_active(Row(enabled=1,mode='Production',protocol_version='DI API V1.12')))

    def _inspect_configuration(self, mode, profile, compliance, general=True, production=False):
        snapshot = fixture()
        snapshot['header']['pos_device']['environment'] = mode
        if mode == 'Production':
            snapshot['header']['pos_device'].update(
                software_registration_number='SOFTWARE-1', onboarding_reference='ONBOARD-1')
        rehash(snapshot)
        stable_identity = dict(snapshot['header']['pos_device'])
        original_hash = snapshot['snapshot_hash']
        doc = Row(doctype='Sales Invoice', name='INV-1', company='Test Company', docstatus=1)
        with ExitStack() as stack:
            for name, value in [('get_profile', profile), ('is_consolidated', False),
                                ('read_persisted_v1_snapshot', snapshot), ('resolve_device', stable_identity)]:
                stack.enter_context(patch.object(readiness, name, return_value=value))
            current = stack.enter_context(patch.object(readiness, 'get_device_compliance_state', return_value=compliance))
            stack.enter_context(patch.object(readiness.transport, 'network_cutover_active', return_value=general))
            stack.enter_context(patch.object(readiness.transport, 'production_cutover_active', return_value=production))
            loader = stack.enter_context(patch.object(frappe, 'get_doc', side_effect=AssertionError('No full document reload')))
            cloud = stack.enter_context(patch.object(readiness.transport, 'post_cloud'))
            local = stack.enter_context(patch.object(readiness.transport, 'post_local'))
            result = readiness.inspect_invoice(doc)
            current.assert_called_once_with('DEVICE-1', include_production=mode == 'Production')
            loader.assert_not_called()
            cloud.assert_not_called()
            local.assert_not_called()
        self.assertEqual(result['device'], stable_identity)
        self.assertEqual(snapshot['header']['pos_device'], stable_identity)
        self.assertEqual(snapshot['snapshot_hash'], original_hash)
        return result

    def test_readiness_blocks_missing_v1_credentials_and_live_cutover(self):
        profile = Row(company='Test Company', provider_type='PRAL', protocol_version=identity.PROTOCOL,
                      mode='Sandbox', enabled=1, transport_enabled=1)
        profile.get_password = Mock(return_value=None)
        compliance = dict(active=1, operational_state='Operational')
        result = self._inspect_configuration('Sandbox', profile, compliance)
        self.assertTrue(result['ready'])
        self.assertFalse(result['network_ready'])
        self.assertEqual(result['network_blockers'], ['Distinct Sandbox V1 cloud credential is missing or unavailable.'])
        profile.get_password.assert_called_once_with('v1_sandbox_token', raise_exception=False)
        # With only the credential supplied, Sandbox needs no Production authority/QR/signature evidence.
        profile.get_password.return_value = 'fake-sandbox-token'
        self.assertTrue(self._inspect_configuration('Sandbox', profile, compliance)['network_ready'])
        closed = self._inspect_configuration('Sandbox', profile, compliance, general=False)
        self.assertFalse(closed['network_ready'])
        self.assertIn('General V1 network cutover is disabled.', closed['network_blockers'])

    def _production_configuration(self):
        profile = Row(company='Test Company', provider_type='PRAL', protocol_version=identity.PROTOCOL,
                      mode='Production', enabled=1, transport_enabled=1, production_post_armed=1,
                      submit_trigger='On Submit', block_print_without_fiscal_result=1,
                      authority_status='FBR / PRAL Directed', authority_reference='AUTH-1',
                      authority_evidence='/private/files/authority', authority_verified_at='2026-09-01',
                      authority_verified_by='test@example.invalid', activation_reference='ACT-1',
                      activation_evidence='/private/files/activation', retention_policy_reference='RET-1',
                      retention_policy_evidence='/private/files/retention')
        profile.get_password = Mock(return_value='fake-production-token')
        compliance = dict(active=1, operational_state='Operational', onboarding_reference='ONBOARD-1',
                          onboarding_evidence='/private/files/onboarding')
        for prefix in ('qr', 'signature'):
            compliance.update({prefix + '_verification_status': 'Verified',
                prefix + '_verification_reference': prefix + '-proof',
                prefix + '_verification_evidence': '/private/files/' + prefix,
                prefix + '_verified_at': '2026-09-01', prefix + '_verified_by': 'test@example.invalid'})
        self.db.exists.return_value = True
        return profile, compliance

    def test_production_profile_requires_submit_and_print_invariants(self):
        base = dict(protocol_version=identity.PROTOCOL, mode='Production', enabled=1,
                    transport_enabled=1, production_post_armed=1, provider_type='PRAL',
                    offline_policy='Disabled', default_pos_device=None,
                    submit_trigger='On Submit', block_print_without_fiscal_result=1)
        with patch.object(profile_controller, 'stamp_verification'):
            manual = Row(**base); manual.submit_trigger = 'Manual'
            with self.assertRaisesRegex(frappe.ValidationError, 'On Submit'):
                profile_controller.LedgixFBRIntegrationProfile.validate(manual)
            unblocked = Row(**base); unblocked.block_print_without_fiscal_result = 0
            with self.assertRaisesRegex(frappe.ValidationError, 'block printing'):
                profile_controller.LedgixFBRIntegrationProfile.validate(unblocked)
            profile_controller.LedgixFBRIntegrationProfile.validate(Row(**base))

        profile, _ = self._production_configuration()
        profile.submit_trigger = 'Manual'
        blockers = configuration.configuration_blockers(profile, None, 'Production')
        self.assertIn('Production profile must use the On Submit trigger.', blockers)
        profile.submit_trigger = 'On Submit'
        profile.block_print_without_fiscal_result = 0
        blockers = configuration.configuration_blockers(profile, None, 'Production')
        self.assertIn('Production profile must block printing until a fiscal result exists.', blockers)
        profile.block_print_without_fiscal_result = 1
        blockers = configuration.configuration_blockers(profile, None, 'Production')
        self.assertFalse(any('On Submit trigger' in row or 'block printing' in row for row in blockers))

    def test_production_requires_current_authority_retention_qr_and_signature_evidence(self):
        for field, message in [('authority_evidence', 'authority evidence'),
                               ('retention_policy_evidence', 'retention policy evidence'),
                               ('qr_verification_status', 'verified qr'),
                               ('signature_verification_status', 'verified signature')]:
            with self.subTest(field=field):
                profile, compliance = self._production_configuration()
                if field in profile:
                    profile[field] = None
                else:
                    compliance[field] = 'Unverified'
                result = self._inspect_configuration('Production', profile, compliance, production=True)
                self.assertTrue(result['ready'])
                self.assertFalse(result['network_ready'])
                self.assertTrue(any(message in blocker for blocker in result['network_blockers']))

    def test_fully_evidenced_production_requires_both_cutover_gates(self):
        for general, production in [(False, False), (True, False), (False, True), (True, True)]:
            with self.subTest(general=general, production=production):
                profile, compliance = self._production_configuration()
                result = self._inspect_configuration('Production', profile, compliance, general, production)
                self.assertTrue(result['ready'])
                self.assertEqual(result['network_ready'], general and production)
                if not general:
                    self.assertIn('General V1 network cutover is disabled.', result['network_blockers'])
                if not production:
                    self.assertIn('Production network cutover is disabled.', result['network_blockers'])
                profile.get_password.assert_called_once_with('v1_production_token', raise_exception=False)

    def test_compliance_state_reads_only_relevant_fields_without_controller(self):
        self.db.get_value.return_value = dict(active=1, operational_state='Operational')
        with patch.object(frappe, 'get_doc', side_effect=AssertionError('No controller load')):
            configuration.get_device_compliance_state('DEVICE-1')
            self.assertEqual(self.db.get_value.call_args.args[2], ['active', 'operational_state'])
            configuration.get_device_compliance_state('DEVICE-1', include_production=True)
            self.assertIn('qr_verification_evidence', self.db.get_value.call_args.args[2])
            self.assertIn('signature_verification_evidence', self.db.get_value.call_args.args[2])
        self.db.set_value.assert_not_called()

    def test_restoration_sets_due_only_for_unrestored_pending_invoices(self):
        device=Row(name='DEVICE-1',operational_state='Offline'); device.db_set=Mock()
        pending=[Row(name='NEW',custom_ledgix_fbr_upload_due_at=None),Row(name='OLD',custom_ledgix_fbr_upload_due_at='2026-01-01')]
        with patch.object(offline,'require_operator'),patch.object(frappe,'get_doc',return_value=device),patch.object(offline,'submission_lock',return_value=nullcontext()),patch.object(frappe,'get_all',side_effect=[pending,[]]),patch.object(offline,'append_event',return_value=Row(name='EVENT')):
            result=offline.record_device_event('DEVICE-1','Restoration')
        self.assertEqual(result['pending'],[{'doctype':'Sales Invoice','name':'NEW'}])
        self.assertEqual(self.db.set_value.call_count,1)
        fields=self.db.set_value.call_args.args[2]
        self.assertEqual(fields['custom_ledgix_fbr_upload_due_at'],offline.restoration_due_at(fields['custom_ledgix_fbr_restored_at']))

    def test_closing_repeated_period_reuses_evidence_without_reaggregation(self):
        device=Row(name='DEVICE-1')
        self.db.get_value.return_value='CLOSING-1'
        with patch.object(closing,'require_operator'),patch.object(frappe,'get_doc',return_value=device),patch.object(closing,'submission_lock',return_value=nullcontext()),patch.object(frappe,'get_all') as query:
            result=closing.generate_closing('DEVICE-1','Monthly','2026-01-01')
            query.assert_not_called()
        self.assertEqual(result['name'],'CLOSING-1');self.assertTrue(result['reused'])

    def test_hooks_center_and_schema_have_no_active_di_bindings(self):
        from fbr_v1 import hooks
        for events in hooks.doc_events.values():
            for path in events.values():
                self.assertNotIn('v2',path);self.assertNotIn('fbr_native',path)
        root=Path(__file__).resolve().parents[1]
        js=(root/'fbr_v1/page/fbr_v1_center/fbr_v1_center.js').read_text()
        for retired in ('fbr_v2','scenarioId','fbr_reference_v2'):
            self.assertNotIn(retired,js)
        for p in (root/'fbr_v1/print_format').glob('*/*.json'):
            d=json.loads(p.read_text());self.assertNotIn('25.4',d['css']);self.assertIn('7mm',d['css'])
        from fbr_v1.setup.erpnext_fbr_schema import CUSTOM_FIELDS
        for dt in ('Sales Invoice','POS Invoice'):
            fields={f['fieldname']:f for f in CUSTOM_FIELDS[dt]}
            self.assertIn('custom_ledgix_fbr_snapshot_protocol',fields)
            self.assertIn('custom_ledgix_fbr_v2_snapshot_json',fields)
            self.assertFalse(fields['custom_ledgix_fbr_snapshot_json']['allow_on_submit'])


    def test_offline_policy_disabled_fails_closed(self):
        doc=Row(
            doctype='Sales Invoice',
            name='INV-OFFLINE',
            company='Test Company',
            docstatus=1,
        )
        profile=Row(offline_policy='Disabled')

        with patch.object(offline,'get_profile',return_value=profile):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                'Known-offline issuance is disabled',
            ):
                offline.offline_invoice(doc)


    def test_cancellation_only_blocks_real_fiscal_history(self):
        doc=Row(
            doctype='Sales Invoice',
            name='INV-1',
            custom_ledgix_fbr_snapshot_hash='SNAPSHOT',
            custom_ledgix_fbr_status='Pending',
            custom_ledgix_fbr_reconciliation_required=0,
        )

        # Internal snapshot/Pending evidence alone must not make the
        # ERPNext document permanently uncancellable.
        pending=[
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id=None,
                transport_outcome='Not Attempted',
                fbr_status='Pending',
            )
        ]
        self.assertFalse(fiscal.cancellation_requires_credit(doc,pending))

        # Durable ambiguous intent followed by definite rejection is resolved.
        rejected=[
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id='A',
                transport_outcome='Ambiguous',
                fbr_status='Reconciliation Required',
            ),
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id='A',
                transport_outcome='Rejected',
                fbr_status='Failed',
            ),
        ]
        doc.custom_ledgix_fbr_status='Failed'
        self.assertFalse(fiscal.cancellation_requires_credit(doc,rejected))

        # Unresolved ambiguity is external-risk fiscal history.
        ambiguous=[
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id='B',
                transport_outcome='Ambiguous',
                fbr_status='Reconciliation Required',
            )
        ]
        self.assertTrue(fiscal.cancellation_requires_credit(doc,ambiguous))

        # Offline fiscal issuance is retained and must use a credit/return.
        offline_rows=[
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id=None,
                transport_outcome='Offline Deferred',
                fbr_status='Offline Pending',
            )
        ]
        self.assertTrue(fiscal.cancellation_requires_credit(doc,offline_rows))
