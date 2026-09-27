import json
from pathlib import Path

from frappe.tests.utils import FrappeTestCase


DOCTYPE_DIR = Path(__file__).resolve().parent


class TestV2POSShiftListView(FrappeTestCase):
    def test_pos_shift_metadata_prioritizes_reconciliation_fields(self):
        meta = json.loads((DOCTYPE_DIR / "ledgix_pos_shift.json").read_text(encoding="utf-8"))
        fields = {row["fieldname"]: row for row in meta["fields"]}

        self.assertEqual(meta.get("sort_field"), "opening_time")
        self.assertEqual(meta.get("sort_order"), "DESC")
        self.assertEqual(fields["opening_time"].get("in_standard_filter"), 1)
        self.assertEqual(fields["status"].get("in_standard_filter"), 1)
        self.assertFalse(fields["closing_time"].get("in_standard_filter", 0))

        for fieldname in (
            "opening_time",
            "closing_time",
            "expected_cash",
            "actual_cash",
            "cash_variance",
            "total_sales",
            "invoice_count",
        ):
            self.assertEqual(fields[fieldname].get("in_list_view"), 1)

        self.assertFalse(fields["opening_cash"].get("in_list_view", 0))
        self.assertFalse(fields["cash_sales"].get("in_list_view", 0))

    def test_pos_shift_list_uses_business_status_and_hides_generic_id_filter(self):
        text = (DOCTYPE_DIR / "ledgix_pos_shift_list.js").read_text(encoding="utf-8")

        self.assertIn("hide_name_filter: true", text)
        self.assertIn("has_indicator_for_draft: true", text)
        self.assertIn("has_indicator_for_cancelled: true", text)
        self.assertIn('[__("Open"), "orange", "status,=,Open"]', text)
        self.assertIn('[__("Closed"), "green", "status,=,Closed"]', text)
        self.assertIn('[__("Cancelled"), "red", "status,=,Cancelled"]', text)
