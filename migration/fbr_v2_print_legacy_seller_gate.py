from __future__ import annotations

"""Rollback-safe LOCAL proof for native print / legacy seller retirement.

This gate creates one real ERPNext Sales Invoice only inside the current DB
transaction, forces the normal V2 before-submit snapshot capture for that fixture,
verifies print identity against the persisted hash-verified snapshot, blocks any
commit/network attempt, and rolls the complete fixture transaction back.
"""

import frappe

from ledgix_saas.api import (
    fbr_native,
    fbr_transport,
    fbr_v2_transport,
    legacy_retirement,
    printing,
)
from ledgix_saas.migration import (
    fbr_redesign_phase1_native_core_parity_gate as core,
)
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.services import (
    erpnext_selling,
    fbr_v2_snapshot_persistence,
    sales,
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Patch 5C gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run() -> dict:
    _assert_safe_site()

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False.")

    if not legacy_retirement.is_frozen():
        frappe.throw(
            "Patch 5C requires Phase 12 legacy history to remain frozen."
        )

    original_user = frappe.session.user
    original_get_single = frappe.get_single
    original_get_single_value = frappe.db.get_single_value
    original_get = fbr_transport.get_json
    original_post = fbr_transport.post_json
    original_v2_validate = fbr_v2_transport.validate_invoice
    original_v2_post = fbr_v2_transport.post_invoice
    original_profile_active = fbr_v2_snapshot_persistence._profile_active
    original_commit = frappe.db.commit

    legacy_settings_attempts = []
    network_attempts = []
    commit_attempts = []
    created = []
    result = None

    def _guarded_get_single(doctype, *args, **kwargs):
        if doctype == "Ledgix FBR Settings":
            legacy_settings_attempts.append(True)
            frappe.throw(
                "OLD FBR SETTINGS FORBIDDEN BY PATCH 5C GATE"
            )
        return original_get_single(doctype, *args, **kwargs)

    def _guarded_get_single_value(doctype, fieldname, *args, **kwargs):
        if doctype == "Ledgix FBR Settings":
            legacy_settings_attempts.append(True)
            frappe.throw(
                "OLD FBR SETTINGS FORBIDDEN BY PATCH 5C GATE"
            )
        return original_get_single_value(
            doctype,
            fieldname,
            *args,
            **kwargs,
        )

    def _forbid_network(*args, **kwargs):
        network_attempts.append(
            {
                "operation": "legacy_get_or_post",
                "args": len(args),
                "kwargs": sorted(kwargs),
            }
        )
        frappe.throw(
            "REAL FBR NETWORK FORBIDDEN BY PATCH 5C GATE"
        )

    def _forbid_v2_transport(*args, **kwargs):
        network_attempts.append(
            {
                "operation": "v2_validate_or_post",
                "args": len(args),
                "kwargs": sorted(kwargs),
            }
        )
        frappe.throw(
            "FBR V2 TRANSPORT FORBIDDEN BY PATCH 5C GATE"
        )

    def _force_snapshot_profile(company: str) -> bool:
        return str(company or "") == core.COMPANY

    def _no_commit():
        commit_attempts.append(True)
        return None

    try:
        frappe.set_user("Administrator")
        core._require_native_foundation()

        frappe.get_single = _guarded_get_single
        frappe.db.get_single_value = _guarded_get_single_value
        fbr_transport.get_json = _forbid_network
        fbr_transport.post_json = _forbid_network
        fbr_v2_transport.validate_invoice = _forbid_v2_transport
        fbr_v2_transport.post_invoice = _forbid_v2_transport
        fbr_v2_snapshot_persistence._profile_active = _force_snapshot_profile
        frappe.db.commit = _no_commit

        core._enable_fixture_items()
        price_list = core._new_price_list()

        sale = erpnext_selling.build_sales_invoice(
            customer=core._customer(),
            items=[{"item": core.ITEMS["ordinary"], "qty": 1}],
            company=core.COMPANY,
            selling_price_list=price_list,
            sale_channel="B2B",
            client_sale_id=(
                "P5C-PRINT-" + frappe.generate_hash(length=10)
            ),
            allow_rate_override=False,
            update_stock=False,
            checkout_source="FBR V2 Print Patch 5C Gate",
        )
        sale.insert(ignore_permissions=True)
        created.append(("Sales Invoice", sale.name))
        sale.submit()
        sale.reload()

        persisted = fbr_v2_snapshot_persistence.read_persisted_v2_snapshot(
            sale.doctype,
            sale.name,
        )
        context = printing.get_native_invoice_print_context(
            sale.doctype,
            sale.name,
        )
        legacy_seller = sales.get_seller_identity()

        identity = dict((persisted.get("header") or {}).get("identity") or {})
        expected_seller = dict(identity.get("seller") or {})
        expected_buyer = dict(identity.get("buyer") or {})
        actual_seller = dict(context.get("seller") or {})
        actual_buyer = dict(context.get("buyer") or {})

        profile_name = actual_seller.get("fbr_profile") or ""
        expected_registration = (
            frappe.db.get_value(
                "Ledgix FBR Integration Profile",
                profile_name,
                "software_registration_number",
            )
            if profile_name
            else ""
        ) or ""

        checks = {
            "fixture_submitted_with_v2_snapshot": (
                sale.docstatus == 1
                and persisted.get("hash_verified") is True
                and persisted.get("snapshot_version")
                == fbr_v2_snapshot_persistence.SNAPSHOT_VERSION
            ),
            "print_uses_persisted_v2_identity": (
                context.get("identity_source") == "persisted_v2"
                and context.get("identity_snapshot_hash")
                == persisted.get("snapshot_hash")
            ),
            "seller_matches_frozen_snapshot": (
                actual_seller.get("name")
                == expected_seller.get("business_name")
                and actual_seller.get("address")
                == expected_seller.get("address")
                and actual_seller.get("province")
                == expected_seller.get("province")
                and actual_seller.get("ntn")
                == expected_seller.get("ntn_cnic")
            ),
            "buyer_matches_frozen_snapshot": (
                actual_buyer.get("name")
                == expected_buyer.get("business_name")
                and actual_buyer.get("address")
                == expected_buyer.get("address")
                and actual_buyer.get("province")
                == expected_buyer.get("province")
                and actual_buyer.get("ntn_cnic")
                == expected_buyer.get("ntn_cnic")
                and actual_buyer.get("registration_type")
                == expected_buyer.get("registration_type")
            ),
            "software_registration_comes_from_v2_profile": (
                actual_seller.get("software_registration_number")
                == expected_registration
            ),
            "no_unproven_fbr_logo_reused": (
                actual_seller.get("digital_invoicing_logo") == ""
            ),
            "legacy_seller_resolver_has_explicit_authority": (
                legacy_seller.get("authority")
                in {"ERPNext", "Legacy Brand Snapshot Fallback"}
            ),
            "legacy_history_stays_frozen": legacy_retirement.is_frozen(),
            "old_fbr_settings_not_read": not legacy_settings_attempts,
            "no_fbr_network_attempts": not network_attempts,
            "no_commit_attempts": not commit_attempts,
            "native_cutover_still_false": (
                getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None)
                is False
            ),
        }

        result = {
            "site": frappe.local.site,
            "proof_type": "v2_print_legacy_seller_retirement_patch5c",
            "reference_doctype": sale.doctype,
            "reference_name": sale.name,
            "real_fbr_network_calls": 0,
            "database_write_transient": True,
            "database_persistence": "PENDING_ROLLBACK",
            "checks": checks,
            "failed_checks": [
                key for key, passed in checks.items() if not passed
            ],
            "evidence": {
                "snapshot_hash": persisted.get("snapshot_hash"),
                "identity_source": context.get("identity_source"),
                "seller": actual_seller,
                "buyer": actual_buyer,
                "legacy_seller_authority": legacy_seller.get("authority"),
                "created": list(created),
            },
            "scope_proven": [
                "real submitted native invoice captures a hash-verified V2 snapshot",
                "native print seller/buyer identity comes from that persisted V2 snapshot",
                "software registration metadata comes from company-scoped V2 profile",
                "legacy seller snapshot resolver no longer reads old FBR Settings",
                "legacy business history remains frozen",
                "no FBR transport/network request is made",
                "no commit is allowed",
            ],
            "scope_not_proven": [
                "legacy fbr_payload/fbr_submission/fbr_client transport retirement",
                "old Ledgix FBR Settings DocType deletion",
                "authorized Sandbox network behavior",
            ],
            "gate_passed": all(checks.values()),
        }

    finally:
        try:
            frappe.db.rollback()
        finally:
            frappe.db.commit = original_commit
            fbr_v2_snapshot_persistence._profile_active = original_profile_active
            fbr_v2_transport.validate_invoice = original_v2_validate
            fbr_v2_transport.post_invoice = original_v2_post
            fbr_transport.get_json = original_get
            fbr_transport.post_json = original_post
            frappe.get_single = original_get_single
            frappe.db.get_single_value = original_get_single_value
            frappe.set_user(original_user)

    if result is None:
        frappe.throw("Patch 5C gate ended before producing proof evidence.")

    persisted_after_rollback = [
        {"doctype": doctype, "name": name}
        for doctype, name in created
        if frappe.db.exists(doctype, name)
    ]
    rollback_clean = not persisted_after_rollback

    result["post_rollback"] = {
        "persisted_gate_invoices": persisted_after_rollback,
        "rollback_clean": rollback_clean,
    }
    result["checks"]["rollback_clean"] = rollback_clean
    result["database_persistence"] = (
        "ROLLBACK_CONFIRMED" if rollback_clean else "ROLLBACK_FAILED"
    )
    result["failed_checks"] = [
        key for key, passed in result["checks"].items() if not passed
    ]
    result["gate_passed"] = (
        all(result["checks"].values())
        and result["database_persistence"] == "ROLLBACK_CONFIRMED"
    )

    if not result["gate_passed"]:
        frappe.throw(
            "Patch 5C print/legacy seller gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
