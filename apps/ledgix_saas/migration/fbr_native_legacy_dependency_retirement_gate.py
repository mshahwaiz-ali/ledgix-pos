from __future__ import annotations

"""LOCAL rollback-safe proof for native legacy-dependency retirement Patch 1."""

import frappe

from ledgix_saas.api import fbr_native
from ledgix_saas.api import fbr_submission as legacy
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.services import fbr_submission_support as support


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing native legacy dependency retirement gate on "
            f"{frappe.local.site!r}; expected {INTEGRATION_SITE!r}."
        )


def _parser_cases():
    return [
        {
            "name": "valid_production_invoice",
            "response": {
                "success": True,
                "network_call": True,
                "response": {
                    "invoiceNumber": "FBR-PARITY-0001",
                    "validationResponse": {
                        "status": "Valid", "statusCode": "00", "invoiceStatuses": [],
                    },
                },
            },
            "require_invoice_number": True,
        },
        {
            "name": "valid_sandbox_qr",
            "response": {
                "success": True,
                "network_call": True,
                "response": {
                    "qrCode": "QR-PARITY",
                    "validationResponse": {
                        "status": "Valid", "statusCode": "00", "invoiceStatuses": [],
                    },
                },
            },
            "require_invoice_number": False,
        },
        {
            "name": "explicit_invalid_item",
            "response": {
                "success": False,
                "network_call": True,
                "response": {
                    "validationResponse": {
                        "status": "Invalid", "statusCode": "01",
                        "errorCode": "P001", "error": "Rejected",
                        "invoiceStatuses": [
                            {
                                "status": "Invalid", "statusCode": "01",
                                "errorCode": "I001", "error": "Bad item",
                            }
                        ],
                    }
                },
            },
            "require_invoice_number": False,
        },
        {
            "name": "malformed_non_json",
            "response": {
                "success": False, "network_call": True,
                "response": "<html>not json</html>",
            },
            "require_invoice_number": False,
        },
    ]


def run() -> dict:
    _assert_safe_site()
    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False.")

    original_user = frappe.session.user
    original_commit = frappe.db.commit
    commit_attempts = []
    created_log = ""

    def _no_commit(*args, **kwargs):
        commit_attempts.append(True)
        return None

    checks = {}
    evidence = {}

    try:
        frappe.set_user("Administrator")
        frappe.db.commit = _no_commit

        parser_results = []
        parser_parity = True
        for case in _parser_cases():
            new = support.parse_fbr_response(
                case["response"],
                require_invoice_number=case["require_invoice_number"],
            )
            old = legacy.parse_fbr_response(
                case["response"],
                require_invoice_number=case["require_invoice_number"],
            )
            same = new == old
            parser_parity = parser_parity and same
            parser_results.append({
                "case": case["name"], "same": same,
                "new": new, "legacy": old,
            })
        checks["parser_behavior_matches_legacy"] = parser_parity
        evidence["parser_cases"] = parser_results

        resolver_inputs = [
            ("Production", {"valid": True, "invoice_number": "FBR-1", "qr_code": ""}),
            ("Production", {"valid": True, "invoice_number": "", "qr_code": ""}),
            ("Sandbox", {"valid": True, "invoice_number": "", "qr_code": "QR"}),
            ("Sandbox", {"valid": False, "invoice_number": "", "qr_code": ""}),
        ]
        resolver_rows = []
        resolver_parity = True
        for mode, parsed in resolver_inputs:
            new = support.resolve_submission_status(mode, parsed)
            old = legacy._resolve_submission_status(mode, parsed)
            same = new == old
            resolver_parity = resolver_parity and same
            resolver_rows.append({
                "mode": mode, "parsed": parsed, "same": same,
                "new": new, "legacy": old,
            })
        checks["resolver_behavior_matches_legacy"] = resolver_parity
        evidence["resolver_cases"] = resolver_rows

        company = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
        if not company:
            frappe.throw("No Company exists for neutral submission-log proof.")

        created_log = support.create_submission_log(
            "Company",
            company,
            "Sale Invoice",
            "Validated",
            request_json={"probe": "native-legacy-retirement"},
            response_json={
                "validationResponse": {"status": "Valid", "statusCode": "00"}
            },
            error_message="Probe Bearer EXAMPLE-SECRET-MUST-NOT-PERSIST",
            attempt_count=1,
        )
        log = frappe.get_doc("Ledgix FBR Submission Log", created_log)
        checks["neutral_log_inserted"] = bool(log.name)
        checks["neutral_log_reference_preserved"] = (
            log.reference_doctype == "Company" and log.reference_name == company
        )
        checks["neutral_log_status_preserved"] = log.fbr_status == "Validated"
        checks["neutral_log_redacts_bearer_tail"] = (
            "SECRET-MUST-NOT-PERSIST" not in str(log.error_message or "")
        )
        evidence["log"] = {
            "name": log.name,
            "reference_doctype": log.reference_doctype,
            "reference_name": log.reference_name,
            "status": log.fbr_status,
            "error_message": log.error_message or "",
        }

        lock_entered = False
        with support.submission_lock("native-legacy-retirement-gate"):
            lock_entered = True
        checks["neutral_submission_lock_enters_and_releases"] = lock_entered
        checks["no_commit_attempts"] = not commit_attempts
        checks["native_cutover_still_false"] = (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
        )
    finally:
        frappe.db.commit = original_commit
        frappe.set_user(original_user)
        frappe.db.rollback()

    rollback_clean = bool(
        not created_log or not frappe.db.exists("Ledgix FBR Submission Log", created_log)
    )
    checks["rollback_clean"] = rollback_clean

    result = {
        "site": frappe.local.site,
        "proof_type": "native_legacy_dependency_retirement_patch1",
        "real_fbr_network_calls": 0,
        "database_persistence": "ROLLBACK_CONFIRMED",
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "evidence": evidence,
        "scope_proven": [
            "neutral response parser matches legacy parser behavior on representative replies",
            "neutral submission-status resolver matches legacy behavior",
            "neutral submission-log helper preserves dynamic audit reference",
            "Bearer-like error tail is not persisted",
            "neutral submission lock can enter and release",
            "native runtime remains network-cutover disabled",
            "gate transaction rolls back cleanly",
        ],
        "scope_not_proven": [
            "legacy Sale/Return API retirement",
            "old global FBR Settings retirement",
            "old FBR client/reference/health retirement",
            "authorized Sandbox network behavior",
        ],
        "gate_passed": all(checks.values()),
    }
    if not result["gate_passed"]:
        frappe.throw(
            "Native legacy dependency retirement Patch 1 gate failed: "
            + frappe.as_json(result["failed_checks"])
        )
    return result
