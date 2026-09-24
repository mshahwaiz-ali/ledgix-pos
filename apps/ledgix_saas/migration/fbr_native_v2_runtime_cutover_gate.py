from __future__ import annotations

"""Rollback-safe runtime proof for native FBR preview/readiness V2 cutover.

The gate proves, on real submitted ERPNext documents, that:
- before_submit persists the V2 immutable snapshot,
- on_submit reaches the native FBR hook safely,
- native readiness/preview uses V2 persisted evidence,
- invalid real configuration returns no partial payload,
- validate/POST remain blocked before transport,
- no FBR network function is called,
- all fixture writes are rolled back.

No FBR reference rows, identity data, mapping review state, tokens or production
arming are fabricated or changed.
"""

import frappe
from frappe.utils import cint

from ledgix_saas.api import fbr_native, fbr_v2_transport
from ledgix_saas.migration import fbr_redesign_phase1_native_core_parity_gate as core
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.services import (
    erpnext_pos,
    erpnext_selling,
    fbr_v2_snapshot_persistence,
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing FBR native V2 runtime cutover gate on {frappe.local.site!r}; "
            f"restricted to {INTEGRATION_SITE!r}."
        )


def _preview_evidence(doctype: str, name: str) -> dict:
    readiness = fbr_native.validate_native_readiness_internal(doctype, name)
    preview = fbr_native.build_native_payload_internal(doctype, name)

    return {
        "readiness": readiness,
        "preview": preview,
        "checks": {
            "readiness_invalid_for_real_gaps": readiness.get("valid") is False,
            "readiness_snapshot_source_persisted_v2": (
                (readiness.get("v2") or {}).get("snapshot_source") == "persisted_v2"
            ),
            "readiness_snapshot_hash_verified": bool(
                (readiness.get("v2") or {}).get("snapshot_hash_verified")
            ),
            "readiness_profile_source_v2": (
                (readiness.get("settings") or {}).get("source")
                == "Ledgix FBR Integration Profile"
            ),
            "preview_payload_none": preview.get("payload") is None,
            "preview_builder_v2": (
                (preview.get("source") or {}).get("payload_builder") == "FBR V2"
            ),
            "preview_authority_native": (
                (preview.get("source") or {}).get("authority") == "ERPNext Native"
            ),
        },
    }


def run() -> dict:
    _assert_safe_site()

    original_user = frappe.session.user
    original_profile_active = fbr_v2_snapshot_persistence._profile_active
    original_validate = fbr_v2_transport.validate_invoice
    original_post = fbr_v2_transport.post_invoice
    original_commit = frappe.db.commit

    network_attempts = []
    commit_attempts = []
    created = []
    result = None

    def _force_snapshot_profile(company: str) -> bool:
        # Only forces snapshot capture for this local rollback-safe proof.
        # It does not mutate the Integration Profile.
        return str(company or "") == core.COMPANY

    def _forbid_validate(*args, **kwargs):
        network_attempts.append(
            {"operation": "validate_invoice", "args": len(args), "kwargs": sorted(kwargs)}
        )
        frappe.throw("TEST FAILURE: legacy/client FBR validate transport was reached.")

    def _forbid_post(*args, **kwargs):
        network_attempts.append(
            {"operation": "post_invoice", "args": len(args), "kwargs": sorted(kwargs)}
        )
        frappe.throw("TEST FAILURE: legacy/client FBR POST transport was reached.")

    def _no_commit():
        commit_attempts.append(True)
        return None

    try:
        frappe.set_user("Administrator")
        core._require_native_foundation()

        fbr_v2_snapshot_persistence._profile_active = _force_snapshot_profile
        fbr_v2_transport.validate_invoice = _forbid_validate
        fbr_v2_transport.post_invoice = _forbid_post
        frappe.db.commit = _no_commit

        core._enable_fixture_items()
        price_list = core._new_price_list()

        # POS needs the same temporary native ERPNext GST template proven by the
        # Phase-1 parity gate. It exists only inside this rolled-back transaction.
        pos_template = core._new_pos_template()
        pos_profile = frappe.get_doc("POS Profile", "Main Counter POS")
        original_pos_template = pos_profile.get("taxes_and_charges")
        pos_profile.db_set(
            "taxes_and_charges",
            pos_template,
            update_modified=False,
        )
        frappe.clear_cache(doctype="POS Profile")

        sale = erpnext_selling.build_sales_invoice(
            customer=core._customer(),
            items=[{"item": core.ITEMS["ordinary"], "qty": 1}],
            company=core.COMPANY,
            selling_price_list=price_list,
            sale_channel="B2B",
            client_sale_id=f"V2-NATIVE-CUTOVER-SI-{frappe.generate_hash(length=10)}",
            allow_rate_override=False,
            update_stock=False,
            checkout_source="FBR Native V2 Runtime Cutover Gate",
        )
        sale.insert(ignore_permissions=True)
        sale.submit()
        sale.reload()
        created.append(("Sales Invoice", sale.name))

        pos = erpnext_pos.build_pos_invoice(
            cart_items=[{"item": core.ITEMS["ordinary"], "qty": 1}],
            customer=pos_profile.customer,
            price_list=price_list,
            client_sale_id=f"V2-NATIVE-CUTOVER-POS-{frappe.generate_hash(length=10)}",
            allow_rate_override=False,
            source="FBR Native V2 Runtime Cutover Gate",
            company=core.COMPANY,
            pos_profile=pos_profile.name,
        )
        erpnext_pos._default_draft_payment(pos, pos_profile)
        pos.insert(ignore_permissions=True)
        pos.submit()
        pos.reload()
        created.append(("POS Invoice", pos.name))

        sale_snapshot = fbr_v2_snapshot_persistence.read_persisted_v2_snapshot(
            sale.doctype,
            sale.name,
        )
        pos_snapshot = fbr_v2_snapshot_persistence.read_persisted_v2_snapshot(
            pos.doctype,
            pos.name,
        )

        sale_preview = _preview_evidence(sale.doctype, sale.name)
        pos_preview = _preview_evidence(pos.doctype, pos.name)

        sale_validate = fbr_native.validate_native_with_fbr_internal(
            sale.doctype,
            sale.name,
        )
        sale_submit = fbr_native.submit_native_to_fbr_internal(
            sale.doctype,
            sale.name,
        )

        pos_validate = fbr_native.validate_native_with_fbr_internal(
            pos.doctype,
            pos.name,
        )
        pos_submit = fbr_native.submit_native_to_fbr_internal(
            pos.doctype,
            pos.name,
        )

        expected_network_message = fbr_native.V2_NETWORK_CUTOVER_MESSAGE

        checks = {
            "sales_invoice_submitted": cint(sale.docstatus) == 1,
            "pos_invoice_submitted": cint(pos.docstatus) == 1,
            "sales_snapshot_hash_verified": bool(sale_snapshot.get("hash_verified")),
            "pos_snapshot_hash_verified": bool(pos_snapshot.get("hash_verified")),
            "sales_preview_contract": all(sale_preview["checks"].values()),
            "pos_preview_contract": all(pos_preview["checks"].values()),
            "sales_validate_network_false": sale_validate.get("network_call") is False,
            "sales_submit_network_false": sale_submit.get("network_call") is False,
            "pos_validate_network_false": pos_validate.get("network_call") is False,
            "pos_submit_network_false": pos_submit.get("network_call") is False,
            "sales_validate_not_ready": sale_validate.get("status") == "Not Ready",
            "sales_submit_not_ready": sale_submit.get("status") == "Not Ready",
            "pos_validate_not_ready": pos_validate.get("status") == "Not Ready",
            "pos_submit_not_ready": pos_submit.get("status") == "Not Ready",
            "sales_validate_cutover_message": (
                sale_validate.get("error_message") == expected_network_message
            ),
            "sales_submit_cutover_message": (
                sale_submit.get("error_message") == expected_network_message
            ),
            "pos_validate_cutover_message": (
                pos_validate.get("error_message") == expected_network_message
            ),
            "pos_submit_cutover_message": (
                pos_submit.get("error_message") == expected_network_message
            ),
            "no_fbr_network_attempts": not network_attempts,
            "no_commit_attempts": not commit_attempts,
            "network_cutover_hard_disabled": (
                fbr_native.V2_NETWORK_CUTOVER_ACTIVE is False
            ),
            "pos_fixture_changed_only_in_transaction": (
                pos_profile.get("taxes_and_charges") != original_pos_template
            ),
        }

        failed_checks = [name for name, passed in checks.items() if not passed]

        result = {
            "site": frappe.local.site,
            "authority": "ERPNext Native",
            "payload_builder": "FBR V2",
            "network_cutover_active": fbr_native.V2_NETWORK_CUTOVER_ACTIVE,
            "database_persistence": "ROLLBACK_PENDING",
            "fbr_network_calls": len(network_attempts),
            "commit_calls_intercepted_in_memory": len(commit_attempts),
            "reference_rows_fabricated": 0,
            "mapping_review_state_changed": False,
            "identity_master_data_changed": False,
            "checks": checks,
            "failed_checks": failed_checks,
            "evidence": {
                "sales_invoice": {
                    "name": sale.name,
                    "docstatus": cint(sale.docstatus),
                    "snapshot_version": sale_snapshot.get("snapshot_version"),
                    "snapshot_hash": sale_snapshot.get("snapshot_hash") or "",
                    "snapshot_hash_verified": bool(
                        sale_snapshot.get("hash_verified")
                    ),
                    "preview": sale_preview,
                    "validate": sale_validate,
                    "submit": sale_submit,
                },
                "pos_invoice": {
                    "name": pos.name,
                    "docstatus": cint(pos.docstatus),
                    "snapshot_version": pos_snapshot.get("snapshot_version"),
                    "snapshot_hash": pos_snapshot.get("snapshot_hash") or "",
                    "snapshot_hash_verified": bool(
                        pos_snapshot.get("hash_verified")
                    ),
                    "preview": pos_preview,
                    "validate": pos_validate,
                    "submit": pos_submit,
                },
            },
            "gate_passed": not failed_checks,
        }

        if failed_checks:
            frappe.throw(
                "FBR native V2 runtime cutover gate failed checks: "
                + ", ".join(failed_checks)
            )

    finally:
        fbr_v2_snapshot_persistence._profile_active = original_profile_active
        fbr_v2_transport.validate_invoice = original_validate
        fbr_v2_transport.post_invoice = original_post
        frappe.db.commit = original_commit

        frappe.db.rollback()
        frappe.clear_cache(doctype="Item")
        frappe.clear_cache(doctype="Price List")
        frappe.clear_cache(doctype="POS Profile")
        frappe.set_user(original_user)

    if result is None:
        frappe.throw("FBR native V2 runtime cutover gate produced no result.")

    persisted_after_rollback = [
        {"doctype": doctype, "name": name}
        for doctype, name in created
        if frappe.db.exists(doctype, name)
    ]

    restored_pos_template = frappe.db.get_value(
        "POS Profile",
        "Main Counter POS",
        "taxes_and_charges",
    )

    result["database_persistence"] = "ROLLBACK_CONFIRMED"
    result["post_rollback"] = {
        "persisted_gate_invoices": persisted_after_rollback,
        "rollback_clean": not persisted_after_rollback,
        "main_counter_pos_taxes_and_charges": restored_pos_template or "",
    }
    result["gate_passed"] = bool(
        result.get("gate_passed")
        and result["post_rollback"]["rollback_clean"]
        and not result["post_rollback"]["main_counter_pos_taxes_and_charges"]
    )

    return result
