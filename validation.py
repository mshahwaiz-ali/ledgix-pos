import importlib

import frappe


REQUIRED_ROLES = (
    "Ledgix Admin",
    "Ledgix Manager",
    "Ledgix Cashier",
)

REQUIRED_DOCTYPE_FIELDS = {
    "Ledgix FBR Settings": (
        "enabled",
        "mode",
        "submit_trigger",
        "sandbox_token",
        "production_token",
        "seller_ntn_cnic",
        "seller_business_name",
        "seller_province",
        "seller_address",
        "retry_enabled",
        "max_retry_count",
        "offline_upload_hours",
    ),
    "Ledgix FBR Submission Log": (
        "reference_doctype",
        "reference_name",
        "invoice_type",
        "fbr_status",
        "request_json",
        "response_json",
        "error_code",
        "error_message",
        "attempt_count",
        "next_retry_time",
    ),
    "Ledgix Sale": (
        "items",
        "tax_details",
        "tax_amount",
        "grand_total",
        "fbr_status",
        "fbr_invoice_number",
        "fbr_error_code",
        "fbr_error_message",
        "fbr_submission_log",
    ),
    "Ledgix Sales Return": (
        "original_sale",
        "items",
        "tax_details",
        "tax_amount",
        "grand_total",
        "fbr_status",
        "fbr_invoice_number",
        "fbr_error_code",
        "fbr_error_message",
        "fbr_submission_log",
    ),
}

REQUIRED_MODULES = (
    "ledgix_saas.api.fbr_client",
    "ledgix_saas.api.fbr_health",
    "ledgix_saas.api.fbr_payload",
    "ledgix_saas.api.fbr_settings",
    "ledgix_saas.api.fbr_submission",
    "ledgix_saas.api.taxation",
)

REQUIRED_SCHEDULER_METHODS = (
    "ledgix_saas.api.fbr_submission.process_fbr_retry_queue",
    "ledgix_saas.api.fbr_submission.process_fbr_offline_upload_queue",
)


def _assert_validation_permission():
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin"}):
        frappe.throw(
            "Only System Manager or Ledgix Admin can run Ledgix validation.",
            frappe.PermissionError,
        )


def _result(name, passed, detail=""):
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "passed": bool(passed),
        "detail": detail or "",
    }


def _doctype_exists(doctype):
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception as exc:
        return False, str(exc)


def _field_names(doctype):
    try:
        meta = frappe.get_meta(doctype)
        names = {field.fieldname for field in meta.fields}
        names.update({"name", "owner", "creation", "modified", "modified_by", "docstatus"})
        return names, ""
    except Exception as exc:
        return set(), str(exc)


def _role_exists(role):
    try:
        return bool(frappe.db.exists("Role", role)), ""
    except Exception as exc:
        return False, str(exc)


def _importable(module_name):
    try:
        importlib.import_module(module_name)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _scheduler_methods_from_hooks():
    try:
        hooks = importlib.import_module("ledgix_saas.hooks")
    except Exception as exc:
        return set(), str(exc)

    methods = set()
    events = getattr(hooks, "scheduler_events", {}) or {}

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
    return methods, ""


@frappe.whitelist()
def run_all():
    """Run read-only Ledgix app validation for deployment smoke checks."""
    _assert_validation_permission()

    checks = []

    for role in REQUIRED_ROLES:
        passed, detail = _role_exists(role)
        checks.append(_result(f"Role: {role}", passed, detail))

    for doctype, fields in REQUIRED_DOCTYPE_FIELDS.items():
        exists = _doctype_exists(doctype)
        if isinstance(exists, tuple):
            passed, detail = exists
        else:
            passed, detail = bool(exists), ""
        checks.append(_result(f"DocType: {doctype}", passed, detail))
        if not passed:
            continue
        field_names, detail = _field_names(doctype)
        for fieldname in fields:
            checks.append(
                _result(
                    f"Field: {doctype}.{fieldname}",
                    fieldname in field_names,
                    detail if fieldname not in field_names else "",
                )
            )

    for module_name in REQUIRED_MODULES:
        passed, detail = _importable(module_name)
        checks.append(_result(f"Import: {module_name}", passed, detail))

    scheduler_methods, detail = _scheduler_methods_from_hooks()
    for method in REQUIRED_SCHEDULER_METHODS:
        checks.append(
            _result(
                f"Scheduler hook: {method}",
                method in scheduler_methods,
                detail if method not in scheduler_methods else "",
            )
        )

    return {
        "ok": all(item["passed"] for item in checks),
        "checks": checks,
    }
