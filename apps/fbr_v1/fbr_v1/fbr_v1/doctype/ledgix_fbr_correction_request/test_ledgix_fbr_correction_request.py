from unittest.mock import Mock
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest
from fbr_v1.fbr_v1.doctype.ledgix_fbr_correction_request.ledgix_fbr_correction_request import LedgixFBRCorrectionRequest

class TestRetiredCorrections(NoNetworkTest):
    def test_unsupported_window_is_retired_and_history_preserved(self):
        with self.assertRaises(frappe.ValidationError):LedgixFBRCorrectionRequest.validate(Mock())
        with self.assertRaises(frappe.ValidationError):LedgixFBRCorrectionRequest.on_trash(Mock())
