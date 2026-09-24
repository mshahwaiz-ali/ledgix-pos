from __future__ import annotations

"""Rollback-safe LOCAL proof for the ordinary canonical FBR V2 payload matrix.

The Phase-1 ERPNext-native fixtures remain the monetary/tax authority. This gate
adds the missing V2 snapshot -> canonical payload mechanics proof for:
- standard 18%,
- inclusive 18%,
- zero-rated,
- exempt,
- mixed standard + zero-rated + exempt.

Official FBR reference acceptance is intentionally not fabricated. Readiness
reference/mapping gaps are bypassed only in-memory after a real submitted invoice
has produced a real hash-verified immutable V2 snapshot.
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
    erpnext_tax_authority,
    fbr_v2_payload_builder,
    fbr_v2_readiness,
    fbr_v2_snapshot_persistence as snapshots,
)


TOLERANCE = 0.02

CASE_PLAN = {
    "standard_18": {
        "rows": [
            {
                "item_code": core.ITEMS["ordinary"],
                "rate": 1000,
            }
        ],
        "expected_net": 1000,
        "expected_tax": 180,
        "expected_grand": 1180,
        "expected_lines": {
            core.ITEMS["ordinary"]: {
                "valueSalesExcludingST": 1000,
                "salesTaxApplicable": 180,
                "totalValues": 1180,
                "discount": 0,
            }
        },
    },
    "inclusive_18": {
        "rows": [
            {
                "item_code": core.ITEMS["inclusive"],
                "rate": 1180,
            }
        ],
        "inclusive": True,
        "expected_net": 1000,
        "expected_tax": 180,
        "expected_grand": 1180,
        "expected_lines": {
            core.ITEMS["inclusive"]: {
                "valueSalesExcludingST": 1000,
                "salesTaxApplicable": 180,
                "totalValues": 1180,
                "discount": 0,
            }
        },
    },
    "zero_rated": {
        "rows": [
            {
                "item_code": core.ITEMS["zero"],
                "rate": 1000,
            }
        ],
        "expected_net": 1000,
        "expected_tax": 0,
        "expected_grand": 1000,
        "expected_lines": {
            core.ITEMS["zero"]: {
                "valueSalesExcludingST": 1000,
                "salesTaxApplicable": 0,
                "totalValues": 1000,
                "discount": 0,
            }
        },
    },
    "exempt": {
        "rows": [
            {
                "item_code": core.ITEMS["exempt"],
                "rate": 1000,
            }
        ],
        "expected_net": 1000,
        "expected_tax": 0,
        "expected_grand": 1000,
        "expected_lines": {
            core.ITEMS["exempt"]: {
                "valueSalesExcludingST": 1000,
                "salesTaxApplicable": 0,
                "totalValues": 1000,
                "discount": 0,
            }
        },
    },
    "mixed_standard_zero_exempt": {
        "rows": [
            {
                "item_code": core.ITEMS["mixed_standard"],
                "rate": 1000,
            },
            {
                "item_code": core.ITEMS["zero"],
                "rate": 1000,
            },
            {
                "item_code": core.ITEMS["exempt"],
                "rate": 1000,
            },
        ],
        "expected_net": 3000,
        "expected_tax": 180,
        "expected_grand": 3180,
        "expected_lines": {
            core.ITEMS["mixed_standard"]: {
                "valueSalesExcludingST": 1000,
                "salesTaxApplicable": 180,
                "totalValues": 1180,
                "discount": 0,
            },
            core.ITEMS["zero"]: {
                "valueSalesExcludingST": 1000,
                "salesTaxApplicable": 0,
                "totalValues": 1000,
                "discount": 0,
            },
            core.ITEMS["exempt"]: {
                "valueSalesExcludingST": 1000,
                "salesTaxApplicable": 0,
                "totalValues": 1000,
                "discount": 0,
            },
        },
    },
}


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing V2 core payload matrix gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def _close(a, b) -> bool:
    return abs(flt(a) - flt(b)) <= TOLERANCE


def _sale_type(item_code: str) -> str:
    if item_code == core.ITEMS["zero"]:
        return "Zero Rated"
    if item_code == core.ITEMS["exempt"]:
        return "Exempt Goods"
    return "Goods at standard rate"


def _rate_description(item_code: str) -> str:
    if item_code in {core.ITEMS["zero"], core.ITEMS["exempt"]}:
        return "0%"
    return "18%"


def _mechanics_readiness(real_readiness: dict) -> dict:
    result = deepcopy(real_readiness)
    snapshot = deepcopy(result.get("native_snapshot_candidate") or {})
    lines = []

    for source_line in snapshot.get("lines") or []:
        line = deepcopy(source_line)
        item_code = str(line.get("item_code") or "")
        mapping = dict(line.get("fbr_mapping") or {})
        mapping.update(
            {
                "name": f"IN-MEMORY-CORE-{item_code}",
                "needs_review": 0,
                "hs_code": mapping.get("hs_code") or "MECHANICS-HS",
                "fbr_uom": mapping.get("fbr_uom") or "Nos",
                "sales_type": _sale_type(item_code),
                "fbr_rate_description": _rate_description(item_code),
                "tax_basis": "Transaction Value",
                "notified_retail_price": 0,
                "sro_schedule_number": "",
                "sro_item_serial_number": "",
            }
        )
        line["fbr_mapping"] = mapping
        lines.append(line)

    snapshot["lines"] = lines

    identity = deepcopy(result.get("identity") or {})
    identity["ready"] = True
    identity["errors"] = []
    identity["snapshot_source"] = "persisted_v2"

    result["identity"] = identity
    result["native_snapshot_candidate"] = snapshot
    result["errors"] = []
    result["payload_input_ready"] = True
    result["mechanics_only_readiness_shim"] = True
    return result


def _payload_by_item(payload: dict) -> dict[str, dict]:
    return {
        str(row.get("productDescription") or ""): dict(row)
        for row in payload.get("items") or []
    }


def _check_payload_lines(
    invoice,
    payload: dict,
    expected_by_item_code: dict[str, dict],
) -> dict:
    payload_rows = list(payload.get("items") or [])
    by_item_code = {}

    invoice_items = list(invoice.get("items") or [])
    if len(invoice_items) != len(payload_rows):
        return {
            "line_count_matches": False,
            "line_values_match": False,
        }

    for invoice_row, payload_row in zip(invoice_items, payload_rows):
        by_item_code[str(invoice_row.item_code)] = dict(payload_row)

    line_values_match = True
    for item_code, expected in expected_by_item_code.items():
        row = by_item_code.get(item_code) or {}
        for fieldname, expected_value in expected.items():
            if not _close(row.get(fieldname), expected_value):
                line_values_match = False

    return {
        "line_count_matches": len(by_item_code) == len(expected_by_item_code),
        "line_values_match": line_values_match,
        "all_payload_discounts_zero": all(
            _close(row.get("discount"), 0)
            for row in by_item_code.values()
        ),
    }


def _run_case(case_name: str, plan: dict) -> tuple[dict, list[dict]]:
    savepoint = f"ledgix_v2_core_{case_name}"
    frappe.db.savepoint(savepoint)

    created = []
    result = None

    try:
        for row in plan["rows"]:
            frappe.db.set_value(
                "Item",
                row["item_code"],
                "disabled",
                0,
                update_modified=False,
            )
        frappe.clear_cache(doctype="Item")

        taxes_and_charges = None
        if plan.get("inclusive"):
            taxes_and_charges = core._new_inclusive_template()
            created.append(
                {
                    "doctype": "Sales Taxes and Charges Template",
                    "name": taxes_and_charges,
                }
            )

        invoice = core._direct_sales_invoice(
            plan["rows"],
            taxes_and_charges=taxes_and_charges,
            remarks=f"FBR V2 Core Payload Matrix {case_name}",
        )
        created.append(
            {
                "doctype": "Sales Invoice",
                "name": invoice.name,
            }
        )

        persisted = snapshots.read_persisted_v2_snapshot(
            invoice.doctype,
            invoice.name,
        )
        real_readiness = fbr_v2_readiness.evaluate_invoice_readiness(
            invoice.doctype,
            invoice.name,
        )
        shim = _mechanics_readiness(real_readiness)

        original_builder_readiness = (
            fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness
        )

        def _shim(reference_doctype, reference_name):
            if (
                reference_doctype != invoice.doctype
                or reference_name != invoice.name
            ):
                frappe.throw("Core payload matrix readiness shim received another invoice.")
            return deepcopy(shim)

        try:
            fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness = _shim
            built = fbr_v2_payload_builder.build_payload_candidate(
                invoice.doctype,
                invoice.name,
            )
        finally:
            fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness = (
                original_builder_readiness
            )

        payload = dict(built.get("payload") or {})
        line_checks = _check_payload_lines(
            invoice,
            payload,
            plan["expected_lines"],
        )

        checks = {
            "submitted": cint(invoice.docstatus) == 1,
            "snapshot_version_2": cint(
                (persisted.get("header") or {}).get("snapshot_version")
            )
            == 2,
            "snapshot_hash_verified": bool(persisted.get("hash_verified")),
            "erpnext_net_matches": _close(
                invoice.net_total,
                plan["expected_net"],
            ),
            "erpnext_tax_matches": _close(
                invoice.total_taxes_and_charges,
                plan["expected_tax"],
            ),
            "erpnext_grand_matches": _close(
                invoice.grand_total,
                plan["expected_grand"],
            ),
            "payload_total_reconciles": bool(
                (built.get("reconciliation") or {}).get("passed")
            ),
            "payload_total_matches_erpnext": _close(
                (built.get("reconciliation") or {}).get(
                    "payload_total_values"
                ),
                plan["expected_grand"],
            ),
            "payload_snapshot_version_2": cint(
                (built.get("source") or {}).get("snapshot_version")
            )
            == 2,
            **line_checks,
        }

        result = {
            "name": case_name,
            "checks": checks,
            "failed_checks": [
                name for name, passed in checks.items() if not passed
            ],
            "erpnext": {
                "net_total": flt(invoice.net_total, 2),
                "tax": flt(invoice.total_taxes_and_charges, 2),
                "grand_total": flt(invoice.grand_total, 2),
            },
            "snapshot": {
                "version": (persisted.get("header") or {}).get(
                    "snapshot_version"
                ),
                "hash": persisted.get("snapshot_hash") or "",
                "hash_verified": bool(persisted.get("hash_verified")),
            },
            "payload": payload,
            "reconciliation": built.get("reconciliation") or {},
            "mechanics_only_mapping_readiness_shim": True,
            "passed": all(checks.values()),
        }
    finally:
        frappe.db.rollback(save_point=savepoint)
        frappe.db.release_savepoint(savepoint)
        frappe.clear_cache(doctype="Item")
        frappe.clear_cache(doctype="Sales Taxes and Charges Template")

    persisted_created = [
        row for row in created
        if frappe.db.exists(row["doctype"], row["name"])
    ]

    if result is None:
        frappe.throw(f"Core payload matrix case {case_name} produced no result.")

    result["post_case_rollback"] = {
        "persisted_records": persisted_created,
        "clean": not persisted_created,
    }
    result["passed"] = bool(result["passed"] and not persisted_created)
    return result, created


def run() -> dict:
    _assert_safe_site()
    core._require_native_foundation()

    if erpnext_tax_authority.current_tax_authority() != "ERPNext Native":
        frappe.throw("Core V2 payload matrix requires ERPNext Native authority.")
    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False.")
    if snapshots.SNAPSHOT_VERSION != 2:
        frappe.throw("Core V2 payload matrix requires snapshot version 2.")

    original_user = frappe.session.user
    original_profile_active = snapshots._profile_active
    original_queue = fbr_native.queue_native_for_fbr
    original_commit = frappe.db.commit

    submit_hook_intercepts = []
    commit_attempts = []
    cases = {}
    all_created = []

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
            "status": "Core Payload Matrix Gate Bypass",
            "reason": "In-memory submit-hook bypass; no FBR network call.",
        }

    def _no_commit(*args, **kwargs):
        commit_attempts.append(True)
        return None

    try:
        frappe.set_user("Administrator")
        snapshots._profile_active = _force_profile_active
        fbr_native.queue_native_for_fbr = _no_network_queue
        frappe.db.commit = _no_commit

        for case_name, plan in CASE_PLAN.items():
            case_result, created = _run_case(case_name, plan)
            cases[case_name] = case_result
            all_created.extend(created)

        failed_cases = [
            name for name, case in cases.items()
            if not case.get("passed")
        ]

        result = {
            "site": frappe.local.site,
            "authority": erpnext_tax_authority.current_tax_authority(),
            "proof_type": "canonical_v2_core_payload_matrix",
            "database_persistence": "PER_CASE_ROLLBACK_CONFIRMED",
            "real_fbr_network_calls": 0,
            "submit_hooks_intercepted_in_memory": len(submit_hook_intercepts),
            "commit_calls_intercepted_in_memory": len(commit_attempts),
            "case_count": len(cases),
            "failed_cases": failed_cases,
            "cases": cases,
            "scope_proven": [
                "standard 18% canonical V2 payload mechanics",
                "inclusive 18% canonical V2 payload mechanics",
                "zero-rated canonical V2 payload mechanics",
                "exempt canonical V2 payload mechanics",
                "mixed standard/zero/exempt canonical V2 payload mechanics",
                "all payload totalValues reconcile to ERPNext grand totals",
                "no ordinary-case commercial discount is fabricated",
                "real snapshot version 2 SHA256 evidence is consumed",
            ],
            "scope_not_proven": [
                "official FBR reference-data acceptance",
                "commercial discount FBR semantics",
                "Sandbox Validate or POST acceptance",
                "Debit/Credit Note semantics",
                "SRO semantics",
                "Production activation",
            ],
            "gate_passed": (
                not failed_cases
                and len(cases) == 5
                and not commit_attempts
            ),
        }

        if not result["gate_passed"]:
            frappe.throw(
                "FBR V2 core payload matrix failed: "
                + frappe.as_json(
                    {
                        "failed_cases": failed_cases,
                        "commit_attempts": len(commit_attempts),
                    }
                )
            )
    finally:
        snapshots._profile_active = original_profile_active
        fbr_native.queue_native_for_fbr = original_queue
        frappe.db.commit = original_commit
        frappe.set_user(original_user)
        frappe.db.rollback()
        frappe.clear_cache(doctype="Item")
        frappe.clear_cache(doctype="Sales Taxes and Charges Template")

    persisted_after = [
        row for row in all_created
        if frappe.db.exists(row["doctype"], row["name"])
    ]
    rollback_clean = not persisted_after
    cutover_still_false = (
        getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
    )

    result["post_rollback"] = {
        "persisted_gate_records": persisted_after,
        "rollback_clean": rollback_clean,
        "v2_network_cutover_still_false": cutover_still_false,
    }
    result["gate_passed"] = bool(
        result["gate_passed"]
        and rollback_clean
        and cutover_still_false
    )

    if not result["gate_passed"]:
        frappe.throw(
            "FBR V2 core payload matrix failed final rollback safety: "
            + frappe.as_json(result["post_rollback"])
        )

    return result
