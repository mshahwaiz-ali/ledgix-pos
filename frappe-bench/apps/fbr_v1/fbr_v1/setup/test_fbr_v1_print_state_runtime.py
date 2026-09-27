from unittest.mock import patch

from fbr_v1.api import fiscalization, printing
from fbr_v1.services.pos_identity import PROTOCOL
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row, fixture


class TestFiscalPrintState(NoNetworkTest):
    def profile(self, **values):
        profile = Row(
            protocol_version=PROTOCOL,
            enabled=1,
            mode='Sandbox',
            submit_trigger='Manual',
            transport_enabled=1,
            block_print_without_fiscal_result=1,
            offline_policy='Disabled',
        )
        profile.update(values)
        return profile

    def invoice(self, status='Pending', **values):
        doc = Row(
            doctype='Sales Invoice',
            name='INV-1',
            company='Test Company',
            custom_ledgix_fbr_snapshot_protocol=PROTOCOL,
            custom_ledgix_fbr_status=status,
            custom_ledgix_fbr_invoice_number='',
            custom_ledgix_fbr_reconciliation_required=0,
        )
        doc.update(values)
        return doc

    def state(self, doc, profile):
        with patch.object(printing, 'get_profile', return_value=profile), patch.object(
            printing.fbr_v1_snapshot_persistence,
            'read_persisted_v1_snapshot',
            return_value=fixture(),
        ):
            return printing.get_invoice_fiscal_print_state(doc)

    def test_normal_submitted_pending_failed_and_reconciliation_states(self):
        no_fbr = self.invoice(custom_ledgix_fbr_snapshot_protocol='')
        state = self.state(no_fbr, None)
        self.assertFalse(state['fbr_required'])
        self.assertTrue(state['print_ready'])

        submitted = self.invoice('Submitted', custom_ledgix_fbr_invoice_number='FBR-1')
        state = self.state(submitted, self.profile())
        self.assertTrue(state['print_ready'])
        self.assertEqual(state['invoice_number'], 'FBR-1')

        pending = self.state(self.invoice(), self.profile())
        self.assertTrue(pending['print_blocked'])
        self.assertFalse(pending['automatic_submission_expected'])
        self.assertTrue(pending['terminal'])

        failed = self.state(self.invoice('Failed'), self.profile())
        self.assertTrue(failed['print_blocked'])
        self.assertTrue(failed['terminal'])

        reconciliation = self.state(
            self.invoice('Reconciliation Required', custom_ledgix_fbr_reconciliation_required=1),
            self.profile(),
        )
        self.assertTrue(reconciliation['print_blocked'])
        self.assertTrue(reconciliation['reconciliation_required'])
        self.assertTrue(reconciliation['terminal'])

    def test_pending_is_polled_only_when_backend_submission_is_expected(self):
        profile = self.profile(submit_trigger='On Submit')
        with patch.object(printing, 'get_profile', return_value=profile), patch.object(
            printing.transport, 'network_cutover_active', return_value=True
        ), patch.object(
            printing.fbr_v1_snapshot_persistence,
            'read_persisted_v1_snapshot',
            return_value=fixture(),
        ), patch.object(
            printing, 'get_device_compliance_state', return_value={}
        ), patch.object(
            printing, 'configuration_blockers', return_value=[]
        ):
            state = printing.get_invoice_fiscal_print_state(self.invoice())
        self.assertTrue(state['automatic_submission_expected'])
        self.assertFalse(state['terminal'])

    def test_authorized_offline_receipt_requires_complete_durable_evidence(self):
        snapshot = fixture()
        profile = self.profile(
            offline_policy='Operator Confirmed',
            offline_authority_reference='AUTH-1',
            offline_authority_evidence='/private/files/offline.pdf',
        )
        doc = self.invoice(
            'Offline Pending',
            custom_ledgix_fbr_pos_device='DEVICE-1',
            custom_ledgix_fbr_offline_issued_at='2026-09-27 10:00:00',
            custom_ledgix_fbr_invoice_number='MUST-NOT-PRINT',
        )

        def evidence_exists(doctype, filters):
            return doctype in {
                'File',
                'Ledgix FBR Submission Log',
                'Ledgix FBR Fiscal Event Log',
            }

        self.db.exists.side_effect = evidence_exists
        with patch.object(printing, 'get_profile', return_value=profile), patch.object(
            printing.fbr_v1_snapshot_persistence,
            'read_persisted_v1_snapshot',
            return_value=snapshot,
        ):
            state = printing.get_invoice_fiscal_print_state(doc)
        self.assertTrue(state['print_ready'])
        self.assertTrue(state['offline_pending'])
        self.assertEqual(state['invoice_number'], '')
        log_filters = next(
            call.args[1]
            for call in self.db.exists.call_args_list
            if call.args[0] == 'Ledgix FBR Submission Log'
        )
        self.assertEqual(log_filters['protocol'], PROTOCOL)
        self.assertEqual(log_filters['transport_outcome'], 'Offline Deferred')
        self.assertEqual(log_filters['source_snapshot_hash'], snapshot['snapshot_hash'])
        self.assertEqual(log_filters['pos_device'], 'DEVICE-1')

        self.db.exists.side_effect = lambda doctype, filters: doctype != 'File'
        with patch.object(printing, 'get_profile', return_value=profile):
            blocked = printing.get_invoice_fiscal_print_state(doc)
        self.assertTrue(blocked['print_blocked'])
        self.assertFalse(blocked['offline_pending'])

        unauthorized = self.state(doc, self.profile(offline_policy='Disabled'))
        self.assertTrue(unauthorized['print_blocked'])
        self.assertFalse(unauthorized['offline_pending'])

    def test_state_endpoint_is_read_only_and_reports_no_network_call(self):
        doc = self.invoice()
        expected = self.state(doc, self.profile())
        with patch.object(fiscalization, 'source', return_value=doc) as source, patch.object(
            printing, 'get_invoice_fiscal_print_state', return_value=expected
        ):
            result = fiscalization.get_invoice_fiscal_state('Sales Invoice', 'INV-1')
        source.assert_called_once_with('Sales Invoice', 'INV-1', 'read')
        self.assertFalse(result['network_call'])
        self.assertFalse(result['automatic_submission_expected'])
        self.db.set_value.assert_not_called()
