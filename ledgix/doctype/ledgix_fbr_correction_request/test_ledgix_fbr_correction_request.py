from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from ledgix.doctype.v2_test_utils import configure_v2_test_environment, make_customer, make_item, make_sale
from ledgix_saas.api.fbr_submission import create_submission_log


CORRECTION_MODULE = "ledgix_saas.ledgix.doctype.ledgix_fbr_correction_request.ledgix_fbr_correction_request"


class TestLedgixFBRCorrectionRequest(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def _make_fbr_sale(self, generated_at=None, submitted_at=None):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="B2B", credit_limit=500)
		sale = make_sale(customer.name, item.name, rate=100, sale_channel="B2B", submit=True)
		frappe.db.set_value(
			"Ledgix Sale",
			sale.name,
			{
				"fbr_status": "Submitted",
				"fbr_invoice_number": f"FBR-{sale.name}",
				"fbr_generated_at": generated_at,
				"fbr_submitted_at": submitted_at or now_datetime(),
			},
			update_modified=False,
		)
		sale.reload()
		return sale

	def _make_request(self, sale, action_type="Edit", reason="Bona fide invoice mistake"):
		return frappe.get_doc({
			"doctype": "Ledgix FBR Correction Request",
			"sale": sale.name,
			"action_type": action_type,
			"reason": reason,
		}).insert(ignore_permissions=True)

	def test_submission_log_captures_official_fbr_generation_time(self):
		sale = self._make_fbr_sale(generated_at=None)
		expected = get_datetime("2026-08-30 10:11:12")

		create_submission_log(
			"Ledgix Sale",
			sale.name,
			"Sale Invoice",
			"Submitted",
			response_json={
				"response": {
					"invoiceNumber": sale.fbr_invoice_number,
					"dated": "2026-08-30 10:11:12",
					"validationResponse": {"statusCode": "00", "status": "Valid"},
				}
			},
			fbr_invoice_number=sale.fbr_invoice_number,
		)

		actual = frappe.db.get_value("Ledgix Sale", sale.name, "fbr_generated_at")
		self.assertEqual(get_datetime(actual), expected)

	def test_request_within_72_hours_routes_to_board_action(self):
		generated_at = add_to_date(now_datetime(), hours=-2, as_datetime=True)
		sale = self._make_fbr_sale(generated_at=generated_at)
		request = self._make_request(sale, action_type="Edit")

		self.assertEqual(request.fbr_invoice_number, sale.fbr_invoice_number)
		self.assertEqual(request.correction_path, "Within 72 Hours")
		self.assertEqual(request.status, "Board Action Pending")
		self.assertEqual(
			get_datetime(request.correction_deadline),
			add_to_date(get_datetime(generated_at), hours=72, as_datetime=True),
		)
		self.assertTrue(request.requested_by)
		self.assertTrue(request.requested_at)

	def test_request_after_72_hours_requires_commissioner_reference_to_complete(self):
		generated_at = add_to_date(now_datetime(), hours=-80, as_datetime=True)
		sale = self._make_fbr_sale(generated_at=generated_at)
		request = self._make_request(sale, action_type="Cancel")

		self.assertEqual(request.correction_path, "Commissioner Approval Required")
		self.assertEqual(request.status, "Commissioner Approval Pending")

		request.status = "Completed"
		request.board_reference = "BOARD-REF-001"
		with self.assertRaises(frappe.ValidationError):
			request.save(ignore_permissions=True)

		# A failed server-side save mutates the in-memory Document timestamp even
		# though the transaction did not persist. Reload before the valid retry.
		request.reload()
		request.status = "Completed"
		request.board_reference = "BOARD-REF-001"
		request.commissioner_approval_reference = "CIR-APPROVAL-001"
		request.save(ignore_permissions=True)
		self.assertEqual(request.status, "Completed")
		self.assertTrue(request.completed_at)

	def test_completion_after_deadline_reclassifies_earlier_open_request(self):
		generated_at = now_datetime()
		sale = self._make_fbr_sale(generated_at=generated_at)
		request = self._make_request(sale)
		self.assertEqual(request.correction_path, "Within 72 Hours")

		after_deadline = add_to_date(generated_at, hours=73, as_datetime=True)
		request.status = "Completed"
		request.board_reference = "BOARD-REF-LATE"
		with patch(f"{CORRECTION_MODULE}.now_datetime", return_value=after_deadline):
			with self.assertRaises(frappe.ValidationError):
				request.save(ignore_permissions=True)

			request.reload()
			request.status = "Completed"
			request.board_reference = "BOARD-REF-LATE"
			request.commissioner_approval_reference = "CIR-APPROVAL-LATE"
			request.save(ignore_permissions=True)

		self.assertEqual(request.correction_path, "Commissioner Approval Required")
		self.assertEqual(get_datetime(request.completed_at), get_datetime(after_deadline))

	def test_duplicate_open_correction_request_is_blocked(self):
		sale = self._make_fbr_sale(generated_at=add_to_date(now_datetime(), hours=-1, as_datetime=True))
		first = self._make_request(sale)
		self.assertEqual(first.status, "Board Action Pending")

		with self.assertRaises(frappe.ValidationError):
			self._make_request(sale, action_type="Delete", reason="Second open request")
