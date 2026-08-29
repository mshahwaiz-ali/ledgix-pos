import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
    configure_v2_test_environment,
    make_customer,
    make_item,
    make_sale,
)


class TestV2PrintFormats(FrappeTestCase):
    def setUp(self):
        super().setUp()
        configure_v2_test_environment()

    def test_thermal_and_b2b_print_formats_render_from_submitted_sale(self):
        item = make_item(selling_price=125, cost_price=50, opening_stock=10)
        customer = make_customer(customer_type="B2B", credit_limit=5000)
        sale = make_sale(
            customer.name,
            item.name,
            quantity=2,
            rate=125,
            sale_channel="B2B",
            submit=True,
        )

        thermal = frappe.get_print(
            "Ledgix Sale",
            sale.name,
            print_format="Ledgix Thermal Receipt",
        )
        invoice = frappe.get_print(
            "Ledgix Sale",
            sale.name,
            print_format="Ledgix B2B Invoice",
        )

        self.assertIn(sale.invoice_number, thermal)
        self.assertIn(item.item_name, thermal)
        self.assertIn(sale.invoice_number, invoice)
        self.assertIn(customer.customer_name, invoice)
        self.assertIn("Total", invoice)
