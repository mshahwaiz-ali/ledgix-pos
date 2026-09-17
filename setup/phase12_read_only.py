from __future__ import annotations

"""Read-only Phase 12 frozen snapshot verification.

The historical Phase 12 admin verifier intentionally records verification metadata.
Recovery and release acceptance need a side-effect-free digest check, so they use
this module instead of the mutating admin workflow.
"""

import json

import frappe

from ledgix_saas.api import legacy_retirement


def verify_frozen_snapshot_read_only() -> dict:
    """Compare the persisted frozen snapshot with current legacy rows without writes."""

    if not legacy_retirement.is_frozen():
        return {
            "frozen": False,
            "matches": False,
            "reason": "Legacy retirement state is not Frozen.",
            "read_only": True,
        }

    doc = frappe.get_single(legacy_retirement.STATE_DOCTYPE)
    try:
        expected = json.loads(doc.snapshot_json or "{}")
    except Exception:
        expected = {}
    current = legacy_retirement.capture_legacy_snapshot()
    reconciliation = legacy_retirement.build_reconciliation()
    matches = bool(expected) and expected == current

    return {
        "frozen": True,
        "snapshot_verified": bool(doc.get("snapshot_verified")),
        "matches": matches,
        "expected": expected,
        "current": current,
        "frozen_digest": expected.get("digest") or "",
        "current_digest": current.get("digest") or "",
        "reconciliation": reconciliation,
        "last_verified_at": doc.get("last_verified_at"),
        "last_verified_by": doc.get("last_verified_by") or "",
        "read_only": True,
    }
