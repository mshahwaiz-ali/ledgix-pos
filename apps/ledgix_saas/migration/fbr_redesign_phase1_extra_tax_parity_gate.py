from __future__ import annotations

"""Rollback-safe ERPNext-native Extra Tax parity proof.

This gate proves that ERPNext remains the sole monetary authority:
- GST is percentage tax from ERPNext Item Tax Template.
- Extra Tax is a per-unit native ERPNext `On Item Quantity` tax.
- Ledgix only maps the authoritative ERPNext tax account to the FBR Extra Tax
  component for snapshot/translation.
- All temporary masters and transactions are rolled back.
"""

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api import fbr_native
from ledgix_saas.migration import fbr_redesign_phase1_native_core_parity_gate as core
from ledgix_saas.services import erpnext_fbr_snapshot, erpnext_selling, erpnext_tax_authority


ITEM = "LEDGIX-P4-EXTRA"
EXTRA_ACCOUNT = "Ledgix P4 Extra Tax Payable - LEI"

SALE_VALUE = 1000.0
GST_RATE = 18.0
GST_AMOUNT = 180.0
EXTRA_PER_UNIT = 25.0
TOTAL_TAX = 205.0
GRAND_TOTAL = 1205.0


def _close(left, right, tolerance=0.01) -> bool:
    return abs(flt(left) - flt(right)) <= tolerance


def _gl_net_credit(voucher_no: str, account: str) -> float:
    rows = frappe.get_all(
        "GL Entry",
        filters={
            "voucher_type": "Sales Invoice",
            "voucher_no": voucher_no,
            "account": account,
            "is_cancelled": 0,
        },
        fields=["debit", "credit"],
        limit_page_length=0,
    )
    return flt(sum(flt(row.credit) - flt(row.debit) for row in rows), 6)


def _new_price_list() -> tuple[str, str]:
    token = frappe.generate_hash(length=8).upper()
    name = f"LEDGIX Extra Tax Gate {token}"
    currency = frappe.db.get_value("Company", core.COMPANY, "default_currency") or "PKR"

    price_list = frappe.get_doc(
        {
            "doctype": "Price List",
            "price_list_name": name,
            "selling": 1,
            "buying": 0,
            "currency": currency,
        }
    )
    price_list.insert(ignore_permissions=True)

    item_price = frappe.get_doc(
        {
            "doctype": "Item Price",
            "price_list": price_list.name,
            "item_code": ITEM,
            "uom": "Nos",
            "price_list_rate": SALE_VALUE,
            "currency": currency,
            "selling": 1,
        }
    )
    item_price.insert(ignore_permissions=True)
    return price_list.name, item_price.name


def _new_item_tax_template() -> str:
    title = f"Ledgix Extra Tax Item Gate {frappe.generate_hash(length=8).upper()}"
    doc = frappe.get_doc(
        {
            "doctype": "Item Tax Template",
            "title": title,
            "company": core.COMPANY,
            "disabled": 0,
            "taxes": [
                {
                    "tax_type": core.GST_ACCOUNT,
                    "tax_rate": GST_RATE,
                    "not_applicable": 0,
                },
                {
                    "tax_type": EXTRA_ACCOUNT,
                    "tax_rate": EXTRA_PER_UNIT,
                    "not_applicable": 0,
                },
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _new_sales_tax_template() -> str:
    title = f"Ledgix Extra Tax Gate {frappe.generate_hash(length=8).upper()}"
    doc = frappe.get_doc(
        {
            "doctype": "Sales Taxes and Charges Template",
            "title": title,
            "company": core.COMPANY,
            "disabled": 0,
            "is_default": 0,
            "taxes": [
                {
                    "charge_type": "On Net Total",
                    "account_head": core.GST_ACCOUNT,
                    "description": "ERPNext Native GST 18%",
                    "rate": 0,
                    "included_in_print_rate": 0,
                },
                {
                    "charge_type": "On Item Quantity",
                    "account_head": EXTRA_ACCOUNT,
                    "description": "ERPNext Native Extra Tax 25 per unit",
                    "rate": 0,
                    "included_in_print_rate": 0,
                },
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _new_tax_rule(sales_tax_template: str) -> str:
    rule = frappe.get_doc(
        {
            "doctype": "Tax Rule",
            "tax_type": "Sales",
            "sales_tax_template": sales_tax_template,
            "item": ITEM,
            "company": core.COMPANY,
            "priority": 1,
        }
    )
    rule.insert(ignore_permissions=True)
    return rule.name


def _mapping():
    rows = frappe.get_all(
        "Ledgix FBR Item Mapping",
        filters={
            "company": core.COMPANY,
            "erpnext_item": ITEM,
            "active": 1,
        },
        fields=[
            "name",
            "needs_review",
            "tax_basis",
            "notified_retail_price",
            "sales_type",
            "fbr_rate_description",
        ],
        limit_page_length=0,
    )
    if len(rows) != 1:
        frappe.throw(
            f"Expected exactly one active FBR Item Mapping for {ITEM}; found {len(rows)}."
        )
    return rows[0]


def _record_state() -> dict:
    item = frappe.get_doc("Item", ITEM)
    mapping = _mapping()
    return {
        "item_disabled": cint(item.disabled),
        "item_tax_templates": sorted(
            row.item_tax_template for row in item.get("taxes") or []
        ),
        "mapping_name": mapping.name,
        "mapping_needs_review": cint(mapping.needs_review),
    }


def _set_fixture_item_template(item_tax_template: str) -> None:
    item = frappe.get_doc("Item", ITEM)
    item.disabled = 0
    item.set("taxes", [])
    item.append(
        "taxes",
        {
            "item_tax_template": item_tax_template,
        },
    )
    item.save(ignore_permissions=True)
    frappe.clear_cache(doctype="Item")


def _ensure_component_mapping(account: str, component: str) -> tuple[str, bool]:
    rows = frappe.get_all(
        "Ledgix FBR Tax Component Mapping",
        filters={
            "company": core.COMPANY,
            "account_head": account,
            "active": 1,
        },
        fields=["name", "component"],
        limit_page_length=0,
    )

    if len(rows) > 1:
        frappe.throw(f"Multiple active FBR component mappings exist for {account}.")

    if rows:
        if rows[0].component != component:
            frappe.throw(
                f"{account} is already mapped to {rows[0].component}, expected {component}."
            )
        return rows[0].name, False

    doc = frappe.get_doc(
        {
            "doctype": "Ledgix FBR Tax Component Mapping",
            "company": core.COMPANY,
            "account_head": account,
            "component": component,
            "active": 1,
            "notes": "Temporary Phase 1 Extra Tax parity mapping.",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name, True


def _case_evidence(doc) -> dict:
    base = core._evidence(doc)
    return {
        **base,
        "extra_tax_net_credit": _gl_net_credit(doc.name, EXTRA_ACCOUNT),
        "tax_rows_by_account": [
            {
                "idx": row.idx,
                "charge_type": row.charge_type,
                "account_head": row.account_head,
                "rate": flt(row.rate),
                "tax_amount": flt(row.tax_amount),
                "description": row.description or "",
            }
            for row in doc.get("taxes") or []
        ],
    }


def _snapshot_evidence(doc) -> dict:
    result = erpnext_fbr_snapshot.collect_native_tax_breakdown(doc)
    if len(result.get("lines") or []) != 1:
        frappe.throw("Expected one Extra Tax snapshot line.")

    line = result["lines"][0]
    gst_rows = [
        row
        for row in line.get("component_rows") or []
        if row.get("component") == "Sales Tax Applicable"
        and row.get("account_head") == core.GST_ACCOUNT
    ]
    extra_rows = [
        row
        for row in line.get("component_rows") or []
        if row.get("component") == "Extra Tax"
        and row.get("account_head") == EXTRA_ACCOUNT
    ]

    if len(gst_rows) != 1:
        frappe.throw("Expected one GST Sales Tax Applicable snapshot row.")
    if len(extra_rows) != 1:
        frappe.throw("Expected one Extra Tax snapshot row.")

    return {
        "line": line,
        "gst_component": gst_rows[0],
        "extra_component": extra_rows[0],
        "reconciliation": result.get("reconciliation") or {},
    }


def run() -> dict:
    original_user = frappe.session.user
    frappe.set_user("Administrator")

    core._assert_safe_site()
    core._require_native_foundation()

    if not frappe.db.exists("Account", EXTRA_ACCOUNT):
        frappe.throw(f"Missing native Extra Tax Account {EXTRA_ACCOUNT}.")

    original_queue = fbr_native.queue_native_for_fbr
    original_commit = frappe.db.commit

    fbr_intercepts: list[dict] = []
    commit_intercepts: list[dict] = []
    created: list[tuple[str, str]] = []
    result = None

    def _no_network_queue(reference_doctype, reference_name, reason=None):
        fbr_intercepts.append(
            {
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "reason": reason or "",
            }
        )
        return {
            "queued": False,
            "status": "Extra Tax Parity Gate Bypass",
            "reason": "In-memory gate bypass; no FBR network call.",
        }

    def _no_commit(*args, **kwargs):
        commit_intercepts.append(
            {
                "index": len(commit_intercepts) + 1,
                "reason": "Database commit intercepted by rollback-safe gate",
            }
        )
        return None

    before = _record_state()

    try:
        fbr_native.queue_native_for_fbr = _no_network_queue
        frappe.db.commit = _no_commit

        mapping = _mapping()
        if mapping.tax_basis != "Transaction Value":
            frappe.throw("Extra Tax fixture FBR mapping must use Transaction Value.")

        # The migrated mapping is intentionally unapproved. The gate temporarily
        # proves the approved path, then rollback restores needs_review=1.
        frappe.db.set_value(
            "Ledgix FBR Item Mapping",
            mapping.name,
            "needs_review",
            0,
            update_modified=False,
        )

        gst_component_name, gst_component_created = _ensure_component_mapping(
            core.GST_ACCOUNT,
            "Sales Tax Applicable",
        )
        if gst_component_created:
            created.append(("Ledgix FBR Tax Component Mapping", gst_component_name))

        extra_component_name, extra_component_created = _ensure_component_mapping(
            EXTRA_ACCOUNT,
            "Extra Tax",
        )
        if extra_component_created:
            created.append(("Ledgix FBR Tax Component Mapping", extra_component_name))

        price_list, item_price = _new_price_list()
        created.extend(
            [
                ("Price List", price_list),
                ("Item Price", item_price),
            ]
        )

        item_tax_template = _new_item_tax_template()
        created.append(("Item Tax Template", item_tax_template))
        _set_fixture_item_template(item_tax_template)

        sales_tax_template = _new_sales_tax_template()
        created.append(("Sales Taxes and Charges Template", sales_tax_template))

        tax_rule = _new_tax_rule(sales_tax_template)
        created.append(("Tax Rule", tax_rule))

        sale = erpnext_selling.build_sales_invoice(
            customer=core._customer(),
            items=[{"item": ITEM, "qty": 1}],
            company=core.COMPANY,
            selling_price_list=price_list,
            sale_channel="B2B",
            client_sale_id=f"NATIVE-GATE-EXTRA-{frappe.generate_hash(length=10)}",
            allow_rate_override=False,
            update_stock=False,
            checkout_source="Phase 1 Extra Tax Parity Gate",
        )
        sale.insert(ignore_permissions=True)
        sale.submit()
        sale.reload()
        created.append(("Sales Invoice", sale.name))

        sale_ev = _case_evidence(sale)
        sale_snapshot = _snapshot_evidence(frappe.get_doc(sale.as_dict()))

        credit = erpnext_selling.create_sales_return(
            sales_invoice=sale.name,
            return_items=[
                {
                    "sales_invoice_item": sale.items[0].name,
                    "qty": 1,
                }
            ],
            reason="Phase 1 Extra Tax parity rollback test",
            client_return_id=f"NATIVE-GATE-EXTRA-RET-{frappe.generate_hash(length=10)}",
            checkout_source="Phase 1 Extra Tax Parity Gate",
        )
        credit.reload()
        created.append(("Sales Invoice", credit.name))

        return_ev = _case_evidence(credit)
        return_snapshot = _snapshot_evidence(frappe.get_doc(credit.as_dict()))

        sale_gst = sale_snapshot["gst_component"]
        sale_extra = sale_snapshot["extra_component"]
        return_gst = return_snapshot["gst_component"]
        return_extra = return_snapshot["extra_component"]

        sale_extra_rows = [
            row
            for row in sale_ev["tax_rows_by_account"]
            if row["account_head"] == EXTRA_ACCOUNT
        ]
        return_extra_rows = [
            row
            for row in return_ev["tax_rows_by_account"]
            if row["account_head"] == EXTRA_ACCOUNT
        ]

        checks = {
            "sale_submitted": sale.docstatus == 1,
            "sale_native_item_template_resolved": item_tax_template
            in sale_ev["item_tax_templates"],
            "sale_transaction_net_1000": _close(sale_ev["net_total"], SALE_VALUE),
            "sale_gst_180": _close(sale_ev["gst_net_credit"], GST_AMOUNT),
            "sale_extra_tax_row_present": len(sale_extra_rows) == 1,
            "sale_extra_tax_uses_on_item_quantity": len(sale_extra_rows) == 1
            and sale_extra_rows[0]["charge_type"] == "On Item Quantity",
            "sale_extra_tax_amount_25": len(sale_extra_rows) == 1
            and _close(sale_extra_rows[0]["tax_amount"], EXTRA_PER_UNIT),
            "sale_extra_tax_gl_25": _close(
                sale_ev["extra_tax_net_credit"], EXTRA_PER_UNIT
            ),
            "sale_total_tax_205": _close(
                sale_ev["total_taxes_and_charges"], TOTAL_TAX
            ),
            "sale_grand_total_1205": _close(sale_ev["grand_total"], GRAND_TOTAL),
            "sale_gl_balanced": sale_ev["gl_balanced"],
            "sale_no_legacy_tax_rows": not sale_ev["legacy_managed_rows"],
            "sale_snapshot_gst_180": _close(
                sale_gst.get("tax_amount"), GST_AMOUNT
            ),
            "sale_snapshot_extra_tax_25": _close(
                sale_extra.get("tax_amount"), EXTRA_PER_UNIT
            ),
            "sale_snapshot_extra_component_25": _close(
                sale_snapshot["line"]["components"]["extra_tax"], EXTRA_PER_UNIT
            ),
            "sale_snapshot_reconciles": bool(
                sale_snapshot["reconciliation"].get("passed")
            ),
            "return_submitted": credit.docstatus == 1,
            "return_links_source": credit.return_against == sale.name,
            "return_net_minus_1000": _close(return_ev["net_total"], -SALE_VALUE),
            "return_gst_minus_180": _close(
                return_ev["gst_net_credit"], -GST_AMOUNT
            ),
            "return_extra_tax_row_present": len(return_extra_rows) == 1,
            "return_extra_tax_uses_on_item_quantity": len(return_extra_rows) == 1
            and return_extra_rows[0]["charge_type"] == "On Item Quantity",
            "return_extra_tax_amount_minus_25": len(return_extra_rows) == 1
            and _close(return_extra_rows[0]["tax_amount"], -EXTRA_PER_UNIT),
            "return_extra_tax_gl_minus_25": _close(
                return_ev["extra_tax_net_credit"], -EXTRA_PER_UNIT
            ),
            "return_total_tax_minus_205": _close(
                return_ev["total_taxes_and_charges"], -TOTAL_TAX
            ),
            "return_grand_total_minus_1205": _close(
                return_ev["grand_total"], -GRAND_TOTAL
            ),
            "return_gl_balanced": return_ev["gl_balanced"],
            "return_no_legacy_tax_rows": not return_ev["legacy_managed_rows"],
            "return_snapshot_gst_minus_180": _close(
                return_gst.get("tax_amount"), -GST_AMOUNT
            ),
            "return_snapshot_extra_tax_minus_25": _close(
                return_extra.get("tax_amount"), -EXTRA_PER_UNIT
            ),
            "return_snapshot_extra_component_minus_25": _close(
                return_snapshot["line"]["components"]["extra_tax"], -EXTRA_PER_UNIT
            ),
            "return_snapshot_reconciles": bool(
                return_snapshot["reconciliation"].get("passed")
            ),
            "gst_round_trip_zero": _close(
                sale_ev["gst_net_credit"] + return_ev["gst_net_credit"], 0
            ),
            "extra_tax_round_trip_zero": _close(
                sale_ev["extra_tax_net_credit"]
                + return_ev["extra_tax_net_credit"],
                0,
            ),
        }

        case = core._case(
            "extra_tax_on_item_quantity",
            {
                "sale": sale_ev,
                "sale_snapshot": sale_snapshot,
                "return": return_ev,
                "return_snapshot": return_snapshot,
                "native_setup": {
                    "item_tax_template": item_tax_template,
                    "sales_tax_template": sales_tax_template,
                    "tax_rule": tax_rule,
                    "gst_item_tax_rate": GST_RATE,
                    "extra_tax_per_unit": EXTRA_PER_UNIT,
                    "extra_tax_account": EXTRA_ACCOUNT,
                },
                "fbr_mapping": {
                    "name": mapping.name,
                    "needs_review_temporarily_cleared": True,
                    "money_field_source": "ERPNext native Item Tax Template, not FBR Item Mapping",
                },
            },
            checks,
        )

        failed_checks = [name for name, passed in checks.items() if not passed]

        result = {
            "site": frappe.local.site,
            "authority": erpnext_tax_authority.current_tax_authority(),
            "database_persistence": "ROLLBACK_PENDING_VERIFICATION",
            "fbr_network_calls": 0,
            "fbr_submit_hooks_intercepted_in_memory": len(fbr_intercepts),
            "erpnext_commit_calls_intercepted_in_memory": len(commit_intercepts),
            "case_count": 1,
            "failed_cases": [] if case["passed"] else [case["name"]],
            "failed_checks": failed_checks,
            "cases": {case["name"]: case},
            "gate_passed": case["passed"],
            "scope_proven": [
                "Extra Tax fixture commercial value PKR 1,000",
                "ERPNext native GST 18% = PKR 180",
                "ERPNext native On Item Quantity Extra Tax = PKR 25/unit",
                "ERPNext authoritative total tax = PKR 205",
                "ERPNext GST and Extra Tax GL accounts",
                "Native FBR collector maps authoritative Extra Tax amount",
                "Native full return reverses GST and Extra Tax",
                "No [LEDGIX-TAX] monetary rows",
            ],
        }

        if failed_checks:
            frappe.throw(
                "Extra Tax native parity failed: " + ", ".join(failed_checks)
            )

    finally:
        frappe.set_user(original_user)
        fbr_native.queue_native_for_fbr = original_queue
        frappe.db.commit = original_commit
        frappe.db.rollback()

    after = _record_state()

    persisted = [
        {"doctype": doctype, "name": name}
        for doctype, name in created
        if name and frappe.db.exists(doctype, name)
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

    rollback_clean = before == after and not persisted and gl_rows_left == 0

    result["post_rollback"] = {
        "state_before": before,
        "state_after": after,
        "persisted_gate_records": persisted,
        "gate_gl_rows_left": gl_rows_left,
        "rollback_clean": rollback_clean,
    }
    result["database_persistence"] = (
        "ROLLBACK_CONFIRMED"
        if rollback_clean
        else "ROLLBACK_VERIFICATION_FAILED"
    )
    result["gate_passed"] = bool(result["gate_passed"] and rollback_clean)

    if not rollback_clean:
        result["failed_cases"].append("post_rollback_cleanup")
        frappe.throw(
            "Extra Tax accounting checks passed, but rollback verification "
            "found persisted gate state. No cleanup was attempted."
        )

    return result
