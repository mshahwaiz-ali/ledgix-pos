# Copyright (c) 2026, Ali and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days

from ledgix.doctype.v2_test_utils import (
	configure_tax_profile,
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_item_tax_profile,
	make_sale,
	make_sales_return,
	make_tax_category,
	make_tax_rate,
)
from ledgix_saas.api import fbr_submission
from ledgix_saas.api.fbr_payload import (
	_validate_return_fbr_readiness_internal,
	build_official_return_invoice_payload,
)
from ledgix_saas.api.v2_returns import create_pos_v2_return, get_pos_v2_return_context
from ledgix_saas.services.receivables import get_customer_receivables


class TestLedgixSalesReturn(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def _make_stock_sale(self):
		item = make_item(selling_price=100, cost_price=40, opening_stock=5)
		customer = make_customer(customer_type="B2B", credit_limit=1000)
		sale = make_sale(
			customer.name,
			item.name,
			quantity=2,
			rate=100,
			sale_channel="B2B",
			submit=True,
		)
		return item, customer, sale

	def _make_fbr_taxed_sale(self):
		tax_category = make_tax_category(rate=18)
		make_tax_rate(tax_category.name, rate=18)
		configure_tax_profile(tax_category.name, price_includes_tax=False)
		item = make_item(selling_price=100, cost_price=40, opening_stock=5)
		make_item_tax_profile(
			item.name,
			tax_category.name,
			fbr_rate_description="18% along with rupees 60 per kilogram",
			sales_tax_withheld_at_source_per_unit=2,
			extra_tax_per_unit=3,
			further_tax_per_unit=4,
			fed_payable_per_unit=5,
		)
		customer = make_customer(customer_type="B2B", credit_limit=5000)
		sale = make_sale(
			customer.name,
			item.name,
			quantity=2,
			rate=100,
			sale_channel="B2B",
			submit=True,
		)
		frappe.db.set_value("Ledgix Sale", sale.name, "fbr_invoice_number", "FBR-TEST-INV-001", update_modified=False)
		sale.reload()
		return item, customer, sale

	def test_return_requires_reason(self):
		_item, _customer, sale = self._make_stock_sale()
		doc = frappe.new_doc("Ledgix Sales Return")
		doc.original_sale = sale.name
		doc.return_reason = ""
		doc.append("items", {
			"item": sale.items[0].item,
			"original_sale_item_row": sale.items[0].name,
			"quantity": 1,
		})

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_return_derives_customer_financials_and_stock_from_original_sale(self):
		item, customer, sale = self._make_stock_sale()
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 3)

		return_doc = make_sales_return(
			sale,
			quantity=1,
			include_row_reference=False,
			submit=True,
		)

		self.assertEqual(return_doc.customer, customer.name)
		self.assertEqual(return_doc.items[0].original_sale_item_row, sale.items[0].name)
		self.assertAlmostEqual(return_doc.items[0].rate, 100, places=2)
		self.assertAlmostEqual(return_doc.items[0].cost_price, 40, places=2)
		self.assertAlmostEqual(return_doc.total_amount, 100, places=2)
		self.assertAlmostEqual(return_doc.grand_total, 100, places=2)
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 4)

		credit = get_customer_receivables(customer.name)
		self.assertAlmostEqual(credit["outstanding"], 100, places=2)

	def test_pos_return_contract_preserves_reason_and_exact_sale_row(self):
		_item, _customer, sale = self._make_stock_sale()
		context = get_pos_v2_return_context(sale.name)
		self.assertEqual(context["sale_id"], sale.name)
		self.assertEqual(len(context["items"]), 1)
		row = context["items"][0]
		self.assertEqual(row["original_sale_item_row"], sale.items[0].name)

		result = create_pos_v2_return(
			original_sale=sale.name,
			return_items=[{
				"item": row["item"],
				"original_sale_item_row": row["original_sale_item_row"],
				"qty": 1,
			}],
			reason="Damaged item",
		)
		return_doc = frappe.get_doc("Ledgix Sales Return", result["return_id"])
		self.assertEqual(return_doc.return_reason, "Damaged item")
		self.assertEqual(return_doc.items[0].original_sale_item_row, sale.items[0].name)
		self.assertEqual(return_doc.customer, sale.customer)
		self.assertAlmostEqual(return_doc.grand_total, 100, places=2)

	def test_return_cannot_exceed_remaining_original_quantity(self):
		_item, _customer, sale = self._make_stock_sale()
		make_sales_return(sale, quantity=1, include_row_reference=False, submit=True)

		with self.assertRaises(frappe.ValidationError):
			make_sales_return(sale, quantity=2, include_row_reference=False, submit=False)

	def test_return_cancel_restores_stock_and_receivable(self):
		item, customer, sale = self._make_stock_sale()
		return_doc = make_sales_return(sale, quantity=1, include_row_reference=True, submit=True)

		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 4)
		self.assertAlmostEqual(get_customer_receivables(customer.name)["outstanding"], 100, places=2)

		return_doc.cancel()

		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 3)
		self.assertAlmostEqual(get_customer_receivables(customer.name)["outstanding"], 200, places=2)
		self.assertEqual(
			frappe.db.count(
				"Ledgix Stock Movement",
				filters={"reference_doctype": "Ledgix Sales Return", "reference_name": return_doc.name, "docstatus": 2},
			),
			1,
		)

	def test_fbr_return_payload_preserves_reference_reason_date_and_tax_snapshots(self):
		_item, _customer, sale = self._make_fbr_taxed_sale()
		return_doc = make_sales_return(
			sale,
			quantity=1,
			return_reason="Damaged item",
			submit=True,
		)
		return_doc.reload()

		frappe.db.set_single_value("Ledgix FBR Settings", "mode", "Sandbox")
		frappe.db.set_single_value("Ledgix FBR Settings", "enabled", 0)
		frappe.clear_cache(doctype="Ledgix FBR Settings")

		self.assertTrue(return_doc.return_date)
		self.assertEqual(len(return_doc.tax_details), 1)
		row = return_doc.tax_details[0]
		self.assertEqual(row.fbr_rate_description, "18% along with rupees 60 per kilogram")
		self.assertAlmostEqual(row.tax_amount, 18, places=2)
		self.assertAlmostEqual(row.sales_tax_withheld_at_source, 2, places=2)
		self.assertAlmostEqual(row.extra_tax, 3, places=2)
		self.assertAlmostEqual(row.further_tax, 4, places=2)
		self.assertAlmostEqual(row.fed_payable, 5, places=2)
		self.assertAlmostEqual(return_doc.tax_amount, 30, places=2)
		self.assertAlmostEqual(return_doc.grand_total, 130, places=2)

		readiness = _validate_return_fbr_readiness_internal(return_doc.name)
		self.assertTrue(readiness["valid"], readiness.get("errors"))

		payload = build_official_return_invoice_payload(return_doc)
		self.assertEqual(payload["invoiceRefNo"], "FBR-TEST-INV-001")
		self.assertEqual(payload["reason"], "Damaged item")
		self.assertEqual(payload["invoiceDate"], str(return_doc.return_date))
		self.assertEqual(payload["scenarioId"], "SN001")
		self.assertEqual(payload["items"][0]["rate"], "18% along with rupees 60 per kilogram")
		self.assertAlmostEqual(payload["items"][0]["salesTaxApplicable"], 18, places=2)
		self.assertAlmostEqual(payload["items"][0]["salesTaxWithheldAtSource"], 2, places=2)
		self.assertAlmostEqual(payload["items"][0]["extraTax"], 3, places=2)
		self.assertAlmostEqual(payload["items"][0]["furtherTax"], 4, places=2)
		self.assertAlmostEqual(payload["items"][0]["fedPayable"], 5, places=2)

	def test_fbr_return_readiness_rejects_note_after_180_days(self):
		_item, _customer, sale = self._make_fbr_taxed_sale()
		return_doc = make_sales_return(sale, quantity=1, return_reason="Late return", submit=True)
		return_doc.reload()

		frappe.db.set_value(
			"Ledgix Sale",
			sale.name,
			"sale_date",
			add_days(return_doc.return_date, -181),
			update_modified=False,
		)
		frappe.db.set_single_value("Ledgix FBR Settings", "mode", "Sandbox")
		frappe.db.set_single_value("Ledgix FBR Settings", "enabled", 0)
		frappe.clear_cache(doctype="Ledgix FBR Settings")

		readiness = _validate_return_fbr_readiness_internal(return_doc.name)
		self.assertFalse(readiness["valid"])
		self.assertTrue(
			any("180 days" in message for message in readiness.get("errors") or []),
			readiness.get("errors"),
		)

	def test_fbr_return_submission_persists_qr_code(self):
		_item, _customer, sale = self._make_fbr_taxed_sale()
		return_doc = make_sales_return(sale, quantity=1, return_reason="Damaged item", submit=True)

		settings = {
			"enabled": True,
			"mode": "Production",
			"submit_trigger": "Manual",
			"production_token_configured": True,
			"production_post_armed": True,
			"sandbox_token_configured": False,
		}
		client_result = {
			"success": True,
			"network_call": True,
			"http_status": 200,
			"status": "HTTP OK",
			"response": {
				"invoiceNumber": "FBR-NOTE-001",
				"QRCode": "QR-RETURN-001",
				"validationResponse": {"status": "Valid", "statusCode": "00"},
			},
			"error": "",
			"fbr_operation": "post",
			"fbr_mode": "Production",
		}
		with patch.object(fbr_submission, "get_fbr_settings_internal", return_value=settings), \
			patch.object(fbr_submission, "_build_ready_return_payload", return_value=({"invoiceType": "Credit Note"}, {"valid": True, "errors": [], "warnings": []}, "")), \
			patch.object(fbr_submission.fbr_client, "post_invoice", return_value=client_result):
			result = fbr_submission._submit_return_to_fbr_internal(return_doc.name)

		self.assertEqual(result["status"], "Submitted")
		self.assertEqual(result["fbr_qr_code"], "QR-RETURN-001")
		return_doc.reload()
		self.assertEqual(return_doc.fbr_invoice_number, "FBR-NOTE-001")
		self.assertEqual(return_doc.fbr_qr_code, "QR-RETURN-001")

	def test_ambiguous_return_post_requires_reconciliation_and_blocks_resend(self):
		_item, _customer, sale = self._make_fbr_taxed_sale()
		return_doc = make_sales_return(sale, quantity=1, return_reason="Damaged item", submit=True)
		settings = {
			"enabled": True,
			"mode": "Production",
			"submit_trigger": "Manual",
			"production_token_configured": True,
			"production_post_armed": True,
			"sandbox_token_configured": False,
		}
		client_result = {
			"success": False,
			"network_call": True,
			"http_status": None,
			"status": "Network Error",
			"response": None,
			"error": "timeout. Production POST outcome may be ambiguous. Reconcile with FBR/PRAL before retransmission.",
			"fbr_operation": "post",
			"fbr_mode": "Production",
		}
		with patch.object(fbr_submission, "get_fbr_settings_internal", return_value=settings), \
			patch.object(fbr_submission, "_build_ready_return_payload", return_value=({"invoiceType": "Credit Note"}, {"valid": True, "errors": [], "warnings": []}, "")), \
			patch.object(fbr_submission.fbr_client, "post_invoice", return_value=client_result) as post_mock:
			result = fbr_submission._submit_return_to_fbr_internal(return_doc.name)
			self.assertEqual(result["status"], fbr_submission.RECONCILIATION_REQUIRED)
			return_doc.reload()
			self.assertEqual(return_doc.fbr_status, fbr_submission.RECONCILIATION_REQUIRED)

			second = fbr_submission._submit_return_to_fbr_internal(return_doc.name)
			self.assertEqual(second["status"], fbr_submission.RECONCILIATION_REQUIRED)
			self.assertFalse(second["network_call"])
			post_mock.assert_called_once()
