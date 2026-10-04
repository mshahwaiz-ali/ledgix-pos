"""Current V1 Sandbox acceptance behavior; no site/network or legacy certification."""
from copy import deepcopy
from unittest.mock import patch

import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row, fixture
from fbr_v1.services import sandbox_acceptance as acceptance
from fbr_v1.services.fbr_v1_payload_builder import build_invoice, digest


class TestSandboxAcceptance(NoNetworkTest):
    def setUp(self):
        super().setUp()
        self.profile = Row(name='PROFILE', company='Test Company', protocol_version=acceptance.PROTOCOL, mode='Sandbox')
        self.device = Row(name='DEVICE-1', company='Test Company', environment='Sandbox', active=1, pos_id='123')
        self.snapshot = fixture()
        request = build_invoice(self.snapshot).to_payload()
        response = {'Code': '100', 'InvoiceNumber': 'FBR-1', 'Response': 'Success'}
        self.row = Row(name='LOG-1', protocol=acceptance.PROTOCOL, pos_device='DEVICE-1',
            reference_doctype='Sales Invoice', reference_name='INV-1', fbr_status='Submitted',
            fbr_invoice_number='FBR-1', attempt_id='ATTEMPT', source_snapshot_hash=self.snapshot['snapshot_hash'],
            request_json=request, request_hash=digest(request), response_json=response, response_hash=digest(response),
            transport_outcome='Accepted', transport_started_at='2026-10-04 10:00:00',
            transport_finished_at='2026-10-04 10:00:01', reconciliation_required=0)
        self.rows = [self.row]
        self.query = self.stack.enter_context(patch.object(frappe, 'get_list', side_effect=lambda *a, **k: self.rows))
        self.stack.enter_context(patch.object(frappe, 'get_doc', return_value=Row(name='INV-1')))
        self.stack.enter_context(patch.object(acceptance, 'read_persisted_v1_snapshot', side_effect=lambda *a: self.snapshot))
        self.decrypt = self.stack.enter_context(patch('frappe.utils.password.get_decrypted_password', side_effect=AssertionError('Credentials forbidden')))

    def inspect(self):
        result = acceptance.get_sandbox_acceptance('Test Company', self.profile, [self.device])
        self.decrypt.assert_not_called()
        for method in ('set_value', 'insert', 'sql', 'commit', 'rollback'):
            getattr(self.db, method).assert_not_called()
        self.assertFalse(result['database_write'])
        self.assertFalse(result['fbr_network_call'])
        return result

    def test_verified_v1_sandbox_is_accepted_without_production_authorization(self):
        result = self.inspect()
        self.assertTrue(result['complete'])
        self.assertEqual(result['status'], 'Accepted')
        self.assertFalse(result['production_authorized'])
        self.assertEqual(result['profile'], 'PROFILE')
        self.assertEqual(result['verified_evidence_count'], 1)
        self.assertNotIn('request_json', result['evidence'][0])
        self.assertNotIn('response_json', result['evidence'][0])
        filters = self.query.call_args.kwargs['filters']
        self.assertEqual(filters['protocol'], acceptance.PROTOCOL)
        self.assertEqual(filters['pos_device'], ['in', ['DEVICE-1']])

    def test_missing_evidence_fails_closed(self):
        self.rows = []
        self.assertFalse(self.inspect()['complete'])

    def test_historical_di_logs_or_profiles_never_count(self):
        self.row.protocol = 'DI API V1.12'
        self.assertFalse(self.inspect()['complete'])
        self.profile.protocol_version = 'DI API V1.12'
        self.assertFalse(self.inspect()['complete'])

    def test_missing_or_foreign_profile_device_company_fails_closed(self):
        for profile, devices in ((None, [self.device]), (Row(name='FOREIGN', company='Other', protocol_version=acceptance.PROTOCOL), [self.device]), (self.profile, [])):
            self.assertFalse(acceptance.get_sandbox_acceptance('Test Company', profile, devices)['complete'])
        self.device.company = 'Other'
        self.assertFalse(self.inspect()['complete'])

    def test_production_device_or_snapshot_never_counts_as_sandbox(self):
        self.device.environment = 'Production'
        self.assertFalse(self.inspect()['complete'])
        self.device.environment = 'Sandbox'
        self.snapshot['header']['pos_device']['environment'] = 'Production'
        self.assertFalse(self.inspect()['complete'])

    def test_snapshot_company_device_or_posid_mismatch_fails_closed(self):
        base = deepcopy(self.snapshot)
        for change in ({'company': 'Other'}, {'name': 'FOREIGN'}, {'pos_id': '999'}):
            self.snapshot = deepcopy(base)
            self.snapshot['header']['pos_device'].update(change)
            self.assertFalse(self.inspect()['complete'])
        self.snapshot = deepcopy(base)
        self.snapshot['header']['company'] = 'Other'
        self.assertFalse(self.inspect()['complete'])

    def test_missing_invalid_or_tampered_transport_evidence_fails_closed(self):
        base = deepcopy(self.row)
        for change in ({'attempt_id': ''}, {'transport_finished_at': None}, {'fbr_invoice_number': ''},
                       {'request_hash': 'tampered'}, {'response_hash': 'tampered'},
                       {'source_snapshot_hash': 'tampered'}, {'request_json': '{'},
                       {'response_json': '[]'}, {'reconciliation_required': 1}, {'transport_outcome': 'Externally Confirmed'}):
            with self.subTest(change=change):
                self.row = Row({**base, **change})
                self.rows = [self.row]
                self.assertFalse(self.inspect()['complete'])

    def test_code_100_without_number_or_wrong_number_does_not_count(self):
        for response in ({'Code': '100'}, {'Code': '101', 'InvoiceNumber': 'FBR-1'}, {'Code': '100', 'InvoiceNumber': 'OTHER'}):
            self.row.update(response_json=response, response_hash=digest(response))
            self.assertFalse(self.inspect()['complete'])

    def test_invalid_snapshot_is_not_rebuilt_or_reinterpreted(self):
        with patch.object(acceptance, 'read_persisted_v1_snapshot', side_effect=frappe.ValidationError('Corrupt')):
            self.assertFalse(self.inspect()['complete'])

    def test_acceptance_survives_profile_mode_change_without_arming(self):
        self.profile.mode = 'Production'
        result = self.inspect()
        self.assertTrue(result['complete'])
        self.assertFalse(result['production_authorized'])

    def test_client_readiness_exposes_the_current_v1_acceptance_projection(self):
        from fbr_v1.api import client_readiness as client
        self.profile.enabled = 1
        self.stack.enter_context(patch.object(client, 'get_profile', return_value=self.profile))
        self.stack.enter_context(patch.object(client, 'resolve_company_seller_identity',
            return_value={'ready': True, 'errors': [], 'seller': {}}))
        self.stack.enter_context(patch.object(client, 'configuration_blockers', return_value=[]))
        self.stack.enter_context(patch('fbr_v1.services.v1_configuration.setup_configuration_blockers', return_value=[]))
        self.stack.enter_context(patch.object(client.erpnext_tax_readiness, 'get_company_tax_readiness',
            return_value={'ready': True, 'blockers': []}))
        self.stack.enter_context(patch.object(client, 'get_payment_readiness',
            return_value={'ready': True, 'blockers': []}))
        self.stack.enter_context(patch.object(client.transport, 'network_cutover_active', return_value=False))
        self.stack.enter_context(patch.object(client.transport, 'production_cutover_active', return_value=False))
        self.query.side_effect = lambda dt, **kw: ['DEVICE-1'] if dt == 'Ledgix FBR POS Device' else self.rows
        with patch.object(frappe, 'get_doc', side_effect=lambda dt, name:
                self.device if dt == 'Ledgix FBR POS Device' else Row(name=name)):
            ready = client.get_client_readiness('Test Company')
            self.assertTrue(ready['sandbox_transport_acceptance_complete'])
            self.assertEqual(ready['sandbox_certification_complete'], ready['sandbox_transport_acceptance_complete'])
            self.assertFalse(ready['external_production_approval_complete'])
            self.assertEqual(ready['sandbox_acceptance']['status'], 'Accepted')
            self.assertFalse(ready['sandbox_acceptance']['production_authorized'])
            self.assertFalse(ready['production_ready'])
            self.rows = []
            self.assertFalse(client.get_client_readiness('Test Company')['sandbox_transport_acceptance_complete'])
        self.decrypt.assert_not_called()
        self.db.set_value.assert_not_called()

    def test_inaccessible_evidence_fails_closed_without_permission_bypass(self):
        self.query.side_effect = frappe.PermissionError('Denied')
        result = self.inspect()
        self.assertFalse(result['complete'])
        self.assertEqual(result['status'], 'Evidence Unavailable')
        self.assertEqual(result['verified_evidence_count'], 0)
