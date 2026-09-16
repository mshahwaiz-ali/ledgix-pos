from __future__ import annotations

import frappe

from ledgix_saas.api import legacy_retirement


ERP_NEXT_READ_DOCTYPES = (
    "Company",
    "Item",
    "Customer",
    "Sales Invoice",
)
LEDGIX_BUSINESS_PROFILE_DOCTYPE = "Ledgix Business Profile"


def _read_business_profile() -> dict | None:
    """Read the Ledgix Single DocType without mutating site configuration."""

    if not frappe.db.exists("DocType", LEDGIX_BUSINESS_PROFILE_DOCTYPE):
        return None

    profile = frappe.get_single(LEDGIX_BUSINESS_PROFILE_DOCTYPE)
    return {
        "doctype": profile.doctype,
        "business_profile": profile.get("business_profile"),
    }


def verify_recovery_state(require_phase12_frozen: int | bool = 1) -> dict:
    """Read-only recovery verification for a restored site.

    This intentionally does not call the Phase 12 migration gate or mutate the
    legacy retirement state. It verifies that required apps can be read,
    representative ERPNext/Ledgix DocTypes are accessible, and (for migrated
    sites) the frozen legacy digest still matches the restored database.
    """

    installed_apps = set(frappe.get_installed_apps())
    reads: dict[str, object] = {}
    for doctype in ERP_NEXT_READ_DOCTYPES:
        if frappe.db.exists("DocType", doctype):
            reads[doctype] = frappe.db.count(doctype)
        else:
            reads[doctype] = None

    reads[LEDGIX_BUSINESS_PROFILE_DOCTYPE] = _read_business_profile()

    require_frozen = str(require_phase12_frozen).strip().lower() not in {"0", "false", "no"}
    phase12_frozen = legacy_retirement.is_frozen()
    snapshot = legacy_retirement.verify_frozen_snapshot() if phase12_frozen else {"matches": False}

    checks = {
        "frappe_installed": "frappe" in installed_apps,
        "erpnext_installed": "erpnext" in installed_apps,
        "ledgix_installed": "ledgix_saas" in installed_apps,
        "representative_erpnext_reads_available": all(
            reads.get(doctype) is not None for doctype in ERP_NEXT_READ_DOCTYPES
        ),
        "business_profile_read_available": reads.get(LEDGIX_BUSINESS_PROFILE_DOCTYPE) is not None,
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
