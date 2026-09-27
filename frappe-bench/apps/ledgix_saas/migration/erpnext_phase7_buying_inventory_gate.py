from __future__ import annotations

import traceback

import frappe
from frappe.utils import add_days, cint, flt, nowdate

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.services import erpnext_buying_inventory
from ledgix_saas.setup import erpnext_phase7_extensions

GATE_VERSION = "P7-V1"
WAREHOUSE_2_NAME = "Phase 7 Secondary"
SUPPLIER = "P7 Supplier"
ITEM_PURCHASE = "P7-PURCHASE"
ITEM_DIRECT = "P7-DIRECT"
ITEM_NONSTOCK = "P7-NONSTOCK"
ITEM_TRANSFER = "P7-TRANSFER"
ITEM_RECON = "P7-RECON"
ITEM_BATCH = "P7-BATCH"
ITEM_SERIAL = "P7-SERIAL"
ITEM_RETURN = "P7-RETURN"
ITEM_CANCEL = "P7-CANCEL"
ITEM_BACKDATED = "P7-BACKDATED"
BATCH_NO = "P7-BATCH-001"
SERIALS = ["P7-SERIAL-001", "P7-SERIAL-002"]
TRACEBACK_TAIL = 12


def _client(kind: str) -> str:
    return f"LEDGIX-{GATE_VERSION}-{kind.upper().replace('_', '-')}"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 7 gate on {frappe.local.site!r}; this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration Company {TEST_COMPANY!r} is missing.")


def _legacy_counts() -> dict:
    return {
        doctype: frappe.db.count(doctype)
        for doctype in (
            "Ledgix Purchase",
            "Ledgix Stock Movement",
            "Ledgix Stock Lot",
            "Ledgix Stock Serial",
        )
        if frappe.db.exists("DocType", doctype)
    }


def _ensure_supplier() -> str:
    if frappe.db.exists("Supplier", SUPPLIER):
        doc = frappe.get_doc("Supplier", SUPPLIER)
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Supplier",
                "supplier_name": SUPPLIER,
                "supplier_type": "Company",
                "supplier_group": "Local",
            }
        )
    doc.custom_ledgix_legacy_supplier = "P7-LEGACY-SUPPLIER-ID"
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_item(item_code: str, *, stock: bool = True, batch: bool = False, serial: bool = False) -> str:
    expected = {
        "is_stock_item": 1 if stock else 0,
        "has_batch_no": 1 if batch else 0,
        "has_serial_no": 1 if serial else 0,
    }
    if frappe.db.exists("Item", item_code):
        doc = frappe.get_doc("Item", item_code)
        for fieldname, value in expected.items():
            if cint(doc.get(fieldname)) != value:
                frappe.throw(
                    f"Safety check failed: {item_code} has {fieldname}={doc.get(fieldname)!r}, expected {value!r}."
                )
        return doc.name

    doc = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_code.replace("-", " ").title(),
            "description": "Phase 7 ERPNext native buying/inventory fixture",
            "item_group": "Products" if stock else "Services",
            "stock_uom": "Nos",
            "is_stock_item": expected["is_stock_item"],
            "has_batch_no": expected["has_batch_no"],
            "has_serial_no": expected["has_serial_no"],
            "include_item_in_manufacturing": 0,
            "valuation_method": "FIFO",
            "custom_ledgix_legacy_item": f"P7-LEGACY-{item_code}",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_second_warehouse() -> str:
    existing = frappe.db.get_value(
        "Warehouse",
        {"warehouse_name": WAREHOUSE_2_NAME, "company": TEST_COMPANY},
        "name",
    )
    if existing:
        return existing
    parent = frappe.db.get_value(
        "Warehouse",
        {"company": TEST_COMPANY, "is_group": 1, "parent_warehouse": ["is", "not set"]},
        "name",
    )
    if not parent:
        parent = frappe.db.get_value(
            "Warehouse", {"company": TEST_COMPANY, "is_group": 1}, "name"
        )
    if not parent:
        frappe.throw("No group Warehouse exists for Phase 7 fixture setup.")
    doc = frappe.get_doc(
        {
            "doctype": "Warehouse",
            "warehouse_name": WAREHOUSE_2_NAME,
            "company": TEST_COMPANY,
            "parent_warehouse": parent,
            "is_group": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_cash_account() -> str:
    account = frappe.db.get_value(
        "Account",
        {"company": TEST_COMPANY, "account_type": "Cash", "is_group": 0, "disabled": 0},
        "name",
    )
    if not account:
        frappe.throw("No leaf Cash account exists for Phase 7 fixture company.")
    mode = frappe.get_doc("Mode of Payment", "Cash")
    row = next((entry for entry in mode.accounts if entry.company == TEST_COMPANY), None)
    if not row:
        mode.append("accounts", {"company": TEST_COMPANY, "default_account": account})
        mode.save(ignore_permissions=True)
    elif row.default_account != account:
        row.default_account = account
        mode.save(ignore_permissions=True)
    return account


def _ensure_fixtures() -> dict:
    erpnext_phase7_extensions.sync_all()
    supplier = _ensure_supplier()
    warehouse = erpnext_buying_inventory.default_warehouse(TEST_COMPANY)
    warehouse_2 = _ensure_second_warehouse()
    _ensure_cash_account()
    item_specs = {
        ITEM_PURCHASE: {},
        ITEM_DIRECT: {},
        ITEM_NONSTOCK: {"stock": False},
        ITEM_TRANSFER: {},
        ITEM_RECON: {},
        ITEM_BATCH: {"batch": True},
        ITEM_SERIAL: {"serial": True},
        ITEM_RETURN: {},
        ITEM_CANCEL: {},
        ITEM_BACKDATED: {},
    }
    items = {code: _ensure_item(code, **opts) for code, opts in item_specs.items()}
    frappe.db.commit()
    return {
        "supplier": supplier,
        "warehouse": warehouse,
        "warehouse_2": warehouse_2,
        "items": items,
    }


def _gl_count(doctype: str, name: str) -> int:
    return frappe.db.count(
        "GL Entry",
        {"voucher_type": doctype, "voucher_no": name, "is_cancelled": 0},
    )


def _sle_rows(voucher_type: str, voucher_no: str, item_code: str) -> list[dict]:
    return frappe.get_all(
        "Stock Ledger Entry",
        filters={
            "voucher_type": voucher_type,
            "voucher_no": voucher_no,
            "item_code": item_code,
            "is_cancelled": 0,
        },
        fields=[
            "warehouse",
            "posting_date",
            "actual_qty",
            "qty_after_transaction",
            "valuation_rate",
            "stock_value_difference",
        ],
        order_by="creation asc",
        limit_page_length=0,
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
            "traceback_tail": trace[-TRACEBACK_TAIL:],
        }


def _case_full_purchase_chain():
    po = erpnext_buying_inventory.create_purchase_order(
        supplier="P7-LEGACY-SUPPLIER-ID",
        items=[{"item": "P7-LEGACY-P7-PURCHASE", "qty": 5, "rate": 100}],
        company=TEST_COMPANY,
        client_purchase_id=_client("po"),
    )
    retry = erpnext_buying_inventory.create_purchase_order(
        supplier=SUPPLIER,
        items=[{"item_code": ITEM_PURCHASE, "qty": 5, "rate": 100}],
        company=TEST_COMPANY,
        client_purchase_id=_client("po"),
    )
    receipt = erpnext_buying_inventory.create_purchase_receipt(
        purchase_order=po.name,
        client_receipt_id=_client("pr"),
    )
    invoice = erpnext_buying_inventory.create_purchase_invoice_from_receipt(
        purchase_receipt=receipt.name,
        client_invoice_id=_client("pi"),
    )
    invoice.reload()
    existing_payment = frappe.db.get_value(
        "Payment Entry",
        {"custom_ledgix_client_payment_id": _client("supplier_payment"), "docstatus": 1},
        "name",
    )
    if existing_payment:
        payment = frappe.get_doc("Payment Entry", existing_payment)
    elif flt(invoice.outstanding_amount) > 0.005:
        payment = erpnext_buying_inventory.post_supplier_payment(
            purchase_invoice=invoice.name,
            mode_of_payment="Cash",
            client_payment_id=_client("supplier_payment"),
        )
    else:
        frappe.throw("Phase 7 purchase invoice is paid but its deterministic Payment Entry is missing.")
    invoice.reload()
    receipt_qty = erpnext_buying_inventory.stock_ledger_qty("Purchase Receipt", receipt.name, ITEM_PURCHASE)
    evidence = {
        "purchase_order": po.name,
        "retry_purchase_order": retry.name,
        "purchase_receipt": receipt.name,
        "purchase_invoice": invoice.name,
        "payment_entry": payment.name,
        "receipt_sle_qty": receipt_qty,
        "invoice_outstanding": flt(invoice.outstanding_amount, 2),
        "invoice_gl_entries": _gl_count("Purchase Invoice", invoice.name),
        "payment_gl_entries": _gl_count("Payment Entry", payment.name),
    }
    checks = {
        "purchase_order_submitted": po.docstatus == 1,
        "purchase_order_idempotent": po.name == retry.name,
        "purchase_receipt_submitted": receipt.docstatus == 1,
        "receipt_added_stock": abs(receipt_qty - 5) < 0.005,
        "purchase_invoice_submitted": invoice.docstatus == 1,
        "purchase_invoice_has_gl": evidence["invoice_gl_entries"] > 0,
        "supplier_payment_submitted": payment.docstatus == 1,
        "supplier_payment_has_gl": evidence["payment_gl_entries"] > 0,
        "invoice_fully_paid": abs(flt(invoice.outstanding_amount)) < 0.005,
    }
    return evidence, checks


def _case_direct_purchase_invoice():
    invoice = erpnext_buying_inventory.create_direct_purchase_invoice(
        supplier=SUPPLIER,
        items=[{"item_code": ITEM_DIRECT, "qty": 2, "rate": 120}],
        company=TEST_COMPANY,
        update_stock=True,
        client_purchase_id=_client("direct_purchase"),
        client_invoice_id=_client("direct_pi"),
    )
    qty = erpnext_buying_inventory.stock_ledger_qty("Purchase Invoice", invoice.name, ITEM_DIRECT)
    snapshot = erpnext_buying_inventory.stock_snapshot(ITEM_DIRECT, company=TEST_COMPANY)
    evidence = {
        "purchase_invoice": invoice.name,
        "sle_qty": qty,
        "gl_entries": _gl_count("Purchase Invoice", invoice.name),
        "snapshot": snapshot,
    }
    checks = {
        "submitted": invoice.docstatus == 1,
        "direct_purchase_added_stock": abs(qty - 2) < 0.005,
        "has_gl": evidence["gl_entries"] > 0,
        "bin_reads_native_stock": snapshot["actual_qty"] >= 2,
        "native_valuation_positive": snapshot["valuation_rate"] > 0,
    }
    return evidence, checks


def _case_nonstock_purchase():
    invoice = erpnext_buying_inventory.create_direct_purchase_invoice(
        supplier=SUPPLIER,
        items=[{"item_code": ITEM_NONSTOCK, "qty": 1, "rate": 300}],
        company=TEST_COMPANY,
        update_stock=False,
        client_purchase_id=_client("nonstock_purchase"),
        client_invoice_id=_client("nonstock_pi"),
    )
    qty = erpnext_buying_inventory.stock_ledger_qty("Purchase Invoice", invoice.name, ITEM_NONSTOCK)
    evidence = {"purchase_invoice": invoice.name, "sle_qty": qty, "gl_entries": _gl_count("Purchase Invoice", invoice.name)}
    checks = {
        "submitted": invoice.docstatus == 1,
        "financial_purchase_has_gl": evidence["gl_entries"] > 0,
        "nonstock_has_no_sle": abs(qty) < 0.005,
    }
    return evidence, checks


def _case_transfer():
    warehouse = erpnext_buying_inventory.default_warehouse(TEST_COMPANY)
    warehouse_2 = _ensure_second_warehouse()
    receipt = erpnext_buying_inventory.create_stock_entry(
        item=ITEM_TRANSFER,
        qty=3,
        purpose="Material Receipt",
        company=TEST_COMPANY,
        target_warehouse=warehouse,
        valuation_rate=75,
        client_stock_id=_client("transfer_seed"),
    )
    transfer = erpnext_buying_inventory.create_stock_entry(
        item=ITEM_TRANSFER,
        qty=1,
        purpose="Material Transfer",
        company=TEST_COMPANY,
        source_warehouse=warehouse,
        target_warehouse=warehouse_2,
        client_stock_id=_client("transfer"),
    )
    rows = _sle_rows("Stock Entry", transfer.name, ITEM_TRANSFER)
    source_qty = sum(flt(row.actual_qty) for row in rows if row.warehouse == warehouse)
    target_qty = sum(flt(row.actual_qty) for row in rows if row.warehouse == warehouse_2)
    evidence = {"seed": receipt.name, "transfer": transfer.name, "rows": rows}
    checks = {
        "transfer_submitted": transfer.docstatus == 1,
        "source_reduced_one": abs(source_qty + 1) < 0.005,
        "target_added_one": abs(target_qty - 1) < 0.005,
        "transfer_net_zero": abs(source_qty + target_qty) < 0.005,
    }
    return evidence, checks


def _case_reconciliation():
    warehouse = erpnext_buying_inventory.default_warehouse(TEST_COMPANY)
    doc = erpnext_buying_inventory.create_stock_reconciliation(
        item=ITEM_RECON,
        qty=7,
        valuation_rate=25,
        warehouse=warehouse,
        company=TEST_COMPANY,
        client_reconciliation_id=_client("reconciliation"),
    )
    snapshot = erpnext_buying_inventory.stock_snapshot(ITEM_RECON, warehouse=warehouse, company=TEST_COMPANY)
    rows = _sle_rows("Stock Reconciliation", doc.name, ITEM_RECON)
    evidence = {"reconciliation": doc.name, "snapshot": snapshot, "sle_rows": rows}
    checks = {
        "submitted": doc.docstatus == 1,
        "target_quantity_exact": abs(snapshot["actual_qty"] - 7) < 0.005,
        "native_sle_present": bool(rows),
        "valuation_positive": snapshot["valuation_rate"] > 0,
    }
    return evidence, checks


def _case_batch():
    warehouse = erpnext_buying_inventory.default_warehouse(TEST_COMPANY)
    batch = erpnext_buying_inventory.ensure_batch(ITEM_BATCH, BATCH_NO)
    receipt = erpnext_buying_inventory.create_stock_entry(
        item=ITEM_BATCH,
        qty=3,
        purpose="Material Receipt",
        company=TEST_COMPANY,
        target_warehouse=warehouse,
        valuation_rate=60,
        batch_no=batch,
        client_stock_id=_client("batch_receipt"),
    )
    issue = erpnext_buying_inventory.create_stock_entry(
        item=ITEM_BATCH,
        qty=1,
        purpose="Material Issue",
        company=TEST_COMPANY,
        source_warehouse=warehouse,
        batch_no=batch,
        client_stock_id=_client("batch_issue"),
    )
    snapshot = erpnext_buying_inventory.stock_snapshot(ITEM_BATCH, warehouse=warehouse, company=TEST_COMPANY)
    evidence = {
        "batch": batch,
        "receipt": receipt.name,
        "issue": issue.name,
        "receipt_bundle": receipt.items[0].serial_and_batch_bundle,
        "issue_bundle": issue.items[0].serial_and_batch_bundle,
        "snapshot": snapshot,
    }
    checks = {
        "batch_exists": bool(frappe.db.exists("Batch", batch)),
        "receipt_has_bundle": bool(receipt.items[0].serial_and_batch_bundle),
        "issue_has_bundle": bool(issue.items[0].serial_and_batch_bundle),
        "native_batch_balance_two": abs(snapshot["actual_qty"] - 2) < 0.005,
    }
    return evidence, checks


def _case_serial():
    warehouse = erpnext_buying_inventory.default_warehouse(TEST_COMPANY)
    receipt = erpnext_buying_inventory.create_stock_entry(
        item=ITEM_SERIAL,
        qty=2,
        purpose="Material Receipt",
        company=TEST_COMPANY,
        target_warehouse=warehouse,
        valuation_rate=90,
        serial_numbers=SERIALS,
        client_stock_id=_client("serial_receipt"),
    )
    before = {row["serial_no"] for row in erpnext_buying_inventory.available_serials(ITEM_SERIAL, warehouse=warehouse)}
    issue = erpnext_buying_inventory.create_stock_entry(
        item=ITEM_SERIAL,
        qty=1,
        purpose="Material Issue",
        company=TEST_COMPANY,
        source_warehouse=warehouse,
        serial_numbers=[SERIALS[0]],
        client_stock_id=_client("serial_issue"),
    )
    after = {row["serial_no"] for row in erpnext_buying_inventory.available_serials(ITEM_SERIAL, warehouse=warehouse)}
    evidence = {
        "receipt": receipt.name,
        "issue": issue.name,
        "available_before_issue": sorted(before),
        "available_after_issue": sorted(after),
        "receipt_bundle": receipt.items[0].serial_and_batch_bundle,
        "issue_bundle": issue.items[0].serial_and_batch_bundle,
    }
    checks = {
        "serial_docs_exist": all(frappe.db.exists("Serial No", serial) for serial in SERIALS),
        "both_available_after_receipt": set(SERIALS).issubset(before),
        "issued_serial_removed_from_warehouse": SERIALS[0] not in after,
        "remaining_serial_available": SERIALS[1] in after,
        "receipt_has_bundle": bool(receipt.items[0].serial_and_batch_bundle),
        "issue_has_bundle": bool(issue.items[0].serial_and_batch_bundle),
    }
    return evidence, checks


def _case_purchase_return():
    original = erpnext_buying_inventory.create_direct_purchase_invoice(
        supplier=SUPPLIER,
        items=[{"item_code": ITEM_RETURN, "qty": 1, "rate": 140}],
        company=TEST_COMPANY,
        update_stock=True,
        client_purchase_id=_client("return_source_purchase"),
        client_invoice_id=_client("return_source_pi"),
    )
    note = erpnext_buying_inventory.create_purchase_return(
        purchase_invoice=original.name,
        client_invoice_id=_client("purchase_return"),
    )
    source_qty = erpnext_buying_inventory.stock_ledger_qty("Purchase Invoice", original.name, ITEM_RETURN)
    return_qty = erpnext_buying_inventory.stock_ledger_qty("Purchase Invoice", note.name, ITEM_RETURN)
    evidence = {
        "source": original.name,
        "return": note.name,
        "return_against": note.return_against,
        "source_sle_qty": source_qty,
        "return_sle_qty": return_qty,
        "return_grand_total": flt(note.grand_total, 2),
        "return_gl_entries": _gl_count("Purchase Invoice", note.name),
    }
    checks = {
        "return_submitted": note.docstatus == 1,
        "linked_to_source": note.return_against == original.name,
        "source_added_one": abs(source_qty - 1) < 0.005,
        "return_removed_one": abs(return_qty + 1) < 0.005,
        "return_total_negative": flt(note.grand_total) < 0,
        "return_has_gl": evidence["return_gl_entries"] > 0,
    }
    return evidence, checks


def _case_cancel_and_backdated():
    warehouse = erpnext_buying_inventory.default_warehouse(TEST_COMPANY)
    before = erpnext_buying_inventory.stock_snapshot(ITEM_CANCEL, warehouse=warehouse, company=TEST_COMPANY)["actual_qty"]
    entry = erpnext_buying_inventory.create_stock_entry(
        item=ITEM_CANCEL,
        qty=1,
        purpose="Material Receipt",
        company=TEST_COMPANY,
        target_warehouse=warehouse,
        valuation_rate=50,
        client_stock_id=_client("cancel_receipt"),
    )
    if entry.docstatus == 1:
        entry = erpnext_buying_inventory.cancel_native_voucher("Stock Entry", entry.name)
    after = erpnext_buying_inventory.stock_snapshot(ITEM_CANCEL, warehouse=warehouse, company=TEST_COMPANY)["actual_qty"]

    existing = frappe.db.get_value(
        "Stock Entry",
        {"custom_ledgix_client_stock_id": _client("backdated"), "docstatus": 1},
        "name",
    )
    if existing:
        backdated = frappe.get_doc("Stock Entry", existing)
    else:
        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

        posting_date = add_days(nowdate(), -1)
        backdated = make_stock_entry(
            item_code=ITEM_BACKDATED,
            qty=1,
            company=TEST_COMPANY,
            rate=40,
            do_not_save=True,
            to_warehouse=warehouse,
            purpose="Material Receipt",
            posting_date=posting_date,
        )
        backdated.custom_ledgix_client_stock_id = _client("backdated")
        backdated.custom_ledgix_stock_source = "Phase 7 backdated policy proof"
        backdated.insert(ignore_permissions=True)
        backdated.submit()
        backdated.reload()
    backdated_rows = _sle_rows("Stock Entry", backdated.name, ITEM_BACKDATED)
    expected_date = add_days(nowdate(), -1)
    evidence = {
        "cancelled_entry": entry.name,
        "cancelled_docstatus": entry.docstatus,
        "cancel_stock_before": before,
        "cancel_stock_after": after,
        "backdated_entry": backdated.name,
        "expected_posting_date": expected_date,
        "sle_posting_dates": [str(row.posting_date) for row in backdated_rows],
    }
    checks = {
        "stock_entry_cancelled": entry.docstatus == 2,
        "cancel_restored_quantity": abs(after - before) < 0.005,
        "backdated_entry_submitted": backdated.docstatus == 1,
        "backdated_sle_uses_requested_date": bool(backdated_rows) and all(str(row.posting_date) == str(expected_date) for row in backdated_rows),
    }
    return evidence, checks


def _case_valuation_authority():
    warehouse = erpnext_buying_inventory.default_warehouse(TEST_COMPANY)
    snapshot = erpnext_buying_inventory.stock_snapshot(ITEM_PURCHASE, warehouse=warehouse, company=TEST_COMPANY)
    rows = frappe.get_all(
        "Stock Ledger Entry",
        filters={"item_code": ITEM_PURCHASE, "warehouse": warehouse, "is_cancelled": 0},
        fields=["valuation_rate", "stock_value", "stock_value_difference"],
        order_by="creation desc",
        limit=5,
    )
    evidence = {"snapshot": snapshot, "recent_sle": rows}
    checks = {
        "bin_is_authority": snapshot["authority"] == "ERPNext Bin + Stock Ledger Entry",
        "valuation_rate_positive": snapshot["valuation_rate"] > 0,
        "stock_ledger_evidence_present": bool(rows),
        "stock_value_is_erpnext_derived": snapshot["stock_value"] > 0,
    }
    return evidence, checks


def run() -> dict:
    """Prove Phase 7 buying/inventory authority on standard ERPNext documents."""

    _assert_safe_site()
    frappe.set_user("Administrator")
    fixtures = _ensure_fixtures()
    legacy_before = _legacy_counts()

    cases = {
        "full_purchase_chain": _case("full_purchase_chain", _case_full_purchase_chain),
        "direct_purchase_invoice_stock": _case("direct_purchase_invoice_stock", _case_direct_purchase_invoice),
        "nonstock_purchase_financial_only": _case("nonstock_purchase_financial_only", _case_nonstock_purchase),
        "material_transfer": _case("material_transfer", _case_transfer),
        "stock_reconciliation": _case("stock_reconciliation", _case_reconciliation),
        "batch_bundle_authority": _case("batch_bundle_authority", _case_batch),
        "serial_number_authority": _case("serial_number_authority", _case_serial),
        "purchase_return": _case("purchase_return", _case_purchase_return),
        "cancel_and_backdated_behavior": _case("cancel_and_backdated_behavior", _case_cancel_and_backdated),
        "valuation_authority": _case("valuation_authority", _case_valuation_authority),
    }

    legacy_after = _legacy_counts()
    unchanged = legacy_before == legacy_after
    cases["no_parallel_ledgix_inventory_docs"] = {
        "name": "no_parallel_ledgix_inventory_docs",
        "evidence": {"before": legacy_before, "after": legacy_after},
        "checks": {"legacy_purchase_stock_counts_unchanged": unchanged},
        "passed": unchanged,
    }

    failed = [name for name, case in cases.items() if not case.get("passed")]
    complete = not failed
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
            "buying_authority": "ERPNext Purchase Order / Purchase Receipt / Purchase Invoice",
            "supplier_payment_authority": "ERPNext Payment Entry",
            "stock_authority": "ERPNext Stock Entry / Stock Reconciliation / Stock Ledger Entry",
            "availability_authority": "ERPNext Bin / Serial No / Batch / Serial and Batch Bundle",
            "valuation_authority": "ERPNext Stock Ledger / Bin",
            "legacy_purchase_stock_doctypes_retired": False,
            "retail_pos_cutover_performed": False,
        },
        "phase7_complete": complete,
        "phase8_ready": complete,
        "next_phase": "Phase 8 — POS Engine Migration",
        "passed": complete,
    }
    frappe.db.commit()
    return result
