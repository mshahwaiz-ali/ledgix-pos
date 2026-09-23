from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = APP_ROOT / "ledgix" / "doctype"


def _schema(folder: str, filename: str) -> dict:
    return json.loads((DOCTYPE_ROOT / folder / filename).read_text(encoding="utf-8"))


class TestFBRRedesignPhase2SchemaContract(unittest.TestCase):
    def test_integration_profile_is_company_scoped_and_tokens_are_passwords(self):
        schema = _schema(
            "ledgix_fbr_integration_profile",
            "ledgix_fbr_integration_profile.json",
        )
        fields = {row["fieldname"]: row for row in schema["fields"]}

        self.assertEqual(fields["company"]["options"], "Company")
        self.assertEqual(fields["company"].get("unique"), 1)
        self.assertEqual(fields["sandbox_token"]["fieldtype"], "Password")
        self.assertEqual(fields["production_token"]["fieldtype"], "Password")
        self.assertIn("business_natures", fields)
        self.assertEqual(
            fields["business_natures"]["options"],
            "Ledgix FBR Business Nature",
        )
        self.assertIn("sector", fields)
        self.assertIn("provider_type", fields)
        self.assertIn("production_post_armed", fields)

        for duplicate_seller_field in (
            "seller_ntn_cnic",
            "seller_business_name",
            "seller_province",
            "seller_address",
        ):
            self.assertNotIn(duplicate_seller_field, fields)

    def test_item_mapping_is_fbr_classification_not_tax_engine(self):
        schema = _schema(
            "ledgix_fbr_item_mapping",
            "ledgix_fbr_item_mapping.json",
        )
        fields = {row["fieldname"]: row for row in schema["fields"]}

        for required in (
            "company",
            "erpnext_item",
            "hs_code",
            "fbr_uom",
            "sales_type",
            "fbr_rate_description",
            "tax_basis",
            "notified_retail_price",
            "sro_schedule_number",
            "sro_item_serial_number",
        ):
            self.assertIn(required, fields)

        for forbidden in (
            "scenario_id",
            "tax_category",
            "taxable",
            "default_tax_rate",
            "tax_rate",
            "sales_tax_withheld_at_source_per_unit",
            "extra_tax_per_unit",
            "further_tax_per_unit",
            "fed_payable_per_unit",
        ):
            self.assertNotIn(forbidden, fields)

    def test_tax_component_mapping_has_no_amount_or_rate_authority(self):
        schema = _schema(
            "ledgix_fbr_tax_component_mapping",
            "ledgix_fbr_tax_component_mapping.json",
        )
        fields = {row["fieldname"]: row for row in schema["fields"]}

        self.assertEqual(fields["account_head"]["options"], "Account")
        self.assertIn("component", fields)
        self.assertIn("active", fields)

        for forbidden in (
            "rate",
            "tax_rate",
            "amount",
            "tax_amount",
            "per_unit",
            "default_rate",
        ):
            self.assertNotIn(forbidden, fields)

    def test_reference_data_models_official_reference_families(self):
        schema = _schema(
            "ledgix_fbr_reference_data",
            "ledgix_fbr_reference_data.json",
        )
        fields = {row["fieldname"]: row for row in schema["fields"]}
        options = set(fields["reference_type"]["options"].splitlines())

        self.assertTrue(
            {
                "Province",
                "Document Type",
                "Transaction Type",
                "UOM",
                "Rate",
                "HS-UOM",
                "SRO Schedule",
                "SRO Item",
                "Registration Type",
            }.issubset(options)
        )
        self.assertIn("source_endpoint", fields)
        self.assertIn("fetched_at", fields)
        self.assertIn("payload_json", fields)

    def test_sandbox_scenarios_live_in_certification_not_item_mapping(self):
        certification = _schema(
            "ledgix_fbr_sandbox_certification",
            "ledgix_fbr_sandbox_certification.json",
        )
        cert_fields = {row["fieldname"]: row for row in certification["fields"]}
        self.assertEqual(
            cert_fields["scenarios"]["options"],
            "Ledgix FBR Sandbox Scenario",
        )

        scenario = _schema(
            "ledgix_fbr_sandbox_scenario",
            "ledgix_fbr_sandbox_scenario.json",
        )
        scenario_fields = {row["fieldname"]: row for row in scenario["fields"]}
        self.assertIn("scenario_id", scenario_fields)
        self.assertIn("validation_log", scenario_fields)
        self.assertIn("post_log", scenario_fields)
        self.assertIn("fbr_invoice_number", scenario_fields)

    def test_phase2_schema_is_additive_and_not_wired_into_current_runtime(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        for doctype in (
            "Ledgix FBR Integration Profile",
            "Ledgix FBR Item Mapping",
            "Ledgix FBR Tax Component Mapping",
            "Ledgix FBR Reference Data",
            "Ledgix FBR Sandbox Certification",
        ):
            self.assertNotIn(doctype, hooks)

        settings = (APP_ROOT / "api" / "fbr_settings.py").read_text(encoding="utf-8")
        self.assertIn('SETTINGS_DOCTYPE = "Ledgix FBR Settings"', settings)
        self.assertNotIn('SETTINGS_DOCTYPE = "Ledgix FBR Integration Profile"', settings)


if __name__ == "__main__":
    unittest.main()
