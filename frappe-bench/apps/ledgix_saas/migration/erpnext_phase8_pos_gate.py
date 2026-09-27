from __future__ import annotations

import traceback

import frappe
from frappe.utils import flt

from ledgix_saas.migration import erpnext_pos_behavioral_spike as pos_base
from ledgix_saas.migration import erpnext_pos_behavioral_spike_runtime as pos_runtime
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.services import erpnext_buying_inventory, erpnext_pos
from ledgix_saas.setup import erpnext_phase8_extensions


ITEM = "P8-POS-NATIVE"
RATE = 125.0
SEED_QTY = 12.0
VALUATION_RATE = 70.0

LEGACY_DOCTYPES = (
    "Ledgix Sale",
    "Ledgix Payment",
    "Ledgix POS Shift",
    "Ledgix POS Hold",
    "Ledgix Stock Movement",
    "Ledgix Stock Lot",
    "Ledgix Stock Serial",
    "Ledgix FBR Submission Log",
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 8 runtime gate on {frappe.local.site!r}; restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing.")


def _count_if_exists(doctype: str):
    if not frappe.db.exists("DocType", doctype):
        return None
    return frappe.db.count(doctype)


def _legacy_counts() -> dict:
    return {doctype: _count_if_exists(doctype) for doctype in LEGACY_DOCTYPES}


def _gl_count(doctype: str, name: str) -> int:
    return frappe.db.count(
        "GL Entry",
        {"voucher_type": doctype, "voucher_no": name, "is_cancelled": 0},
    )


def _sle_count(doctype: str, name: str) -> int:
    return frappe.db.count(
        "Stock Ledger Entry",
        {"voucher_type": doctype, "voucher_no": name, "is_cancelled": 0},
    )


def _ensure_item() -> str:
    if frappe.db.exists("Item", ITEM):
        item = frappe.get_doc("Item", ITEM)
        if not item.is_stock_item:
            frappe.throw(f"Safety check failed: {ITEM} must remain a stock item.")
    else:
        item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": ITEM,
                "item_name": "Phase 8 Native POS Item",
                "description": "ERPNext-native Phase 8 POS integration gate item",
                "item_group": "Products",
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "is_sales_item": 1,
                "include_item_in_manufacturing": 0,
                "valuation_method": "FIFO",
            }
        )
        item.insert(ignore_permissions=True)

    existing_price = frappe.db.get_value(
        "Item Price",
        {"item_code": ITEM, "price_list": "Standard Selling", "uom": "Nos"},
        "name",
    )
    if existing_price:
        frappe.db.set_value("Item Price", existing_price, "price_list_rate", RATE, update_modified=False)
    else:
        frappe.get_doc(
            {
                "doctype": "Item Price",
                "item_code": ITEM,
                "price_list": "Standard Selling",
                "price_list_rate": RATE,
                "currency": "PKR",
                "uom": "Nos",
            }
        ).insert(ignore_permissions=True)
    return ITEM


def _prepare_profile_and_stock() -> dict:
    warehouse = pos_base._leaf_warehouse()
    customer = pos_base._ensure_customer()
    cash_account = pos_base._ensure_cash_mode_account()
    profile_name = pos_runtime._ensure_pos_profile(customer, warehouse, cash_account)
    profile = frappe.get_doc("POS Profile", profile_name)

    mop_meta = frappe.get_meta("Mode of Payment")
    if mop_meta.has_field("custom_ledgix_allow_change"):
        frappe.db.set_value("Mode of Payment", pos_base.PRIMARY_MODE, "custom_ledgix_allow_change", 1, update_modified=False)
    if mop_meta.has_field("custom_ledgix_requires_reference"):
        frappe.db.set_value("Mode of Payment", pos_base.SECONDARY_MODE, "custom_ledgix_requires_reference", 1, update_modified=False)

    item = _ensure_item()
    erpnext_buying_inventory.create_stock_reconciliation(
        item=item,
        qty=SEED_QTY,
        valuation_rate=VALUATION_RATE,
        warehouse=warehouse,
        company=TEST_COMPANY,
        client_reconciliation_id=f"P8-SEED-{frappe.generate_hash(length=10)}",
        source="Phase 8 POS Gate Seed",
    )
    snapshot = erpnext_buying_inventory.stock_snapshot(item, warehouse=warehouse, company=TEST_COMPANY)
    return {
        "warehouse": warehouse,
        "customer": customer,
        "profile": profile.name,
        "item": item,
        "snapshot": snapshot,
    }


def _ensure_clean_opening() -> None:
    current = erpnext_pos.shift_info(company=TEST_COMPANY)
    if current.get("has_active_shift"):
        erpnext_pos.close_shift(
            actual_cash=max(flt(current.get("expected_cash")), 0),
            shift_name=current.get("shift_id"),
            company=TEST_COMPANY,
        )


def _case(name: str, fn) -> dict:
    try:
        evidence, checks = fn()
        return {"name": name, "evidence": evidence, "checks": checks, "passed": all(checks.values())}
    except Exception as exc:
        return {
            "name": name,
            "evidence": {},
            "checks": {},
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": traceback.format_exc().splitlines()[-10:],
        }


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")
    erpnext_phase8_extensions.sync_all()
    legacy_before = _legacy_counts()
    fixtures = _prepare_profile_and_stock()
    _ensure_clean_opening()

    state: dict = {"fixtures": fixtures, "starting_qty": flt(fixtures["snapshot"]["actual_qty"])}
    run_token = frappe.generate_hash(length=10).upper()

    def boot_case():
        data = erpnext_pos.boot("Retail", fixtures["customer"], company=TEST_COMPANY)
        catalog = erpnext_pos.search_items(
            query=ITEM,
            customer=fixtures["customer"],
            sale_channel="Retail",
            price_list="Standard Selling",
            company=TEST_COMPANY,
        )
        matched = next((row for row in catalog["items"] if row["item_code"] == ITEM), None)
        checks = {
            "native_pos_profile": data.get("pos_profile") == fixtures["profile"],
            "native_customer": data.get("customer", {}).get("name") == fixtures["customer"],
            "native_catalog_item": matched is not None,
            "native_price": matched is not None and abs(flt(matched.get("rate")) - RATE) < 0.005,
            "native_stock": matched is not None and abs(flt(matched.get("current_stock")) - SEED_QTY) < 0.005,
            "payment_methods_from_profile": len(data.get("payment_methods") or []) >= 2,
        }
        state["boot"] = data
        return {"boot": data, "catalog_match": matched}, checks

    def opening_case():
        opening = erpnext_pos.open_shift(
            50,
            notes="Phase 8 native POS gate",
            company=TEST_COMPANY,
        )
        info = erpnext_pos.shift_info(company=TEST_COMPANY)
        state["opening"] = opening.name
        checks = {
            "opening_submitted": opening.docstatus == 1,
            "opening_open": opening.status == "Open",
            "shift_info_native": info.get("shift_id") == opening.name,
            "opening_cash_preserved": abs(flt(info.get("opening_cash")) - 50) < 0.005,
        }
        return {"opening": opening.name, "info": info}, checks

    def hold_case():
        hold = erpnext_pos.create_hold(
            cart_items=[{"item": ITEM, "qty": 1}],
            sale_channel="Retail",
            customer=fixtures["customer"],
            price_list="Standard Selling",
            company=TEST_COMPANY,
        )
        hold_gl = _gl_count("POS Invoice", hold.name)
        hold_sle = _sle_count("POS Invoice", hold.name)
        listed = {row["name"] for row in erpnext_pos.list_holds()}
        resumed = erpnext_pos.resume_hold(hold.custom_ledgix_hold_id)

        cancel_hold = erpnext_pos.create_hold(
            cart_items=[{"item": ITEM, "qty": 1}],
            sale_channel="Retail",
            customer=fixtures["customer"],
            price_list="Standard Selling",
            company=TEST_COMPANY,
        )
        erpnext_pos.cancel_hold(cancel_hold.custom_ledgix_hold_id)
        cancel_hold.reload()
        checks = {
            "held_native_pos_invoice": hold.doctype == "POS Invoice" and hold.docstatus == 0,
            "held_has_no_gl": hold_gl == 0,
            "held_has_no_sle": hold_sle == 0,
            "held_listed": hold.custom_ledgix_hold_id in listed,
            "resume_returns_cart": bool(resumed.get("cart_items")) and resumed.get("sale_channel") == "Retail",
            "resume_marks_native_draft": frappe.db.get_value("POS Invoice", hold.name, "custom_ledgix_hold_status") == "Resumed",
            "cancel_marks_native_draft": cancel_hold.custom_ledgix_hold_status == "Cancelled",
        }
        state["holds"] = [hold.name, cancel_hold.name]
        return {
            "hold": hold.name,
            "resume": resumed,
            "cancel_hold": cancel_hold.name,
            "hold_gl": hold_gl,
            "hold_sle": hold_sle,
        }, checks

    def checkout_case():
        preview = erpnext_pos.preview_checkout(
            cart_items=[{"item": ITEM, "qty": 1}],
            customer=fixtures["customer"],
            price_list="Standard Selling",
            company=TEST_COMPANY,
        )
        total = flt(preview["grand_total"], 2)
        cash = flt(total * 0.60 + 5, 2)
        card = flt(total - flt(total * 0.60, 2), 2)
        client_id = f"P8-SALE-{run_token}"
        tenders = [
            {"payment_method": pos_base.PRIMARY_MODE, "amount": cash},
            {
                "payment_method": pos_base.SECONDARY_MODE,
                "amount": card,
                "reference_number": f"P8-CARD-{run_token}",
            },
        ]
        sale = erpnext_pos.complete_sale(
            cart_items=[{"item": ITEM, "qty": 1}],
            tenders=tenders,
            customer=fixtures["customer"],
            price_list="Standard Selling",
            client_sale_id=client_id,
            company=TEST_COMPANY,
        )
        retry = erpnext_pos.complete_sale(
            cart_items=[{"item": ITEM, "qty": 1}],
            tenders=tenders,
            customer=fixtures["customer"],
            price_list="Standard Selling",
            client_sale_id=client_id,
            company=TEST_COMPANY,
        )
        before_close = erpnext_buying_inventory.stock_snapshot(ITEM, warehouse=fixtures["warehouse"], company=TEST_COMPANY)
        checks = {
            "pos_invoice_submitted": sale.docstatus == 1,
            "checkout_idempotent": retry.name == sale.name,
            "split_tender_native": len([row for row in sale.payments if flt(row.amount) > 0]) >= 2,
            "change_native": flt(sale.change_amount) > 0,
            "no_direct_pos_gl_before_close": _gl_count("POS Invoice", sale.name) == 0,
            "no_direct_pos_sle_before_close": _sle_count("POS Invoice", sale.name) == 0,
            "stock_waits_for_closing": abs(flt(before_close["actual_qty"]) - state["starting_qty"]) < 0.005,
        }
        state["keep_sale"] = sale.name
        return {
            "preview": preview,
            "sale": sale.name,
            "retry": retry.name,
            "payments": [{"mode": row.mode_of_payment, "amount": flt(row.amount)} for row in sale.payments],
            "change_amount": flt(sale.change_amount),
            "before_close_stock": before_close,
        }, checks

    def return_case():
        preview = erpnext_pos.preview_checkout(
            cart_items=[{"item": ITEM, "qty": 1}],
            customer=fixtures["customer"],
            price_list="Standard Selling",
            company=TEST_COMPANY,
        )
        total = flt(preview["grand_total"], 2)
        client_id = f"P8-RETURN-SOURCE-{run_token}"
        source = erpnext_pos.complete_sale(
            cart_items=[{"item": ITEM, "qty": 1}],
            tenders=[{"payment_method": pos_base.PRIMARY_MODE, "amount": total}],
            customer=fixtures["customer"],
            price_list="Standard Selling",
            client_sale_id=client_id,
            company=TEST_COMPANY,
        )
        context = erpnext_pos.get_return_context(source.name)
        source_row = source.items[0]
        returned = erpnext_pos.create_return(
            original_sale=source.name,
            return_items=[
                {
                    "item": source_row.item_code,
                    "original_sale_item_row": source_row.name,
                    "qty": 1,
                }
            ],
            reason="Phase 8 native return proof",
            client_return_id=f"P8-RET-{run_token}",
        )
        checks = {
            "return_context_native": context is not None and context.get("sale_id") == source.name,
            "return_submitted": returned.docstatus == 1 and returned.return_against == source.name,
            "return_negative_qty": len(returned.items) == 1 and abs(flt(returned.items[0].qty) + 1) < 0.005,
            "return_rate_authoritative": abs(flt(returned.items[0].rate) - flt(source_row.rate)) < 0.005,
            "return_waits_for_closing": _sle_count("POS Invoice", returned.name) == 0,
        }
        state["return_source"] = source.name
        state["return_invoice"] = returned.name
        return {
            "source": source.name,
            "context": context,
            "return": returned.name,
            "source_rate": flt(source_row.rate),
            "return_rate": flt(returned.items[0].rate),
        }, checks

    def closing_case():
        info = erpnext_pos.shift_info(company=TEST_COMPANY)
        opening, closing = erpnext_pos.close_shift(
            actual_cash=max(flt(info.get("expected_cash")), 0),
            shift_name=info.get("shift_id"),
            closing_notes="Phase 8 native closing proof",
            company=TEST_COMPANY,
        )
        keep = frappe.get_doc("POS Invoice", state["keep_sale"])
        source = frappe.get_doc("POS Invoice", state["return_source"])
        returned = frappe.get_doc("POS Invoice", state["return_invoice"])
        final_stock = erpnext_buying_inventory.stock_snapshot(ITEM, warehouse=fixtures["warehouse"], company=TEST_COMPANY)
        consolidated = {keep.consolidated_invoice, source.consolidated_invoice, returned.consolidated_invoice}
        consolidated.discard(None)
        consolidated.discard("")
        total_gl = sum(_gl_count("Sales Invoice", name) for name in consolidated)
        total_sle = sum(_sle_count("Sales Invoice", name) for name in consolidated)
        checks = {
            "opening_closed": opening.status == "Closed",
            "closing_submitted": closing.docstatus == 1,
            "sales_consolidated": bool(keep.consolidated_invoice) and bool(source.consolidated_invoice),
            "return_consolidated": bool(returned.consolidated_invoice),
            "consolidated_has_gl": total_gl > 0,
            "consolidated_has_sle": total_sle > 0,
            "sale_plus_full_return_plus_sale_net_one": abs(flt(final_stock["actual_qty"]) - (state["starting_qty"] - 1)) < 0.005,
        }
        state["closing"] = closing.name
        return {
            "opening": opening.name,
            "closing": closing.name,
            "consolidated_sales_invoices": sorted(consolidated),
            "consolidated_gl_entries": total_gl,
            "consolidated_sle_entries": total_sle,
            "starting_stock": state["starting_qty"],
            "final_stock": final_stock,
        }, checks

    cases = {}
    for name, fn in (
        ("native_pos_boot_catalog", boot_case),
        ("native_opening_shift", opening_case),
        ("native_draft_holds", hold_case),
        ("native_retail_checkout_split_change_idempotency", checkout_case),
        ("native_retail_return", return_case),
        ("native_closing_consolidation_stock", closing_case),
    ):
        cases[name] = _case(name, fn)
        if not cases[name]["passed"]:
            break

    legacy_after = _legacy_counts()
    legacy_case = {
        "name": "no_parallel_legacy_pos_writes",
        "evidence": {"before": legacy_before, "after": legacy_after},
        "checks": {"legacy_pos_counts_unchanged": legacy_before == legacy_after},
        "passed": legacy_before == legacy_after,
    }
    cases["no_parallel_legacy_pos_writes"] = legacy_case

    failed = [name for name, case in cases.items() if not case.get("passed")]
    passed = not failed
    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": TEST_COMPANY,
        "fixtures": fixtures,
        "legacy_counts_before": legacy_before,
        "legacy_counts_after": legacy_after,
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed,
        "decisions": {
            "pos_ui": "Ledgix POS retained",
            "retail_transaction_authority": "ERPNext POS Invoice",
            "pos_shift_authority": "ERPNext POS Opening Entry / POS Closing Entry",
            "pos_hold_authority": "ERPNext draft POS Invoice / Sales Invoice",
            "retail_return_authority": "ERPNext POS Invoice Return",
            "catalog_pricing_stock_authority": "ERPNext Item / Customer / Price List / Pricing Rule / Bin",
            "legacy_pos_ledgers_retired_for_new_writes": True,
            "fbr_source_cutover_performed": False,
        },
        "phase8_complete": passed,
        "phase9_ready": passed,
        "next_phase": "Phase 9 — FBR Source Cutover",
        "passed": passed,
    }
    frappe.db.commit()
    return result
