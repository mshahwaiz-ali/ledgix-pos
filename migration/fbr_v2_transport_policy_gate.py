from __future__ import annotations

"""In-memory proof for FBR V2 transport policy.

No HTTP request is allowed. Profile lookup, token retrieval, requests
availability and neutral POST transport are all replaced in-memory. The gate
proves endpoint/mode/token/Production-arm/ambiguity behavior without changing
database state or contacting FBR.
"""

import json

import frappe

from ledgix_saas.api import fbr_transport, fbr_v2_transport
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


COMPANY = "Ledgix ERPNext Integration"
SANDBOX_SECRET = "gate-sandbox-secret"
PRODUCTION_SECRET = "gate-production-secret"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing FBR V2 transport policy gate on {frappe.local.site!r}; "
            f"restricted to {INTEGRATION_SITE!r}."
        )


def _profile(*, mode: str, enabled: int = 1, armed: int = 0):
    return frappe._dict(
        {
            "name": "FBR-PROFILE-TRANSPORT-GATE",
            "company": COMPANY,
            "enabled": enabled,
            "mode": mode,
            "production_post_armed": armed,
        }
    )


def _valid_http_result(*, invoice_number: str = "") -> dict:
    response = {
        "validationResponse": {
            "status": "Valid",
            "statusCode": "00",
            "invoiceStatuses": [],
        }
    }
    if invoice_number:
        response["invoiceNumber"] = invoice_number
    return {
        "success": True,
        "network_call": True,
        "http_status": 200,
        "status": "HTTP OK",
        "response": response,
        "error": "",
    }


def _invalid_http_result() -> dict:
    return {
        "success": True,
        "network_call": True,
        "http_status": 200,
        "status": "HTTP OK",
        "response": {
            "validationResponse": {
                "status": "Invalid",
                "statusCode": "01",
                "error": "Simulated invalid invoice.",
                "invoiceStatuses": [],
            }
        },
        "error": "",
    }


def _network_error_result() -> dict:
    return {
        "success": False,
        "network_call": True,
        "http_status": None,
        "status": "Network Error",
        "response": None,
        "error": "Simulated connection timeout.",
    }


def _server_error_result() -> dict:
    return {
        "success": False,
        "network_call": True,
        "http_status": 503,
        "status": "HTTP Error",
        "response": {"message": "Simulated upstream failure."},
        "error": "FBR returned HTTP 503.",
    }


def _request_timeout_result() -> dict:
    return {
        "success": False,
        "network_call": True,
        "http_status": 408,
        "status": "HTTP Error",
        "response": {"message": "Simulated request timeout."},
        "error": "FBR returned HTTP 408.",
    }


def _malformed_success_result() -> dict:
    return {
        "success": True,
        "network_call": True,
        "http_status": 200,
        "status": "HTTP OK",
        "response": "<html>gateway response</html>",
        "error": "",
    }


def run() -> dict:
    _assert_safe_site()

    original_profile = fbr_v2_transport._profile_for_company
    original_token = fbr_v2_transport._token
    original_certification = fbr_v2_transport._production_certification
    original_requests_available = fbr_transport.requests_available
    original_post_json = fbr_transport.post_json
    original_commit = frappe.db.commit

    state = {
        "profile": None,
        "sandbox_token": SANDBOX_SECRET,
        "production_token": PRODUCTION_SECRET,
        "certification_complete": False,
        "http_result": _valid_http_result(),
    }
    calls = []
    commit_attempts = []

    def _fake_profile(company: str):
        if company != COMPANY:
            return None
        return state["profile"]

    def _fake_token(profile, mode: str) -> str:
        if mode == "Sandbox":
            return state["sandbox_token"]
        return state["production_token"]

    def _fake_production_certification(profile) -> dict:
        complete = bool(state["certification_complete"])
        return {
            "name": "FBR-CERT-TRANSPORT-GATE" if complete else "",
            "status": "Complete" if complete else "In Progress",
            "evidence_complete": complete,
            "complete": complete,
        }

    def _fake_requests_available() -> bool:
        return True

    def _fake_post_json(*, url: str, token: str, payload: dict, timeout: int = 30):
        calls.append(
            {
                "url": url,
                "token_kind": (
                    "sandbox"
                    if token == SANDBOX_SECRET
                    else "production"
                    if token == PRODUCTION_SECRET
                    else "unknown"
                ),
                "payload_keys": sorted(payload),
                "timeout": timeout,
            }
        )
        return dict(state["http_result"])

    def _no_commit():
        commit_attempts.append(True)
        return None

    results = {}
    checks = {}

    try:
        fbr_v2_transport._profile_for_company = _fake_profile
        fbr_v2_transport._token = _fake_token
        fbr_v2_transport._production_certification = _fake_production_certification
        fbr_transport.requests_available = _fake_requests_available
        fbr_transport.post_json = _fake_post_json
        frappe.db.commit = _no_commit

        payload = {"invoiceType": "Sale Invoice", "items": [{"hsCode": "0101.21"}]}

        before = len(calls)
        state["profile"] = None
        results["no_profile"] = fbr_v2_transport.validate_invoice(
            company=COMPANY,
            payload=payload,
            mode="Sandbox",
        )
        checks["no_profile_blocks_without_transport"] = (
            results["no_profile"].get("network_call") is False
            and len(calls) == before
        )

        before = len(calls)
        state["profile"] = _profile(mode="Sandbox", enabled=0)
        results["disabled_profile"] = fbr_v2_transport.validate_invoice(
            company=COMPANY,
            payload=payload,
            mode="Sandbox",
        )
        checks["disabled_profile_blocks_without_transport"] = (
            results["disabled_profile"].get("network_call") is False
            and len(calls) == before
        )

        before = len(calls)
        state["profile"] = _profile(mode="Sandbox", enabled=1)
        results["mode_mismatch"] = fbr_v2_transport.validate_invoice(
            company=COMPANY,
            payload=payload,
            mode="Production",
        )
        checks["mode_mismatch_blocks_without_transport"] = (
            results["mode_mismatch"].get("network_call") is False
            and len(calls) == before
        )

        before = len(calls)
        state["sandbox_token"] = ""
        results["missing_sandbox_token"] = fbr_v2_transport.validate_invoice(
            company=COMPANY,
            payload=payload,
            mode="Sandbox",
        )
        checks["missing_token_blocks_without_transport"] = (
            results["missing_sandbox_token"].get("network_call") is False
            and len(calls) == before
        )
        state["sandbox_token"] = SANDBOX_SECRET

        before = len(calls)
        state["profile"] = _profile(mode="Sandbox", enabled=1)
        state["http_result"] = _valid_http_result()
        results["sandbox_validate"] = fbr_v2_transport.validate_invoice(
            company=COMPANY,
            payload=payload,
            mode="Sandbox",
        )
        sandbox_validate_call = calls[-1] if len(calls) > before else {}
        checks["sandbox_validate_uses_fixed_endpoint"] = (
            len(calls) == before + 1
            and sandbox_validate_call.get("url")
            == fbr_v2_transport.SANDBOX_VALIDATE_URL
            and sandbox_validate_call.get("token_kind") == "sandbox"
            and results["sandbox_validate"].get("success") is True
        )

        before = len(calls)
        results["sandbox_post"] = fbr_v2_transport.post_invoice(
            company=COMPANY,
            payload=payload,
            mode="Sandbox",
        )
        sandbox_post_call = calls[-1] if len(calls) > before else {}
        checks["sandbox_post_uses_fixed_endpoint"] = (
            len(calls) == before + 1
            and sandbox_post_call.get("url") == fbr_v2_transport.SANDBOX_POST_URL
            and sandbox_post_call.get("token_kind") == "sandbox"
            and results["sandbox_post"].get("success") is True
        )

        before = len(calls)
        state["profile"] = _profile(mode="Production", enabled=1, armed=0)
        state["certification_complete"] = False
        state["http_result"] = _valid_http_result()
        results["production_validate_unarmed"] = fbr_v2_transport.validate_invoice(
            company=COMPANY,
            payload=payload,
            mode="Production",
        )
        production_validate_call = calls[-1] if len(calls) > before else {}
        checks["production_validate_allowed_while_post_unarmed"] = (
            len(calls) == before + 1
            and production_validate_call.get("url")
            == fbr_v2_transport.PRODUCTION_VALIDATE_URL
            and production_validate_call.get("token_kind") == "production"
            and results["production_validate_unarmed"].get("success") is True
        )

        before = len(calls)
        state["profile"] = _profile(mode="Production", enabled=1, armed=1)
        state["certification_complete"] = False
        results["production_post_uncertified"] = fbr_v2_transport.post_invoice(
            company=COMPANY,
            payload=payload,
            mode="Production",
        )
        checks["production_post_requires_completed_certification"] = (
            results["production_post_uncertified"].get("network_call") is False
            and len(calls) == before
            and "completed sandbox certification"
            in str(
                results["production_post_uncertified"].get("error") or ""
            ).lower()
        )

        before = len(calls)
        state["profile"] = _profile(mode="Production", enabled=1, armed=0)
        state["certification_complete"] = True
        results["production_post_unarmed"] = fbr_v2_transport.post_invoice(
            company=COMPANY,
            payload=payload,
            mode="Production",
        )
        checks["production_post_requires_arm"] = (
            results["production_post_unarmed"].get("network_call") is False
            and len(calls) == before
            and "not armed" in str(
                results["production_post_unarmed"].get("error") or ""
            ).lower()
        )

        before = len(calls)
        state["profile"] = _profile(mode="Production", enabled=1, armed=1)
        state["certification_complete"] = True
        state["http_result"] = _network_error_result()
        results["production_post_ambiguous"] = fbr_v2_transport.post_invoice(
            company=COMPANY,
            payload=payload,
            mode="Production",
        )
        production_post_call = calls[-1] if len(calls) > before else {}
        checks["production_network_error_requires_reconciliation"] = (
            len(calls) == before + 1
            and production_post_call.get("url")
            == fbr_v2_transport.PRODUCTION_POST_URL
            and production_post_call.get("token_kind") == "production"
            and results["production_post_ambiguous"].get("ambiguous_outcome")
            is True
            and results["production_post_ambiguous"].get(
                "requires_reconciliation"
            )
            is True
            and "automatic recovery is intentionally disabled"
            in str(results["production_post_ambiguous"].get("error") or "")
        )

        before = len(calls)
        state["http_result"] = _server_error_result()
        results["production_post_503_ambiguous"] = fbr_v2_transport.post_invoice(
            company=COMPANY,
            payload=payload,
            mode="Production",
        )
        checks["production_http_503_requires_reconciliation"] = (
            len(calls) == before + 1
            and results["production_post_503_ambiguous"].get(
                "requires_reconciliation"
            )
            is True
        )

        before = len(calls)
        state["http_result"] = _request_timeout_result()
        results["production_post_408_ambiguous"] = fbr_v2_transport.post_invoice(
            company=COMPANY,
            payload=payload,
            mode="Production",
        )
        checks["production_http_408_requires_reconciliation"] = (
            len(calls) == before + 1
            and results["production_post_408_ambiguous"].get(
                "requires_reconciliation"
            )
            is True
        )

        before = len(calls)
        state["http_result"] = _malformed_success_result()
        results["production_post_malformed_ambiguous"] = fbr_v2_transport.post_invoice(
            company=COMPANY,
            payload=payload,
            mode="Production",
        )
        checks["production_malformed_2xx_requires_reconciliation"] = (
            len(calls) == before + 1
            and results["production_post_malformed_ambiguous"].get(
                "requires_reconciliation"
            )
            is True
            and results["production_post_malformed_ambiguous"].get("status")
            == "FBR Response Uncertain"
        )

        before = len(calls)
        state["http_result"] = _valid_http_result()
        results["production_post_missing_invoice_number"] = (
            fbr_v2_transport.post_invoice(
                company=COMPANY,
                payload=payload,
                mode="Production",
            )
        )
        checks["production_valid_body_without_invoice_number_is_ambiguous"] = (
            len(calls) == before + 1
            and results["production_post_missing_invoice_number"].get(
                "requires_reconciliation"
            )
            is True
        )

        before = len(calls)
        state["http_result"] = _valid_http_result(
            invoice_number="FBR-GATE-INV-0001"
        )
        results["production_post_conclusive_success"] = (
            fbr_v2_transport.post_invoice(
                company=COMPANY,
                payload=payload,
                mode="Production",
            )
        )
        checks["production_valid_invoice_number_is_conclusive"] = (
            len(calls) == before + 1
            and results["production_post_conclusive_success"].get("success")
            is True
            and results["production_post_conclusive_success"].get(
                "requires_reconciliation"
            )
            is False
        )

        before = len(calls)
        state["http_result"] = _invalid_http_result()
        results["production_post_explicit_invalid"] = (
            fbr_v2_transport.post_invoice(
                company=COMPANY,
                payload=payload,
                mode="Production",
            )
        )
        checks["production_explicit_invalid_is_conclusive_rejection"] = (
            len(calls) == before + 1
            and results["production_post_explicit_invalid"].get("success")
            is False
            and results["production_post_explicit_invalid"].get("status")
            == "FBR Invalid"
            and results["production_post_explicit_invalid"].get(
                "requires_reconciliation"
            )
            is False
        )

        state["profile"] = _profile(mode="Sandbox", enabled=1)
        state["http_result"] = _invalid_http_result()
        results["invalid_fbr_body"] = fbr_v2_transport.validate_invoice(
            company=COMPANY,
            payload=payload,
            mode="Sandbox",
        )
        checks["http_200_invalid_body_fails"] = (
            results["invalid_fbr_body"].get("network_call") is True
            and results["invalid_fbr_body"].get("success") is False
            and results["invalid_fbr_body"].get("status") == "FBR Invalid"
        )

        serialized_results = json.dumps(
            results,
            sort_keys=True,
            default=str,
        )
        checks["tokens_not_exposed_in_results"] = (
            SANDBOX_SECRET not in serialized_results
            and PRODUCTION_SECRET not in serialized_results
        )
        checks["no_commit_attempts"] = not commit_attempts

        failed_checks = [name for name, passed in checks.items() if not passed]

        return {
            "site": frappe.local.site,
            "proof_type": "simulated_transport_policy",
            "real_fbr_network_calls": 0,
            "simulated_transport_calls": len(calls),
            "database_writes": 0,
            "commit_calls_intercepted_in_memory": len(commit_attempts),
            "checks": checks,
            "failed_checks": failed_checks,
            "evidence": {
                "calls": calls,
                "results": results,
            },
            "gate_passed": not failed_checks,
        }

    finally:
        fbr_v2_transport._profile_for_company = original_profile
        fbr_v2_transport._token = original_token
        fbr_v2_transport._production_certification = original_certification
        fbr_transport.requests_available = original_requests_available
        fbr_transport.post_json = original_post_json
        frappe.db.commit = original_commit
