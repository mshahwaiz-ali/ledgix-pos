from __future__ import annotations

import frappe
from frappe.utils import flt

from ledgix_saas.api.security import require_ledgix_manager_or_above
from ledgix_saas.services import erpnext_buying_inventory


def _serial_list(serial_numbers) -> list[str]:
    if isinstance(serial_numbers, str):
        raw = serial_numbers.replace(",", "\n").splitlines()
    else:
        raw = serial_numbers or []
    return [str(value).strip() for value in raw if str(value).strip()]


def _native_batch_for_manual_in(item_code: str, batch_no: str | None) -> str | None:
    if not frappe.db.get_value("Item", item_code, "has_batch_no"):
        return None
    batch_no = str(batch_no or "").strip()
    if not batch_no:
        batch_no = f"LEDGIX-MANUAL-{frappe.generate_hash(length=10).upper()}"
    return erpnext_buying_inventory.ensure_batch(item_code, batch_no)


def _valuation_rate(item_input: str, item_code: str, warehouse: str, requested=None) -> float:
    if requested not in (None, ""):
        return max(flt(requested), 0)
    snapshot = erpnext_buying_inventory.stock_snapshot(item_code, warehouse=warehouse)
    if flt(snapshot.get("valuation_rate")) > 0:
        return flt(snapshot["valuation_rate"])
    frappe.throw(
        "No positive ERPNext valuation rate is available for this Item and Warehouse. "
        "Enter an explicit Valuation Rate for the native stock receipt "
        "(including zero only when intentionally authorized)."
    )


@frappe.whitelist()
def manual_stock_entry(
    item,
    qty_in=0,
    qty_out=0,
    serial_numbers=None,
    note=None,
    warehouse=None,
    batch_no=None,
    valuation_rate=None,
    client_stock_id=None,
):
    """Create a native ERPNext Stock Entry while preserving the old RPC shape."""

    require_ledgix_manager_or_above()
    item_input = str(item or "").strip()
    qty_in = flt(qty_in)
    qty_out = flt(qty_out)
    note = str(note or "").strip()
    if not item_input:
        frappe.throw("Item is required.")
    if not note:
        frappe.throw("Reason / Note is required for a manual stock adjustment.")
    if qty_in <= 0 and qty_out <= 0:
        frappe.throw("Enter Add Stock or Remove Stock quantity.")
    if qty_in > 0 and qty_out > 0:
        frappe.throw("Enter either Add Stock or Remove Stock, not both at the same time.")

    item_code = erpnext_buying_inventory._resolve_item(item_input)
    company = erpnext_buying_inventory._company(None)
    warehouse = erpnext_buying_inventory._resolve_warehouse(warehouse, company)
    has_serial = bool(frappe.db.get_value("Item", item_code, "has_serial_no"))
    has_batch = bool(frappe.db.get_value("Item", item_code, "has_batch_no"))
    serials = _serial_list(serial_numbers)

    if has_serial and qty_out > 0:
        frappe.throw(
            "Serial-tracked items cannot be reduced from this compatibility action. "
            "Use the native Stock Entry flow and select the exact ERPNext Serial Nos."
        )
    if has_serial and qty_in > 0 and len(serials) != int(qty_in):
        frappe.throw("Serial number count must match Add Stock quantity.")
    if has_batch and qty_out > 0 and not str(batch_no or "").strip():
        frappe.throw("Batch No is required when removing a batch-tracked item.")

    client_stock_id = str(client_stock_id or "").strip() or f"MANUAL-{frappe.generate_hash(length=16)}"
    created = []
    native_batch = None

    if qty_in > 0:
        native_batch = _native_batch_for_manual_in(item_code, batch_no)
        entry = erpnext_buying_inventory.create_stock_entry(
            item=item_code,
            qty=qty_in,
            purpose="Material Receipt",
            company=company,
            target_warehouse=warehouse,
            valuation_rate=_valuation_rate(item_input, item_code, warehouse, valuation_rate),
            batch_no=native_batch,
            serial_numbers=serials,
            client_stock_id=client_stock_id,
            source="Ledgix Manual IN",
            remarks=note,
        )
        created.append(entry.name)

    if qty_out > 0:
        entry = erpnext_buying_inventory.create_stock_entry(
            item=item_code,
            qty=qty_out,
            purpose="Material Issue",
            company=company,
            source_warehouse=warehouse,
            batch_no=str(batch_no or "").strip() or None,
            client_stock_id=client_stock_id,
            source="Ledgix Manual OUT",
            remarks=note,
        )
        created.append(entry.name)

    snapshot = erpnext_buying_inventory.stock_snapshot(item_code, warehouse=warehouse, company=company)
    return {
        "item": item_input,
        "erpnext_item": item_code,
        "movements": created,
        "lot_name": native_batch,
        "batch_no": native_batch,
        "serial_count": len(serials),
        "current_stock": flt(snapshot["actual_qty"]),
        "warehouse": warehouse,
        "authority": "ERPNext Stock Entry + Stock Ledger Entry",
    }


@frappe.whitelist()
def record_opening_stock(
    item,
    qty,
    serial_numbers=None,
    warehouse=None,
    batch_no=None,
    valuation_rate=None,
    client_stock_id=None,
):
    require_ledgix_manager_or_above()
    qty = flt(qty)
    if qty <= 0:
        return None
    result = manual_stock_entry(
        item=item,
        qty_in=qty,
        serial_numbers=serial_numbers,
        note="Opening Stock",
        warehouse=warehouse,
        batch_no=batch_no,
        valuation_rate=valuation_rate,
        client_stock_id=client_stock_id or f"OPENING-{frappe.generate_hash(length=16)}",
    )
    return (result.get("movements") or [None])[0]
