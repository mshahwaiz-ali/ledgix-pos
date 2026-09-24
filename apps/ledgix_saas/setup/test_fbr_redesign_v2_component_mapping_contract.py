from __future__ import annotations

import ast
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = APP_ROOT / "setup" / "fbr_v2_component_mappings.py"
DRIVER = APP_ROOT / "migration" / "fbr_redesign_v2_component_mapping_local.py"


def _literal_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]
            if name in targets:
                return ast.literal_eval(node.value)
    raise AssertionError(f"Assignment {name} not found in {path}")


class TestFBRRedesignV2ComponentMappingContract(unittest.TestCase):
    def test_local_plan_is_exactly_the_phase1_proven_semantic_map(self):
        plan = _literal_assignment(DRIVER, "LOCAL_COMPONENT_PLAN")

        self.assertEqual(
            plan,
            (
                ("GST - LEI", "Sales Tax Applicable"),
                ("Ledgix P4 Extra Tax Payable - LEI", "Extra Tax"),
                ("Ledgix P4 Further Tax Payable - LEI", "Further Tax"),
                ("Ledgix P4 FED Payable - LEI", "FED Payable"),
                (
                    "Ledgix P4 Sales Tax Withheld - LEI",
                    "Sales Tax Withheld At Source",
                ),
            ),
        )

    def test_legacy_ledgix_sales_tax_account_is_excluded(self):
        source = DRIVER.read_text(encoding="utf-8")
        plan = _literal_assignment(DRIVER, "LOCAL_COMPONENT_PLAN")

        accounts = {account for account, _component in plan}
        self.assertNotIn("Ledgix P4 Sales Tax Payable - LEI", accounts)
        self.assertIn(
            'LEGACY_MONETARY_SALES_TAX_ACCOUNT = "Ledgix P4 Sales Tax Payable - LEI"',
            source,
        )

    def test_provisioner_is_classification_only(self):
        source = PROVISIONER.read_text(encoding="utf-8")

        for forbidden in (
            "tax_rate",
            "tax_amount",
            "default_rate",
            "per_unit",
            "calculate_taxes_and_totals",
            "erpnext_tax_foundation",
            "[LEDGIX-TAX]",
        ):
            self.assertNotIn(forbidden, source)

        self.assertIn('"account_head": row["account_head"]', source)
        self.assertIn('"component": row["component"]', source)
        self.assertIn('"active": 1', source)

    def test_provisioner_is_idempotent_and_conflict_safe_by_contract(self):
        source = PROVISIONER.read_text(encoding="utf-8")

        self.assertIn('"action": action', source)
        self.assertIn('action = "keep_existing"', source)
        self.assertIn('action = "blocked_conflict"', source)
        self.assertIn('action = "blocked_duplicate"', source)
        self.assertIn('if preview["blockers"]:', source)
        self.assertIn("doc.insert(ignore_permissions=True)", source)

    def test_account_company_and_ledger_state_are_validated(self):
        source = PROVISIONER.read_text(encoding="utf-8")

        self.assertIn('frappe.db.get_value(', source)
        self.assertIn('"Account"', source)
        self.assertIn("account.company != company", source)
        self.assertIn("cint(account.is_group)", source)
        self.assertIn("cint(account.disabled)", source)

    def test_withheld_is_explicitly_non_posting_fbr_evidence(self):
        source = PROVISIONER.read_text(encoding="utf-8")

        self.assertIn("NON_POSTING_FBR_COMPONENTS", source)
        self.assertIn('"Sales Tax Withheld At Source"', source)
        self.assertIn('"non_posting_fbr_evidence"', source)

    def test_driver_is_local_only_and_apply_requires_exact_confirmation(self):
        source = DRIVER.read_text(encoding="utf-8")

        self.assertIn("INTEGRATION_SITE", source)
        self.assertIn("_assert_safe_site()", source)
        self.assertIn(
            'APPLY_CONFIRMATION = "APPLY FBR V2 COMPONENT MAPPINGS LOCAL"',
            source,
        )
        self.assertIn("confirmation_verified", source)

    def test_no_fbr_transport_or_network_dependency(self):
        combined = (
            PROVISIONER.read_text(encoding="utf-8")
            + "\n"
            + DRIVER.read_text(encoding="utf-8")
        )

        for forbidden in (
            "requests.",
            "fbr_client",
            "fbr_transport",
            "post_invoice",
            "validate_invoice",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
