from __future__ import annotations

"""Rollback-safe real-state proof for the canonical FBR V2 payload builder.

This gate intentionally does NOT fabricate or approve:
- Company NTN/CNIC or legal addresses,
- Customer legal addresses,
- FBR Item Mapping review state,
- official FBR reference-cache evidence,
- Sandbox scenario evidence.

It creates one temporary native ERPNext Sales Invoice, forces the already-proven
V2 snapshot capture only inside this Python process, then proves that the
canonical payload builder rejects the invoice for the current real configuration
gaps. All transactional/master fixture writes are rolled back.
"""

import frappe
from frappe.utils import cint

from ledgix_saas.api import fbr_native
from ledgix_saas.migration import fbr_redesign_phase1_native_core_parity_gate as core
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.services import (
    erpnext_selling,
    fbr_v2_payload_builder,
    fbr_v2_readiness,
    fbr_v2_snapshot_persistence,
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing FBR V2 payload fail-closed gate on {frappe.local.site!r}; "
            f"restricted to {INTEGRATION_SITE!r}."
        )


def _has_error(errors: list[str], *parts: str) -> bool:
    folded = [str(row or "").casefold() for row in errors]
    wanted = [str(part or "").casefold() for part in parts]
    return any(all(part in row for part in wanted) for row in folded)


def run() -> dict:
    _assert_safe_site()

    original_user = frappe.session.user
    original_queue = fbr_native.queue_native_for_fbr
    original_profile_active = fbr_v2_snapshot_persistence._profile_active
    original_commit = frappe.db.commit

    created_invoice_name = ""
    fbr_hook_intercepts = []
    commit_intercepts = []
    result = None

    def _no_network_queue(reference_doctype, reference_name, reason=None):
        fbr_hook_intercepts.append(
            {
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "reason": reason or "",
            }
        )
        return {
            "queued": False,
            "status": "V2 Payload Fail-Closed Gate Bypass",
            "reason": "In-memory gate bypass; no FBR network call.",
        }

    def _force_snapshot_profile(company: str) -> bool:
        # Snapshot capture is forced only for the local proof document. The V2
        # Integration Profile itself remains Disabled/unarmed in the database.
        return str(company or "") == core.COMPANY

    def _no_commit():
        commit_intercepts.append(True)
        return None

    try:
        frappe.set_user("Administrator")
        core._require_native_foundation()

        fbr_native.queue_native_for_fbr = _no_network_queue
        fbr_v2_snapshot_persistence._profile_active = _force_snapshot_profile
        frappe.db.commit = _no_commit

        core._enable_fixture_items()
        price_list = core._new_price_list()

        invoice = erpnext_selling.build_sales_invoice(
            customer=core._customer(),
            items=[{"item": core.ITEMS["ordinary"], "qty": 1}],
            company=core.COMPANY,
            selling_price_list=price_list,
            sale_channel="B2B",
            client_sale_id=f"V2-PAYLOAD-FAIL-CLOSED-{frappe.generate_hash(length=10)}",
            allow_rate_override=False,
            update_stock=False,
            checkout_source="FBR V2 Payload Fail-Closed Gate",
        )
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        invoice.reload()
        created_invoice_name = invoice.name

        persisted = fbr_v2_snapshot_persistence.read_persisted_v2_snapshot(
            invoice.doctype,
            invoice.name,
        )
        readiness = fbr_v2_readiness.evaluate_invoice_readiness(
            invoice.doctype,
            invoice.name,
        )
        errors = list(readiness.get("errors") or [])

        builder_blocked = False
        builder_error = ""
        try:
            fbr_v2_payload_builder.build_payload_candidate(
                invoice.doctype,
                invoice.name,
            )
        except Exception as exc:
            builder_blocked = True
            builder_error = str(exc)

        profile = dict(readiness.get("profile") or {})

        checks = {
            "invoice_submitted": cint(invoice.docstatus) == 1,
            "snapshot_hash_verified": bool(persisted.get("hash_verified")),
            "readiness_uses_persisted_snapshot": (
                (readiness.get("native_snapshot_candidate") or {}).get("snapshot_source")
                == "persisted_v2"
            ),
            "readiness_snapshot_hash_verified": bool(
                (readiness.get("native_snapshot_candidate") or {}).get("hash_verified")
            ),
            "payload_input_not_ready": readiness.get("payload_input_ready") is False,
            "seller_tax_id_blocker_present": _has_error(
                errors,
                "company tax id",
            ),
            "seller_address_blocker_present": _has_error(
                errors,
                "company",
                "address",
            ),
            "buyer_address_blocker_present": _has_error(
                errors,
                "customer",
                "address",
            ),
            "mapping_review_blocker_present": _has_error(
                errors,
                "item mapping",
                "review",
            ),
            "official_reference_blocker_present": any(
                "reference" in str(row or "").casefold()
                or "verified against active fbr" in str(row or "").casefold()
                for row in errors
            ),
            "builder_blocked": builder_blocked,
            "builder_reports_readiness_failure": (
                "FBR V2 payload input is not ready" in builder_error
            ),
            "profile_still_disabled": (
                profile.get("enabled") is False
                and profile.get("mode") == "Disabled"
            ),
            "production_still_unarmed": profile.get("production_post_armed") is False,
            "no_commit": len(commit_intercepts) == 0,
            "one_submit_hook_intercepted": len(fbr_hook_intercepts) == 1,
        }

        failed_checks = [name for name, passed in checks.items() if not passed]

        result = {
            "site": frappe.local.site,
            "authority": "ERPNext Native",
            "proof_type": "real_state_fail_closed",
            "database_persistence": "ROLLBACK_PENDING",
            "fbr_network_calls": 0,
            "fbr_submit_hooks_intercepted_in_memory": len(fbr_hook_intercepts),
            "commit_calls_intercepted_in_memory": len(commit_intercepts),
            "reference_rows_fabricated": 0,
            "mapping_review_state_changed": False,
            "identity_master_data_changed": False,
            "checks": checks,
            "failed_checks": failed_checks,
            "evidence": {
                "invoice": {
                    "doctype": invoice.doctype,
                    "name": invoice.name,
                    "docstatus": cint(invoice.docstatus),
                    "customer": invoice.customer,
                    "grand_total": invoice.grand_total,
                },
                "snapshot": {
                    "snapshot_version": persisted.get("snapshot_version"),
                    "snapshot_hash": persisted.get("snapshot_hash"),
                    "hash_verified": bool(persisted.get("hash_verified")),
                },
                "readiness": {
                    "payload_input_ready": readiness.get("payload_input_ready"),
                    "profile": profile,
                    "errors": errors,
                    "warning_count": len(readiness.get("warnings") or []),
                },
                "builder": {
                    "blocked": builder_blocked,
                    "error": builder_error,
                },
            },
            "gate_passed": not failed_checks,
        }

        if failed_checks:
            frappe.throw(
                "FBR V2 payload real-state fail-closed gate failed checks: "
                + ", ".join(failed_checks)
            )

    finally:
        fbr_native.queue_native_for_fbr = original_queue
        fbr_v2_snapshot_persistence._profile_active = original_profile_active
        frappe.db.commit = original_commit

        frappe.db.rollback()
        frappe.clear_cache(doctype="Item")
        frappe.clear_cache(doctype="Price List")
        frappe.set_user(original_user)

    if result is None:
        frappe.throw("FBR V2 payload fail-closed gate produced no result.")

    persisted_after_rollback = []
    if created_invoice_name and frappe.db.exists("Sales Invoice", created_invoice_name):
        persisted_after_rollback.append(created_invoice_name)

    result["database_persistence"] = "ROLLBACK_CONFIRMED"
    result["post_rollback"] = {
        "persisted_gate_invoices": persisted_after_rollback,
        "rollback_clean": not persisted_after_rollback,
    }
    result["gate_passed"] = bool(
        result.get("gate_passed")
        and result["post_rollback"]["rollback_clean"]
    )

    return result
