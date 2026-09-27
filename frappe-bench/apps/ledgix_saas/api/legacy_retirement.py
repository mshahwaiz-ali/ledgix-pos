from __future__ import annotations

"""Phase 12 legacy freeze and retirement controls.

Legacy Ledgix business-engine DocTypes remain historical migration/audit sources.
ERPNext owns all current masters, transactions, accounting, stock and payments.
This module deliberately does not delete legacy rows.  It records a deterministic
snapshot, blocks mutation after an explicit successful freeze, and provides a
controlled rollback release that requires an exact confirmation phrase.
"""

import hashlib
import json
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import now_datetime

STATE_DOCTYPE = "Ledgix Legacy Retirement State"
STATE_NAME = STATE_DOCTYPE
FREEZE_CONFIRMATION = "FREEZE LEGACY LEDGERS AFTER RECONCILIATION"
UNFREEZE_CONFIRMATION = "UNFREEZE LEGACY LEDGERS FOR CONTROLLED ROLLBACK"
BYPASS_FLAG = "ledgix_legacy_retirement_bypass"

# Top-level duplicated business-engine records.  Compliance/product DocTypes such
# as FBR Settings, FBR logs, Item Tax Profile, Brand Settings and Business Profile
# are intentionally NOT included because Ledgix still owns those capabilities.
LEGACY_TOP_LEVEL_DOCTYPES = (
    "Ledgix Item",
    "Ledgix Category",
    "Ledgix Customer",
    "Ledgix Supplier",
    "Ledgix Price List",
    "Ledgix Item Price",
    "Ledgix Payment Method",
    "Ledgix Sale",
    "Ledgix Purchase",
    "Ledgix Sales Return",
    "Ledgix POS Shift",
    "Ledgix POS Hold",
    "Ledgix Payment",
    "Ledgix Stock Movement",
    "Ledgix Stock Lot",
    "Ledgix Stock Serial",
)

LEGACY_CHILD_DOCTYPES = (
    "Ledgix Sale Item",
    "Ledgix Sale Payment",
    "Ledgix Purchase Item",
    "Ledgix Sales Return Item",
    "Ledgix POS Hold Item",
    "Ledgix Payment Allocation",
    "Ledgix Stock Lot Allocation",
)

LEGACY_ALL_DOCTYPES = LEGACY_TOP_LEVEL_DOCTYPES + LEGACY_CHILD_DOCTYPES

# Draft/open operational records must be resolved before the historical ledgers
# are frozen.  Submitted/cancelled records are preserved as immutable history.
OPEN_OPERATIONAL_CHECKS = {
    "Ledgix Sale": {"docstatus": 0},
    "Ledgix Purchase": {"docstatus": 0},
    "Ledgix Sales Return": {"docstatus": 0},
    "Ledgix Payment": {"docstatus": 0},
    "Ledgix Stock Movement": {"docstatus": 0},
    "Ledgix POS Shift": {"docstatus": 0, "status": "Open"},
    "Ledgix POS Hold": {"status": "Hold"},
}

MASTER_MAPPINGS = (
    ("Ledgix Item", "Item", "custom_ledgix_legacy_item", None),
    ("Ledgix Category", "Item Group", "custom_ledgix_legacy_category", None),
    ("Ledgix Customer", "Customer", "custom_ledgix_legacy_customer", None),
    ("Ledgix Supplier", "Supplier", "custom_ledgix_legacy_supplier", None),
    ("Ledgix Price List", "Price List", "custom_ledgix_legacy_price_list", None),
    # Disabled historical prices were intentionally not activated in Phase 5.
    ("Ledgix Item Price", "Item Price", "custom_ledgix_legacy_item_price", {"enabled": 1}),
    ("Ledgix Payment Method", "Mode of Payment", "custom_ledgix_legacy_payment_method", None),
)


def _state_exists() -> bool:
    return bool(frappe.db.exists("DocType", STATE_DOCTYPE))


def _state_status() -> str:
    if not _state_exists():
        return "Not Frozen"
    try:
        return str(frappe.db.get_single_value(STATE_DOCTYPE, "status") or "Not Frozen")
    except Exception:
        return "Not Frozen"


def is_frozen() -> bool:
    return _state_status() == "Frozen"


def _require_retirement_admin() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin"}):
        frappe.throw(_("Ledgix Admin or System Manager access is required."), frappe.PermissionError)


@contextmanager
def legacy_write_bypass(reason: str):
    """Explicit internal escape hatch for a controlled rollback/migration only."""

    previous = getattr(frappe.flags, BYPASS_FLAG, None)
    frappe.flags.ledgix_legacy_retirement_bypass = str(reason or "controlled migration")
    try:
        yield
    finally:
        if previous is None:
            try:
                delattr(frappe.flags, BYPASS_FLAG)
            except Exception:
                frappe.flags.ledgix_legacy_retirement_bypass = None
        else:
            frappe.flags.ledgix_legacy_retirement_bypass = previous


def guard_legacy_write(doc, method=None):
    """Document-event guard: frozen legacy ledgers are immutable history."""

    if not is_frozen():
        return
    if getattr(frappe.flags, BYPASS_FLAG, None):
        return
    frappe.throw(
        _(
            "{0} is frozen historical Ledgix data after ERPNext cutover. "
            "Create or correct the authoritative ERPNext document instead."
        ).format(doc.doctype),
        frappe.ValidationError,
        title=_("Legacy Ledgix records are read-only"),
    )


def _digest_rows(doctype: str) -> dict:
    if not frappe.db.exists("DocType", doctype):
        return {"exists": False, "count": 0, "latest_modified": "", "digest": ""}
    meta = frappe.get_meta(doctype)
    fields = ["name", "modified"]
    if meta.is_submittable:
        fields.append("docstatus")
    rows = frappe.get_all(
        doctype,
        fields=fields,
        order_by="name asc",
        limit_page_length=0,
    )
    payload = []
    latest = ""
    for row in rows:
        normalized = {field: str(row.get(field) or "") for field in fields}
        payload.append(normalized)
        modified = normalized.get("modified") or ""
        if modified > latest:
            latest = modified
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "exists": True,
        "count": len(rows),
        "latest_modified": latest,
        "digest": hashlib.sha256(encoded).hexdigest(),
    }


def capture_legacy_snapshot() -> dict:
    return {
        "schema_version": 1,
        "doctypes": {doctype: _digest_rows(doctype) for doctype in LEGACY_ALL_DOCTYPES},
    }


def _mapping_reconciliation() -> dict:
    rows = []
    blockers = []
    for legacy_doctype, target_doctype, marker_field, legacy_filters in MASTER_MAPPINGS:
        if not frappe.db.exists("DocType", legacy_doctype):
            rows.append(
                {
                    "legacy_doctype": legacy_doctype,
                    "target_doctype": target_doctype,
                    "source_count": 0,
                    "mapped_count": 0,
                    "unmapped": [],
                    "missing_source_doctype": True,
                }
            )
            continue
        filters = legacy_filters or {}
        names = frappe.get_all(
            legacy_doctype,
            filters=filters,
            pluck="name",
            order_by="name asc",
            limit_page_length=0,
        )
        unmapped = []
        mapped_count = 0
        for name in names:
            target = frappe.db.get_value(target_doctype, {marker_field: name}, "name")
            if target:
                mapped_count += 1
            else:
                unmapped.append(name)
        record = {
            "legacy_doctype": legacy_doctype,
            "target_doctype": target_doctype,
            "marker_field": marker_field,
            "source_count": len(names),
            "mapped_count": mapped_count,
            "unmapped": unmapped,
        }
        rows.append(record)
        if unmapped:
            blockers.append(record)
    return {"rows": rows, "blockers": blockers, "ready": not blockers}


def _open_operational_reconciliation() -> dict:
    rows = []
    blockers = []
    for doctype, filters in OPEN_OPERATIONAL_CHECKS.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        count = frappe.db.count(doctype, filters=filters)
        record = {"doctype": doctype, "filters": filters, "count": count}
        rows.append(record)
        if count:
            blockers.append(record)
    return {"rows": rows, "blockers": blockers, "ready": not blockers}


def build_reconciliation() -> dict:
    mapping = _mapping_reconciliation()
    open_ops = _open_operational_reconciliation()
    blockers = []
    blockers.extend({"type": "unmapped_master", **row} for row in mapping["blockers"])
    blockers.extend({"type": "open_legacy_operation", **row} for row in open_ops["blockers"])
    return {
        "master_mapping": mapping,
        "open_operations": open_ops,
        "blockers": blockers,
        "ready": not blockers,
        "policy": (
            "Phase 12 freezes historical Ledgix rows only after migrated master provenance is complete "
            "and no unresolved legacy drafts/open POS operations remain. Current ERPNext balances and stock "
            "are intentionally not forced to equal stale post-cutover legacy ledgers."
        ),
    }


def _commit_hint(commit: str | None = None) -> str:
    value = str(commit or "").strip()
    if value:
        return value
    return str(frappe.local.conf.get("ledgix_release_commit") or "").strip()


def _write_state(*, status: str, snapshot: dict | None, reconciliation: dict, commit: str | None = None) -> dict:
    doc = frappe.get_single(STATE_DOCTYPE)
    doc.status = status
    if status == "Frozen" and not doc.frozen_at:
        doc.frozen_at = now_datetime()
        doc.frozen_by = frappe.session.user
        doc.frozen_commit = _commit_hint(commit)
    doc.snapshot_json = json.dumps(snapshot or {}, sort_keys=True, default=str)
    doc.reconciliation_json = json.dumps(reconciliation or {}, sort_keys=True, default=str)
    doc.last_verified_at = now_datetime()
    doc.last_verified_by = frappe.session.user
    doc.flags.ignore_permissions = True
    doc.save()
    return {
        "status": doc.status,
        "frozen_at": doc.frozen_at,
        "frozen_by": doc.frozen_by,
        "frozen_commit": doc.frozen_commit or "",
        "last_verified_at": doc.last_verified_at,
    }


def verify_frozen_snapshot() -> dict:
    if not is_frozen():
        return {"frozen": False, "matches": False, "reason": "Legacy retirement state is not Frozen."}
    doc = frappe.get_single(STATE_DOCTYPE)
    expected = json.loads(doc.snapshot_json or "{}")
    current = capture_legacy_snapshot()
    matches = expected == current
    reconciliation = build_reconciliation()
    if matches:
        doc.last_verified_at = now_datetime()
        doc.last_verified_by = frappe.session.user
        doc.reconciliation_json = json.dumps(reconciliation, sort_keys=True, default=str)
        doc.flags.ignore_permissions = True
        doc.save()
    return {
        "frozen": True,
        "matches": matches,
        "expected": expected,
        "current": current,
        "reconciliation": reconciliation,
    }


def freeze_legacy_history(*, confirmation: str, commit: str | None = None) -> dict:
    _require_retirement_admin()
    if str(confirmation or "").strip() != FREEZE_CONFIRMATION:
        frappe.throw(_("Exact Phase 12 freeze confirmation phrase is required."))

    from ledgix_saas.setup import erpnext_phase12_legacy_retirement as retirement_setup

    if is_frozen():
        verification = verify_frozen_snapshot()
        if not verification.get("matches"):
            frappe.throw(_("Frozen legacy snapshot changed. Retirement verification failed closed."))
        retirement_setup.sync_legacy_read_only_permissions()
        return {"already_frozen": True, **verification}

    reconciliation = build_reconciliation()
    snapshot = capture_legacy_snapshot()
    if not reconciliation.get("ready"):
        _write_state(
            status="Blocked",
            snapshot=snapshot,
            reconciliation=reconciliation,
            commit=commit,
        )
        return {
            "frozen": False,
            "status": "Blocked",
            "reconciliation": reconciliation,
            "snapshot": snapshot,
        }

    state = _write_state(
        status="Frozen",
        snapshot=snapshot,
        reconciliation=reconciliation,
        commit=commit,
    )
    retirement_setup.sync_legacy_read_only_permissions()
    frappe.clear_cache()
    return {
        "frozen": True,
        "status": "Frozen",
        "state": state,
        "reconciliation": reconciliation,
        "snapshot": snapshot,
    }


@frappe.whitelist()
def get_legacy_retirement_status() -> dict:
    _require_retirement_admin()
    reconciliation = build_reconciliation()
    state = {}
    if _state_exists():
        doc = frappe.get_single(STATE_DOCTYPE)
        state = {
            "status": doc.status or "Not Frozen",
            "frozen_at": doc.frozen_at,
            "frozen_by": doc.frozen_by,
            "frozen_commit": doc.frozen_commit or "",
            "last_verified_at": doc.last_verified_at,
            "last_verified_by": doc.last_verified_by,
        }
    return {
        "state": state,
        "reconciliation": reconciliation,
        "snapshot": capture_legacy_snapshot(),
        "authority": "ERPNext current business engine; Ledgix legacy records are historical audit only",
    }


@frappe.whitelist()
def release_legacy_freeze_for_rollback(confirmation: str) -> dict:
    _require_retirement_admin()
    if str(confirmation or "").strip() != UNFREEZE_CONFIRMATION:
        frappe.throw(_("Exact controlled rollback confirmation phrase is required."))
    if not _state_exists():
        frappe.throw(_("Legacy retirement state is not installed."))

    doc = frappe.get_single(STATE_DOCTYPE)
    doc.status = "Not Frozen"
    doc.last_verified_at = now_datetime()
    doc.last_verified_by = frappe.session.user
    doc.flags.ignore_permissions = True
    doc.save()

    # Restore the pre-retirement Ledgix permission policy for a controlled
    # rollback window.  The next freeze reapplies read-only audit permissions.
    from ledgix_saas.setup.fast_permissions import sync_doctype_permissions

    sync_doctype_permissions()
    frappe.clear_cache()
    return {
        "status": "Not Frozen",
        "released_by": frappe.session.user,
        "released_at": now_datetime(),
        "warning": "Legacy writes are temporarily available only for a controlled rollback. Reconcile and freeze again before normal operation.",
    }
