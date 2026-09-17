from __future__ import annotations

"""Stock-safe local runtime for the retail operating dataset.

The native demo engine intentionally backdates purchases, transfers, POS shifts,
returns and stock shaping. For the realistic retail profile we keep that tested
transaction engine, but correct two temporal assumptions:

* the first POS shift starts 84 days ago, so POS-floor stock must arrive before
  that shift rather than two days after it;
* final low-stock shaping must inspect stock at the issue posting date rather
  than today's Bin quantity (which may include later returns).

This module also gives batch/serial examples clean retail identifiers so the
new dataset does not leak historical LXD/DEMO naming into the UI.
"""

from datetime import time

import frappe
from frappe.utils import add_days, flt, getdate

from erpnext.stock.utils import get_stock_balance
from ledgix_saas.services import erpnext_buying_inventory
from ledgix_saas.setup import demo_data
from ledgix_saas.setup import erpnext_demo_data as native
from ledgix_saas.setup import retail_operating_profile as retail


def _historical_qty(item_code: str, warehouse: str, date_value, hour: int = 10, minute: int = 59) -> float:
    return flt(
        get_stock_balance(
            item_code,
            warehouse,
            posting_date=getdate(date_value),
            posting_time=time(hour, minute, 59),
        )
    )


def _ensure_historical_source_stock(
    company: str,
    *,
    item_code: str,
    warehouse: str,
    required_qty: float,
    balance_date,
    receipt_date,
    marker: str,
) -> float:
    """Top up only the historical shortfall before a planned stock movement."""
    balance = _historical_qty(item_code, warehouse, balance_date)
    if balance + 1e-9 >= required_qty:
        return balance

    # Keep a realistic back-store buffer while guaranteeing the downstream move.
    target = max(220.0, flt(required_qty))
    qty = target - balance
    native._stock_entry(
        company,
        item_code=item_code,
        qty=qty,
        date_value=receipt_date,
        purpose="Material Receipt",
        target_warehouse=warehouse,
        valuation_rate=native.ITEM_BY_CODE[item_code]["cost"],
        marker=marker,
    )
    balance = _historical_qty(item_code, warehouse, balance_date)
    if balance + 1e-9 < required_qty:
        frappe.throw(
            f"Historical stock preparation failed for {item_code}: "
            f"{balance} available in {warehouse} before {balance_date}, "
            f"{required_qty} required."
        )
    return balance


def _inventory_safe(company: str, main: str, pos: str, back: str, base_date) -> None:
    """Build deterministic inventory with all sale stock available before sale dates."""
    normal = list(native.NORMAL_STOCK_ITEMS)

    # Normal supplier history remains unchanged and ERPNext-authoritative.
    for index, offset in enumerate((-86, -72, -56, -40, -23, -8), 1):
        subset = normal[(index - 1) % 3 :: 3] + normal[(index + 1) % 4 :: 4]
        subset = list(dict.fromkeys(subset))[:10]
        native._purchase_cycle(
            company,
            main,
            native.SUPPLIERS[(index - 1) % len(native.SUPPLIERS)],
            add_days(base_date, offset),
            index,
            subset,
        )

    # Earliest POS shift is base_date - 84. Put floor stock there beforehand.
    transfer_date = add_days(base_date, -85)
    opening_date = add_days(base_date, -87)
    for index, code in enumerate(normal, 1):
        transfer_qty = 120 if native.ITEM_BY_CODE[code]["cost"] < 500 else 35
        _ensure_historical_source_stock(
            company,
            item_code=code,
            warehouse=main,
            required_qty=transfer_qty,
            balance_date=transfer_date,
            receipt_date=opening_date,
            marker=f"{retail.SEED}-OPEN-{index:03d}",
        )
        native._stock_entry(
            company,
            item_code=code,
            qty=transfer_qty,
            date_value=transfer_date,
            purpose="Material Transfer",
            source_warehouse=main,
            target_warehouse=pos,
            marker=f"{retail.SEED}-POS-{index:03d}",
        )

    # Batch examples are operational-looking and contain no legacy LXD label.
    for index, code in enumerate(
        [row["code"] for row in native.ITEMS if row["tracking"] == "batch"], 1
    ):
        batch = erpnext_buying_inventory.ensure_batch(
            code,
            f"CM-BATCH-{getdate(base_date).strftime('%y%m')}-{index:03d}",
            manufacturing_date=add_days(base_date, -80),
        )
        native._stock_entry(
            company,
            item_code=code,
            qty=24,
            date_value=add_days(base_date, -79),
            purpose="Material Receipt",
            target_warehouse=pos,
            valuation_rate=native.ITEM_BY_CODE[code]["cost"],
            batch_no=batch,
            marker=f"{retail.SEED}-BATCH-{index:03d}",
        )

    # Serial examples likewise avoid the historical -DEMO- identifier.
    for index, code in enumerate(
        [row["code"] for row in native.ITEMS if row["tracking"] == "serial"], 1
    ):
        serials = [f"{code}-SN-{n:03d}" for n in range(1, 9)]
        native._stock_entry(
            company,
            item_code=code,
            qty=len(serials),
            date_value=add_days(base_date, -78),
            purpose="Material Receipt",
            target_warehouse=pos,
            valuation_rate=native.ITEM_BY_CODE[code]["cost"],
            serial_numbers=serials,
            marker=f"{retail.SEED}-SERIAL-{index:03d}",
        )

    # Demonstrate a genuine Main Store -> Back Store movement safely.
    back_date = add_days(base_date, -35)
    for index, code in enumerate(normal[:4], 1):
        _ensure_historical_source_stock(
            company,
            item_code=code,
            warehouse=main,
            required_qty=8,
            balance_date=back_date,
            receipt_date=add_days(back_date, -1),
            marker=f"{retail.SEED}-BACKTOPUP-{index:03d}",
        )
        native._stock_entry(
            company,
            item_code=code,
            qty=8,
            date_value=back_date,
            purpose="Material Transfer",
            source_warehouse=main,
            target_warehouse=back,
            marker=f"{retail.SEED}-BACK-{index:03d}",
        )


def _shape_stock_safe(company: str, warehouse: str, base_date) -> None:
    """Create low/out-of-stock examples from the balance at the issue date itself."""
    targets = (
        (native.NORMAL_STOCK_ITEMS[2], 0),
        (native.NORMAL_STOCK_ITEMS[5], 2),
        (native.NORMAL_STOCK_ITEMS[8], 5),
    )
    issue_date = add_days(base_date, -1)
    for index, (code, target) in enumerate(targets, 1):
        balance = _historical_qty(code, warehouse, issue_date)
        if balance <= target:
            continue
        native._stock_entry(
            company,
            item_code=code,
            qty=balance - target,
            date_value=issue_date,
            purpose="Material Issue",
            source_warehouse=warehouse,
            marker=f"{retail.SEED}-SHAPE-{index:03d}",
        )


def seed() -> dict:
    """Run the retail seed with corrected inventory chronology and stock shaping."""
    retail.configure()
    previous_inventory = native._inventory
    previous_shape = native._shape_stock
    native._inventory = _inventory_safe
    native._shape_stock = _shape_stock_safe
    try:
        return demo_data.seed()
    finally:
        native._inventory = previous_inventory
        native._shape_stock = previous_shape


__all__ = ["seed", "_inventory_safe", "_shape_stock_safe"]
