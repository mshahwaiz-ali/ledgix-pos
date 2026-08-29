import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_item_price,
	make_price_list,
)
from ledgix_saas.services.pricing import resolve_item_price, resolve_price_list


class TestLedgixItemPrice(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def test_b2b_customer_price_list_wins_over_default_retail(self):
		retail = make_price_list(default_retail=True, priority=-100)
		b2b = make_price_list()
		item = make_item(selling_price=90)
		make_item_price(item.name, retail.name, 120)
		b2b_price = make_item_price(item.name, b2b.name, 95)
		customer = make_customer(customer_type="B2B", default_price_list=b2b.name)

		self.assertEqual(resolve_price_list(customer.name, None, "B2B"), b2b.name)
		result = resolve_item_price(item.name, customer=customer.name, sale_channel="B2B")

		self.assertEqual(result["price_list"], b2b.name)
		self.assertEqual(result["item_price_reference"], b2b_price.name)
		self.assertAlmostEqual(result["list_rate"], 95, places=2)
		self.assertAlmostEqual(result["rate"], 95, places=2)
		self.assertFalse(result["price_override"])

	def test_explicit_price_list_has_highest_precedence(self):
		retail = make_price_list(default_retail=True, priority=-100)
		b2b = make_price_list()
		item = make_item(selling_price=90)
		retail_price = make_item_price(item.name, retail.name, 125)
		make_item_price(item.name, b2b.name, 95)
		customer = make_customer(customer_type="B2B", default_price_list=b2b.name)

		result = resolve_item_price(
			item.name,
			customer=customer.name,
			price_list=retail.name,
			sale_channel="B2B",
		)

		self.assertEqual(result["price_list"], retail.name)
		self.assertEqual(result["item_price_reference"], retail_price.name)
		self.assertAlmostEqual(result["rate"], 125, places=2)

	def test_future_item_price_is_ignored_and_legacy_rate_is_fallback(self):
		price_list = make_price_list()
		item = make_item(selling_price=77)
		customer = make_customer(customer_type="B2B", default_price_list=price_list.name)
		make_item_price(
			item.name,
			price_list.name,
			120,
			effective_from=add_days(today(), 1),
		)

		result = resolve_item_price(
			item.name,
			customer=customer.name,
			sale_channel="B2B",
			transaction_date=today(),
		)

		self.assertIsNone(result["item_price_reference"])
		self.assertAlmostEqual(result["list_rate"], 77, places=2)
		self.assertAlmostEqual(result["rate"], 77, places=2)

	def test_price_override_requires_authority_and_reason(self):
		price_list = make_price_list(default_retail=True, priority=-100)
		item = make_item(selling_price=100)
		make_item_price(item.name, price_list.name, 100)

		with self.assertRaises(frappe.ValidationError):
			resolve_item_price(
				item.name,
				price_list=price_list.name,
				requested_rate=80,
				allow_override=True,
				override_reason="",
			)

		result = resolve_item_price(
			item.name,
			price_list=price_list.name,
			requested_rate=80,
			allow_override=True,
			override_reason="Manager-approved promotion",
		)
		self.assertTrue(result["price_override"])
		self.assertAlmostEqual(result["rate"], 80, places=2)
		self.assertEqual(result["price_override_reason"], "Manager-approved promotion")

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.ValidationError):
				resolve_item_price(
					item.name,
					price_list=price_list.name,
					requested_rate=70,
					allow_override=True,
					override_reason="Unauthorized override",
				)
		finally:
			frappe.set_user("Administrator")
