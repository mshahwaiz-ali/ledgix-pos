from pathlib import Path

from ledgix_saas.setup import erpnext_phase6_extensions


ROOT = Path(__file__).resolve().parents[4]


def test_phase6_extensions_only_target_native_financial_documents():
    assert set(erpnext_phase6_extensions.CUSTOM_FIELDS) == {"Sales Invoice", "Payment Entry"}


def test_phase6_extensions_do_not_duplicate_erpnext_money_fields():
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
    assert not forbidden.intersection(fieldnames)
    assert all(name.startswith("custom_ledgix_") for name in fieldnames)


def test_phase6_sales_invoice_metadata_contract():
    fieldnames = {
        row["fieldname"] for row in erpnext_phase6_extensions.CUSTOM_FIELDS["Sales Invoice"]
    }
    assert {
        "custom_ledgix_sale_channel",
        "custom_ledgix_client_return_id",
        "custom_ledgix_exchange_reference",
        "custom_ledgix_checkout_source",
    }.issubset(fieldnames)


def test_phase6_payment_entry_metadata_contract():
    fieldnames = {
        row["fieldname"] for row in erpnext_phase6_extensions.CUSTOM_FIELDS["Payment Entry"]
    }
    assert {
        "custom_ledgix_client_payment_id",
        "custom_ledgix_payment_source",
        "custom_ledgix_reversal_reason",
    }.issubset(fieldnames)


def test_phase6_hooks_install_schema_and_compatibility_routes():
    hooks = (ROOT / "hooks.py").read_text(encoding="utf-8")
    assert "ledgix_saas.setup.erpnext_phase6_extensions.after_migrate" in hooks
    assert "ledgix_saas.api.selling.complete_pos_v2_sale_compat" in hooks
    assert "ledgix_saas.api.selling.preview_pos_v2_checkout_compat" in hooks
    assert "ledgix_saas.api.selling.get_pos_v2_customer_context_compat" in hooks
    assert "ledgix_saas.api.selling.get_pos_return_context_compat" in hooks
    assert "ledgix_saas.api.selling.create_pos_return_compat" in hooks


def test_native_selling_service_does_not_write_legacy_financial_doctypes():
    source = (ROOT / "services" / "erpnext_selling.py").read_text(encoding="utf-8")
    assert 'frappe.new_doc("Ledgix Sale")' not in source
    assert 'frappe.new_doc("Ledgix Payment")' not in source
    assert 'frappe.get_doc("Ledgix Sale"' not in source
    assert 'frappe.get_doc("Ledgix Payment"' not in source
    assert '"si_detail"' not in source
    assert 'row.get("sales_invoice_item")' in source
    assert "payment.references[0].allocated_amount = -refund_amount" in source
