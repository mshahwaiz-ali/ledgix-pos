import json
from pathlib import Path

from frappe.tests.utils import FrappeTestCase


APP_ROOT = Path(__file__).resolve().parents[3]


class TestV2SalesReturnListView(FrappeTestCase):
    def test_sales_return_list_uses_business_facing_fields(self):
        path = APP_ROOT / "ledgix" / "doctype" / "ledgix_sales_return" / "ledgix_sales_return.json"
        meta = json.loads(path.read_text(encoding="utf-8"))
        fields = {field["fieldname"]: field for field in meta["fields"]}

        self.assertEqual(meta.get("sort_field"), "return_date")
        self.assertEqual(meta.get("sort_order"), "DESC")
        self.assertEqual(fields["original_sale"].get("label"), "Original Invoice")
        self.assertEqual(fields["customer"].get("in_standard_filter"), 1)
        self.assertEqual(fields["original_sale"].get("in_standard_filter"), 1)
        self.assertNotEqual(fields["total_amount"].get("in_list_view"), 1)
        self.assertEqual(fields["grand_total"].get("in_list_view"), 1)
        self.assertEqual(fields["fbr_status"].get("in_list_view"), 1)

    def test_return_list_hides_generic_id_filter_and_sale_links_use_invoice_title(self):
        list_path = APP_ROOT / "ledgix" / "doctype" / "ledgix_sales_return" / "ledgix_sales_return_list.js"
        list_text = list_path.read_text(encoding="utf-8")
        self.assertIn("hide_name_filter: true", list_text)

        sale_path = APP_ROOT / "ledgix" / "doctype" / "ledgix_sale" / "ledgix_sale.json"
        sale_meta = json.loads(sale_path.read_text(encoding="utf-8"))
        self.assertEqual(sale_meta.get("title_field"), "invoice_number")
        self.assertEqual(sale_meta.get("show_title_field_in_link"), 1)
