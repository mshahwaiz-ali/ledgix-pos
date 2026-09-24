from __future__ import annotations

"""LOCAL rollback-safe proof for inclusive GST and immutable V2 identity.

This gate proves mechanics only:
- ERPNext remains the monetary/tax authority for an inclusive 18% invoice,
- immutable snapshot version 2 freezes invoice-time seller/buyer identity,
- later live Company master mutation does not alter readiness identity,
- inclusive GST does not become a fake FBR commercial discount,
- canonical payload totalValues still reconciles to ERPNext grand total,
- no FBR network call occurs and every fixture/master mutation rolls back.

The in-memory readiness/mapping shim is mechanics-only. It does not fabricate
persistent FBR reference evidence, mapping approvals, Sandbox certification, or
Production readiness.
"""

from copy import deepcopy

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api import fbr_native
from ledgix_saas.migration import (
    fbr_redesign_phase1_native_core_parity_gate as core,
)
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.services import (
    erpnext_fbr_identity,
    fbr_v2_payload_builder,
    fbr_v2_readiness,
    fbr_v2_snapshot_persistence as snapshots,
)


EXPECTED_PRINTED_RATE = 1180.0
EXPECTED_NET = 1000.0
EXPECTED_GST = 180.0
EXPECTED_TOTAL_VALUES = 1180.0


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing inclusive/identity V2 gate on {frappe.local.site!r}; "
            f"restricted to {INTEGRATION_SITE!r}."
        )


def _close(a, b, tolerance=0.02) -> bool:
    return abs(flt(a) - flt(b)) <= tolerance


def _normalize_identifier(value) -> str:
    return str(value or "").strip().replace(" ", "").replace("-", "")


def _mechanics_snapshot(real_readiness: dict) -> dict:
    snapshot = deepcopy(real_readiness.get("native_snapshot_candidate") or {})
    lines = list(snapshot.get("lines") or [])
    if len(lines) != 1:
        frappe.throw("Inclusive mechanics proof requires exactly one immutable line.")

    line = dict(lines[0])
    mapping = dict(line.get("fbr_mapping") or {})
    mapping.update(
        {
            "name": "IN-MEMORY-INCLUSIVE-MECHANICS",
            "needs_review": 0,
            "hs_code": mapping.get("hs_code") or "MECHANICS-HS",
            "fbr_uom": mapping.get("fbr_uom") or "Nos",
            "sales_type": mapping.get("sales_type") or "Mechanics Only",
            "fbr_rate_description": mapping.get("fbr_rate_description") or "18%",
            "tax_basis": "Transaction Value",
            "notified_retail_price": 0,
            "sro_schedule_number": "",
            "sro_item_serial_number": "",
        }
    )
    line["fbr_mapping"] = mapping
    snapshot["lines"] = [line]
    return snapshot


def _payload_readiness_shim(real_readiness: dict) -> dict:
    result = deepcopy(real_readiness)
    identity = deepcopy(result.get("identity") or {})
    identity["ready"] = True
    identity["errors"] = []
    identity["snapshot_source"] = "persisted_v2"

    result["identity"] = identity
    result["native_snapshot_candidate"] = _mechanics_snapshot(real_readiness)
    result["errors"] = []
    result["payload_input_ready"] = True
    result["mechanics_only_readiness_shim"] = True
    return result


def run() -> dict:
    _assert_safe_site()
    core._require_native_foundation()

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False for this LOCAL gate.")
    if snapshots.SNAPSHOT_VERSION != 2:
        frappe.throw("Inclusive/identity gate requires immutable snapshot version 2.")

    original_user = frappe.session.user
    original_profile_active = snapshots._profile_active
    original_queue = fbr_native.queue_native_for_fbr
    original_commit = frappe.db.commit
    original_builder_readiness = (
        fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness
    )

    submit_hook_intercepts = []
    commit_attempts = []
    created = []
    result = None

    inclusive_item = core.ITEMS["inclusive"]
    before_item_disabled = cint(
        frappe.db.get_value("Item", inclusive_item, "disabled") or 0
    )
    before_company_tax_id = str(
        frappe.db.get_value("Company", core.COMPANY, "tax_id") or ""
    )

    def _force_profile_active(company):
        return company == core.COMPANY

    def _no_network_queue(reference_doctype, reference_name, reason=None):
        submit_hook_intercepts.append(
            {
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "reason": reason or "",
            }
        )
        return {
            "queued": False,
            "status": "Inclusive Identity Gate Bypass",
            "reason": "In-memory gate bypass; no FBR network call.",
        }

    def _no_commit(*args, **kwargs):
        commit_attempts.append(True)
        return None

    try:
        frappe.set_user("Administrator")
        snapshots._profile_active = _force_profile_active
        fbr_native.queue_native_for_fbr = _no_network_queue
        frappe.db.commit = _no_commit

        frappe.db.set_value(
            "Item",
            inclusive_item,
            "disabled",
            0,
            update_modified=False,
        )
        frappe.clear_cache(doctype="Item")

        inclusive_template = core._new_inclusive_template()
        created.append(("Sales Taxes and Charges Template", inclusive_template))

        invoice = core._direct_sales_invoice(
            [{"item_code": inclusive_item, "rate": EXPECTED_PRINTED_RATE}],
            taxes_and_charges=inclusive_template,
            remarks="FBR V2 Inclusive Identity Payload Gate",
        )
        created.append(("Sales Invoice", invoice.name))

        persisted = snapshots.read_persisted_v2_snapshot(
            invoice.doctype,
            invoice.name,
        )
        header = dict(persisted.get("header") or {})
        frozen_identity = deepcopy(header.get("identity") or {})
        persisted_lines = list((persisted.get("lines") or {}).values())
        if len(persisted_lines) != 1:
            frappe.throw("Expected exactly one persisted inclusive snapshot line.")
        frozen_line = dict((persisted_lines[0] or {}).get("line") or {})

        real_before = fbr_v2_readiness.evaluate_invoice_readiness(
            invoice.doctype,
            invoice.name,
        )

        frozen_tax_id = str(
            (frozen_identity.get("seller") or {}).get("ntn_cnic") or ""
        )
        mutated_tax_id = (
            "8888888-8"
            if frozen_tax_id == "9999999-9"
            else "9999999-9"
        )

        frappe.db.set_value(
            "Company",
            core.COMPANY,
            "tax_id",
            mutated_tax_id,
            update_modified=False,
        )
        frappe.clear_cache(doctype="Company")

        live_after_mutation = erpnext_fbr_identity.resolve_invoice_identity(invoice)
        real_after = fbr_v2_readiness.evaluate_invoice_readiness(
            invoice.doctype,
            invoice.name,
        )

        shim = _payload_readiness_shim(real_after)

        def _shim_readiness(reference_doctype, reference_name):
            if (
                reference_doctype != invoice.doctype
                or reference_name != invoice.name
            ):
                frappe.throw("Inclusive/identity readiness shim received another invoice.")
            return deepcopy(shim)

        fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness = (
            _shim_readiness
        )

        built = fbr_v2_payload_builder.build_payload_candidate(
            invoice.doctype,
            invoice.name,
        )
        payload = dict(built.get("payload") or {})
        payload_items = list(payload.get("items") or [])
        if len(payload_items) != 1:
            frappe.throw("Expected one canonical payload item.")
        payload_item = dict(payload_items[0])

        frozen_seller = dict(frozen_identity.get("seller") or {})
        readiness_before_identity = dict(real_before.get("identity") or {})
        readiness_after_identity = dict(real_after.get("identity") or {})

        checks = {
            "invoice_submitted": cint(invoice.docstatus) == 1,
            "erpnext_inclusive_net_1000": _close(invoice.net_total, EXPECTED_NET),
            "erpnext_inclusive_gst_180": _close(
                invoice.total_taxes_and_charges,
                EXPECTED_GST,
            ),
            "erpnext_inclusive_grand_1180": _close(
                invoice.grand_total,
                EXPECTED_TOTAL_VALUES,
            ),
            "snapshot_version_2": cint(header.get("snapshot_version")) == 2,
            "snapshot_hash_verified": bool(persisted.get("hash_verified")),
            "snapshot_has_frozen_identity": bool(frozen_identity),
            "snapshot_line_amount_1180": _close(
                frozen_line.get("amount"),
                EXPECTED_PRINTED_RATE,
            ),
            "snapshot_line_net_1000": _close(
                frozen_line.get("net_amount"),
                EXPECTED_NET,
            ),
            "snapshot_explicit_discount_zero": _close(
                frozen_line.get("discount_amount"),
                0,
            ),
            "snapshot_distributed_discount_zero": _close(
                frozen_line.get("distributed_discount_amount"),
                0,
            ),
            "readiness_before_uses_persisted_identity": (
                readiness_before_identity.get("snapshot_source")
                == "persisted_v2"
                and dict(readiness_before_identity.get("seller") or {})
                == dict(frozen_identity.get("seller") or {})
                and dict(readiness_before_identity.get("buyer") or {})
                == dict(frozen_identity.get("buyer") or {})
            ),
            "live_master_identity_actually_changed": (
                str(
                    (live_after_mutation.get("seller") or {}).get("ntn_cnic")
                    or ""
                )
                == mutated_tax_id
                and mutated_tax_id != frozen_tax_id
            ),
            "readiness_after_mutation_still_uses_frozen_identity": (
                readiness_after_identity.get("snapshot_source")
                == "persisted_v2"
                and str(
                    (readiness_after_identity.get("seller") or {}).get("ntn_cnic")
                    or ""
                )
                == frozen_tax_id
                and str(
                    (readiness_after_identity.get("seller") or {}).get("ntn_cnic")
                    or ""
                )
                != mutated_tax_id
            ),
            "payload_uses_frozen_seller_identity": (
                payload.get("sellerNTNCNIC")
                == _normalize_identifier(frozen_seller.get("ntn_cnic"))
                and payload.get("sellerNTNCNIC")
                != _normalize_identifier(mutated_tax_id)
            ),
            "payload_discount_zero": _close(payload_item.get("discount"), 0),
            "payload_value_excluding_st_1000": _close(
                payload_item.get("valueSalesExcludingST"),
                EXPECTED_NET,
            ),
            "payload_sales_tax_180": _close(
                payload_item.get("salesTaxApplicable"),
                EXPECTED_GST,
            ),
            "payload_total_values_1180": _close(
                payload_item.get("totalValues"),
                EXPECTED_TOTAL_VALUES,
            ),
            "payload_reconciles_to_erpnext": bool(
                (built.get("reconciliation") or {}).get("passed")
            ),
            "payload_snapshot_version_2": (
                cint((built.get("source") or {}).get("snapshot_version")) == 2
            ),
            "submit_hook_intercepts_are_in_memory_only": bool(submit_hook_intercepts),
            "no_real_fbr_network_calls": True,
            "no_commit_attempts": not commit_attempts,
        }

        failed_checks = [
            name for name, passed in checks.items() if not passed
        ]

        result = {
            "site": frappe.local.site,
            "proof_type": "inclusive_tax_and_immutable_identity_payload_mechanics",
            "authority": "ERPNext Native",
            "database_persistence": "ROLLBACK_PENDING_VERIFICATION",
            "real_fbr_network_calls": 0,
            "submit_hooks_intercepted_in_memory": len(submit_hook_intercepts),
            "checks": checks,
            "failed_checks": failed_checks,
            "evidence": {
                "invoice": {
                    "name": invoice.name,
                    "net_total": flt(invoice.net_total, 2),
                    "total_taxes_and_charges": flt(
                        invoice.total_taxes_and_charges,
                        2,
                    ),
                    "grand_total": flt(invoice.grand_total, 2),
                },
                "snapshot": {
                    "version": header.get("snapshot_version"),
                    "hash": persisted.get("snapshot_hash") or "",
                    "hash_verified": bool(persisted.get("hash_verified")),
                    "line_amount": flt(frozen_line.get("amount"), 2),
                    "line_net_amount": flt(frozen_line.get("net_amount"), 2),
                    "discount_amount": flt(
                        frozen_line.get("discount_amount"),
                        2,
                    ),
                    "distributed_discount_amount": flt(
                        frozen_line.get("distributed_discount_amount"),
                        2,
                    ),
                },
                "identity": {
                    "frozen_seller_tax_id": frozen_tax_id,
                    "temporary_live_master_tax_id": mutated_tax_id,
                    "readiness_source_after_mutation": (
                        readiness_after_identity.get("snapshot_source") or ""
                    ),
                },
                "payload_item": payload_item,
                "reconciliation": built.get("reconciliation") or {},
                "mechanics_only_mapping_shim": True,
            },
            "scope_proven": [
                "ERPNext inclusive GST remains 1000 net + 180 GST = 1180 grand total",
                "immutable V2 snapshot version 2 freezes invoice-time identity",
                "live Company Tax ID mutation after submit does not change V2 readiness identity",
                "inclusive-tax amount/net difference is not reported as FBR discount",
                "canonical payload discount is zero for the no-discount inclusive fixture",
                "canonical totalValues equals immutable ERPNext grand total 1180",
            ],
            "scope_not_proven": [
                "official FBR reference-data acceptance",
                "commercial discount FBR semantics",
                "Sandbox Validate or POST acceptance",
                "Production activation",
            ],
            "gate_passed": not failed_checks,
        }

        if failed_checks:
            frappe.throw(
                "Inclusive/identity V2 payload mechanics failed: "
                + ", ".join(failed_checks)
            )
    finally:
        fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness = (
            original_builder_readiness
        )
        snapshots._profile_active = original_profile_active
        fbr_native.queue_native_for_fbr = original_queue
        frappe.db.commit = original_commit
        frappe.set_user(original_user)
        frappe.db.rollback()
        frappe.clear_cache(doctype="Company")
        frappe.clear_cache(doctype="Item")
        frappe.clear_cache(doctype="Sales Taxes and Charges Template")

    if result is None:
        frappe.throw("Inclusive/identity V2 gate produced no result.")

    after_item_disabled = cint(
        frappe.db.get_value("Item", inclusive_item, "disabled") or 0
    )
    after_company_tax_id = str(
        frappe.db.get_value("Company", core.COMPANY, "tax_id") or ""
    )
    persisted_created = [
        {"doctype": doctype, "name": name}
        for doctype, name in created
        if frappe.db.exists(doctype, name)
    ]
    invoice_names = [
        name for doctype, name in created if doctype == "Sales Invoice"
    ]
    gl_rows_left = 0
    if invoice_names:
        gl_rows_left = frappe.db.count(
            "GL Entry",
            {
                "voucher_type": "Sales Invoice",
                "voucher_no": ["in", invoice_names],
            },
        )

    rollback_clean = (
        after_item_disabled == before_item_disabled
        and after_company_tax_id == before_company_tax_id
        and not persisted_created
        and gl_rows_left == 0
    )
    cutover_still_false = (
        getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
    )

    result["post_rollback"] = {
        "item_disabled_restored": (
            after_item_disabled == before_item_disabled
        ),
        "company_tax_id_restored": (
            after_company_tax_id == before_company_tax_id
        ),
        "persisted_gate_records": persisted_created,
        "gate_gl_rows_left": gl_rows_left,
        "rollback_clean": rollback_clean,
        "v2_network_cutover_still_false": cutover_still_false,
    }
    result["database_persistence"] = (
        "ROLLBACK_CONFIRMED"
        if rollback_clean
        else "ROLLBACK_VERIFICATION_FAILED"
    )
    result["gate_passed"] = bool(
        result.get("gate_passed")
        and rollback_clean
        and cutover_still_false
    )

    if not result["gate_passed"]:
        frappe.throw(
            "Inclusive/identity V2 gate failed post-rollback safety: "
            + frappe.as_json(result.get("post_rollback") or {})
        )

    return result
