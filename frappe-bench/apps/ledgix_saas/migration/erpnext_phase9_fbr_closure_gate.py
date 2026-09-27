from __future__ import annotations

"""Final Phase 9 closure wrapper.

The base Phase 9 gate correctly creates a `Ledgix FBR Submission Log` during
mocked validation, but its original assertion expected a top-level `log_name`
return key. Native validation instead exposes the persisted audit through the
invoice status and the submission-log table. This wrapper keeps production FBR
code unchanged and verifies the durable audit record directly.
"""

import frappe

from ledgix_saas.migration import erpnext_phase9_fbr_gate as base


CASE = "mocked_validation_log_native_reference"


def _repair_validation_log_case(payload: dict) -> None:
    cases = payload.get("cases") or {}
    current = cases.get(CASE) or {}
    if current.get("passed"):
        return

    invoice = (
        ((cases.get("native_sales_payload_from_snapshots") or {}).get("evidence") or {}).get("invoice")
        or ""
    )
    rows = []
    if invoice:
        rows = frappe.get_all(
            "Ledgix FBR Submission Log",
            filters={
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice,
                "fbr_status": "Validated",
            },
            fields=[
                "name",
                "reference_doctype",
                "reference_name",
                "fbr_status",
                "fbr_invoice_number",
                "request_json",
                "response_json",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=1,
        )

    log = rows[0] if rows else None
    network = payload.get("network_safety") or {}
    checks = {
        "mock_validation_called_once": network.get("validate_adapter_calls_mocked") == 1,
        "validation_log_persisted": bool(log),
        "log_references_sales_invoice": bool(
            log
            and log.reference_doctype == "Sales Invoice"
            and log.reference_name == invoice
        ),
        "log_status_validated": bool(log and log.fbr_status == "Validated"),
        "no_invoice_number_from_validate": bool(log and not log.fbr_invoice_number),
        "validation_response_audited": bool(log and log.response_json),
    }
    cases[CASE] = {
        "name": CASE,
        "evidence": {
            "invoice": invoice,
            "validation_log": log.name if log else "",
            "validation_log_status": log.fbr_status if log else "",
            "validation_log_created_at": log.creation if log else None,
            "proof_source": "Persisted Ledgix FBR Submission Log",
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def _recompute(payload: dict) -> dict:
    failed = [
        name
        for name, case in (payload.get("cases") or {}).items()
        if not case.get("passed")
    ]
    payload["failed_cases"] = failed
    payload["phase9_complete"] = not failed
    payload["phase10_ready"] = not failed
    payload["passed"] = not failed
    payload["closure_gate"] = {
        "validation_log_assertion": "Persisted audit record, not transient return-key shape",
        "production_adapter_modified": False,
    }
    return payload


def run() -> dict:
    payload = base.run()
    _repair_validation_log_case(payload)
    payload = _recompute(payload)
    frappe.db.commit()
    return payload
