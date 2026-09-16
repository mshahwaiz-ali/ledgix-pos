from __future__ import annotations

import frappe
from frappe.utils import cint

from ledgix_saas.migration import erpnext_phase5_master_migration_gate_profiles as base
from ledgix_saas.setup import erpnext_extensions


def _snapshot_profile(doc) -> dict:
    return {
        "business_profile": doc.business_profile,
        "use_profile_defaults": cint(doc.use_profile_defaults),
        **{field: cint(doc.get(field)) for field in erpnext_extensions.FEATURE_FIELDS},
    }


def _restore_profile(snapshot: dict) -> None:
    doc = frappe.get_single("Ledgix Business Profile")
    doc.business_profile = snapshot["business_profile"] or erpnext_extensions.DEFAULT_BUSINESS_PROFILE
    doc.use_profile_defaults = snapshot["use_profile_defaults"]
    if cint(doc.use_profile_defaults):
        erpnext_extensions.apply_business_profile_defaults(doc)
    else:
        for field in erpnext_extensions.FEATURE_FIELDS:
            doc.set(field, snapshot[field])
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def run() -> dict:
    """Run Phase 5 from a deterministic stock-enabled profile and restore site state."""

    profile = frappe.get_single("Ledgix Business Profile")
    original = _snapshot_profile(profile)
    try:
        profile.business_profile = "Small Retail"
        profile.use_profile_defaults = 1
        erpnext_extensions.apply_business_profile_defaults(profile)
        profile.save(ignore_permissions=True)
        frappe.db.commit()

        result = base.run()
        result.setdefault("checks", {})["stock_profile_inventory_enabled"] = bool(
            cint(erpnext_extensions.get_effective_business_features().get("enable_inventory"))
        )
        complete = all((result.get("checks") or {}).values())
        result["phase5_complete"] = complete
        result["phase6_ready"] = complete
        result["passed"] = complete
        result["gate_stock_profile"] = "Small Retail"
        return result
    finally:
        _restore_profile(original)