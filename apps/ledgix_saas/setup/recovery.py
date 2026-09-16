from __future__ import annotations

import frappe

from ledgix_saas.api import legacy_retirement


REPRESENTATIVE_READ_DOCTYPES = (
    "Company",
    "Item",
    "Customer",
    "Sales Invoice",
    "Business Profile",
)


def verify_recovery_state(require_phase12_frozen: int | bool = 1) -> dict:
    """Read-only recovery verification for a restored site.

    This intentionally does not call the Phase 12 migration gate or mutate the
    legacy retirement state. It verifies that required apps can be read,
    representative ERPNext/Ledgix DocTypes are accessible, and (for migrated
    sites) the frozen legacy digest still matches the restored database.
    """

    installed_apps = set(frappe.get_installed_apps())
    reads: dict[str, int | None] = {}
    for doctype in REPRESENTATIVE_READ_DOCTYPES:
        if frappe.db.exists("DocType", doctype):
            reads[doctype] = frappe.db.count(doctype)
        else:
            reads[doctype] = None

    require_frozen = str(require_phase12_frozen).strip().lower() not in {"0", "false", "no"}
    phase12_frozen = legacy_retirement.is_frozen()
    snapshot = legacy_retirement.verify_frozen_snapshot() if phase12_frozen else {"matches": False}

    checks = {
        "frappe_installed": "frappe" in installed_apps,
        "erpnext_installed": "erpnext" in installed_apps,
        "ledgix_installed": "ledgix_saas" in installed_apps,
        "representative_erpnext_reads_available": all(
            reads.get(doctype) is not None for doctype in ("Company", "Item", "Customer", "Sales Invoice")
        ),
        "business_profile_read_available": reads.get("Business Profile") is not None,
        "phase12_frozen_when_required": (not require_frozen) or phase12_frozen,
        "phase12_snapshot_matches_when_required": (not require_frozen) or bool(snapshot.get("matches")),
    }

    failed = [name for name, passed in checks.items() if not passed]
    result = {
        "site": frappe.local.site,
        "installed_apps": sorted(installed_apps),
        "representative_reads": reads,
        "phase12_frozen": phase12_frozen,
        "phase12_snapshot": snapshot,
        "checks": checks,
        "failed_checks": failed,
        "recovery_state_verified": not failed,
    }
    if failed:
        frappe.throw(f"Recovery verification failed: {', '.join(failed)}")
    return result
