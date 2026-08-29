import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_tax_profile,
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_item_tax_profile,
	make_sale,
	make_tax_category,
	make_tax_rate,
)
from ledgix_saas.api.fbr_payload import (
	_validate_sale_fbr_readiness_internal,
	build_official_sale_invoice_payload,
)


class TestLedgixItemTaxProfile(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def _third_schedule_sale(self, *, notified_retail_price=200, sale_rate=150):
		tax_category = make_tax_category(rate=18)
		make_tax_rate(tax_category.name, rate=18)
		configure_tax_profile(tax_category.name, price_includes_tax=False)
		item = make_item(selling_price=sale_rate, cost_price=80)
		mapping = make_item_tax_profile(
			item.name,
			tax_category.name,
			tax_basis="Notified Retail Price",
			notified_retail_price=notified_retail_price,
		)
		customer = make_customer(customer_type="B2B", credit_limit=5000)
		sale = make_sale(
			customer.name,
			item.name,
			rate=sale_rate,
			sale_channel="B2B",
			submit=True,
		)
		return sale, customer, mapping, tax_category

	def test_third_schedule_snapshot_drives_official_payload(self):
		sale, customer, _mapping, _tax_category = self._third_schedule_sale()
		sale.reload()

		self.assertEqual(sale.items[0].tax_basis_snapshot, "Notified Retail Price")
		self.assertAlmostEqual(sale.items[0].notified_retail_price_snapshot, 200, places=2)
		self.assertAlmostEqual(sale.items[0].tax_rate_snapshot, 18, places=2)
		self.assertEqual(len(sale.tax_details), 1)
		self.assertEqual(sale.tax_details[0].tax_basis, "Notified Retail Price")
		self.assertAlmostEqual(sale.tax_details[0].notified_retail_price, 200, places=2)

		payload = build_official_sale_invoice_payload(sale)
		self.assertEqual(payload["buyerBusinessName"], customer.customer_name)
		self.assertEqual(payload["buyerNTNCNIC"], "12345678")
		self.assertEqual(payload["items"][0]["rate"], "18%")
		self.assertAlmostEqual(payload["items"][0]["fixedNotifiedValueOrRetailPrice"], 200, places=2)

	def test_finalized_fbr_payload_is_immune_to_customer_and_tax_master_edits(self):
		sale, customer, mapping, tax_category = self._third_schedule_sale()
		original_payload = build_official_sale_invoice_payload(frappe.get_doc("Ledgix Sale", sale.name))

		frappe.db.set_value(
			"Ledgix Customer",
			customer.name,
			{
				"buyer_ntn_cnic": "9999999-9",
				"buyer_fbr_address": "Changed Buyer Address",
			},
			update_modified=False,
		)
		frappe.db.set_value(
			"Ledgix Item Tax Profile",
			mapping.name,
			"notified_retail_price",
			999,
			update_modified=False,
		)
		frappe.db.set_value(
			"Ledgix Tax Category",
			tax_category.name,
			"default_rate",
			5,
			update_modified=False,
		)

		finalized_sale = frappe.get_doc("Ledgix Sale", sale.name)
		payload = build_official_sale_invoice_payload(finalized_sale)
		self.assertEqual(payload["buyerNTNCNIC"], original_payload["buyerNTNCNIC"])
		self.assertEqual(payload["buyerAddress"], original_payload["buyerAddress"])
		self.assertEqual(payload["items"][0]["rate"], original_payload["items"][0]["rate"])
		self.assertEqual(
			payload["items"][0]["fixedNotifiedValueOrRetailPrice"],
			original_payload["items"][0]["fixedNotifiedValueOrRetailPrice"],
		)

	def test_third_schedule_sale_requires_notified_retail_price(self):
		tax_category = make_tax_category(rate=18)
		make_tax_rate(tax_category.name, rate=18)
		configure_tax_profile(tax_category.name)
		item = make_item(selling_price=150)
		make_item_tax_profile(
			item.name,
			tax_category.name,
			tax_basis="Notified Retail Price",
			notified_retail_price=0,
		)
		customer = make_customer(customer_type="B2B", credit_limit=5000)

		with self.assertRaises(frappe.ValidationError):
			make_sale(customer.name, item.name, rate=150, sale_channel="B2B")

	def test_transaction_value_payload_does_not_emit_notified_retail_price(self):
		tax_category = make_tax_category(rate=18)
		make_tax_rate(tax_category.name, rate=18)
		configure_tax_profile(tax_category.name)
		item = make_item(selling_price=150)
		make_item_tax_profile(item.name, tax_category.name, tax_basis="Transaction Value")
		customer = make_customer(customer_type="B2B", credit_limit=5000)
		sale = make_sale(customer.name, item.name, rate=150, sale_channel="B2B", submit=True)

		payload = build_official_sale_invoice_payload(frappe.get_doc("Ledgix Sale", sale.name))
		self.assertEqual(payload["items"][0]["fixedNotifiedValueOrRetailPrice"], 0)

	def test_complete_tax_snapshot_passes_internal_fbr_readiness(self):
		sale, _customer, _mapping, _tax_category = self._third_schedule_sale()
		readiness = _validate_sale_fbr_readiness_internal(sale.name)
		self.assertTrue(readiness["valid"], readiness.get("errors"))
