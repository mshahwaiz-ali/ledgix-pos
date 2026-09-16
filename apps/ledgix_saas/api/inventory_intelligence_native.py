from __future__ import annotations

import frappe

from ledgix_saas.api.security import require_ledgix_manager_or_above
from ledgix_saas.services import erpnext_reporting


@frappe.whitelist()
def get_inventory_intelligence_data(
    item=None,
    from_date=None,
    to_date=None,
    mode="Overview",
    search=None,
    tracking_type="All",
    entity_type=None,
    entity_value=None,
):
    """Return Ledgix Inventory Intelligence from ERPNext-native sources only."""

    require_ledgix_manager_or_above()
    if entity_type == "item" and entity_value:
        item = entity_value
    return erpnext_reporting.inventory_intelligence(
        {
            "item": item,
            "from_date": from_date,
            "to_date": to_date,
            "mode": mode,
            "search": search,
            "tracking_type": tracking_type,
            "entity_type": entity_type,
            "entity_value": entity_value,
        }
    )
