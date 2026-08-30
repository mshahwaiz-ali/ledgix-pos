import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
    configure_v2_test_environment,
    make_customer,
    make_item,
    make_sale,
)
from ledgix_saas.api import brand as brand_api
from ledgix_saas.api.printing import get_fbr_qr_data_uri


class TestV2PrintFormats(FrappeTestCase):
    def setUp(self):
        super().setUp()
        configure_v2_test_environment()

    def _set_brand_identity(self, name, address, ntn, strn="STRN-PRINT"):
        frappe.db.set_single_value("Ledgix Brand Settings", "legal_business_name", name)
        frappe.db.set_single_value("Ledgix Brand Settings", "business_address", address)
        frappe.db.set_single_value("Ledgix Brand Settings", "business_phone", "+92-300-0000000")
        frappe.db.set_single_value("Ledgix Brand Settings", "business_email", "billing@example.com")
        frappe.db.set_single_value("Ledgix Brand Settings", "ntn", ntn)
        frappe.db.set_single_value("Ledgix Brand Settings", "strn", strn)
        frappe.clear_cache(doctype="Ledgix Brand Settings")

    def test_thermal_and_b2b_print_formats_render_from_submitted_sale(self):
        self._set_brand_identity("Original Seller Pvt Ltd", "Original Seller Address", "1234567")
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
        sale.reload()

        self.assertEqual(sale.seller_name_snapshot, "Original Seller Pvt Ltd")
        self.assertEqual(sale.seller_address_snapshot, "Original Seller Address")
        self.assertEqual(sale.seller_ntn_cnic_snapshot, "1234567")

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
        self.assertIn("Original Seller Pvt Ltd", thermal)
        self.assertIn("Original Seller Address", thermal)
        self.assertIn('<div class="shop-name">', thermal)
        self.assertNotIn("<divclass=", thermal)
        self.assertIn(sale.invoice_number, invoice)
        self.assertIn(customer.customer_name, invoice)
        self.assertIn("Original Seller Pvt Ltd", invoice)
        self.assertIn("Total", invoice)

    def test_submit_refreshes_draft_seller_snapshot_before_finalization(self):
        self._set_brand_identity("Draft Seller Ltd", "Draft Address", "1111111")
        item = make_item(selling_price=100, cost_price=40, opening_stock=5)
        customer = make_customer(customer_type="B2B", credit_limit=5000)
        sale = make_sale(customer.name, item.name, rate=100, sale_channel="B2B", submit=False)
        self.assertEqual(sale.seller_name_snapshot, "Draft Seller Ltd")

        self._set_brand_identity("Submit Seller Ltd", "Submit Address", "2222222")
        sale.submit()
        sale.reload()

        self.assertEqual(sale.seller_name_snapshot, "Submit Seller Ltd")
        self.assertEqual(sale.seller_address_snapshot, "Submit Address")
        self.assertEqual(sale.seller_ntn_cnic_snapshot, "2222222")

    def test_reprint_keeps_original_seller_legal_identity_after_brand_edit(self):
        self._set_brand_identity("Frozen Seller Ltd", "Frozen Address", "7654321", "STRN-FROZEN")
        item = make_item(selling_price=100, cost_price=40, opening_stock=5)
        customer = make_customer(customer_type="B2B", credit_limit=5000)
        sale = make_sale(customer.name, item.name, rate=100, sale_channel="B2B", submit=True)
        sale.reload()

        self.assertEqual(sale.seller_name_snapshot, "Frozen Seller Ltd")
        self.assertEqual(sale.seller_address_snapshot, "Frozen Address")
        self.assertEqual(sale.seller_ntn_cnic_snapshot, "7654321")
        self.assertEqual(sale.seller_strn_snapshot, "STRN-FROZEN")

        self._set_brand_identity("Changed Seller Ltd", "Changed Address", "9999999", "STRN-CHANGED")

        persisted = frappe.db.get_value(
            "Ledgix Sale",
            sale.name,
            [
                "seller_name_snapshot",
                "seller_address_snapshot",
                "seller_ntn_cnic_snapshot",
                "seller_strn_snapshot",
            ],
            as_dict=True,
        )
        self.assertEqual(persisted.seller_name_snapshot, "Frozen Seller Ltd")
        self.assertEqual(persisted.seller_address_snapshot, "Frozen Address")
        self.assertEqual(persisted.seller_ntn_cnic_snapshot, "7654321")
        self.assertEqual(persisted.seller_strn_snapshot, "STRN-FROZEN")

        thermal = frappe.get_print("Ledgix Sale", sale.name, print_format="Ledgix Thermal Receipt")
        invoice = frappe.get_print("Ledgix Sale", sale.name, print_format="Ledgix B2B Invoice")

        for rendered in (thermal, invoice):
            self.assertIn("Frozen Seller Ltd", rendered)
            self.assertIn("Frozen Address", rendered)
            self.assertIn("7654321", rendered)
            self.assertNotIn("Changed Seller Ltd", rendered)
            self.assertNotIn("Changed Address", rendered)

    def test_receipt_and_invoice_use_frozen_item_identity(self):
        self._set_brand_identity("Item Snapshot Seller", "Snapshot Address", "1234567")
        item = make_item(selling_price=1900, cost_price=900, opening_stock=5)
        frappe.db.set_value(
            "Ledgix Item",
            item.name,
            {"item_name": "Akhrot Halwa", "unit": "Kg"},
            update_modified=False,
        )
        customer = make_customer(customer_type="B2B", credit_limit=5000)
        sale = make_sale(customer.name, item.name, rate=1900, sale_channel="B2B", submit=True)
        sale.reload()

        row = sale.items[0]
        self.assertEqual(row.item_name_snapshot, "Akhrot Halwa")
        self.assertEqual(row.item_code_snapshot, item.name)
        self.assertEqual(row.unit_snapshot, "Kg")

        frappe.db.set_value(
            "Ledgix Item",
            item.name,
            {"item_name": "Renamed Halwa", "unit": "Pack"},
            update_modified=False,
        )

        thermal = frappe.get_print("Ledgix Sale", sale.name, print_format="Ledgix Thermal Receipt")
        invoice = frappe.get_print("Ledgix Sale", sale.name, print_format="Ledgix B2B Invoice")

        for rendered in (thermal, invoice):
            self.assertIn("Akhrot Halwa", rendered)
            self.assertIn(item.name, rendered)
            self.assertIn("Kg", rendered)
            self.assertNotIn("Renamed Halwa", rendered)

    def test_fbr_invoice_qr_is_rendered_from_unique_invoice_number(self):
        self._set_brand_identity("QR Seller Ltd", "QR Address", "1234567")
        item = make_item(selling_price=100, cost_price=40, opening_stock=5)
        customer = make_customer(customer_type="B2B", credit_limit=5000)
        sale = make_sale(customer.name, item.name, rate=100, sale_channel="B2B", submit=True)
        fbr_invoice_number = "7000007DI1747119701593"
        frappe.db.set_value(
            "Ledgix Sale",
            sale.name,
            {"fbr_invoice_number": fbr_invoice_number, "fbr_status": "Submitted"},
            update_modified=False,
        )

        expected_qr = get_fbr_qr_data_uri(fbr_invoice_number)
        self.assertTrue(expected_qr.startswith("data:image/svg+xml;base64,"))

        thermal = frappe.get_print("Ledgix Sale", sale.name, print_format="Ledgix Thermal Receipt")
        invoice = frappe.get_print("Ledgix Sale", sale.name, print_format="Ledgix B2B Invoice")

        for rendered in (thermal, invoice):
            self.assertIn(fbr_invoice_number, rendered)
            self.assertIn(expected_qr, rendered)
            self.assertIn("FBR Digital Invoicing System", rendered)

    def test_empty_logo_fields_use_bundled_ledgix_lockup_in_prints(self):
        self._set_brand_identity("Fallback Logo Seller", "Fallback Address", "1234567")
        for fieldname in ("symbol_logo", "full_logo", "favicon"):
            frappe.db.set_single_value("Ledgix Brand Settings", fieldname, "")
        frappe.clear_cache(doctype="Ledgix Brand Settings")

        item = make_item(selling_price=100, cost_price=40, opening_stock=5)
        customer = make_customer(customer_type="B2B", credit_limit=5000)
        sale = make_sale(customer.name, item.name, rate=100, sale_channel="B2B", submit=True)

        thermal = frappe.get_print("Ledgix Sale", sale.name, print_format="Ledgix Thermal Receipt")
        invoice = frappe.get_print("Ledgix Sale", sale.name, print_format="Ledgix B2B Invoice")

        for rendered in (thermal, invoice):
            self.assertIn(brand_api.DEFAULT_FULL_LOGO, rendered)
