import json
from pathlib import Path

from frappe.tests.utils import FrappeTestCase


DOCTYPE_DIR = Path(__file__).resolve().parent


class TestV2SaleListView(FrappeTestCase):
    def test_sale_list_uses_business_facing_identity_and_filters(self):
        meta = json.loads((DOCTYPE_DIR / "ledgix_sale.json").read_text(encoding="utf-8"))
        fields = {field["fieldname"]: field for field in meta.get("fields", [])}

        self.assertEqual(meta.get("title_field"), "invoice_number")
        self.assertEqual(meta.get("sort_field"), "sale_date")
        self.assertEqual(meta.get("sort_order"), "DESC")

        self.assertEqual(fields["invoice_number"].get("in_standard_filter"), 1)
        self.assertEqual(fields["customer"].get("in_standard_filter"), 1)
        self.assertFalse(fields["client_sale_id"].get("in_standard_filter", 0))

        self.assertEqual(fields["grand_total"].get("in_list_view"), 1)
        self.assertFalse(fields["fbr_invoice_number"].get("in_list_view", 0))

    def test_sale_list_hides_internal_document_name(self):
        text = (DOCTYPE_DIR / "ledgix_sale_list.js").read_text(encoding="utf-8")

        self.assertIn('frappe.listview_settings["Ledgix Sale"]', text)
        self.assertIn("hide_name_column: true", text)
        self.assertIn("hide_name_filter: true", text)
