from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row
from fbr_v1.fbr_v1.doctype.ledgix_fbr_correction_request import ledgix_fbr_correction_request as controller
from fbr_v1.api import corrections


class TestCorrectionTracking(NoNetworkTest):
    def setUp(self):
        super().setUp()
        self.at = datetime(2026, 9, 27, 12)
        self.invoice = Row(doctype='Sales Invoice', name='INV-1', company='Test Company', docstatus=1,
            custom_ledgix_fbr_pos_device='DEVICE-1', custom_ledgix_fbr_invoice_number='FBR-1',
            custom_ledgix_fbr_snapshot_protocol='Federal POS/IMS V1',
            custom_ledgix_fbr_generated_at=self.at - timedelta(hours=1))
        self.db.get_value.return_value = 'Test Company'
        self.db.exists.return_value = True
        self.stack.enter_context(patch.object(frappe, 'get_doc', return_value=self.invoice))
        self.stack.enter_context(patch.object(controller, 'history', return_value=[]))
        self.stack.enter_context(patch.object(controller, 'now_datetime', return_value=self.at))
        # Validation must not use either role lookup or a session user, even on a valid request.
        self.stack.enter_context(patch.object(frappe, 'session', None))
        self.roles = self.stack.enter_context(patch.object(frappe, 'get_roles', side_effect=AssertionError('No role lookup in validation')))

    def request(self, **values):
        doc = Row(reference_doctype='Sales Invoice', reference_name='INV-1', action_type='Edit',
                  reason='Correct externally recorded buyer evidence', requested_at=self.at,
                  requested_by='operator@example.invalid', status='Board Action Pending')
        doc.update(values)
        doc.get_doc_before_save = Mock(return_value=None)
        return doc

    def validate(self, doc):
        controller.LedgixFBRCorrectionRequest.validate(doc)

    def test_valid_request_invariants_do_not_require_session_or_roles(self):
        doc = self.request()
        self.validate(doc)
        self.assertEqual(doc.fbr_invoice_number, 'FBR-1')
        self.assertEqual(doc.correction_deadline, self.invoice.custom_ledgix_fbr_generated_at + timedelta(hours=72))
        self.assertEqual(doc.correction_path, 'Within 72 Hours')
        self.assertEqual(doc.requested_by, 'operator@example.invalid')
        self.roles.assert_not_called()
        self.db.set_value.assert_not_called()

    def test_invalid_source_action_and_reason_fail_closed(self):
        for values, message in [({'reference_doctype': 'Journal Entry'}, 'Select Sales Invoice'),
                                ({'action_type': 'Refund'}, 'Cancel/Delete/Edit'),
                                ({'reason': '  '}, 'bona-fide reason')]:
            with self.subTest(values=values), self.assertRaisesRegex(frappe.ValidationError, message):
                self.validate(self.request(**values))
        self.invoice.docstatus = 0
        with self.assertRaisesRegex(frappe.ValidationError, 'submitted source'):
            self.validate(self.request())
        self.invoice.docstatus = 1
        self.invoice.custom_ledgix_fbr_invoice_number = None
        with self.assertRaisesRegex(frappe.ValidationError, 'authoritative FBR invoice number'):
            self.validate(self.request())

    def test_missing_official_time_requires_authoritative_evidence(self):
        self.invoice.custom_ledgix_fbr_generated_at = None
        with self.assertRaisesRegex(frappe.ValidationError, 'external reference and evidence'):
            self.validate(self.request(fbr_generated_at=self.at))
        with self.assertRaisesRegex(frappe.ValidationError, 'generation timestamp is required'):
            self.validate(self.request(generation_time_reference='TIME-1', generation_time_evidence='/private/files/time'))

    def test_completion_requires_external_proof_and_late_commissioner_approval(self):
        with self.assertRaisesRegex(frappe.ValidationError, 'external reference and evidence'):
            self.validate(self.request(status='Completed'))
        self.db.exists.return_value = False
        with self.assertRaisesRegex(frappe.ValidationError, 'uploaded evidence attachment'):
            self.validate(self.request(status='Completed', board_reference='BOARD-1', external_evidence='/private/files/missing'))
        self.db.exists.return_value = True
        self.invoice.custom_ledgix_fbr_generated_at = self.at - timedelta(hours=73)
        doc = self.request(status='Completed', board_reference='BOARD-1', external_evidence='/private/files/completion')
        with self.assertRaisesRegex(frappe.ValidationError, 'commissioner approval'):
            self.validate(doc)
        doc.commissioner_approval_reference = 'APPROVAL-1'
        self.validate(doc)
        self.assertEqual(doc.correction_path, 'Commissioner Approval Required')
        self.assertEqual(doc.completed_at, self.at)

    def test_completed_and_original_request_evidence_remain_frozen(self):
        doc = self.request(status='Completed', board_reference='CHANGED')
        doc.get_doc_before_save.return_value = Row(status='Completed')
        with self.assertRaisesRegex(frappe.ValidationError, 'immutable'):
            self.validate(doc)
        doc = self.request(reason='Changed request reason')
        old = Row(doc)
        old.reason = 'Original request reason'
        doc.get_doc_before_save.return_value = old
        with self.assertRaisesRegex(frappe.ValidationError, 'Original correction request evidence is immutable'):
            self.validate(doc)

    def test_deletion_and_uncontrolled_persistence_remain_prohibited(self):
        with self.assertRaisesRegex(frappe.ValidationError, 'cannot be deleted'):
            controller.LedgixFBRCorrectionRequest.on_trash(Mock())
        with self.assertRaisesRegex(frappe.ValidationError, 'controlled correction'):
            controller.LedgixFBRCorrectionRequest._require_controlled_write(Row(flags=Row()))

    def test_controlled_apis_authorize_before_reading_or_writing(self):
        with patch.object(corrections, 'require_operator', side_effect=frappe.PermissionError('Denied')) as authorize, \
                patch.object(corrections, 'source') as source:
            with self.assertRaises(frappe.PermissionError):
                corrections.request_correction('Sales Invoice', 'INV-1', 'Edit', 'Reason')
            with self.assertRaises(frappe.PermissionError):
                corrections.record_correction_result('CORRECTION-1', 'Completed', 'BOARD-1', '/private/files/proof')
            self.assertEqual(authorize.call_count, 2)
            source.assert_not_called()
