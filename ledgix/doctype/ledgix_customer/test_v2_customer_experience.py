import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _meta():
	return json.loads((ROOT / "ledgix_customer.json").read_text(encoding="utf-8"))


def _fields():
	return {row["fieldname"]: row for row in _meta()["fields"]}


def test_customer_list_is_business_first():
	meta = _meta()
	fields = _fields()

	assert meta["title_field"] == "customer_name"
	assert meta["sort_field"] == "customer_name"
	assert meta["sort_order"] == "ASC"
	assert fields["customer_name"].get("in_standard_filter") == 1
	assert fields["mobile_number"].get("in_standard_filter") == 1
	assert fields["outstanding_amount"].get("in_list_view") == 1
	assert fields["available_credit"].get("in_list_view") == 1
	assert not fields["buyer_ntn_cnic"].get("in_list_view")
	assert not fields["buyer_registration_type"].get("in_list_view")


def test_customer_form_groups_operational_and_compliance_details():
	meta = _meta()
	fields = _fields()

	assert fields["receivables_section"].get("collapsible") == 1
	assert fields["fbr_buyer_details_section"].get("collapsible") == 1
	assert fields["mobile_number"].get("allow_in_quick_entry") == 1
	assert fields["customer_type"].get("allow_in_quick_entry") == 1
	assert "mobile_number" in meta["search_fields"]
	assert "buyer_ntn_cnic" in meta["search_fields"]


def test_customer_list_hides_internal_name_and_uses_activity_indicator():
	source = (ROOT / "ledgix_customer_list.js").read_text(encoding="utf-8")

	assert "hide_name_filter: true" in source
	assert "hide_name_column: true" in source
	assert '__("Active")' in source
	assert '__("Inactive")' in source
