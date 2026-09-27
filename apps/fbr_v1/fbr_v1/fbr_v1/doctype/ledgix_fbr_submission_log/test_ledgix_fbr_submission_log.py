from unittest.mock import Mock
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest
from fbr_v1.fbr_v1.doctype.ledgix_fbr_submission_log.ledgix_fbr_submission_log import LedgixFBRSubmissionLog

class TestSubmissionEvidence(NoNetworkTest):
    def test_existing_evidence_cannot_be_saved_or_deleted(self):
        doc=Mock();doc.is_new.return_value=False
        with self.assertRaises(frappe.ValidationError):LedgixFBRSubmissionLog.validate(doc)
        with self.assertRaises(frappe.ValidationError):LedgixFBRSubmissionLog.on_trash(doc)
