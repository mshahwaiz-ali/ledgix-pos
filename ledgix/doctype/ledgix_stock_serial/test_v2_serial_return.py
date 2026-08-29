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
from ledgix_saas.api.v2_pos import complete_pos_v2_sale
from ledgix_saas.api.v2_returns import create_pos_v2_return, get_pos_v2_return_context


class TestV2SerialReturn(FrappeTestCase):
    def setUp(self):
        super().setUp()
        configure_v2_test_environment()

    def _sale_serial_item(self):
        code = f"TEST-SERIAL-RETURN-{uuid4().hex[:8]}"
        serials = (f"{code}-001", f"{code}-002")
        item = frappe.get_doc({
            "doctype": "Ledgix Item",
            "item_code": code,
            "item_name": code,
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
            qty_in=2,
            serial_numbers="\n".join(serials),
            note="Seed serial return test",
        )
        price_list = make_price_list()
        make_item_price(item.name, price_list.name, 100)
        customer = make_customer(
            customer_type="B2B",
            default_price_list=price_list.name,
            credit_limit=5000,
        )
        sale = complete_pos_v2_sale(
            cart_items=[{
                "item": item.name,
                "qty": 2,
                "serial_numbers": "\n".join(serials),
            }],
            tenders=[],
            customer=customer.name,
            sale_channel="B2B",
            price_list=price_list.name,
            client_sale_id=f"SERIAL-RETURN-{uuid4().hex}",
        )
        return item, customer, frappe.get_doc("Ledgix Sale", sale["sale"]), serials

    def _status(self, item, serial_no):
        return frappe.db.get_value(
            "Ledgix Stock Serial",
            {"item": item, "serial_no": serial_no},
            "status",
        )

    def test_serial_return_context_exposes_original_serial_identity(self):
        item, _customer, sale, serials = self._sale_serial_item()
        context = get_pos_v2_return_context(sale.name)
        row = context["items"][0]
        returned_serials = set(str(row.get("serial_numbers") or "").replace(",", "\n").split())
        self.assertEqual(returned_serials, set(serials))
        self.assertEqual(self._status(item.name, serials[0]), "Sold")

    def test_partial_serial_return_restores_exact_selected_serial(self):
        item, _customer, sale, serials = self._sale_serial_item()
        result = create_pos_v2_return(
            original_sale=sale.name,
            return_items=[{
                "item": item.name,
                "original_sale_item_row": sale.items[0].name,
                "qty": 1,
                "serial_numbers": serials[0],
            }],
            reason="Customer returned exact serialized unit",
        )

        self.assertTrue(result["success"])
        self.assertEqual(self._status(item.name, serials[0]), "Available")
        self.assertEqual(self._status(item.name, serials[1]), "Sold")
        return_doc = frappe.get_doc("Ledgix Sales Return", result["return_id"])
        self.assertEqual(return_doc.items[0].serial_numbers.strip(), serials[0])

    def test_serial_return_rejects_serial_not_sold_on_original_sale(self):
        item, _customer, sale, _serials = self._sale_serial_item()
        unrelated_serial = f"{item.name}-OTHER-{uuid4().hex[:8]}"
        manual_stock_entry(
            item.name,
            qty_in=1,
            serial_numbers=unrelated_serial,
            note="Seed unrelated serial",
        )
        with self.assertRaises(frappe.ValidationError):
            create_pos_v2_return(
                original_sale=sale.name,
                return_items=[{
                    "item": item.name,
                    "original_sale_item_row": sale.items[0].name,
                    "qty": 1,
                    "serial_numbers": unrelated_serial,
                }],
                reason="Attempt wrong serial",
            )
