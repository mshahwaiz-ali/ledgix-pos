from __future__ import annotations

"""Historical-stock guard for the local retail operating-data seed.

The native seed engine intentionally creates backdated purchases and transfers.
Its original opening-stock decision uses the current Bin quantity, which can be
positive because of a later purchase even when the earlier transfer date had no
stock. This local wrapper checks the source warehouse at the actual transfer
posting date and adds only the opening quantity needed to make that historical
transfer valid.
"""

from datetime import time

import frappe
from frappe.utils import add_days, flt

from erpnext.stock.utils import get_stock_balance
from ledgix_saas.setup import demo_data
from ledgix_saas.setup import erpnext_demo_data as native
from ledgix_saas.setup import retail_operating_profile as retail

_ORIGINAL_STOCK_ENTRY = native._stock_entry


def _historical_safe_stock_entry(company: str, **kwargs):
    marker = str(kwargs.get("marker") or "")
    purpose = kwargs.get("purpose")
    item_code = kwargs.get("item_code")
    source_warehouse = kwargs.get("source_warehouse")
    target_warehouse = kwargs.get("target_warehouse")
    date_value = kwargs.get("date_value")
    qty = flt(kwargs.get("qty"))

    is_retail_pos_transfer = bool(
        purpose == "Material Transfer"
        and item_code
        and source_warehouse
        and target_warehouse
        and date_value
        and qty > 0
        and marker.startswith(f"{retail.SEED}-POS-")
    )

    if is_retail_pos_transfer:
        balance = flt(
            get_stock_balance(
                item_code,
                source_warehouse,
                posting_date=date_value,
                posting_time=time(10, 59, 59),
            )
        )
        if balance + 1e-9 < qty:
            # Preserve the native seeder's intended 220-unit opening position,
            # but decide from the historical transfer date rather than today's Bin.
            opening_target = max(220.0, qty)
            top_up_qty = opening_target - balance
            suffix = marker.rsplit("-", 1)[-1]
            _ORIGINAL_STOCK_ENTRY(
                company,
                item_code=item_code,
                qty=top_up_qty,
                date_value=add_days(date_value, -2),
                purpose="Material Receipt",
                target_warehouse=source_warehouse,
                valuation_rate=retail.ITEM_BY_CODE[item_code]["cost"],
                marker=f"{retail.SEED}-HISTOPEN-{suffix}",
            )

            balance = flt(
                get_stock_balance(
                    item_code,
                    source_warehouse,
                    posting_date=date_value,
                    posting_time=time(10, 59, 59),
                )
            )
            if balance + 1e-9 < qty:
                frappe.throw(
                    f"Historical stock preparation failed for {item_code}: "
                    f"{balance} available in {source_warehouse} before "
                    f"{date_value}, {qty} required."
                )

    return _ORIGINAL_STOCK_ENTRY(company, **kwargs)


def seed() -> dict:
    """Run the normal retail seed with the historical transfer guard enabled."""
    retail.configure()
    previous = native._stock_entry
    native._stock_entry = _historical_safe_stock_entry
    try:
        return demo_data.seed()
    finally:
        native._stock_entry = previous


__all__ = ["seed"]
