from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
BUILDER = APP / "services" / "fbr_v2_payload_builder.py"
READINESS = APP / "services" / "fbr_v2_readiness.py"


class TestFBRV2PayloadBuilderContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.readiness = READINESS.read_text(encoding="utf-8")

    def test_builder_uses_persisted_v2_readiness_only(self):
        self.assertIn("fbr_v2_readiness.evaluate_invoice_readiness", self.builder)
        self.assertIn('snapshot_source") != "persisted_v2"', self.builder)
        self.assertIn('"hash_verified"', self.builder)
        self.assertNotIn("build_snapshot_candidate", self.builder)

    def test_readiness_uses_hash_verified_persisted_snapshot(self):
        self.assertIn("fbr_v2_snapshot_persistence", self.readiness)
        self.assertIn("read_persisted_v2_snapshot", self.readiness)
        self.assertIn('"snapshot_source": "persisted_v2"', self.readiness)
        self.assertNotIn("erpnext_fbr_snapshot.build_snapshot_candidate", self.readiness)

    def test_builder_has_official_di_invoice_shape(self):
        for fieldname in (
            "invoiceType",
            "invoiceDate",
            "sellerNTNCNIC",
            "sellerBusinessName",
            "sellerProvince",
            "sellerAddress",
            "buyerNTNCNIC",
            "buyerBusinessName",
            "buyerProvince",
            "buyerAddress",
            "buyerRegistrationType",
            "invoiceRefNo",
            "items",
        ):
            self.assertIn(f'"{fieldname}"', self.builder)

    def test_builder_has_official_di_item_shape(self):
        for fieldname in (
            "hsCode",
            "productDescription",
            "rate",
            "uoM",
            "quantity",
            "totalValues",
            "valueSalesExcludingST",
            "fixedNotifiedValueOrRetailPrice",
            "salesTaxApplicable",
            "salesTaxWithheldAtSource",
            "extraTax",
            "furtherTax",
            "sroScheduleNo",
            "fedPayable",
            "discount",
            "saleType",
            "sroItemSerialNo",
        ):
            self.assertIn(f'"{fieldname}"', self.builder)

    def test_builder_does_not_depend_on_legacy_fbr_runtime(self):
        forbidden = (
            "api.fbr_payload",
            "api.fbr_settings",
            "api.taxation",
            "get_fbr_settings_internal",
            "Ledgix Item Tax Profile",
            "Ledgix Tax Profile",
            "custom_ledgix_fbr_snapshot_json",
        )
        for value in forbidden:
            self.assertNotIn(value, self.builder)

    def test_scenario_id_is_explicit_sandbox_context_only(self):
        self.assertIn("scenario_id: str | None = None", self.builder)
        self.assertIn('profile.get("mode") != "Sandbox"', self.builder)
        self.assertIn('payload["scenarioId"] = explicit_scenario', self.builder)
        self.assertNotIn('mapping.get("scenario_id")', self.builder)

    def test_return_and_sro_contracts_fail_closed(self):
        self.assertIn("FBR V2 return payload is not activated", self.builder)
        self.assertIn("SRO payload semantics are not yet Sandbox-certified", self.builder)
        self.assertNotIn('"Credit Note"', self.builder)
        self.assertNotIn('"Debit Note"', self.builder)

    def test_withheld_does_not_change_total_values(self):
        self.assertIn("sales_tax_withheld_non_posting", self.builder)
        total_block = self.builder.split("total_values = _money(", 1)[1].split(")\n", 1)[0]
        self.assertNotIn("sales_tax_withheld", total_block)

    def test_discount_uses_explicit_erpnext_evidence_and_inclusive_tax_is_not_discount(self):
        self.assertIn('line.get("discount_amount")', self.builder)
        self.assertIn('line.get("distributed_discount_amount")', self.builder)
        self.assertIn(
            "FBR V2 commercial discount payload semantics are not activated until",
            self.builder,
        )
        self.assertNotIn(
            "pre_discount_value - value_excluding_st",
            self.builder,
        )

    def test_builder_is_non_writing_and_non_networked(self):
        self.assertIn('"database_write": False', self.builder)
        self.assertIn('"fbr_network_call": False', self.builder)
        self.assertNotIn("requests.", self.builder)
        self.assertNotIn("fbr_transport", self.builder)
        self.assertNotIn("fbr_client", self.builder)
        for token in (".insert(", ".save(", ".submit(", "db_set(", "frappe.db.set_value"):
            self.assertNotIn(token, self.builder)

    def test_payload_reconciles_to_erpnext_grand_total(self):
        self.assertIn("erpnext_grand_total", self.builder)
        self.assertIn("payload_total", self.builder)
        self.assertIn("MONEY_TOLERANCE", self.builder)
        self.assertIn("do not reconcile to immutable ERPNext grand total", self.builder)


if __name__ == "__main__":
    unittest.main()
