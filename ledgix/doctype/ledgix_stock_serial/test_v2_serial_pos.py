from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
    configure_v2_test_environment,
    make_customer,
    make_item_price,
    make_price_list,
)
from ledgix_saas.api.stock_ops import manual_stock_entry
from ledgix_saas.api.v2_holds import hold_pos_v2_sale, resume_pos_v2_hold
from ledgix_saas.api.v2_inventory import get_available_pos_serials
from ledgix_saas.api.v2_pos import complete_pos_v2_sale


class TestV2SerialPOS(FrappeTestCase):
    def setUp(self):
        super().setUp()
        configure_v2_test_environment()

    def _serial_item(self):
        item_code = f"TEST-SERIAL-{uuid4().hex[:10]}"
        serials = (f"{item_code}-001", f"{item_code}-002")
        item = frappe.get_doc({
            "doctype": "Ledgix Item",
            "item_code": item_code,
            "item_name": item_code,
            "unit": "Piece",
            "tracking_type": "Serial Based",
            "cost_price": 40,
            "selling_price": 100,
            "opening_stock": 0,
            "minimum_stock": 0,
            "active": 1,
        })
        item.insert(ignore_permissions=True)
        manual_stock_entry(
            item.name,
            qty_in=len(serials),
            serial_numbers="\n".join(serials),
            note="Seed serial POS test inventory",
        )
        return item, serials

    def _b2b_context(self, item):
        price_list = make_price_list()
        make_item_price(item.name, price_list.name, 100)
        customer = make_customer(
            customer_type="B2B",
            default_price_list=price_list.name,
            credit_limit=5000,
        )
        return price_list, customer

    def _serial_status(self, item, serial_no):
        return frappe.db.get_value(
            "Ledgix Stock Serial",
            {"item": item, "serial_no": serial_no},
            "status",
        )

    def test_available_serial_endpoint_returns_only_available_item_serials(self):
        item, serials = self._serial_item()
        result = get_available_pos_serials(item.name)
        serial_numbers = {row["serial_no"] for row in result["serials"]}
        self.assertEqual(serial_numbers, set(serials))

    def test_serial_hold_preserves_selection_and_resume_revalidates(self):
        item, serials = self._serial_item()
        price_list, customer = self._b2b_context(item)

        held = hold_pos_v2_sale(
            cart_items=[{
                "item": item.name,
                "qty": 1,
                "rate": 100,
                "serial_numbers": serials[0],
            }],
            sale_channel="B2B",
            customer=customer.name,
            price_list=price_list.name,
        )
        resumed = resume_pos_v2_hold(held["hold_id"])
        self.assertEqual(resumed["cart_items"][0]["tracking_type"], "Serial Based")
        self.assertEqual(resumed["cart_items"][0]["serial_numbers"], serials[0])

    def test_serial_checkout_marks_sold_and_sale_cancel_restores_available(self):
        item, serials = self._serial_item()
        price_list, customer = self._b2b_context(item)

        result = complete_pos_v2_sale(
            cart_items=[{
                "item": item.name,
                "qty": 1,
                "serial_numbers": serials[0],
            }],
            tenders=[],
            customer=customer.name,
            sale_channel="B2B",
            price_list=price_list.name,
            client_sale_id=f"SERIAL-{uuid4().hex}",
        )
        self.assertEqual(self._serial_status(item.name, serials[0]), "Sold")
        self.assertEqual(self._serial_status(item.name, serials[1]), "Available")
        self.assertAlmostEqual(
            frappe.db.get_value("Ledgix Item", item.name, "current_stock"),
            1,
            places=6,
        )

        sale = frappe.get_doc("Ledgix Sale", result["sale"])
        sale.cancel()
        self.assertEqual(self._serial_status(item.name, serials[0]), "Available")
        self.assertAlmostEqual(
            frappe.db.get_value("Ledgix Item", item.name, "current_stock"),
            2,
            places=6,
        )

    def test_hold_rejects_serial_that_is_no_longer_available(self):
        item, serials = self._serial_item()
        price_list, customer = self._b2b_context(item)
        result = complete_pos_v2_sale(
            cart_items=[{
                "item": item.name,
                "qty": 1,
                "serial_numbers": serials[0],
            }],
            tenders=[],
            customer=customer.name,
            sale_channel="B2B",
            price_list=price_list.name,
            client_sale_id=f"SERIAL-SOLD-{uuid4().hex}",
        )
        self.assertTrue(result["success"])
        self.assertEqual(self._serial_status(item.name, serials[0]), "Sold")

        with self.assertRaises(frappe.ValidationError):
            hold_pos_v2_sale(
                cart_items=[{
                    "item": item.name,
                    "qty": 1,
                    "rate": 100,
                    "serial_numbers": serials[0],
                }],
                sale_channel="B2B",
                customer=customer.name,
                price_list=price_list.name,
            )
