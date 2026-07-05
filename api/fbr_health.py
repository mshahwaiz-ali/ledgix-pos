import importlib

import frappe

from ledgix_saas.api import fbr_client
from ledgix_saas.api.fbr_settings import (
    assert_fbr_view_permission,
    get_fbr_control_state_internal,
    get_fbr_settings_internal,
)


REQUIRED_DOCTYPES = (
    "Ledgix FBR Settings",
    "Ledgix FBR Submission Log",
    "Ledgix Sale",
    "Ledgix Sales Return",
    "Ledgix Invoice Tax Detail",
    "Ledgix Return Tax Detail",
)

SCHEDULER_METHODS = (
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


def _importable(dotted_path):
    module_name, _, attr = dotted_path.rpartition(".")
    try:
        module = importlib.import_module(module_name)
        return bool(getattr(module, attr, None))
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
    """Return safe FBR readiness checks without submitting or leaking tokens."""
    assert_fbr_view_permission()

    settings = get_fbr_settings_internal()
    control_state = get_fbr_control_state_internal()
    registered_scheduler_methods = _scheduler_methods_from_hooks()
    checks = []

    checks.append(_check("requests package", fbr_client.requests_available()))

    for doctype in REQUIRED_DOCTYPES:
        checks.append(_check(f"DocType: {doctype}", _doctype_exists(doctype)))

    for method in SCHEDULER_METHODS:
        checks.append(
            _check(
                f"scheduler hook: {method}",
                method in registered_scheduler_methods and _importable(method),
            )
        )

    checks.append(
        _check(
            "active mode has token configured",
            not control_state.get("enabled") or bool(control_state.get("token_configured")),
            "Token values are intentionally not returned.",
        )
    )

    return {
        "ok": all(item["passed"] for item in checks),
        "mode": settings.get("mode") or "Disabled",
        "enabled": bool(control_state.get("enabled")),
        "submit_trigger": settings.get("submit_trigger") or "Manual",
        "token_configured": bool(control_state.get("token_configured")),
        "network_call": False,
        "checks": checks,
    }
