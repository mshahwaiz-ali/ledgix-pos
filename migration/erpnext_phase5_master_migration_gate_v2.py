from __future__ import annotations

import frappe
from frappe.utils import flt

from ledgix_saas.api import stock_ops
from ledgix_saas.migration import erpnext_phase5_master_migration_gate as base


NAMES = {
    "CATEGORY": "P5-Retail-Category",
    "PRICE_LIST": "P5-Retail",
    "CUSTOMER": "P5-Customer",
    "SUPPLIER": "P5-Supplier",
    "PAYMENT_METHOD": "P5-Wallet",
    "TAX_CATEGORY": "P5-Standard-18",
}


def _apply_names() -> dict[str, str]:
    previous = {}
    for key, value in NAMES.items():
        previous[key] = getattr(base, key)
        setattr(base, key, value)
    return previous


def _restore_names(previous: dict[str, str]) -> None:
    for key, value in previous.items():
        setattr(base, key, value)


def _ensure_exact_serial_opening(serial_item) -> list[str]:
    expected = list(base.SERIALS)
    rows = frappe.get_all(
        "Ledgix Stock Serial",
        filters={"item": serial_item.name, "status": ["!=", "Cancelled"]},
        fields=["name", "serial_no", "status"],
        order_by="creation asc, name asc",
        limit_page_length=0,
    )
    current_qty = flt(serial_item.current_stock)

    if current_qty <= 0.000001 and not rows:
        stock_ops.record_opening_stock(
            serial_item.name,
            len(expected),
            serial_numbers="\n".join(expected),
        )
        serial_item.reload()
        rows = frappe.get_all(
            "Ledgix Stock Serial",
            filters={"item": serial_item.name, "status": ["!=", "Cancelled"]},
            fields=["name", "serial_no", "status"],
            order_by="creation asc, name asc",
            limit_page_length=0,
        )
        current_qty = flt(serial_item.current_stock)

    actual = [row.serial_no for row in rows if row.status in {"Available", "Returned"}]
    if current_qty != len(expected) or sorted(actual) != sorted(expected):
        frappe.throw(
            "Phase 5 serial fixture is inconsistent: "
            f"current_stock={current_qty}, available={actual}, expected={expected}."
        )
    return [row.name for row in rows if row.serial_no in expected]


def _ensure_legacy_fixtures() -> dict:
    base._ensure_tax_category()
    base._ensure_category()
    base._ensure_price_list()

    normal = base._ensure_legacy_item(
        base.NORMAL_ITEM, "Normal", 5, 100, 150, "P5BAR001", "P5SKU001"
    )
    batch = base._ensure_legacy_item(
        base.BATCH_ITEM, "Lot Based", 3, 110, 165, "P5BAR002", "P5SKU002"
    )
    # A Serial Based Ledgix Item auto-generates serial numbers when opening_stock
    # is supplied during insert. Create it at zero and then post one exact
    # opening movement with deterministic legacy serial identities.
    serial = base._ensure_legacy_item(
        base.SERIAL_ITEM, "Serial Based", 0, 120, 180, "P5BAR003", "P5SKU003"
    )

    lot = base._ensure_lot(batch.name, 3, 110)
    serial_rows = _ensure_exact_serial_opening(serial)
    prices = {
        normal.name: base._ensure_item_price(normal.name, 155),
        batch.name: base._ensure_item_price(batch.name, 170),
        serial.name: base._ensure_item_price(serial.name, 185),
    }
    customer = base._ensure_customer()
    supplier = base._ensure_supplier()
    method = base._ensure_payment_method()
    profiles = {
        item.name: base._ensure_item_profile(item.name)
        for item in (normal, batch, serial)
    }
    frappe.db.commit()
    return {
        "category": base.CATEGORY,
        "price_list": base.PRICE_LIST,
        "items": [normal.name, batch.name, serial.name],
        "lot": lot,
        "serial_rows": serial_rows,
        "prices": prices,
        "customer": customer,
        "supplier": supplier,
        "payment_method": method,
        "profiles": profiles,
    }


def run() -> dict:
    previous_names = _apply_names()
    original_fixtures = base._ensure_legacy_fixtures
    base._ensure_legacy_fixtures = _ensure_legacy_fixtures
    try:
        result = base.run()
        result["fixture_namespace"] = dict(NAMES)
        return result
    finally:
        base._ensure_legacy_fixtures = original_fixtures
        _restore_names(previous_names)
