"""Rollback-safe LOCAL proof for V2 special-component snapshot -> payload mechanics.

This gate deliberately reuses the already-proven Phase-1 ERPNext fixtures. It
proves mechanics only: ERPNext monetary truth -> immutable V2 snapshot ->
hash-verified persisted evidence -> canonical V2 payload fields. It does not
certify live FBR reference data, legal rates, Sandbox acceptance, or Production.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api import fbr_native, fbr_v2_transport
from ledgix_saas.migration import (
    fbr_redesign_phase1_extra_tax_parity_gate as extra,
    fbr_redesign_phase1_fed_parity_gate as fed,
    fbr_redesign_phase1_further_tax_parity_gate as further,
    fbr_redesign_phase1_native_core_parity_gate as core,
    fbr_redesign_phase1_third_schedule_parity_gate as third,
    fbr_redesign_phase1_withheld_parity_gate as withheld,
)
from ledgix_saas.services import (
    erpnext_selling,
    fbr_v2_payload_builder,
    fbr_v2_snapshot_persistence as snapshots,
)

SAFE_SITE = "ledgix-erpnext.local"
MONEY_TOLERANCE = 0.01
RETURN_REJECTION = (
    "FBR V2 return payload is not activated until Debit/Credit Note semantics "
    "are proven in Sandbox."
)
MECHANICS_WARNING = (
    "LOCAL mechanics-only in-memory readiness shim; this does not prove FBR "
    "reference-data, legal-rate, Sandbox, or Production certification."
)

REQUIRED_PAYLOAD_FIELDS = {
    "fixedNotifiedValueOrRetailPrice",
    "salesTaxApplicable",
    "extraTax",
    "furtherTax",
    "fedPayable",
    "salesTaxWithheldAtSource",
    "totalValues",
}

CASE_SPECS = (
    {
        "name": "third_schedule",
        "module": third,
        "item": third.ITEM,
        "kind": "third",
        "tax_basis": "Notified Retail Price",
        "notified": 1200.0,
        "gst": 216.0,
        "extra": 0.0,
        "further": 0.0,
        "fed": 0.0,
        "withheld": 0.0,
        "total_tax": 216.0,
        "grand_total": 1216.0,
    },
    {
        "name": "extra_tax",
        "module": extra,
        "item": extra.ITEM,
        "kind": "quantity",
        "tax_basis": "Transaction Value",
        "special_account": extra.EXTRA_ACCOUNT,
        "special_component": "Extra Tax",
        "notified": 0.0,
        "gst": 180.0,
        "extra": extra.EXTRA_PER_UNIT,
        "further": 0.0,
        "fed": 0.0,
        "withheld": 0.0,
        "total_tax": 205.0,
        "grand_total": 1205.0,
    },
    {
        "name": "further_tax",
        "module": further,
        "item": further.ITEM,
        "kind": "quantity",
        "tax_basis": "Transaction Value",
        "special_account": further.FURTHER_ACCOUNT,
        "special_component": "Further Tax",
        "notified": 0.0,
        "gst": 180.0,
        "extra": 0.0,
        "further": further.FURTHER_PER_UNIT,
        "fed": 0.0,
        "withheld": 0.0,
        "total_tax": 230.0,
        "grand_total": 1230.0,
    },
    {
        "name": "fed",
        "module": fed,
        "item": fed.ITEM,
        "kind": "quantity",
        "tax_basis": "Transaction Value",
        "special_account": fed.FED_ACCOUNT,
        "special_component": "FED Payable",
        "notified": 0.0,
        "gst": 180.0,
        "extra": 0.0,
        "further": 0.0,
        "fed": fed.FED_PER_UNIT,
        "withheld": 0.0,
        "total_tax": 210.0,
        "grand_total": 1210.0,
    },
    {
        "name": "sales_tax_withheld",
        "module": withheld,
        "item": withheld.ITEM,
        "kind": "quantity",
        "tax_basis": "Transaction Value",
        "special_account": withheld.WITHHELD_ACCOUNT,
        "special_component": "Sales Tax Withheld At Source",
        "notified": 0.0,
        "gst": 180.0,
        "extra": 0.0,
        "further": 0.0,
        "fed": 0.0,
        "withheld": withheld.WITHHELD_PER_UNIT,
        "total_tax": 180.0,
        "grand_total": 1180.0,
    },
)


def _close(left, right, tolerance=MONEY_TOLERANCE) -> bool:
    return abs(flt(left) - flt(right)) <= tolerance


def _assert_safe_site() -> None:
    if frappe.local.site != SAFE_SITE:
        frappe.throw(
            f"This FBR V2 special-component mechanics gate is restricted to {SAFE_SITE}."
        )


def _tax_amount(doc, account: str) -> float:
    total = 0.0
    for row in doc.get("taxes") or []:
        if str(row.get("account_head") or "") != account:
            continue
        amount = row.get("tax_amount_after_discount_amount")
        if amount is None:
            amount = row.get("tax_amount")
        total += flt(amount)
    return flt(total, 2)


def _persisted_snapshot_candidate(reference_doctype: str, reference_name: str) -> dict:
    persisted = snapshots.read_persisted_v2_snapshot(reference_doctype, reference_name)
    header = dict(persisted.get("header") or {})
    line_payloads = persisted.get("lines") or {}

    lines = []
    for item_row, payload in line_payloads.items():
        line = dict((payload or {}).get("line") or {})
        if not line:
            frappe.throw(
                f"FBR V2 immutable snapshot row {item_row} has no native line evidence."
            )
        lines.append(line)

    lines.sort(key=lambda row: cint(row.get("idx")))
    if cint(header.get("line_count")) != len(lines):
        frappe.throw("FBR V2 immutable snapshot line count is inconsistent.")

    return {
        **header,
        "lines": lines,
        "snapshot_hash": persisted.get("snapshot_hash") or "",
        "hash_verified": bool(persisted.get("hash_verified")),
        "snapshot_source": "persisted_v2",
        "database_write": False,
        "fbr_network_call": False,
    }


def _mechanics_readiness(reference_doctype: str, reference_name: str) -> dict:
    """In-memory shim for payload mechanics only; never writes reference evidence."""

    snapshot = _persisted_snapshot_candidate(reference_doctype, reference_name)
    return {
        "errors": [],
        "warnings": [MECHANICS_WARNING],
        "payload_input_ready": True,
        "native_snapshot_candidate": snapshot,
        "identity": {
            "ready": True,
            "errors": [],
            "seller": {
                "ntn_cnic": "LOCAL-MECHANICS-ONLY",
                "business_name": "LOCAL Mechanics Seller",
                "province": "LOCAL",
                "address": "LOCAL mechanics-only identity shim",
            },
            "buyer": {
                "ntn_cnic": "LOCAL-MECHANICS-ONLY",
                "business_name": "LOCAL Mechanics Buyer",
                "province": "LOCAL",
                "address": "LOCAL mechanics-only identity shim",
                "registration_type": "Unregistered",
            },
        },
        "profile": {"mode": "Disabled"},
        "mechanics_only_readiness_shim": True,
    }


def _persisted_line(doc) -> tuple[dict, dict]:
    persisted = snapshots.read_persisted_v2_snapshot(doc.doctype, doc.name)
    if not persisted.get("hash_verified"):
        frappe.throw(f"{doc.doctype} {doc.name} V2 snapshot hash verification failed.")
    if not persisted.get("snapshot_hash"):
        frappe.throw(f"{doc.doctype} {doc.name} V2 snapshot has no SHA256 evidence.")

    line_payloads = persisted.get("lines") or {}
    if len(line_payloads) != 1:
        frappe.throw(
            f"{doc.doctype} {doc.name} gate fixture must contain exactly one invoice line."
        )

    payload = next(iter(line_payloads.values())) or {}
    line = dict(payload.get("line") or {})
    if not line:
        frappe.throw(f"{doc.doctype} {doc.name} persisted V2 line evidence is empty.")
    return persisted, line


def _track(created: list[tuple[str, str]], doctype: str, name: str | None) -> None:
    if name:
        created.append((doctype, str(name)))


def _temporary_approve_mapping(module):
    mapping = module._mapping()
    frappe.db.set_value(
        "Ledgix FBR Item Mapping",
        mapping.name,
        "needs_review",
        0,
        update_modified=False,
    )
    return mapping


def _setup_case(spec: dict, created: list[tuple[str, str]]) -> tuple[object, str]:
    module = spec["module"]
    mapping = _temporary_approve_mapping(module)
    if str(mapping.tax_basis or "") != spec["tax_basis"]:
        frappe.throw(
            f"{spec['name']} fixture mapping must use {spec['tax_basis']}."
        )

    if spec["kind"] == "third":
        module._ensure_item_tax_template()
        component_name, component_created = module._ensure_component_mapping()
        if component_created:
            _track(created, "Ledgix FBR Tax Component Mapping", component_name)

        price_list, item_price = module._new_price_list()
        _track(created, "Price List", price_list)
        _track(created, "Item Price", item_price)

        tax_template = module._new_third_schedule_template()
        _track(created, "Sales Taxes and Charges Template", tax_template)
        tax_rule = module._new_tax_rule(tax_template)
        _track(created, "Tax Rule", tax_rule)
        return mapping, price_list

    gst_component_name, gst_component_created = module._ensure_component_mapping(
        core.GST_ACCOUNT,
        "Sales Tax Applicable",
    )
    if gst_component_created:
        _track(created, "Ledgix FBR Tax Component Mapping", gst_component_name)

    special_component_name, special_component_created = module._ensure_component_mapping(
        spec["special_account"],
        spec["special_component"],
    )
    if special_component_created:
        _track(created, "Ledgix FBR Tax Component Mapping", special_component_name)

    price_list, item_price = module._new_price_list()
    _track(created, "Price List", price_list)
    _track(created, "Item Price", item_price)

    item_tax_template = module._new_item_tax_template()
    _track(created, "Item Tax Template", item_tax_template)
    module._set_fixture_item_template(item_tax_template)

    sales_tax_template = module._new_sales_tax_template()
    _track(created, "Sales Taxes and Charges Template", sales_tax_template)
    tax_rule = module._new_tax_rule(sales_tax_template)
    _track(created, "Tax Rule", tax_rule)
    return mapping, price_list


def _build_sale(spec: dict, price_list: str, created: list[tuple[str, str]]):
    sale = erpnext_selling.build_sales_invoice(
        customer=core._customer(),
        items=[{"item": spec["item"], "qty": 1}],
        company=core.COMPANY,
        selling_price_list=price_list,
        sale_channel="B2B",
        client_sale_id=(
            f"V2-SPECIAL-{spec['name'].upper()}-{frappe.generate_hash(length=10)}"
        ),
        allow_rate_override=False,
        update_stock=False,
        checkout_source="FBR V2 Special Component Payload Mechanics Gate",
    )
    sale.insert(ignore_permissions=True)
    sale.submit()
    sale.reload()
    _track(created, "Sales Invoice", sale.name)
    return sale


def _build_return(spec: dict, sale, created: list[tuple[str, str]]):
    credit = erpnext_selling.create_sales_return(
        sales_invoice=sale.name,
        return_items=[
            {
                "sales_invoice_item": sale.items[0].name,
                "qty": 1,
            }
        ],
        reason="FBR V2 special-component rollback mechanics proof",
        client_return_id=(
            f"V2-SPECIAL-{spec['name'].upper()}-RET-{frappe.generate_hash(length=10)}"
        ),
        checkout_source="FBR V2 Special Component Payload Mechanics Gate",
    )
    credit.reload()
    _track(created, "Sales Invoice", credit.name)
    return credit


def _build_payload(doc) -> tuple[dict, dict]:
    candidate = fbr_v2_payload_builder.build_payload_candidate(doc.doctype, doc.name)
    items = list((candidate.get("payload") or {}).get("items") or [])
    if len(items) != 1:
        frappe.throw("Special-component payload gate expects exactly one payload item.")
    return candidate, items[0]


def _return_rejection(doc) -> dict:
    try:
        fbr_v2_payload_builder.build_payload_candidate(doc.doctype, doc.name)
    except Exception as exc:
        message = str(exc)
        return {
            "rejected": RETURN_REJECTION in message,
            "message": message,
        }
    return {"rejected": False, "message": "Return payload unexpectedly built."}


def _case_result(spec: dict, created: list[tuple[str, str]]) -> dict:
    module = spec["module"]
    mapping, price_list = _setup_case(spec, created)

    sale = _build_sale(spec, price_list, created)
    sale_persisted, sale_line = _persisted_line(sale)
    sale_candidate, sale_payload = _build_payload(sale)
    sale_ev = module._case_evidence(sale)

    credit = _build_return(spec, sale, created)
    return_persisted, return_line = _persisted_line(credit)
    return_ev = module._case_evidence(credit)
    return_rejection = _return_rejection(credit)

    sale_components = dict(sale_line.get("components") or {})
    return_components = dict(return_line.get("components") or {})
    sale_mapping = dict(sale_line.get("fbr_mapping") or {})

    checks = {
        "sale_submitted": cint(sale.docstatus) == 1,
        "sale_erpnext_net_1000": _close(sale.net_total, 1000.0),
        "sale_erpnext_total_tax": _close(
            sale.total_taxes_and_charges, spec["total_tax"]
        ),
        "sale_erpnext_grand_total": _close(sale.grand_total, spec["grand_total"]),
        "sale_erpnext_gl_balanced": bool(sale_ev.get("gl_balanced")),
        "sale_snapshot_hash_verified": bool(sale_persisted.get("hash_verified")),
        "sale_snapshot_has_sha256": bool(sale_persisted.get("snapshot_hash")),
        "sale_snapshot_mapping_temporarily_reviewed": not cint(
            sale_mapping.get("needs_review")
        ),
        "sale_snapshot_net_1000": _close(sale_line.get("net_amount"), 1000.0),
        "sale_snapshot_gst": _close(
            sale_components.get("sales_tax"), spec["gst"]
        ),
        "sale_snapshot_extra": _close(
            sale_components.get("extra_tax"), spec["extra"]
        ),
        "sale_snapshot_further": _close(
            sale_components.get("further_tax"), spec["further"]
        ),
        "sale_snapshot_fed": _close(
            sale_components.get("fed_payable"), spec["fed"]
        ),
        "sale_snapshot_withheld": _close(
            sale_components.get("sales_tax_withheld_at_source"), spec["withheld"]
        ),
        "payload_required_fields_present": REQUIRED_PAYLOAD_FIELDS.issubset(
            set(sale_payload)
        ),
        "payload_notified_value": _close(
            sale_payload.get("fixedNotifiedValueOrRetailPrice"), spec["notified"]
        ),
        "payload_sales_tax_matches_snapshot": _close(
            sale_payload.get("salesTaxApplicable"),
            sale_components.get("sales_tax"),
        ),
        "payload_extra_matches_snapshot": _close(
            sale_payload.get("extraTax"), sale_components.get("extra_tax")
        ),
        "payload_further_matches_snapshot": _close(
            sale_payload.get("furtherTax"), sale_components.get("further_tax")
        ),
        "payload_fed_matches_snapshot": _close(
            sale_payload.get("fedPayable"), sale_components.get("fed_payable")
        ),
        "payload_withheld_matches_snapshot": _close(
            sale_payload.get("salesTaxWithheldAtSource"),
            sale_components.get("sales_tax_withheld_at_source"),
        ),
        "payload_total_values_matches_erpnext_grand_total": _close(
            sale_payload.get("totalValues"), sale.grand_total
        ),
        "payload_reconciliation_passed": bool(
            (sale_candidate.get("reconciliation") or {}).get("passed")
        ),
        "payload_snapshot_hash_matches_persisted": (
            (sale_candidate.get("source") or {}).get("snapshot_hash")
            == sale_persisted.get("snapshot_hash")
        ),
        "return_submitted": cint(credit.docstatus) == 1,
        "return_links_source": credit.return_against == sale.name,
        "return_erpnext_net_reversed": _close(credit.net_total, -1000.0),
        "return_erpnext_grand_total_reversed": _close(
            credit.grand_total, -spec["grand_total"]
        ),
        "return_erpnext_gl_balanced": bool(return_ev.get("gl_balanced")),
        "return_snapshot_hash_verified": bool(return_persisted.get("hash_verified")),
        "return_snapshot_has_sha256": bool(return_persisted.get("snapshot_hash")),
        "return_snapshot_net_reversed": _close(return_line.get("net_amount"), -1000.0),
        "return_snapshot_gst_reversed": _close(
            return_components.get("sales_tax"), -spec["gst"]
        ),
        "return_snapshot_extra_reversed": _close(
            return_components.get("extra_tax"), -spec["extra"]
        ),
        "return_snapshot_further_reversed": _close(
            return_components.get("further_tax"), -spec["further"]
        ),
        "return_snapshot_fed_reversed": _close(
            return_components.get("fed_payable"), -spec["fed"]
        ),
        "return_snapshot_withheld_reversed": _close(
            return_components.get("sales_tax_withheld_at_source"), -spec["withheld"]
        ),
        "return_payload_still_fail_closed": bool(return_rejection["rejected"]),
    }

    if spec["kind"] == "third":
        checks.update(
            {
                "third_mapping_notified_1200": _close(
                    sale_mapping.get("notified_retail_price"), 1200.0
                ),
                "third_erpnext_gst_row_216": _close(
                    _tax_amount(sale, core.GST_ACCOUNT), 216.0
                ),
                "third_payload_total_1216": _close(
                    sale_payload.get("totalValues"), 1216.0
                ),
            }
        )

    if spec["name"] in {"extra_tax", "further_tax", "fed"}:
        expected_special = spec["extra"] or spec["further"] or spec["fed"]
        checks["special_erpnext_tax_row_matches_fixture"] = _close(
            _tax_amount(sale, spec["special_account"]), expected_special
        )

    if spec["name"] == "sales_tax_withheld":
        checks.update(
            {
                "withheld_not_in_financial_tax_rows": _close(
                    _tax_amount(sale, withheld.WITHHELD_ACCOUNT), 0.0
                ),
                "withheld_not_posted_to_gl": _close(
                    sale_ev.get("withheld_gl_net_credit"), 0.0
                ),
                "withheld_only_financial_tax_is_gst": sale_ev.get(
                    "financial_tax_accounts"
                )
                == [core.GST_ACCOUNT],
                "withheld_payload_40": _close(
                    sale_payload.get("salesTaxWithheldAtSource"), 40.0
                ),
                "withheld_payload_total_1180": _close(
                    sale_payload.get("totalValues"), 1180.0
                ),
                "withheld_payload_total_not_1220": not _close(
                    sale_payload.get("totalValues"), 1220.0
                ),
                "withheld_return_not_posted_to_gl": _close(
                    return_ev.get("withheld_gl_net_credit"), 0.0
                ),
            }
        )

    failed = [name for name, passed in checks.items() if not passed]
    return {
        "name": spec["name"],
        "mapping": mapping.name,
        "sale": sale.name,
        "return": credit.name,
        "sale_snapshot_hash": sale_persisted.get("snapshot_hash"),
        "return_snapshot_hash": return_persisted.get("snapshot_hash"),
        "payload_item": sale_payload,
        "payload_reconciliation": sale_candidate.get("reconciliation"),
        "return_rejection": return_rejection,
        "checks": checks,
        "failed_checks": failed,
        "passed": not failed,
    }


def _record_fixture_states() -> dict:
    return {spec["name"]: spec["module"]._record_state() for spec in CASE_SPECS}


def run() -> dict:
    _assert_safe_site()
    core._require_native_foundation()

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False for this LOCAL gate.")

    original_user = frappe.session.user
    original_profile_active = snapshots._profile_active
    original_queue = fbr_native.queue_native_for_fbr
    original_commit = frappe.db.commit
    original_readiness = (
        fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness
    )
    original_validate = fbr_v2_transport.validate_invoice
    original_post = fbr_v2_transport.post_invoice

    queue_intercepts: list[dict] = []
    network_attempts: list[dict] = []
    commit_intercepts: list[int] = []
    created: list[tuple[str, str]] = []
    result = None

    def _force_profile_active(company: str) -> bool:
        return str(company or "") == str(core.COMPANY)

    def _no_network_queue(reference_doctype, reference_name, reason=None):
        queue_intercepts.append(
            {
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "reason": reason or "",
            }
        )
        return {
            "queued": False,
            "status": "V2 Special Component Gate Bypass",
            "reason": "LOCAL in-memory queue bypass; no FBR network call.",
        }

    def _block_transport(*args, **kwargs):
        network_attempts.append({"args": len(args), "kwargs": sorted(kwargs)})
        frappe.throw("Real FBR transport is blocked by the LOCAL special-component gate.")

    def _no_commit(*args, **kwargs):
        commit_intercepts.append(len(commit_intercepts) + 1)
        return None

    frappe.set_user("Administrator")
    before_states = _record_fixture_states()

    try:
        snapshots._profile_active = _force_profile_active
        fbr_native.queue_native_for_fbr = _no_network_queue
        frappe.db.commit = _no_commit
        fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness = (
            _mechanics_readiness
        )
        fbr_v2_transport.validate_invoice = _block_transport
        fbr_v2_transport.post_invoice = _block_transport

        cases = {}
        failed_cases = []
        failed_checks = {}
        case_isolation = {}

        # Each Phase-1 fixture was originally proven in its own rollback-safe
        # transaction. Reproduce that isolation here so one temporary Tax Rule,
        # Item Tax Template, or master cannot influence the next component case.
        for index, spec in enumerate(CASE_SPECS, start=1):
            savepoint = f"v2_special_case_{index}"
            case_created_start = len(created)
            state_before_case = _record_fixture_states()

            frappe.db.savepoint(savepoint)
            try:
                case = _case_result(spec, created)
            finally:
                frappe.db.rollback(save_point=savepoint)
                frappe.db.release_savepoint(savepoint)

                # The database rollback removes temporary masters. Clear
                # document caches as well so the next case resolves only its
                # own ERPNext-native Item/Tax Rule configuration.
                for doctype in (
                    "Item",
                    "Item Tax Template",
                    "Sales Taxes and Charges Template",
                    "Tax Rule",
                ):
                    frappe.clear_cache(doctype=doctype)

            state_after_case = _record_fixture_states()
            case_created = created[case_created_start:]
            persisted_after_case = [
                {"doctype": doctype, "name": name}
                for doctype, name in case_created
                if frappe.db.exists(doctype, name)
            ]
            per_case_rollback_clean = (
                state_before_case == state_after_case and not persisted_after_case
            )

            case["post_case_rollback"] = {
                "fixture_states_restored": state_before_case == state_after_case,
                "persisted_gate_records": persisted_after_case,
                "per_case_rollback_clean": per_case_rollback_clean,
            }
            case.setdefault("checks", {})["per_case_rollback_clean"] = (
                per_case_rollback_clean
            )
            case["failed_checks"] = [
                name for name, passed in case["checks"].items() if not passed
            ]
            case["passed"] = not case["failed_checks"]

            case_isolation[spec["name"]] = case["post_case_rollback"]
            cases[spec["name"]] = case
            if not case["passed"]:
                failed_cases.append(spec["name"])
                failed_checks[spec["name"]] = case["failed_checks"]

        result = {
            "site": frappe.local.site,
            "authority": "ERPNext Native",
            "readiness_shim": "IN_MEMORY_LOCAL_PAYLOAD_MECHANICS_ONLY",
            "readiness_warning": MECHANICS_WARNING,
            "database_persistence": "ROLLBACK_PENDING_VERIFICATION",
            "real_fbr_network_calls": len(network_attempts),
            "fbr_queue_hooks_intercepted_in_memory": len(queue_intercepts),
            "erpnext_commit_calls_intercepted_in_memory": len(commit_intercepts),
            "v2_network_cutover_active": bool(
                getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None)
            ),
            "case_count": len(cases),
            "failed_cases": failed_cases,
            "failed_checks": failed_checks,
            "cases": cases,
            "case_isolation": case_isolation,
            "gate_passed": not failed_cases and not network_attempts,
            "scope_proven": [
                "ERPNext remains the monetary/accounting authority",
                "real immutable V2 snapshots persist inside the rollback transaction",
                "persisted V2 header/line SHA256 evidence is hash-verified",
                "Third Schedule notified value 1200 and GST 216 reach canonical payload mechanics",
                "Extra Tax, Further Tax, and FED payload fields equal persisted ERPNext components",
                "Sales Tax Withheld 40 is preserved as non-posting FBR evidence",
                "Sales Tax Withheld does not increase totalValues beyond ERPNext grand total 1180",
                "all special-component totalValues reconcile to immutable ERPNext grand total",
                "return snapshots preserve reversal evidence while V2 return payload stays fail-closed",
            ],
            "scope_not_proven": [
                "official FBR reference-data acceptance",
                "legal production certification of fixture rates or amounts",
                "Sandbox Validate or POST acceptance",
                "Debit/Credit Note payload semantics",
                "SRO payload semantics",
                "Production activation",
            ],
        }
    finally:
        snapshots._profile_active = original_profile_active
        fbr_native.queue_native_for_fbr = original_queue
        frappe.db.commit = original_commit
        fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness = (
            original_readiness
        )
        fbr_v2_transport.validate_invoice = original_validate
        fbr_v2_transport.post_invoice = original_post
        frappe.set_user(original_user)
        frappe.db.rollback()

    after_states = _record_fixture_states()
    persisted_created = [
        {"doctype": doctype, "name": name}
        for doctype, name in created
        if frappe.db.exists(doctype, name)
    ]
    rollback_clean = before_states == after_states and not persisted_created
    cutover_still_false = (
        getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
    )

    result["post_rollback"] = {
        "fixture_states_restored": before_states == after_states,
        "persisted_gate_records": persisted_created,
        "rollback_clean": rollback_clean,
        "v2_network_cutover_still_false": cutover_still_false,
    }
    result["database_persistence"] = "ROLLED_BACK_CLEAN" if rollback_clean else "FAILED"
    result["gate_passed"] = bool(
        result["gate_passed"] and rollback_clean and cutover_still_false
    )

    if not result["gate_passed"]:
        frappe.throw(
            "FBR V2 special-component mechanics gate failed: "
            + frappe.as_json(
                {
                    "failed_checks": result.get("failed_checks"),
                    "post_rollback": result.get("post_rollback"),
                    "real_fbr_network_calls": result.get("real_fbr_network_calls"),
                }
            )
        )

    return result
