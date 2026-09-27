import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _meta():
	return json.loads((ROOT / "ledgix_customer.json").read_text(encoding="utf-8"))


def _fields():
	return {row["fieldname"]: row for row in _meta()["fields"]}


class TestCustomerExperience(unittest.TestCase):
	def test_customer_list_is_business_first(self):
		meta = _meta()
		fields = _fields()

		self.assertEqual(meta["title_field"], "customer_name")
		self.assertEqual(meta["sort_field"], "customer_name")
		self.assertEqual(meta["sort_order"], "ASC")
		self.assertEqual(fields["customer_name"].get("in_standard_filter"), 1)
		self.assertEqual(fields["mobile_number"].get("in_standard_filter"), 1)
		self.assertEqual(fields["outstanding_amount"].get("in_list_view"), 1)
		self.assertEqual(fields["available_credit"].get("in_list_view"), 1)
		self.assertFalse(fields["buyer_ntn_cnic"].get("in_list_view"))
		self.assertFalse(fields["buyer_registration_type"].get("in_list_view"))

	def test_customer_form_groups_operational_and_compliance_details(self):
		meta = _meta()
		fields = _fields()

		self.assertEqual(fields["receivables_section"].get("collapsible"), 1)
		self.assertEqual(fields["fbr_buyer_details_section"].get("collapsible"), 1)
		self.assertEqual(fields["mobile_number"].get("allow_in_quick_entry"), 1)
		self.assertEqual(fields["customer_type"].get("allow_in_quick_entry"), 1)
		self.assertIn("mobile_number", meta["search_fields"])
		self.assertIn("buyer_ntn_cnic", meta["search_fields"])

	def test_customer_list_hides_internal_name_and_uses_activity_indicator(self):
		source = (ROOT / "ledgix_customer_list.js").read_text(encoding="utf-8")

		self.assertIn("hide_name_filter: true", source)
		self.assertIn("hide_name_column: true", source)
		self.assertIn('__("Active")', source)
		self.assertIn('__("Inactive")', source)
