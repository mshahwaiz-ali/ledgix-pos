import unittest
from pathlib import Path

from ledgix_saas.setup import erpnext_phase6_extensions


APP_ROOT = Path(__file__).resolve().parents[1]


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
        fieldnames = {
            row["fieldname"]
            for row in erpnext_phase6_extensions.CUSTOM_FIELDS["Sales Invoice"]
        }
        self.assertTrue(
            {
                "custom_ledgix_sale_channel",
                "custom_ledgix_client_return_id",
                "custom_ledgix_exchange_reference",
                "custom_ledgix_checkout_source",
            }.issubset(fieldnames)
        )

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
        self.assertIn("ledgix_saas.api.selling_compat.get_pos_v2_boot", hooks)
        self.assertIn("ledgix_saas.api.selling_compat.search_pos_v2_items", hooks)
        self.assertIn("ledgix_saas.api.selling_compat.complete_pos_v2_sale", hooks)
        self.assertIn("ledgix_saas.api.selling.preview_pos_v2_checkout_compat", hooks)
        self.assertIn("ledgix_saas.api.selling.get_pos_v2_customer_context_compat", hooks)
        self.assertIn("ledgix_saas.api.selling.get_pos_return_context_compat", hooks)
        self.assertIn("ledgix_saas.api.selling.create_pos_return_compat", hooks)

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
        self.assertIn('row["pricing_authority"] = "ERPNext"', source)
        self.assertIn('result["pricing_authority"] = "ERPNext"', source)
        self.assertIn('result["financial_authority"] = "ERPNext"', source)
        self.assertIn("erpnext_selling.get_customer_receivables(customer)", source)

    def test_legacy_b2b_module_is_only_a_compatibility_wrapper(self):
        source = (APP_ROOT / "api" / "v2_b2b.py").read_text(encoding="utf-8")
        self.assertNotIn("ledgix_saas.services.payments", source)
        self.assertNotIn("ledgix_saas.services.receivables", source)
        self.assertIn("from ledgix_saas.api import selling", source)
        self.assertIn('row.setdefault("sale", row.get("invoice"))', source)
        self.assertIn('row["reference_name"] = row["sale"]', source)
