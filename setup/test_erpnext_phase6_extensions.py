import unittest
from pathlib import Path

from ledgix_saas.setup import erpnext_phase6_extensions


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]


class TestERPNextPhase6ExtensionContract(unittest.TestCase):
    def test_phase6_extensions_only_target_native_financial_documents(self):
        self.assertEqual(
            set(erpnext_phase6_extensions.CUSTOM_FIELDS),
            {"Sales Invoice", "Payment Entry"},
        )

    def test_phase6_extensions_do_not_duplicate_erpnext_money_fields(self):
        forbidden = {
            "grand_total",
            "net_total",
            "outstanding_amount",
            "paid_amount",
            "received_amount",
            "allocated_amount",
            "total_taxes_and_charges",
        }
        fieldnames = {
            row["fieldname"]
            for rows in erpnext_phase6_extensions.CUSTOM_FIELDS.values()
            for row in rows
        }
        self.assertFalse(forbidden.intersection(fieldnames))
        self.assertTrue(all(name.startswith("custom_ledgix_") for name in fieldnames))

    def test_phase6_sales_invoice_metadata_contract(self):
        fields = {
            row["fieldname"]: row
            for row in erpnext_phase6_extensions.CUSTOM_FIELDS["Sales Invoice"]
        }
        self.assertTrue(
            {
                "custom_ledgix_sale_channel",
                "custom_ledgix_client_return_id",
                "custom_ledgix_exchange_reference",
                "custom_ledgix_checkout_source",
                "custom_ledgix_price_override_json",
            }.issubset(fields)
        )
        audit = fields["custom_ledgix_price_override_json"]
        self.assertEqual(audit.get("read_only"), 1)
        self.assertEqual(audit.get("no_copy"), 1)
        self.assertEqual(audit.get("allow_on_submit"), 1)

    def test_phase6_payment_entry_metadata_contract(self):
        fieldnames = {
            row["fieldname"]
            for row in erpnext_phase6_extensions.CUSTOM_FIELDS["Payment Entry"]
        }
        self.assertTrue(
            {
                "custom_ledgix_client_payment_id",
                "custom_ledgix_payment_source",
                "custom_ledgix_reversal_reason",
            }.issubset(fieldnames)
        )

    def test_phase6_hooks_install_schema_and_compatibility_routes(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("ledgix_saas.setup.erpnext_phase6_extensions.after_migrate", hooks)

        # Phase 6 owns the native B2B financial compatibility routes. Retail POS
        # entry points are intentionally superseded by Phase 8 and are covered by
        # the Phase 8 contract suite, so this regression test must not pin the old
        # pre-Phase-8 POS routing implementation.
        self.assertIn(
            '"ledgix_saas.api.selling.preview_b2b_invoice": "ledgix_saas.api.selling_compat.preview_b2b_invoice"',
            hooks,
        )
        self.assertIn(
            '"ledgix_saas.api.selling.create_b2b_invoice": "ledgix_saas.api.selling_compat.create_b2b_invoice"',
            hooks,
        )
        self.assertIn(
            '"ledgix_saas.api.selling.complete_b2b_sale": "ledgix_saas.api.selling_compat.complete_b2b_sale"',
            hooks,
        )
        self.assertIn(
            '"ledgix_saas.api.selling.create_exchange": "ledgix_saas.api.selling_compat.create_exchange"',
            hooks,
        )
        self.assertIn(
            "ledgix_saas.services.erpnext_payment_policy.validate_ledgix_payment_entry",
            hooks,
        )

    def test_native_selling_service_does_not_write_legacy_financial_doctypes(self):
        source = (APP_ROOT / "services" / "erpnext_selling.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('frappe.new_doc("Ledgix Sale")', source)
        self.assertNotIn('frappe.new_doc("Ledgix Payment")', source)
        self.assertNotIn('frappe.get_doc("Ledgix Sale"', source)
        self.assertNotIn('frappe.get_doc("Ledgix Payment"', source)
        self.assertNotIn('"si_detail"', source)
        self.assertIn('row.get("sales_invoice_item")', source)
        self.assertIn(
            "payment.references[0].allocated_amount = -refund_amount", source
        )

    def test_return_compatibility_uses_pinned_erpnext_source_row_field(self):
        source = (APP_ROOT / "api" / "selling.py").read_text(encoding="utf-8")
        self.assertNotIn('"si_detail"', source)
        self.assertIn('fields=["sales_invoice_item", "item_code", "qty"]', source)

    def test_native_b2b_compat_suppresses_legacy_ledgix_sale_print_target(self):
        source = (APP_ROOT / "api" / "selling_compat.py").read_text(encoding="utf-8")
        self.assertIn('result["erpnext_sales_invoice"] = invoice', source)
        self.assertIn('result["sale"] = ""', source)
        self.assertIn('result["print_deferred"] = True', source)

    def test_b2b_catalog_and_credit_display_use_erpnext_authority(self):
        source = (APP_ROOT / "api" / "selling_compat.py").read_text(encoding="utf-8")
        self.assertIn('pos_compat.search_pos_v2_items(', source)
        self.assertNotIn('from ledgix_saas.api.v2_pos', source)
        self.assertIn('result["financial_authority"] = "ERPNext"', source)
        self.assertIn("erpnext_selling.get_customer_receivables(customer)", source)

    def test_b2b_price_override_reason_and_audit_are_preserved(self):
        source = (APP_ROOT / "api" / "selling_compat.py").read_text(encoding="utf-8")
        self.assertIn("Authorized B2B price override requires a reason.", source)
        self.assertIn("custom_ledgix_price_override_json", source)
        self.assertIn("if not current:", source)
        self.assertIn(
            "_persist_override_audit(_invoice_from_result(result), audit)", source
        )
        self.assertIn('_persist_override_audit(str(invoice or ""), audit)', source)
        self.assertIn("def preview_b2b_invoice(", source)
        self.assertIn("def create_b2b_invoice(", source)
        self.assertIn("def complete_b2b_sale(", source)
        self.assertIn("def create_exchange(", source)

    def test_b2b_checkout_retry_recovers_deterministic_payments(self):
        source = (APP_ROOT / "api" / "selling_compat.py").read_text(encoding="utf-8")
        self.assertIn("def _ensure_checkout_payments(", source)
        self.assertIn('payment_client_id = f"{client_sale_id}:PAY:{index}"', source)
        self.assertIn("custom_ledgix_client_payment_id", source)
        self.assertIn("result = _ensure_checkout_payments(result, tenders, client_sale_id)", source)
        self.assertIn("if existing:", source)

    def test_legacy_b2b_module_is_only_a_compatibility_wrapper(self):
        source = (APP_ROOT / "api" / "v2_b2b.py").read_text(encoding="utf-8")
        self.assertNotIn("ledgix_saas.services.payments", source)
        self.assertNotIn("ledgix_saas.services.receivables", source)
        self.assertIn("from ledgix_saas.api import selling", source)
        self.assertIn('row.setdefault("sale", row.get("invoice"))', source)
        self.assertIn('row["reference_name"] = row["sale"]', source)
        self.assertIn("def _validate_company_currency(currency)", source)
        self.assertIn("Use native ERPNext multi-currency Payment Entry", source)
        self.assertIn("_validate_company_currency(currency)", source)

    def test_native_payment_policy_uses_migrated_mode_metadata(self):
        source = (APP_ROOT / "services" / "erpnext_payment_policy.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("custom_ledgix_requires_reference", source)
        self.assertIn('"Mode of Payment Account"', source)
        self.assertIn("doc.reference_no", source)
        self.assertIn("if not _is_ledgix_payment(doc):", source)

    def test_consolidated_runner_includes_runtime_policy_gate(self):
        runner = (REPO_ROOT / "scripts" / "run_erpnext_phase6_final_gate.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("erpnext_phase6_policy_gate.run", runner)
        self.assertIn("phase6_policy_complete", runner)
        self.assertIn("erpnext-phase6-policy-gate.txt", runner)
