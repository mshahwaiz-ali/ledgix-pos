from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.migration.erpnext_stock_purchase_behavioral_spike import _bin_qty, _leaf_warehouse


STOCK_ENTRY_ITEM = "LEDGIX-STOCK-ENTRY-SPIKE"
STOCK_ENTRY_RECEIPT_MARKER = "LEDGIX-ERPNEXT-STOCK-ENTRY-RECEIPT-V1"
STOCK_RECON_QTY = 7.0
STOCK_RECEIPT_QTY = 5.0
STOCK_RATE = 100.0

BATCH_ITEM = "LEDGIX-BATCH-SPIKE"
BATCH_ID = "LEDGIX-BATCH-001"
BATCH_RECEIPT_MARKER = "LEDGIX-ERPNEXT-BATCH-RECEIPT-V1"
BATCH_ISSUE_MARKER = "LEDGIX-ERPNEXT-BATCH-ISSUE-V1"
BATCH_RECEIPT_QTY = 3.0
BATCH_ISSUE_QTY = 1.0

SERIAL_ITEM = "LEDGIX-SERIAL-SPIKE"
SERIAL_NUMBERS = ["LEDGIX-SERIAL-001", "LEDGIX-SERIAL-002"]
SERIAL_RECEIPT_MARKER = "LEDGIX-ERPNEXT-SERIAL-RECEIPT-V1"
SERIAL_ISSUE_MARKER = "LEDGIX-ERPNEXT-SERIAL-ISSUE-V1"
SERIAL_RECEIPT_QTY = 2.0
SERIAL_ISSUE_QTY = 1.0


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing ERPNext stock-tracking behavioral spike on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing; run the integration bootstrap first.")


def _ensure_stock_item(item_code: str, **properties) -> str:
    if frappe.db.exists("Item", item_code):
        item = frappe.get_doc("Item", item_code)
        for fieldname, expected in properties.items():
            if item.get(fieldname) != expected:
                frappe.throw(
                    f"Safety check failed: existing Item {item_code!r} has {fieldname}={item.get(fieldname)!r}, "
                    f"expected {expected!r}."
                )
        return item.name

    values = {
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code.replace("-", " ").title(),
        "description": "ERPNext extended stock behavior integration spike",
        "item_group": "Products",
        "stock_uom": "Nos",
        "is_stock_item": 1,
        "include_item_in_manufacturing": 0,
        "valuation_method": "FIFO",
    }
    values.update(properties)
    item = frappe.get_doc(values)
    item.insert(ignore_permissions=True)
    return item.name


def _stock_entry_by_marker(marker: str):
    name = frappe.db.get_value(
        "Stock Entry",
        {"company": TEST_COMPANY, "remarks": marker, "docstatus": 1},
        "name",
    )
    return frappe.get_doc("Stock Entry", name) if name else None


def _ensure_stock_entry(
    *,
    item_code: str,
    marker: str,
    qty: float,
    warehouse: str,
    inward: bool,
    rate: float = STOCK_RATE,
    batch_no: str | None = None,
    serial_no: str | None = None,
):
    existing = _stock_entry_by_marker(marker)
    if existing:
        return existing

    from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

    kwargs = {
        "item_code": item_code,
        "qty": qty,
        "company": TEST_COMPANY,
        "rate": rate,
        "do_not_save": True,
        "use_serial_batch_fields": 0,
    }
    if inward:
        kwargs["to_warehouse"] = warehouse
        kwargs["purpose"] = "Material Receipt"
    else:
        kwargs["from_warehouse"] = warehouse
        kwargs["purpose"] = "Material Issue"
    if batch_no:
        kwargs["batch_no"] = batch_no
    if serial_no:
        kwargs["serial_no"] = serial_no

    doc = make_stock_entry(**kwargs)
    doc.remarks = marker
    doc.insert(ignore_permissions=True)
    doc.submit()
    doc.reload()
    return doc


def _find_stock_reconciliation(item_code: str, warehouse: str):
    rows = frappe.db.sql(
        """
        select sr.name
        from `tabStock Reconciliation` sr
        inner join `tabStock Reconciliation Item` sri on sri.parent = sr.name
        where sr.company = %s
          and sr.docstatus = 1
          and sri.item_code = %s
          and sri.warehouse = %s
        order by sr.creation asc
        limit 1
        """,
        (TEST_COMPANY, item_code, warehouse),
        as_dict=True,
    )
    return frappe.get_doc("Stock Reconciliation", rows[0].name) if rows else None


def _ensure_stock_reconciliation(item_code: str, warehouse: str):
    existing = _find_stock_reconciliation(item_code, warehouse)
    if existing:
        return existing

    doc = frappe.get_doc(
        {
            "doctype": "Stock Reconciliation",
            "company": TEST_COMPANY,
            "purpose": "Stock Reconciliation",
            "posting_date": nowdate(),
            "items": [
                {
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "qty": STOCK_RECON_QTY,
                    "valuation_rate": STOCK_RATE,
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    doc.reload()
    return doc


def _ensure_batch(item_code: str) -> str:
    if frappe.db.exists("Batch", BATCH_ID):
        item = frappe.db.get_value("Batch", BATCH_ID, "item")
        if item != item_code:
            frappe.throw(f"Safety check failed: Batch {BATCH_ID!r} belongs to {item!r}, not {item_code!r}.")
        return BATCH_ID

    batch = frappe.get_doc(
        {
            "doctype": "Batch",
            "batch_id": BATCH_ID,
            "item": item_code,
            "manufacturing_date": nowdate(),
        }
    )
    batch.insert(ignore_permissions=True)
    return batch.name


def _sle_qty(voucher_type: str, voucher_no: str, item_code: str) -> float:
    result = frappe.db.sql(
        """
        select coalesce(sum(actual_qty), 0)
        from `tabStock Ledger Entry`
        where voucher_type = %s
          and voucher_no = %s
          and item_code = %s
          and is_cancelled = 0
        """,
        (voucher_type, voucher_no, item_code),
    )
    return flt(result[0][0] if result else 0)


def _bundle(doc) -> str:
    if not doc.items:
        return ""
    return str(doc.items[0].serial_and_batch_bundle or "")


def run() -> dict:
    """Prove native Stock Entry/Reconciliation plus Batch/Serial bundle behavior."""

    _assert_safe_site()
    frappe.set_user("Administrator")
    warehouse = _leaf_warehouse()

    stock_item = _ensure_stock_item(STOCK_ENTRY_ITEM)
    stock_receipt = _ensure_stock_entry(
        item_code=stock_item,
        marker=STOCK_ENTRY_RECEIPT_MARKER,
        qty=STOCK_RECEIPT_QTY,
        warehouse=warehouse,
        inward=True,
    )
    stock_reconciliation = _ensure_stock_reconciliation(stock_item, warehouse)

    batch_item = _ensure_stock_item(BATCH_ITEM, has_batch_no=1, create_new_batch=0)
    batch_id = _ensure_batch(batch_item)
    batch_receipt = _ensure_stock_entry(
        item_code=batch_item,
        marker=BATCH_RECEIPT_MARKER,
        qty=BATCH_RECEIPT_QTY,
        warehouse=warehouse,
        inward=True,
        batch_no=batch_id,
    )
    batch_issue = _ensure_stock_entry(
        item_code=batch_item,
        marker=BATCH_ISSUE_MARKER,
        qty=BATCH_ISSUE_QTY,
        warehouse=warehouse,
        inward=False,
        batch_no=batch_id,
    )

    serial_item = _ensure_stock_item(SERIAL_ITEM, has_serial_no=1)
    serial_receipt = _ensure_stock_entry(
        item_code=serial_item,
        marker=SERIAL_RECEIPT_MARKER,
        qty=SERIAL_RECEIPT_QTY,
        warehouse=warehouse,
        inward=True,
        serial_no="\n".join(SERIAL_NUMBERS),
    )
    serial_issue = _ensure_stock_entry(
        item_code=serial_item,
        marker=SERIAL_ISSUE_MARKER,
        qty=SERIAL_ISSUE_QTY,
        warehouse=warehouse,
        inward=False,
        serial_no=SERIAL_NUMBERS[0],
    )

    stock_receipt_sle = _sle_qty("Stock Entry", stock_receipt.name, stock_item)
    reconciliation_sle = _sle_qty("Stock Reconciliation", stock_reconciliation.name, stock_item)
    batch_receipt_sle = _sle_qty("Stock Entry", batch_receipt.name, batch_item)
    batch_issue_sle = _sle_qty("Stock Entry", batch_issue.name, batch_item)
    serial_receipt_sle = _sle_qty("Stock Entry", serial_receipt.name, serial_item)
    serial_issue_sle = _sle_qty("Stock Entry", serial_issue.name, serial_item)

    evidence = {
        "site": frappe.local.site,
        "company": TEST_COMPANY,
        "warehouse": warehouse,
        "stock_entry_reconciliation": {
            "item": stock_item,
            "receipt": stock_receipt.name,
            "receipt_docstatus": stock_receipt.docstatus,
            "receipt_sle_qty": stock_receipt_sle,
            "reconciliation": stock_reconciliation.name,
            "reconciliation_docstatus": stock_reconciliation.docstatus,
            "reconciliation_sle_qty": reconciliation_sle,
            "final_bin_qty": _bin_qty(stock_item, warehouse),
            "target_qty": STOCK_RECON_QTY,
        },
        "batch": {
            "item": batch_item,
            "batch": batch_id,
            "receipt": batch_receipt.name,
            "receipt_bundle": _bundle(batch_receipt),
            "receipt_sle_qty": batch_receipt_sle,
            "issue": batch_issue.name,
            "issue_bundle": _bundle(batch_issue),
            "issue_sle_qty": batch_issue_sle,
            "final_bin_qty": _bin_qty(batch_item, warehouse),
        },
        "serial": {
            "item": serial_item,
            "serial_numbers": SERIAL_NUMBERS,
            "serial_docs_exist": {serial: bool(frappe.db.exists("Serial No", serial)) for serial in SERIAL_NUMBERS},
            "receipt": serial_receipt.name,
            "receipt_bundle": _bundle(serial_receipt),
            "receipt_sle_qty": serial_receipt_sle,
            "issue": serial_issue.name,
            "issue_bundle": _bundle(serial_issue),
            "issue_sle_qty": serial_issue_sle,
            "final_bin_qty": _bin_qty(serial_item, warehouse),
        },
    }

    checks = {
        "stock_entry_submitted": stock_receipt.docstatus == 1,
        "stock_entry_added_qty": abs(stock_receipt_sle - STOCK_RECEIPT_QTY) < 0.005,
        "stock_reconciliation_submitted": stock_reconciliation.docstatus == 1,
        "stock_reconciliation_target_qty": abs(
            evidence["stock_entry_reconciliation"]["final_bin_qty"] - STOCK_RECON_QTY
        ) < 0.005,
        "stock_reconciliation_created_ledger_effect": abs(reconciliation_sle) > 0.005,
        "batch_exists": bool(frappe.db.exists("Batch", batch_id)),
        "batch_receipt_has_bundle": bool(evidence["batch"]["receipt_bundle"]),
        "batch_issue_has_bundle": bool(evidence["batch"]["issue_bundle"]),
        "batch_receipt_added_qty": abs(batch_receipt_sle - BATCH_RECEIPT_QTY) < 0.005,
        "batch_issue_removed_qty": abs(batch_issue_sle + BATCH_ISSUE_QTY) < 0.005,
        "batch_final_qty_correct": abs(
            evidence["batch"]["final_bin_qty"] - (BATCH_RECEIPT_QTY - BATCH_ISSUE_QTY)
        ) < 0.005,
        "serial_docs_created": all(evidence["serial"]["serial_docs_exist"].values()),
        "serial_receipt_has_bundle": bool(evidence["serial"]["receipt_bundle"]),
        "serial_issue_has_bundle": bool(evidence["serial"]["issue_bundle"]),
        "serial_receipt_added_qty": abs(serial_receipt_sle - SERIAL_RECEIPT_QTY) < 0.005,
        "serial_issue_removed_qty": abs(serial_issue_sle + SERIAL_ISSUE_QTY) < 0.005,
        "serial_final_qty_correct": abs(
            evidence["serial"]["final_bin_qty"] - (SERIAL_RECEIPT_QTY - SERIAL_ISSUE_QTY)
        ) < 0.005,
    }

    evidence["checks"] = checks
    evidence["passed"] = all(checks.values())
    frappe.db.commit()
    return evidence
