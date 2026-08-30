import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from ledgix.doctype.v2_test_utils import (
	configure_tax_profile,
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_item_tax_profile,
	make_sale,
	make_tax_category,
	make_tax_rate,
	unique_name,
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
		self.assertEqual(sale.seller_name_snapshot, "Ledgix Test Seller")
		self.assertEqual(sale.seller_ntn_cnic_snapshot, "1234567")
		self.assertEqual(sale.seller_province_snapshot, "Punjab")
		self.assertEqual(sale.seller_address_snapshot, "Test Seller Address")

		payload = build_official_sale_invoice_payload(sale)
		self.assertEqual(payload["sellerBusinessName"], "Ledgix Test Seller")
		self.assertEqual(payload["sellerNTNCNIC"], "1234567")
		self.assertEqual(payload["buyerBusinessName"], customer.customer_name)
		self.assertEqual(payload["buyerNTNCNIC"], "12345678")
		self.assertEqual(payload["items"][0]["rate"], "18%")
		self.assertAlmostEqual(payload["items"][0]["fixedNotifiedValueOrRetailPrice"], 200, places=2)

	def test_finalized_fbr_payload_is_immune_to_seller_buyer_and_tax_master_edits(self):
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
		frappe.db.set_single_value("Ledgix FBR Settings", "seller_ntn_cnic", "9999999")
		frappe.db.set_single_value("Ledgix FBR Settings", "seller_business_name", "Changed Seller")
		frappe.db.set_single_value("Ledgix FBR Settings", "seller_province", "Sindh")
		frappe.db.set_single_value("Ledgix FBR Settings", "seller_address", "Changed Seller Address")
		frappe.db.set_single_value("Ledgix Brand Settings", "legal_business_name", "Changed Brand Legal Name")
		frappe.db.set_single_value("Ledgix Brand Settings", "ntn", "8888888")
		frappe.clear_cache(doctype="Ledgix FBR Settings")
		frappe.clear_cache(doctype="Ledgix Brand Settings")

		finalized_sale = frappe.get_doc("Ledgix Sale", sale.name)
		payload = build_official_sale_invoice_payload(finalized_sale)
		self.assertEqual(payload["sellerBusinessName"], original_payload["sellerBusinessName"])
		self.assertEqual(payload["sellerNTNCNIC"], original_payload["sellerNTNCNIC"])
		self.assertEqual(payload["sellerProvince"], original_payload["sellerProvince"])
		self.assertEqual(payload["sellerAddress"], original_payload["sellerAddress"])
		self.assertEqual(payload["buyerNTNCNIC"], original_payload["buyerNTNCNIC"])
		self.assertEqual(payload["buyerAddress"], original_payload["buyerAddress"])
		self.assertEqual(payload["items"][0]["rate"], original_payload["items"][0]["rate"])
		self.assertEqual(
			payload["items"][0]["fixedNotifiedValueOrRetailPrice"],
			original_payload["items"][0]["fixedNotifiedValueOrRetailPrice"],
		)

	def test_fbr_rate_description_and_special_tax_components_are_frozen(self):
		tax_category = make_tax_category(rate=18)
		make_tax_rate(tax_category.name, rate=18)
		configure_tax_profile(tax_category.name, price_includes_tax=False)
		item = make_item(selling_price=100, cost_price=50)
		mapping = make_item_tax_profile(
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
		sale.reload()

		row = sale.tax_details[0]
		self.assertEqual(row.fbr_rate_description, "18% along with rupees 60 per kilogram")
		self.assertAlmostEqual(row.tax_amount, 36, places=2)
		self.assertAlmostEqual(row.sales_tax_withheld_at_source, 4, places=2)
		self.assertAlmostEqual(row.extra_tax, 6, places=2)
		self.assertAlmostEqual(row.further_tax, 8, places=2)
		self.assertAlmostEqual(row.fed_payable, 10, places=2)
		self.assertAlmostEqual(sale.tax_amount, 60, places=2)
		self.assertAlmostEqual(sale.grand_total, 260, places=2)

		before = build_official_sale_invoice_payload(sale)["items"][0]
		self.assertEqual(before["rate"], "18% along with rupees 60 per kilogram")
		self.assertAlmostEqual(before["salesTaxApplicable"], 36, places=2)
		self.assertAlmostEqual(before["salesTaxWithheldAtSource"], 4, places=2)
		self.assertAlmostEqual(before["extraTax"], 6, places=2)
		self.assertAlmostEqual(before["furtherTax"], 8, places=2)
		self.assertAlmostEqual(before["fedPayable"], 10, places=2)
		self.assertAlmostEqual(before["totalValues"], 260, places=2)

		frappe.db.set_value(
			"Ledgix Item Tax Profile",
			mapping.name,
			{
				"fbr_rate_description": "Changed",
				"sales_tax_withheld_at_source_per_unit": 99,
				"extra_tax_per_unit": 99,
				"further_tax_per_unit": 99,
				"fed_payable_per_unit": 99,
			},
			update_modified=False,
		)
		after = build_official_sale_invoice_payload(frappe.get_doc("Ledgix Sale", sale.name))["items"][0]
		self.assertEqual(after, before)

	def test_buyer_snapshot_uses_tax_profile_fallbacks(self):
		tax_category = make_tax_category(rate=18)
		make_tax_rate(tax_category.name, rate=18)
		configure_tax_profile(tax_category.name)
		item = make_item(selling_price=150)
		make_item_tax_profile(item.name, tax_category.name, tax_basis="Transaction Value")

		customer_name = unique_name("FBR-FALLBACK-CUSTOMER")
		customer = frappe.get_doc({
			"doctype": "Ledgix Customer",
			"customer_name": customer_name,
			"customer_type": "B2B",
			"credit_limit": 5000,
			"buyer_registration_type": "Unregistered",
			"buyer_province": "",
			"buyer_fbr_address": "",
			"address_line_1": "",
			"city": "",
			"is_active": 1,
		})
		customer.insert(ignore_permissions=True)

		sale = make_sale(customer.name, item.name, rate=150, sale_channel="B2B", submit=True)
		sale.reload()
		self.assertEqual(sale.buyer_province_snapshot, "Punjab")
		self.assertEqual(sale.buyer_address_snapshot, "Test Outlet")
		self.assertEqual(sale.buyer_registration_type_snapshot, "Unregistered")

		payload = build_official_sale_invoice_payload(sale)
		self.assertEqual(payload["buyerProvince"], "Punjab")
		self.assertEqual(payload["buyerAddress"], "Test Outlet")
		self.assertEqual(payload["buyerRegistrationType"], "Unregistered")

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

	def test_sandbox_rejects_invoice_with_mixed_scenario_ids(self):
		tax_category = make_tax_category(rate=18)
		make_tax_rate(tax_category.name, rate=18)
		configure_tax_profile(tax_category.name)
		item_one = make_item(selling_price=100)
		item_two = make_item(selling_price=100)
		make_item_tax_profile(item_one.name, tax_category.name, scenario_id="SN001")
		make_item_tax_profile(item_two.name, tax_category.name, scenario_id="SN002")
		customer = make_customer(customer_type="B2B", credit_limit=5000)

		sale = frappe.get_doc({
			"doctype": "Ledgix Sale",
			"customer": customer.name,
			"sale_channel": "B2B",
			"sale_date": today(),
		})
		for item in (item_one, item_two):
			sale.append("items", {
				"item": item.name,
				"quantity": 1,
				"list_rate": 100,
				"rate": 100,
				"cost_price": item.cost_price,
			})
		sale.insert(ignore_permissions=True)
		sale.submit()

		frappe.db.set_single_value("Ledgix FBR Settings", "mode", "Sandbox")
		frappe.db.set_single_value("Ledgix FBR Settings", "enabled", 0)
		frappe.clear_cache(doctype="Ledgix FBR Settings")
		readiness = _validate_sale_fbr_readiness_internal(sale.name)

		self.assertFalse(readiness["valid"])
		self.assertTrue(
			any("multiple scenario ids" in message.lower() for message in readiness.get("errors") or []),
			readiness.get("errors"),
		)
