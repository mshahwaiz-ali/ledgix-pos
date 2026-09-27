from __future__ import annotations

import importlib

import frappe

from ledgix_saas.services.fbr_v2_status import (
    assert_fbr_v2_view_permission,
    get_fbr_v2_status_internal,
)


REQUIRED_DOCTYPES = (
    "Ledgix FBR Integration Profile",
    "Ledgix FBR Business Nature",
    "Ledgix FBR Item Mapping",
    "Ledgix FBR Tax Component Mapping",
    "Ledgix FBR Reference Data",
    "Ledgix FBR Sandbox Scenario",
    "Ledgix FBR Sandbox Certification",
    "Ledgix FBR Submission Log",
    "Ledgix FBR Correction Request",
)

LEGACY_RECOVERY_METHODS = (
    "ledgix_saas.api.fbr_submission.process_fbr_retry_queue",
    "ledgix_saas.api.fbr_submission.process_fbr_offline_upload_queue",
)


def _check(name, passed, detail=""):
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "passed": bool(passed),
        "detail": detail or "",
    }


def _doctype_exists(doctype):
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


def _scheduler_methods_from_hooks():
    try:
        hooks = importlib.import_module("ledgix_saas.hooks")
    except Exception:
        return set()

    methods = set()
    events = getattr(hooks, "scheduler_events", {}) or {}
    if not isinstance(events, dict):
        return methods

    def visit(value):
        if isinstance(value, str):
            methods.add(value)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)

    visit(events)
    return methods


@frappe.whitelist()
def check():
    """Return V2 FBR health without submitting or exposing tokens."""

    assert_fbr_v2_view_permission()
    status = get_fbr_v2_status_internal()
    registered = _scheduler_methods_from_hooks()

    checks = [
        _check(
            "setup company selected",
            bool(status.get("company")),
            status.get("company") or "No setup company",
        ),
        _check(
            "V2 integration profile exists",
            bool(status.get("profile_exists")),
            status.get("profile_name") or "No V2 profile",
        ),
        _check("requests package", bool(status.get("requests_available"))),
        _check(
            "legacy recovery schedulers disabled",
            not any(method in registered for method in LEGACY_RECOVERY_METHODS),
            "Blind retry/offline recovery must remain disabled.",
        ),
    ]

    for doctype in REQUIRED_DOCTYPES:
        checks.append(_check(f"DocType: {doctype}", _doctype_exists(doctype)))

    checks.append(
        _check(
            "active V2 mode has token configured",
            not status.get("enabled") or bool(status.get("token_configured")),
            "Token values are intentionally not returned.",
        )
    )

    if status.get("mode") == "Production" and status.get("enabled"):
        checks.append(
            _check(
                "Production POST certification interlock",
                (
                    not status.get("production_post_armed")
                    or status.get("sandbox_certification_complete")
                ),
                "Armed Production requires completed Sandbox certification.",
            )
        )

    return {
        "ok": all(item["passed"] for item in checks),
        **status,
        "checks": checks,
    }
