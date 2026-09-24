from __future__ import annotations

"""Read-only proof that the legacy FBR execution/transport stack is retired."""

import frappe

from ledgix_saas.api import (
    fbr_client,
    fbr_native,
    fbr_payload,
    fbr_settings,
    fbr_submission,
    fbr_transport,
    fbr_v2_transport,
)
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.services import fbr_submission_support


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Patch 5D gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run() -> dict:
    _assert_safe_site()

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False.")

    original_user = frappe.session.user
    original_settings = fbr_settings.get_fbr_settings_internal
    original_control = fbr_settings.get_fbr_control_state_internal
    original_token = fbr_settings.get_active_fbr_token
    original_get = fbr_transport.get_json
    original_post = fbr_transport.post_json
    original_v2_validate = fbr_v2_transport.validate_invoice
    original_v2_post = fbr_v2_transport.post_invoice

    legacy_attempts = []
    network_attempts = []

    def _forbid_legacy(*args, **kwargs):
        legacy_attempts.append(True)
        frappe.throw(
            "OLD FBR SETTINGS FORBIDDEN BY PATCH 5D GATE"
        )

    def _forbid_network(*args, **kwargs):
        network_attempts.append(True)
        frappe.throw(
            "FBR NETWORK FORBIDDEN BY PATCH 5D GATE"
        )

    try:
        frappe.set_user("Administrator")

        fbr_settings.get_fbr_settings_internal = _forbid_legacy
        fbr_settings.get_fbr_control_state_internal = _forbid_legacy
        fbr_settings.get_active_fbr_token = _forbid_legacy
        fbr_transport.get_json = _forbid_network
        fbr_transport.post_json = _forbid_network
        fbr_v2_transport.validate_invoice = _forbid_network
        fbr_v2_transport.post_invoice = _forbid_network

        client_status = fbr_client.get_client_status()
        client_validate = fbr_client.validate_invoice(
            {"invoiceType": "Sale Invoice"},
            mode="Sandbox",
        )
        client_post = fbr_client.post_invoice(
            {"invoiceType": "Sale Invoice"},
            mode="Production",
        )

        sale_submit = fbr_submission._submit_sale_to_fbr_internal(
            "LEGACY-SALE-PROBE"
        )
        return_submit = fbr_submission._submit_return_to_fbr_internal(
            "LEGACY-RETURN-PROBE"
        )
        sale_queue = fbr_submission.queue_sale_for_fbr(
            "LEGACY-SALE-PROBE"
        )
        return_queue = fbr_submission.queue_return_for_fbr(
            "LEGACY-RETURN-PROBE"
        )
        retry_queue = fbr_submission.process_fbr_retry_queue()
        offline_queue = fbr_submission.process_fbr_offline_upload_queue()

        payload_guarded = False
        payload_message = ""
        try:
            fbr_payload.validate_sale_fbr_readiness(
                "LEGACY-SALE-PROBE"
            )
        except frappe.ValidationError as exc:
            payload_message = str(exc)
            payload_guarded = (
                "Legacy Ledgix Sale / Sales Return FBR execution is retired"
                in payload_message
            )

    finally:
        fbr_settings.get_fbr_settings_internal = original_settings
        fbr_settings.get_fbr_control_state_internal = original_control
        fbr_settings.get_active_fbr_token = original_token
        fbr_transport.get_json = original_get
        fbr_transport.post_json = original_post
        fbr_v2_transport.validate_invoice = original_v2_validate
        fbr_v2_transport.post_invoice = original_v2_post
        frappe.set_user(original_user)

    checks = {
        "client_status_stays_v2": (
            client_status.get("source")
            == "Ledgix FBR Integration Profile"
        ),
        "legacy_client_validate_retired": (
            client_validate.get("status") == "Retired"
            and client_validate.get("network_call") is False
        ),
        "legacy_client_post_retired": (
            client_post.get("status") == "Retired"
            and client_post.get("network_call") is False
        ),
        "legacy_sale_submission_retired": (
            sale_submit.get("status") == "Retired"
            and sale_submit.get("network_call") is False
        ),
        "legacy_return_submission_retired": (
            return_submit.get("status") == "Retired"
            and return_submit.get("network_call") is False
        ),
        "legacy_queues_retired": (
            sale_queue.get("status") == "Retired"
            and return_queue.get("status") == "Retired"
            and retry_queue.get("processed") == 0
            and retry_queue.get("retired") is True
            and offline_queue.get("processed") == 0
            and offline_queue.get("retired") is True
        ),
        "legacy_payload_rpc_guarded": payload_guarded,
        "neutral_log_helper_reexported": (
            fbr_submission.create_submission_log
            is fbr_submission_support.create_submission_log
        ),
        "old_settings_not_called": not legacy_attempts,
        "no_fbr_network_attempts": not network_attempts,
        "native_cutover_false": (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None)
            is False
        ),
    }

    result = {
        "site": frappe.local.site,
        "proof_type": "v2_legacy_transport_retirement_patch5d",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "checks": checks,
        "failed_checks": [
            key for key, passed in checks.items() if not passed
        ],
        "evidence": {
            "client_status": client_status,
            "legacy_client_validate": client_validate,
            "legacy_client_post": client_post,
            "legacy_sale_submit": sale_submit,
            "legacy_return_submit": return_submit,
            "payload_guard_message": payload_message,
        },
        "scope_proven": [
            "legacy fbr_client cannot validate or POST invoices",
            "legacy fbr_submission cannot submit/mutate Sale or Sales Return FBR state",
            "legacy queues are inert",
            "legacy payload RPC fails closed",
            "neutral submission helpers remain available outside legacy engine",
            "old Ledgix FBR Settings/token APIs are not read",
            "no FBR network request is made",
        ],
        "scope_not_proven": [
            "old Ledgix FBR Settings DocType/schema deletion",
            "old demo/setup/settings writer cleanup",
            "authorized Sandbox V2 network behavior",
        ],
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "Patch 5D legacy transport retirement gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
