from __future__ import annotations

"""Fail-closed boundary for the retired Ledgix monetary tax configuration surface."""

import frappe


LEGACY_TAX_RETIRED_MESSAGE = (
    "Legacy Ledgix monetary tax configuration/calculation is retired. "
    "Use ERPNext Tax Category, Tax Rule, Sales Taxes and Charges Template, "
    "Item Tax Template and the FBR V2 compliance mappings."
)


@frappe.whitelist()
def reject_legacy_tax_action(action=None, **kwargs):
    _ = action, kwargs
    frappe.throw(LEGACY_TAX_RETIRED_MESSAGE)
