from __future__ import annotations

"""Rollback-safe ERPNext-native Third Schedule / notified-value parity proof."""

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api import fbr_native
from ledgix_saas.migration import fbr_redesign_phase1_native_core_parity_gate as core
from ledgix_saas.services import (
    erpnext_fbr_snapshot,
    erpnext_selling,
    erpnext_tax_authority,
    erpnext_taxable_base,
)

ITEM = "LEDGIX-P4-THIRD"
EXPECTED_RATE = 1000.0
EXPECTED_NOTIFIED = 1200.0
EXPECTED_TAX = 216.0


def _new_price_list() -> tuple[str, str]:
    token = frappe.generate_hash(length=8).upper()
    name = f"LEDGIX Third Schedule Gate {token}"
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
    price = frappe.get_doc(
        {
            "doctype": "Item Price",
            "price_list": price_list.name,
            "item_code": ITEM,
            "uom": "Nos",
            "price_list_rate": EXPECTED_RATE,
            "currency": currency,
            "selling": 1,
        }
    )
    price.insert(ignore_permissions=True)
    return price_list.name, price.name


def _new_third_schedule_template() -> str:
    title = f"Ledgix Third Schedule Gate {frappe.generate_hash(length=8).upper()}"
    doc = frappe.get_doc(
        {
            "doctype": "Sales Taxes and Charges Template",
            "title": title,
            "company": core.COMPANY,
            "disabled": 0,
            "is_default": 0,
            "taxes": [
                {
                    "charge_type": erpnext_taxable_base.CHARGE_TYPE,
                    "account_head": core.GST_ACCOUNT,
                    "description": "ERPNext Native Third Schedule GST",
                    "rate": 18,
                    "included_in_print_rate": 0,
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _new_tax_rule(template: str) -> str:
    rule = frappe.get_doc(
        {
            "doctype": "Tax Rule",
            "tax_type": "Sales",
            "sales_tax_template": template,
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
        filters={"company": core.COMPANY, "erpnext_item": ITEM, "active": 1},
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
        frappe.throw(f"Expected exactly one active FBR Item Mapping for {ITEM}; found {len(rows)}.")
    row = rows[0]
    if row.tax_basis != "Notified Retail Price":
        frappe.throw("Third Schedule fixture mapping does not use Notified Retail Price.")
    if not core._close(row.notified_retail_price, EXPECTED_NOTIFIED):
        frappe.throw(f"Third Schedule fixture notified value must be {EXPECTED_NOTIFIED}.")
    return row


def _ensure_item_tax_template() -> None:
    item = frappe.get_doc("Item", ITEM)
    item.disabled = 0
    if not any(row.item_tax_template == core.STANDARD_TEMPLATE for row in item.get("taxes") or []):
        item.append("taxes", {"item_tax_template": core.STANDARD_TEMPLATE})
    item.save(ignore_permissions=True)
    frappe.clear_cache(doctype="Item")


def _ensure_component_mapping() -> tuple[str, bool]:
    rows = frappe.get_all(
        "Ledgix FBR Tax Component Mapping",
        filters={"company": core.COMPANY, "account_head": core.GST_ACCOUNT, "active": 1},
        fields=["name", "component"],
        limit_page_length=0,
    )
    if len(rows) > 1:
        frappe.throw("Multiple active FBR component mappings exist for GST - LEI.")
    if rows:
        if rows[0].component != "Sales Tax Applicable":
            frappe.throw("GST - LEI active FBR component mapping is not Sales Tax Applicable.")
        return rows[0].name, False
    doc = frappe.get_doc(
        {
            "doctype": "Ledgix FBR Tax Component Mapping",
            "company": core.COMPANY,
            "account_head": core.GST_ACCOUNT,
            "component": "Sales Tax Applicable",
            "active": 1,
            "notes": "Temporary Phase 1 Third Schedule parity mapping.",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name, True


def _snapshot_evidence(doc) -> dict:
    result = erpnext_fbr_snapshot.collect_native_tax_breakdown(doc)
    if len(result.get("lines") or []) != 1:
        frappe.throw("Expected one Third Schedule snapshot line.")
    line = result["lines"][0]
    sales_rows = [
        row
        for row in line.get("component_rows") or []
        if row.get("component") == "Sales Tax Applicable" and row.get("account_head") == core.GST_ACCOUNT
    ]
    if len(sales_rows) != 1:
        frappe.throw("Expected one native GST Sales Tax Applicable component row.")
    return {
        "line": line,
        "sales_tax_component": sales_rows[0],
        "reconciliation": result.get("reconciliation") or {},
    }


def _case_evidence(doc) -> dict:
    ev = core._evidence(doc)
    item = doc.items[0]
    return {
        **ev,
        "tax_basis": item.get("custom_ledgix_fbr_tax_basis") or "",
        "notified_retail_price": flt(item.get("custom_ledgix_fbr_notified_retail_price"), 2),
        "tax_charge_types": [row.get("charge_type") or "" for row in doc.get("taxes") or []],
    }


def _record_state() -> dict:
    mapping = _mapping()
    item = frappe.get_doc("Item", ITEM)
    return {
        "item_disabled": cint(item.disabled),
        "item_tax_templates": sorted(row.item_tax_template for row in item.get("taxes") or []),
        "mapping_name": mapping.name,
        "mapping_needs_review": cint(mapping.needs_review),
    }


def run() -> dict:
    core._assert_safe_site()
    frappe.set_user("Administrator")
    core._require_native_foundation()

    charge_meta = frappe.get_meta("Sales Taxes and Charges", cached=False).get_field("charge_type")
    if erpnext_taxable_base.CHARGE_TYPE not in str(charge_meta.options or "").splitlines():
        frappe.throw(
            "Third Schedule charge type is not registered. Run "
            "ledgix_saas.setup.erpnext_extensions.sync_sales_tax_charge_type_extension first."
        )

    hooks = frappe.get_hooks("erpnext_taxable_base_resolvers") or {}
    if not hooks.get(erpnext_taxable_base.CHARGE_TYPE):
        frappe.throw("ERPNext taxable-base resolver hook is not registered.")

    original_user = frappe.session.user
    original_queue = fbr_native.queue_native_for_fbr
    original_commit = frappe.db.commit
    fbr_intercepts = []
    commit_intercepts = []

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
            "status": "Third Schedule Parity Gate Bypass",
            "reason": "In-memory gate bypass; no FBR network call.",
        }

    def _no_commit(*args, **kwargs):
        commit_intercepts.append(
            {"index": len(commit_intercepts) + 1, "reason": "Database commit intercepted by rollback-safe gate"}
        )
        return None

    before = _record_state()
    created = []
    result = None

    try:
        fbr_native.queue_native_for_fbr = _no_network_queue
        frappe.db.commit = _no_commit

        mapping = _mapping()
        frappe.db.set_value(
            "Ledgix FBR Item Mapping",
            mapping.name,
            "needs_review",
            0,
            update_modified=False,
        )

        _ensure_item_tax_template()
        component_name, component_created = _ensure_component_mapping()
        if component_created:
            created.append(("Ledgix FBR Tax Component Mapping", component_name))

        price_list, item_price = _new_price_list()
        created.extend([("Price List", price_list), ("Item Price", item_price)])

        tax_template = _new_third_schedule_template()
        created.append(("Sales Taxes and Charges Template", tax_template))
        tax_rule = _new_tax_rule(tax_template)
        created.append(("Tax Rule", tax_rule))

        invoice = erpnext_selling.build_sales_invoice(
            customer=core._customer(),
            items=[{"item": ITEM, "qty": 1}],
            company=core.COMPANY,
            selling_price_list=price_list,
            sale_channel="B2B",
            client_sale_id=f"NATIVE-GATE-THIRD-{frappe.generate_hash(length=10)}",
            allow_rate_override=False,
            update_stock=False,
            checkout_source="Phase 1 Third Schedule Parity Gate",
        )
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        invoice.reload()
        created.append(("Sales Invoice", invoice.name))

        sale_ev = _case_evidence(invoice)
        sale_snapshot = _snapshot_evidence(frappe.get_doc(invoice.as_dict()))

        credit = erpnext_selling.create_sales_return(
            sales_invoice=invoice.name,
            return_items=[{"sales_invoice_item": invoice.items[0].name, "qty": 1}],
            reason="Phase 1 Third Schedule parity rollback test",
            client_return_id=f"NATIVE-GATE-THIRD-RET-{frappe.generate_hash(length=10)}",
            checkout_source="Phase 1 Third Schedule Parity Gate",
        )
        credit.reload()
        created.append(("Sales Invoice", credit.name))

        return_ev = _case_evidence(credit)
        return_snapshot = _snapshot_evidence(frappe.get_doc(credit.as_dict()))

        sale_component = sale_snapshot["sales_tax_component"]
        return_component = return_snapshot["sales_tax_component"]

        checks = {
            "sale_submitted": invoice.docstatus == 1,
            "sale_uses_native_item_tax_template": core.STANDARD_TEMPLATE in sale_ev["item_tax_templates"],
            "sale_uses_custom_native_charge_type": erpnext_taxable_base.CHARGE_TYPE in sale_ev["tax_charge_types"],
            "sale_transaction_net_1000": core._close(sale_ev["net_total"], EXPECTED_RATE),
            "sale_notified_base_stamped_1200": sale_ev["tax_basis"] == "Notified Retail Price" and core._close(sale_ev["notified_retail_price"], EXPECTED_NOTIFIED),
            "sale_erpnext_tax_216": core._close(sale_ev["total_taxes_and_charges"], EXPECTED_TAX),
            "sale_grand_total_1216": core._close(sale_ev["grand_total"], EXPECTED_RATE + EXPECTED_TAX),
            "sale_gst_gl_216": core._close(sale_ev["gst_net_credit"], EXPECTED_TAX),
            "sale_gl_balanced": sale_ev["gl_balanced"],
            "sale_no_legacy_tax_rows": not sale_ev["legacy_managed_rows"],
            "sale_snapshot_resolver_base_1200": core._close(sale_component.get("taxable_base"), EXPECTED_NOTIFIED),
            "sale_snapshot_erpnext_tax_216": core._close(sale_component.get("tax_amount"), EXPECTED_TAX),
            "sale_snapshot_reconciles": bool(sale_snapshot["reconciliation"].get("passed")),
            "return_submitted": credit.docstatus == 1,
            "return_links_source": credit.return_against == invoice.name,
            "return_preserves_source_notified_base": return_ev["tax_basis"] == "Notified Retail Price" and core._close(return_ev["notified_retail_price"], EXPECTED_NOTIFIED),
            "return_net_minus_1000": core._close(return_ev["net_total"], -EXPECTED_RATE),
            "return_tax_minus_216": core._close(return_ev["total_taxes_and_charges"], -EXPECTED_TAX),
            "return_grand_minus_1216": core._close(return_ev["grand_total"], -(EXPECTED_RATE + EXPECTED_TAX)),
            "return_gst_gl_reversed": core._close(return_ev["gst_net_credit"], -EXPECTED_TAX),
            "return_gl_balanced": return_ev["gl_balanced"],
            "return_no_legacy_tax_rows": not return_ev["legacy_managed_rows"],
            "return_snapshot_base_minus_1200": core._close(return_component.get("taxable_base"), -EXPECTED_NOTIFIED),
            "return_snapshot_tax_minus_216": core._close(return_component.get("tax_amount"), -EXPECTED_TAX),
            "return_snapshot_reconciles": bool(return_snapshot["reconciliation"].get("passed")),
            "gst_round_trip_zero": core._close(sale_ev["gst_net_credit"] + return_ev["gst_net_credit"], 0),
        }

        case = core._case(
            "third_schedule_notified_retail_price",
            {
                "sale": sale_ev,
                "sale_snapshot": sale_snapshot,
                "return": return_ev,
                "return_snapshot": return_snapshot,
                "fbr_mapping": {
                    "name": mapping.name,
                    "notified_retail_price": flt(mapping.notified_retail_price, 2),
                    "needs_review_temporarily_cleared": True,
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
                "Third Schedule transaction value remains PKR 1,000",
                "Approved notified retail base PKR 1,200 is stamped as legal input",
                "ERPNext applies native 18% rate to resolver base",
                "ERPNext authoritative GST is PKR 216",
                "ERPNext GST GL uses GST - LEI",
                "Native FBR collector captures taxable base PKR 1,200 and tax PKR 216",
                "Full native return preserves original notified base and reverses PKR 216 GST",
                "No [LEDGIX-TAX] monetary rows",
            ],
        }
        if failed_checks:
            frappe.throw("Third Schedule native parity failed: " + ", ".join(failed_checks))
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
    invoice_names = [name for doctype, name in created if doctype == "Sales Invoice"]
    gl_rows_left = 0
    if invoice_names:
        gl_rows_left = frappe.db.count(
            "GL Entry",
            {"voucher_type": "Sales Invoice", "voucher_no": ["in", invoice_names]},
        )
    rollback_clean = before == after and not persisted and gl_rows_left == 0
    result["post_rollback"] = {
        "state_before": before,
        "state_after": after,
        "persisted_gate_records": persisted,
        "gate_gl_rows_left": gl_rows_left,
        "rollback_clean": rollback_clean,
    }
    result["database_persistence"] = "ROLLBACK_CONFIRMED" if rollback_clean else "ROLLBACK_VERIFICATION_FAILED"
    result["gate_passed"] = bool(result["gate_passed"] and rollback_clean)
    if not rollback_clean:
        result["failed_cases"].append("post_rollback_cleanup")
        frappe.throw(
            "Third Schedule accounting checks passed, but rollback verification found persisted gate state. No cleanup was attempted."
        )
    return result
