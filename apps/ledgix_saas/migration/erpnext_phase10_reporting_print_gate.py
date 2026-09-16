from __future__ import annotations

import traceback

import frappe
from frappe.utils import flt, nowdate

from ledgix_saas.api import fbr_native, printing
from ledgix_saas.api import pos_compat
from ledgix_saas.migration import erpnext_phase4_tax_parity_gate as tax_gate
from ledgix_saas.migration import erpnext_phase7_buying_inventory_gate as p7_gate
from ledgix_saas.migration import erpnext_pos_behavioral_spike_runtime as pos_runtime
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.services import erpnext_buying_inventory, erpnext_pos, erpnext_reporting, erpnext_selling


ITEM = "LEDGIX-P10-NATIVE"
CATEGORY = tax_gate.STANDARD_CATEGORY
SCENARIO = "SN001"
SELLING_RATE = 150.0
VALUATION_RATE = 70.0


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(f"Refusing Phase 10 gate on {frappe.local.site!r}; restricted to {INTEGRATION_SITE!r}.")
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration Company {TEST_COMPANY!r} is missing.")


def _legacy_counts() -> dict:
    result = {}
    for doctype in (
        "Ledgix Sale",
        "Ledgix Sales Return",
        "Ledgix Payment",
        "Ledgix Purchase",
        "Ledgix Stock Movement",
        "Ledgix Stock Lot",
        "Ledgix Stock Serial",
    ):
        if frappe.db.exists("DocType", doctype):
            result[doctype] = frappe.db.count(doctype)
    return result


def _disabled_settings() -> dict:
    return {
        "enabled": False,
        "mode": "Disabled",
        "submit_trigger": "Manual",
        "sandbox_token_configured": False,
        "production_token_configured": False,
        "production_post_armed": False,
        "sandbox_post_on_submit": False,
    }


def _disabled_control() -> dict:
    return {"enabled": False, "mode": "Disabled", "submit_trigger": "Manual", "token_configured": False}


class _NoFBRNetwork:
    def __init__(self):
        self.originals = {}
        self.calls = 0

    def __enter__(self):
        self.originals["settings"] = fbr_native.get_fbr_settings_internal
        self.originals["control"] = fbr_native.get_fbr_control_state_internal
        self.originals["post"] = fbr_native.fbr_client.post_invoice
        self.originals["validate"] = fbr_native.fbr_client.validate_invoice
        fbr_native.get_fbr_settings_internal = _disabled_settings
        fbr_native.get_fbr_control_state_internal = _disabled_control

        def blocked(*args, **kwargs):
            self.calls += 1
            raise AssertionError("Phase 10 gate must not call FBR/PRAL network adapters")

        fbr_native.fbr_client.post_invoice = blocked
        fbr_native.fbr_client.validate_invoice = blocked
        return self

    def __exit__(self, exc_type, exc, tb):
        fbr_native.get_fbr_settings_internal = self.originals["settings"]
        fbr_native.get_fbr_control_state_internal = self.originals["control"]
        fbr_native.fbr_client.post_invoice = self.originals["post"]
        fbr_native.fbr_client.validate_invoice = self.originals["validate"]
        return False


def _ensure_item_price(item: str) -> None:
    name = frappe.db.get_value(
        "Item Price",
        {"item_code": item, "price_list": "Standard Selling", "uom": "Nos"},
        "name",
    )
    if name:
        frappe.db.set_value("Item Price", name, "price_list_rate", SELLING_RATE, update_modified=False)
        return
    frappe.get_doc(
        {
            "doctype": "Item Price",
            "item_code": item,
            "price_list": "Standard Selling",
            "price_list_rate": SELLING_RATE,
            "currency": "PKR",
            "uom": "Nos",
        }
    ).insert(ignore_permissions=True)


def _ensure_fixtures() -> dict:
    tax_gate._ensure_tax_accounts()
    customer = tax_gate._ensure_customer()
    tax_gate._ensure_category(CATEGORY, rate=18)
    tax_gate._ensure_item(ITEM)
    tax_gate._ensure_profile(
        ITEM,
        tax_gate.ProfileSpec(
            category=CATEGORY,
            hs_code="0101.21",
            sales_type="Goods at standard rate",
            scenario_id=SCENARIO,
        ),
    )
    _ensure_item_price(ITEM)
    supplier = p7_gate._ensure_supplier()
    p7_gate._ensure_cash_account()
    warehouse = erpnext_buying_inventory.default_warehouse(TEST_COMPANY)
    seed = erpnext_buying_inventory.create_stock_entry(
        item=ITEM,
        qty=25,
        purpose="Material Receipt",
        company=TEST_COMPANY,
        target_warehouse=warehouse,
        valuation_rate=VALUATION_RATE,
        client_stock_id="LEDGIX-P10-STOCK-SEED",
        source="Phase 10 Reporting/Print Seed",
    )
    profile = pos_runtime._ensure_pos_profile(customer, warehouse, frappe.db.get_value(
        "Mode of Payment Account", {"parent": "Cash", "company": TEST_COMPANY}, "default_account"
    ))
    frappe.db.commit()
    return {
        "customer": customer,
        "supplier": supplier,
        "item": ITEM,
        "warehouse": warehouse,
        "stock_seed": seed.name,
        "pos_profile": profile,
    }


def _ensure_pos_opening() -> str:
    info = erpnext_pos.shift_info(company=TEST_COMPANY)
    if info.get("has_active_shift"):
        return info.get("shift_id")
    return erpnext_pos.open_shift(0, notes="Phase 10 reporting/print gate", company=TEST_COMPANY).name


def _set_mock_fbr(doctype: str, name: str, invoice_number: str) -> None:
    frappe.db.set_value(
        doctype,
        name,
        {
            "custom_ledgix_fbr_status": "Submitted",
            "custom_ledgix_fbr_invoice_number": invoice_number,
            "custom_ledgix_fbr_reference": invoice_number,
            "custom_ledgix_fbr_reconciliation_required": 0,
        },
        update_modified=False,
    )


def _case(name: str, fn) -> dict:
    try:
        evidence, checks = fn()
        result = {"name": name, "evidence": evidence, "checks": checks, "passed": all(checks.values())}
        frappe.db.commit()
        return result
    except Exception as exc:
        trace = traceback.format_exc().strip().splitlines()
        frappe.db.rollback()
        if hasattr(frappe.local, "message_log"):
            frappe.local.message_log = []
        return {
            "name": name,
            "evidence": {},
            "checks": {},
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": trace[-12:],
        }


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")
    legacy_before = _legacy_counts()
    token = frappe.generate_hash(length=9).upper()
    state: dict = {}

    with _NoFBRNetwork() as network:
        fixtures = _ensure_fixtures()
        state["fixtures"] = fixtures

        purchase = erpnext_buying_inventory.create_direct_purchase_invoice(
            supplier=fixtures["supplier"],
            items=[{"item": ITEM, "qty": 2, "rate": VALUATION_RATE, "warehouse": fixtures["warehouse"]}],
            company=TEST_COMPANY,
            warehouse=fixtures["warehouse"],
            update_stock=False,
            client_purchase_id=f"P10-PUR-{token}",
            client_invoice_id=f"P10-PI-{token}",
            source="Phase 10 Reporting Gate",
        )
        sale = erpnext_selling.create_sales_invoice(
            customer=fixtures["customer"],
            items=[{"item": ITEM, "qty": 1}],
            company=TEST_COMPANY,
            selling_price_list="Standard Selling",
            sale_channel="B2B",
            client_sale_id=f"P10-SI-{token}",
            checkout_source="Phase 10 Reporting/Print Gate",
            submit=True,
        )
        _set_mock_fbr("Sales Invoice", sale.name, f"P10-FBR-SI-{token}")
        sale.reload()

        source_row = sale.items[0]
        credit = erpnext_selling.create_sales_return(
            sales_invoice=sale.name,
            return_items=[{"sales_invoice_item": source_row.name, "qty": 1}],
            reason="Phase 10 native print Credit Note",
            client_return_id=f"P10-CN-{token}",
            checkout_source="Phase 10 Reporting/Print Gate",
        )
        _set_mock_fbr("Sales Invoice", credit.name, f"P10-FBR-CN-{token}")
        credit.reload()

        opening = _ensure_pos_opening()
        preview = erpnext_pos.preview_checkout(
            cart_items=[{"item": ITEM, "qty": 1}],
            customer=fixtures["customer"],
            price_list="Standard Selling",
            company=TEST_COMPANY,
        )
        pos = erpnext_pos.complete_sale(
            cart_items=[{"item": ITEM, "qty": 1}],
            tenders=[{"payment_method": "Cash", "amount": preview["grand_total"]}],
            customer=fixtures["customer"],
            price_list="Standard Selling",
            client_sale_id=f"P10-POS-{token}",
            company=TEST_COMPANY,
        )
        _set_mock_fbr("POS Invoice", pos.name, f"P10-FBR-POS-{token}")
        pos.reload()
        state.update({"purchase": purchase, "sale": sale, "credit": credit, "pos": pos, "opening": opening})

        def print_context_case():
            si_context = printing.get_native_invoice_print_context("Sales Invoice", sale.name)
            cn_context = printing.get_native_invoice_print_context("Sales Invoice", credit.name)
            pos_context = printing.get_native_invoice_print_context("POS Invoice", pos.name)
            checks = {
                "sales_invoice_native": si_context.get("doctype") == "Sales Invoice" and si_context.get("title") == "TAX INVOICE",
                "pos_invoice_native": pos_context.get("doctype") == "POS Invoice" and pos_context.get("title") == "SALES RECEIPT",
                "credit_note_native": cn_context.get("is_return") and cn_context.get("title") == "CREDIT NOTE",
                "original_fbr_reference_preserved": cn_context.get("original_fbr_invoice_number") == sale.custom_ledgix_fbr_invoice_number,
                "sales_qr_generated": str(si_context.get("fbr_qr_data_uri") or "").startswith("data:image/svg+xml;base64,"),
                "pos_qr_generated": str(pos_context.get("fbr_qr_data_uri") or "").startswith("data:image/svg+xml;base64,"),
                "tax_snapshot_present": bool(si_context.get("items")) and si_context["items"][0].get("snapshot_version", 0) > 0,
            }
            return {"sales": si_context, "credit": cn_context, "pos": pos_context}, checks

        def rendered_print_case():
            sales_html = frappe.get_print("Sales Invoice", sale.name, "Ledgix ERPNext Tax Invoice")
            credit_html = frappe.get_print("Sales Invoice", credit.name, "Ledgix ERPNext Tax Invoice")
            pos_html = frappe.get_print("POS Invoice", pos.name, "Ledgix ERPNext POS Receipt")
            checks = {
                "a4_tax_invoice_renders": "TAX INVOICE" in sales_html and sale.name in sales_html,
                "a4_fbr_number_renders": sale.custom_ledgix_fbr_invoice_number in sales_html,
                "a4_qr_data_renders": "data:image/svg+xml;base64," in sales_html,
                "credit_note_label_renders": "CREDIT NOTE" in credit_html and credit.name in credit_html,
                "credit_original_fbr_renders": sale.custom_ledgix_fbr_invoice_number in credit_html,
                "thermal_receipt_renders": "SALES RECEIPT" in pos_html and pos.name in pos_html,
                "thermal_fbr_number_renders": pos.custom_ledgix_fbr_invoice_number in pos_html,
                "thermal_qr_data_renders": "data:image/svg+xml;base64," in pos_html,
            }
            return {
                "sales_html_size": len(sales_html),
                "credit_html_size": len(credit_html),
                "pos_html_size": len(pos_html),
            }, checks

        def native_print_route_case():
            retail = pos_compat._native_print_target({}, native_document=pos.name, doctype="POS Invoice")
            b2b = pos_compat._native_print_target({}, native_document=sale.name, doctype="Sales Invoice")
            checks = {
                "retail_native_document": retail.get("native_document") == pos.name,
                "retail_format": retail.get("print_format") == "Ledgix ERPNext POS Receipt",
                "b2b_native_document": b2b.get("native_document") == sale.name,
                "b2b_format": b2b.get("print_format") == "Ledgix ERPNext Tax Invoice",
                "not_deferred": retail.get("print_deferred") is False and b2b.get("print_deferred") is False,
                "legacy_sale_identity_empty": not retail.get("sale") and not b2b.get("sale"),
            }
            return {"retail": retail, "b2b": b2b}, checks

        def report_case():
            from ledgix_saas.ledgix.report.ledgix_current_stock import ledgix_current_stock
            from ledgix_saas.ledgix.report.ledgix_low_stock import ledgix_low_stock
            from ledgix_saas.ledgix.report.ledgix_stock_movement_report import ledgix_stock_movement_report
            from ledgix_saas.ledgix.report.ledgix_sales_report import ledgix_sales_report
            from ledgix_saas.ledgix.report.ledgix_purchase_report import ledgix_purchase_report
            from ledgix_saas.ledgix.report.ledgix_sales_return_report import ledgix_sales_return_report
            from ledgix_saas.ledgix.report.ledgix_customer_statement import ledgix_customer_statement

            common = {"from_date": nowdate(), "to_date": nowdate()}
            stock = ledgix_current_stock.execute({"item": ITEM})[1]
            low = ledgix_low_stock.execute({"item": ITEM})[1]
            moves = ledgix_stock_movement_report.execute({**common, "item": ITEM})[1]
            sales = ledgix_sales_report.execute({**common, "customer": fixtures["customer"], "docstatus": "Submitted"})[1]
            purchases = ledgix_purchase_report.execute({**common, "supplier": fixtures["supplier"], "docstatus": "Submitted"})[1]
            returns = ledgix_sales_return_report.execute({**common, "customer": fixtures["customer"], "docstatus": "Submitted"})[1]
            statement = ledgix_customer_statement.execute({**common, "customer": fixtures["customer"]})[1]
            sale_row = next((row for row in sales if row.sale == sale.name), None)
            purchase_row = next((row for row in purchases if row.purchase == purchase.name), None)
            return_row = next((row for row in returns if row.sales_return == credit.name), None)
            checks = {
                "stock_report_native_item": bool(stock) and all(row.item == ITEM for row in stock),
                "low_stock_report_executes": isinstance(low, list),
                "stock_movement_native_sle": bool(moves) and all(row.get("authority") == "ERPNext Stock Ledger Entry" for row in moves),
                "sales_report_native_reference": bool(sale_row) and sale_row.reference_doctype == "Sales Invoice",
                "purchase_report_native_reference": bool(purchase_row) and purchase_row.reference_doctype == "Purchase Invoice",
                "return_report_native_reference": bool(return_row) and return_row.reference_doctype == "Sales Invoice",
                "customer_statement_native_gl": bool(statement) and any(row.get("reference_doctype") == "Sales Invoice" for row in statement),
            }
            return {
                "stock_rows": len(stock),
                "low_stock_rows": len(low),
                "movement_rows": len(moves),
                "sales_rows": len(sales),
                "purchase_rows": len(purchases),
                "return_rows": len(returns),
                "statement_rows": len(statement),
            }, checks

        def intelligence_case():
            data = erpnext_reporting.inventory_intelligence(
                {"item": ITEM, "from_date": nowdate(), "to_date": nowdate(), "tracking_type": "All"}
            )
            authority = str((data.get("meta") or {}).get("authority") or "")
            timeline = data.get("timeline") or []
            checks = {
                "authority_is_erpnext": authority.startswith("ERPNext"),
                "no_legacy_authority": "Ledgix Sale" not in authority and "Ledgix Stock" not in authority,
                "summary_present": "current_qty" in (data.get("summary") or {}),
                "native_stock_timeline": bool(timeline) and all(row.get("authority") == "ERPNext Stock Ledger Entry" for row in timeline),
                "native_dynamic_references": all(row.get("reference_doctype") and row.get("reference_name") for row in timeline),
            }
            return {"summary": data.get("summary"), "meta": data.get("meta"), "timeline_count": len(timeline)}, checks

        cases = {}
        for name, fn in (
            ("native_print_context_and_historical_fbr_qr", print_context_case),
            ("native_a4_thermal_credit_note_render", rendered_print_case),
            ("pos_native_print_target", native_print_route_case),
            ("native_workspace_reports", report_case),
            ("native_inventory_intelligence", intelligence_case),
        ):
            cases[name] = _case(name, fn)

        info = erpnext_pos.shift_info(company=TEST_COMPANY)
        if info.get("has_active_shift") and info.get("shift_id") == opening:
            cases["native_pos_close_for_reporting"] = _case(
                "native_pos_close_for_reporting",
                lambda: _close_pos_case(info),
            )

    legacy_after = _legacy_counts()
    cases["no_parallel_legacy_reporting_writes"] = {
        "name": "no_parallel_legacy_reporting_writes",
        "evidence": {"before": legacy_before, "after": legacy_after},
        "checks": {"legacy_counts_unchanged": legacy_before == legacy_after},
        "passed": legacy_before == legacy_after,
    }
    failed = [name for name, case in cases.items() if not case.get("passed")]
    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": TEST_COMPANY,
        "fixtures": state.get("fixtures"),
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed,
        "network_safety": {"real_fbr_network_calls": network.calls},
        "decisions": {
            "bi_authority": "ERPNext Item/Bin/SLE + native sales/purchase documents",
            "active_report_authority": "ERPNext",
            "a4_print_source": "Sales Invoice",
            "thermal_print_source": "POS Invoice",
            "credit_note_print_source": "ERPNext native return invoice",
            "legacy_print_formats": "Historical only",
        },
        "phase10_complete": not failed and network.calls == 0,
        "phase11_ready": not failed and network.calls == 0,
        "next_phase": "Phase 11 — Workspace and Product Simplification",
        "passed": not failed and network.calls == 0,
    }
    frappe.db.commit()
    return result


def _close_pos_case(info: dict):
    opening, closing = erpnext_pos.close_shift(
        actual_cash=max(flt(info.get("expected_cash")), 0),
        shift_name=info.get("shift_id"),
        company=TEST_COMPANY,
    )
    checks = {"opening_closed": opening.status == "Closed", "closing_submitted": closing.docstatus == 1}
    return {"opening": opening.name, "closing": closing.name}, checks
