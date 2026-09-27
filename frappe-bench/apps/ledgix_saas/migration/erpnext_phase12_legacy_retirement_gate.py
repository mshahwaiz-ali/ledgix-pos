from __future__ import annotations

import os
import traceback

import frappe

from ledgix_saas.api import legacy_retirement
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.setup import erpnext_phase12_legacy_retirement as retirement_setup


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 12 retirement gate on {frappe.local.site!r}; restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing.")


def _legacy_counts() -> dict:
    return {
        doctype: frappe.db.count(doctype) if frappe.db.exists("DocType", doctype) else None
        for doctype in legacy_retirement.LEGACY_ALL_DOCTYPES
    }


def _case(name: str, fn) -> dict:
    try:
        evidence, checks = fn()
        return {
            "name": name,
            "evidence": evidence,
            "checks": checks,
            "passed": all(checks.values()),
        }
    except Exception as exc:
        return {
            "name": name,
            "evidence": {},
            "checks": {},
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": traceback.format_exc().splitlines()[-12:],
        }


def _first_legacy_doc():
    for doctype in legacy_retirement.LEGACY_TOP_LEVEL_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        names = frappe.get_all(doctype, pluck="name", order_by="name asc", limit=1)
        if names:
            return frappe.get_doc(doctype, names[0])
    return None


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")

    counts_before = _legacy_counts()
    reconciliation_before = legacy_retirement.build_reconciliation()
    release_commit = str(os.environ.get("LEDGIX_PHASE12_COMMIT") or "").strip()
    freeze_result = legacy_retirement.freeze_legacy_history(
        confirmation=legacy_retirement.FREEZE_CONFIRMATION,
        commit=release_commit,
    )

    cases = {}

    def reconciliation_case():
        reconciliation = legacy_retirement.build_reconciliation()
        mapping = reconciliation.get("master_mapping") or {}
        open_ops = reconciliation.get("open_operations") or {}
        checks = {
            "reconciliation_ready": bool(reconciliation.get("ready")),
            "all_required_master_mappings_complete": bool(mapping.get("ready")),
            "no_open_legacy_operations": bool(open_ops.get("ready")),
            "freeze_activated": legacy_retirement.is_frozen(),
            "freeze_call_succeeded": bool(freeze_result.get("frozen") or freeze_result.get("already_frozen")),
        }
        return {
            "before": reconciliation_before,
            "after": reconciliation,
            "freeze_result": freeze_result,
        }, checks

    def snapshot_case():
        verification = legacy_retirement.verify_frozen_snapshot()
        state = frappe.get_single(legacy_retirement.STATE_DOCTYPE)
        checks = {
            "state_frozen": state.status == "Frozen",
            "legacy_snapshot_matches": bool(verification.get("matches")),
            "snapshot_json_persisted": bool(state.snapshot_json),
            "reconciliation_json_persisted": bool(state.reconciliation_json),
            "frozen_identity_persisted": bool(state.frozen_at and state.frozen_by),
            "frozen_commit_persisted_when_supplied": (not release_commit) or state.frozen_commit == release_commit,
        }
        return {
            "state": {
                "status": state.status,
                "frozen_at": state.frozen_at,
                "frozen_by": state.frozen_by,
                "frozen_commit": state.frozen_commit,
                "last_verified_at": state.last_verified_at,
            },
            "verification": verification,
        }, checks

    def permissions_case():
        status = retirement_setup.read_only_permission_status()
        checks = {
            "read_only_permission_policy_green": bool(status.get("ready")),
            "no_permission_violations": not status.get("violations"),
            "all_legacy_top_level_doctypes_covered": set(status.get("rows") or {})
            == {
                doctype
                for doctype in legacy_retirement.LEGACY_TOP_LEVEL_DOCTYPES
                if frappe.db.exists("DocType", doctype)
            },
        }
        return status, checks

    def guard_case():
        doc = _first_legacy_doc()
        if not doc:
            return {"document": None}, {"existing_legacy_document_available": False}

        blocked = False
        blocked_error = ""
        try:
            # run_method executes the normal Frappe document-event hook chain.
            doc.run_method("before_save")
        except Exception as exc:
            blocked = True
            blocked_error = str(exc)

        bypass_ok = True
        try:
            with legacy_retirement.legacy_write_bypass("Phase 12 gate: guard bypass proof only; no save performed"):
                legacy_retirement.guard_legacy_write(doc, "before_save")
        except Exception:
            bypass_ok = False

        checks = {
            "write_guard_blocks_normal_save_path": blocked,
            "write_guard_message_is_retirement_specific": "frozen historical Ledgix data" in blocked_error,
            "controlled_bypass_requires_explicit_context": bypass_ok,
            "state_remains_frozen": legacy_retirement.is_frozen(),
        }
        return {
            "doctype": doc.doctype,
            "name": doc.name,
            "blocked_error": blocked_error,
            "bypass_saved_document": False,
        }, checks

    def compatibility_case():
        from ledgix_saas.api import pos as legacy_pos_api

        recent = legacy_pos_api.get_recent_pos_sales(limit=1, offset=0)
        checks = {
            "old_pos_list_path_uses_erpnext": recent.get("authority") == "ERPNext POS Invoice",
            "old_pos_path_did_not_unfreeze_history": legacy_retirement.is_frozen(),
            "returned_rows_are_native_when_present": all(
                row.get("authority") == "ERPNext POS Invoice" for row in (recent.get("sales") or [])
            ),
        }
        return recent, checks

    def idempotent_case():
        before = legacy_retirement.capture_legacy_snapshot()
        second = legacy_retirement.freeze_legacy_history(
            confirmation=legacy_retirement.FREEZE_CONFIRMATION,
            commit=release_commit,
        )
        after = legacy_retirement.capture_legacy_snapshot()
        checks = {
            "second_freeze_is_idempotent": bool(second.get("already_frozen")),
            "legacy_snapshot_unchanged": before == after,
            "legacy_snapshot_matches": bool((second.get("matches") if second.get("already_frozen") else False)),
        }
        return {"second_freeze": second, "snapshot": after}, checks

    for name, fn in (
        ("retirement_reconciliation_ready", reconciliation_case),
        ("frozen_snapshot_and_state", snapshot_case),
        ("legacy_permissions_read_only", permissions_case),
        ("legacy_write_guard_and_controlled_bypass", guard_case),
        ("old_pos_compatibility_is_erpnext_native", compatibility_case),
        ("freeze_is_idempotent_and_observable", idempotent_case),
    ):
        cases[name] = _case(name, fn)

    counts_after = _legacy_counts()
    final_verification = legacy_retirement.verify_frozen_snapshot()
    cases["legacy_history_preserved_without_delete"] = {
        "name": "legacy_history_preserved_without_delete",
        "evidence": {
            "counts_before": counts_before,
            "counts_after": counts_after,
            "verification": final_verification,
        },
        "checks": {
            "legacy_row_counts_unchanged": counts_before == counts_after,
            "legacy_snapshot_matches": bool(final_verification.get("matches")),
            "legacy_remains_frozen": legacy_retirement.is_frozen(),
        },
        "passed": (
            counts_before == counts_after
            and bool(final_verification.get("matches"))
            and legacy_retirement.is_frozen()
        ),
    }

    failed = [name for name, case in cases.items() if not case.get("passed")]
    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": TEST_COMPANY,
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed,
        "decisions": {
            "current_business_authority": "ERPNext",
            "legacy_ledgix_business_records": "Frozen historical audit only",
            "legacy_schema_deleted": False,
            "legacy_rows_deleted": False,
            "compliance_product_doctypes_retained": True,
            "rollback_release_requires_confirmation": legacy_retirement.UNFREEZE_CONFIRMATION,
            "retirement_observation": "Persisted digest snapshot must remain unchanged before later physical deletion.",
        },
        "phase12_complete": not failed and legacy_retirement.is_frozen(),
        "phase13_ready": not failed and legacy_retirement.is_frozen(),
        "next_phase": "Phase 13 — Client Profiles and SaaS Productization",
        "passed": not failed and legacy_retirement.is_frozen(),
    }
    frappe.db.commit()
    return result
