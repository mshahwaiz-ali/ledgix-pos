# Copyright (c) 2026, Ali and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_price_list,
	unique_name,
)
from ledgix_saas.api.v2_pos import complete_pos_v2_sale


class TestLedgixPOSShift(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def test_b2b_pos_checkout_is_idempotent_by_client_sale_id(self):
		price_list = make_price_list()
		item = make_item(selling_price=125, cost_price=50)
		customer = make_customer(
			customer_type="B2B",
			default_price_list=price_list.name,
			credit_limit=1000,
		)
		client_sale_id = unique_name("CLIENT-SALE")
		cart = [{"item": item.name, "qty": 1}]

		first = complete_pos_v2_sale(
			cart_items=cart,
			tenders=[],
			customer=customer.name,
			sale_channel="B2B",
			price_list=price_list.name,
			client_sale_id=client_sale_id,
		)
		second = complete_pos_v2_sale(
			cart_items=cart,
			tenders=[],
			customer=customer.name,
			sale_channel="B2B",
			price_list=price_list.name,
			client_sale_id=client_sale_id,
		)

		self.assertTrue(first["success"])
		self.assertTrue(second["success"])
		self.assertTrue(second["duplicate"])
		self.assertEqual(first["sale"], second["sale"])
		self.assertEqual(
			frappe.db.count("Ledgix Sale", filters={"client_sale_id": client_sale_id, "docstatus": 1}),
			1,
		)

	def test_retail_pos_api_requires_open_shift_before_sale_creation(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="Retail", credit_limit=0)
		client_sale_id = unique_name("RETAIL-CLIENT")

		with patch("ledgix_saas.api.v2_pos._open_shift", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				complete_pos_v2_sale(
					cart_items=[{"item": item.name, "qty": 1}],
					tenders=[],
					customer=customer.name,
					sale_channel="Retail",
					client_sale_id=client_sale_id,
				)

		self.assertFalse(frappe.db.exists("Ledgix Sale", {"client_sale_id": client_sale_id}))
