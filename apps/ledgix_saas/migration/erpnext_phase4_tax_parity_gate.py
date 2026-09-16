from __future__ import annotations

import json
from dataclasses import dataclass

import frappe
from frappe.utils import cint, flt, nowdate

from ledgix_saas.migration.erpnext_integration_bootstrap import CURRENCY, INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.setup import erpnext_tax_foundation as tax_foundation

GATE_VERSION = "P4-V1"
TEST_CUSTOMER = "Ledgix Phase 4 Tax Customer"
STANDARD_CATEGORY = "Ledgix P4 Standard 18"
ZERO_CATEGORY = "Ledgix P4 Zero Rated"
EXEMPT_CATEGORY = "Ledgix P4 Exempt"

ITEMS = {
    "ordinary": "LEDGIX-P4-ORDINARY",
    "inclusive": "LEDGIX-P4-INCLUSIVE",
    "zero": "LEDGIX-P4-ZERO",
    "exempt": "LEDGIX-P4-EXEMPT",
    "third_schedule": "LEDGIX-P4-THIRD",
    "further_tax": "LEDGIX-P4-FURTHER",
    "extra_tax": "LEDGIX-P4-EXTRA",
    "fed": "LEDGIX-P4-FED",
    "withheld": "LEDGIX-P4-WITHHELD",
    "mixed_a": "LEDGIX-P4-MIX-A",
    "mixed_b": "LEDGIX-P4-MIX-B",
    "return": "LEDGIX-P4-RETURN",
    "price_credit": "LEDGIX-P4-PRICE-CREDIT",
}

ACCOUNT_NAMES = {
    "sales_tax": "Ledgix P4 Sales Tax Payable",
    "extra_tax": "Ledgix P4 Extra Tax Payable",
    "further_tax": "Ledgix P4 Further Tax Payable",
    "fed_payable": "Ledgix P4 FED Payable",
    "sales_tax_withheld_at_source": "Ledgix P4 Sales Tax Withheld",
}


@dataclass(frozen=True)
class ProfileSpec:
    category: str
    tax_basis: str = "Transaction Value"
    notified_retail_price: float = 0.0
    withheld_per_unit: float = 0.0
    extra_per_unit: float = 0.0
    further_per_unit: float = 0.0
    fed_per_unit: float = 0.0
    hs_code: str = "0101.21"
    sales_type: str = "Goods at standard rate"
    scenario_id: str = "SN001"


def _money(value) -> float:
    return flt(value, 2)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 4 tax parity gate on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing; run the integration bootstrap first.")


def _ensure_customer() -> str:
    if frappe.db.exists("Customer", TEST_CUSTOMER):
        return TEST_CUSTOMER
    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": TEST_CUSTOMER,
            "customer_type": "Individual",
            "customer_group": "All Customer Groups",
            "territory": "All Territories",
            "custom_ledgix_buyer_registration_type": "Unregistered",
            "custom_ledgix_buyer_province": "Sindh",
            "custom_ledgix_buyer_fbr_address": "Phase 4 Integration Address",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item(item_code: str) -> str:
    if frappe.db.exists("Item", item_code):
        doc = frappe.get_doc("Item", item_code)
        if cint(doc.is_stock_item):
            frappe.throw(f"Safety check failed: Phase 4 item {item_code} must remain non-stock.")
        return doc.name
    doc = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_code.replace("LEDGIX-P4-", "Phase 4 ").replace("-", " ").title(),
            "description": f"Dedicated Phase 4 ERPNext tax parity item: {item_code}",
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_category(name: str, *, rate: float, exempt: bool = False, zero: bool = False) -> str:
    if frappe.db.exists("Ledgix Tax Category", name):
        doc = frappe.get_doc("Ledgix Tax Category", name)
    else:
        doc = frappe.get_doc({"doctype": "Ledgix Tax Category", "category_name": name})
    values = {
        "tax_type": "Sales Tax",
        "default_rate": rate,
        "active": 1,
        "is_exempt": 1 if exempt else 0,
        "is_zero_rated": 1 if zero else 0,
        "description": f"Phase 4 ERPNext tax parity category: {name}",
    }
    for fieldname, value in values.items():
        doc.set(fieldname, value)
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_profile(item_code: str, spec: ProfileSpec) -> str:
    name = frappe.db.get_value(
        "Ledgix Item Tax Profile",
        {"erpnext_item": item_code},
        "name",
        order_by="modified desc",
    )
    if name:
        doc = frappe.get_doc("Ledgix Item Tax Profile", name)
    else:
        doc = frappe.get_doc({"doctype": "Ledgix Item Tax Profile", "erpnext_item": item_code})

    values = {
        "erpnext_item": item_code,
        "item": None,
        "tax_category": spec.category,
        "taxable": 0 if spec.category in {ZERO_CATEGORY, EXEMPT_CATEGORY} else 1,
        "active": 1,
        "needs_review": 0,
        "tax_basis": spec.tax_basis,
        "notified_retail_price": spec.notified_retail_price,
        "hs_code": spec.hs_code,
        "uom_for_fbr": "Numbers, pieces, units",
        "sales_type": spec.sales_type,
        "fbr_rate_description": "18%" if spec.category == STANDARD_CATEGORY else "0%",
        "scenario_id": spec.scenario_id,
        "sro_schedule_number": "",
        "sro_item_serial_number": "",
        "sales_tax_withheld_at_source_per_unit": spec.withheld_per_unit,
        "extra_tax_per_unit": spec.extra_per_unit,
        "further_tax_per_unit": spec.further_per_unit,
        "fed_payable_per_unit": spec.fed_per_unit,
    }
    for fieldname, value in values.items():
        doc.set(fieldname, value)
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _find_tax_parent() -> str:
    rows = frappe.get_all(
        "Account",
        filters={"company": TEST_COMPANY, "is_group": 1, "disabled": 0},
        fields=["name", "account_name", "root_type", "lft"],
        order_by="lft asc",
    )
    for row in rows:
        if "duties and taxes" in str(row.account_name or "").lower():
            return row.name
    for row in rows:
        if row.root_type == "Liability" and row.account_name not in {"Liabilities", "Current Liabilities"}:
            return row.name
    for row in rows:
        if row.root_type == "Liability":
            return row.name
    frappe.throw("Could not find a Liability group account for Phase 4 tax accounts.")


def _ensure_account(account_name: str, parent: str) -> str:
    existing = frappe.db.get_value(
        "Account",
        {"company": TEST_COMPANY, "account_name": account_name},
        "name",
    )
    if existing:
        return existing
    doc = frappe.get_doc(
        {
            "doctype": "Account",
            "account_name": account_name,
            "company": TEST_COMPANY,
            "parent_account": parent,
            "is_group": 0,
            "account_type": "Tax",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_tax_accounts() -> dict:
    tax_foundation.sync_all()
    parent = _find_tax_parent()
    accounts = {component: _ensure_account(name, parent) for component, name in ACCOUNT_NAMES.items()}
    updates = {
        tax_foundation.COMPONENT_ACCOUNT_FIELDS[component]: account
        for component, account in accounts.items()
    }
    frappe.db.set_value("Company", TEST_COMPANY, updates, update_modified=False)
    frappe.clear_cache(doctype="Company")
    return accounts


def _ensure_fixture_data() -> dict:
    categories = {
        "standard": _ensure_category(STANDARD_CATEGORY, rate=18),
        "zero": _ensure_category(ZERO_CATEGORY, rate=0, zero=True),
        "exempt": _ensure_category(EXEMPT_CATEGORY, rate=0, exempt=True),
    }
    for item_code in ITEMS.values():
        _ensure_item(item_code)

    specs = {
        "ordinary": ProfileSpec(STANDARD_CATEGORY),
        "inclusive": ProfileSpec(STANDARD_CATEGORY),
        "zero": ProfileSpec(ZERO_CATEGORY, sales_type="Goods at zero rate"),
        "exempt": ProfileSpec(EXEMPT_CATEGORY, sales_type="Exempt goods"),
        "third_schedule": ProfileSpec(
            STANDARD_CATEGORY,
            tax_basis="Notified Retail Price",
            notified_retail_price=1200,
            sales_type="Third Schedule Goods",
        ),
        "further_tax": ProfileSpec(STANDARD_CATEGORY, further_per_unit=50),
        "extra_tax": ProfileSpec(STANDARD_CATEGORY, extra_per_unit=25),
        "fed": ProfileSpec(STANDARD_CATEGORY, fed_per_unit=30),
        "withheld": ProfileSpec(STANDARD_CATEGORY, withheld_per_unit=40),
        "mixed_a": ProfileSpec(STANDARD_CATEGORY),
        "mixed_b": ProfileSpec(
            STANDARD_CATEGORY,
            tax_basis="Notified Retail Price",
            notified_retail_price=800,
            withheld_per_unit=7,
            extra_per_unit=20,
            further_per_unit=10,
            fed_per_unit=5,
            sales_type="Third Schedule Goods",
        ),
        "return": ProfileSpec(STANDARD_CATEGORY),
        "price_credit": ProfileSpec(STANDARD_CATEGORY),
    }
    profiles = {key: _ensure_profile(ITEMS[key], spec) for key, spec in specs.items()}
    return {"categories": categories, "profiles": profiles}


def _marker(name: str) -> str:
    return f"LEDGIX-ERPNEXT-{GATE_VERSION}-{name.upper().replace('_', '-')}"


def _submitted_invoice(marker: str):
    name = frappe.db.get_value(
        "Sales Invoice",
        {"company": TEST_COMPANY, "remarks": marker, "docstatus": 1},
        "name",
    )
    return frappe.get_doc("Sales Invoice", name) if name else None


def _make_invoice(
    marker: str,
    items: list[dict],
    *,
    price_includes_tax: bool = False,
):
    existing = _submitted_invoice(marker)
    if existing:
        return existing

    doc = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "company": TEST_COMPANY,
            "customer": TEST_CUSTOMER,
            "posting_date": nowdate(),
            "currency": CURRENCY,
            "remarks": marker,
            "update_stock": 0,
            "items": items,
        }
    )
    tax_foundation.apply_tax_plan(
        doc,
        price_includes_tax=price_includes_tax,
        replace_managed_rows=True,
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    doc.reload()
    return doc


def _make_return(
    source,
    marker: str,
    *,
    qty: float | None = None,
    rate: float | None = None,
    price_includes_tax: bool = False,
):
    existing = _submitted_invoice(marker)
    if existing:
        return existing

    from erpnext.controllers.sales_and_purchase_return import make_return_doc

    doc = make_return_doc("Sales Invoice", source.name)
    doc.remarks = marker
    doc.update_stock = 0
    doc.payment_schedule = []
    if not doc.items:
        frappe.throw(f"Native return mapper produced no rows for {source.name}.")
    if qty is not None:
        doc.items[0].qty = qty
        doc.items[0].stock_qty = qty
    if rate is not None:
        doc.items[0].rate = rate
        doc.items[0].price_list_rate = rate
        doc.items[0].discount_percentage = 0
        doc.items[0].discount_amount = 0

    tax_foundation.apply_tax_plan(
        doc,
        price_includes_tax=price_includes_tax,
        replace_managed_rows=True,
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    doc.reload()
    return doc


def _gl_rows(voucher_no: str) -> list[dict]:
    return frappe.get_all(
        "GL Entry",
        filters={
            "voucher_type": "Sales Invoice",
            "voucher_no": voucher_no,
            "is_cancelled": 0,
        },
        fields=["account", "debit", "credit"],
    )


def _gl_net_credit(voucher_no: str, account: str) -> float:
    rows = [row for row in _gl_rows(voucher_no) if row.account == account]
    return _money(sum(flt(row.credit) - flt(row.debit) for row in rows))


def _gl_balanced(voucher_no: str) -> bool:
    rows = _gl_rows(voucher_no)
    return abs(sum(flt(row.debit) - flt(row.credit) for row in rows)) < 0.01


def _sle_count(voucher_no: str) -> int:
    return frappe.db.count(
        "Stock Ledger Entry",
        {"voucher_type": "Sales Invoice", "voucher_no": voucher_no, "is_cancelled": 0},
    )


def _tax_rows(doc) -> list[dict]:
    return [
        {
            "description": row.description,
            "account": row.account_head,
            "amount": _money(row.tax_amount),
            "included": cint(row.included_in_print_rate),
        }
        for row in doc.get("taxes") or []
        if str(row.description or "").startswith(tax_foundation.MANAGED_TAX_DESCRIPTION_PREFIX)
    ]


def _line_snapshot(doc, index: int = 0) -> dict:
    raw = doc.items[index].get("custom_ledgix_fbr_snapshot_json")
    return json.loads(raw) if raw else {}


def _invoice_evidence(doc, accounts: dict) -> dict:
    return {
        "name": doc.name,
        "docstatus": doc.docstatus,
        "net_total": _money(doc.net_total),
        "total_taxes_and_charges": _money(doc.total_taxes_and_charges),
        "grand_total": _money(doc.grand_total),
        "outstanding_amount": _money(doc.outstanding_amount),
        "tax_rows": _tax_rows(doc),
        "gl_entry_count": len(_gl_rows(doc.name)),
        "gl_balanced": _gl_balanced(doc.name),
        "tax_account_net_credit": {
            component: _gl_net_credit(doc.name, account)
            for component, account in accounts.items()
        },
        "stock_ledger_entries": _sle_count(doc.name),
        "fbr_preview": tax_foundation.build_fbr_tax_preview(doc),
    }


def _case(name: str, evidence: dict, checks: dict) -> dict:
    result = {"name": name, "evidence": evidence, "checks": checks}
    result["passed"] = all(checks.values())
    return result


def _standard_case(accounts: dict) -> dict:
    doc = _make_invoice(
        _marker("ordinary"),
        [{"item_code": ITEMS["ordinary"], "qty": 1, "uom": "Nos", "rate": 1000}],
    )
    ev = _invoice_evidence(doc, accounts)
    snap = _line_snapshot(doc)
    checks = {
        "submitted": doc.docstatus == 1,
        "net_total_1000": abs(ev["net_total"] - 1000) < 0.01,
        "sales_tax_180": abs(ev["total_taxes_and_charges"] - 180) < 0.01,
        "grand_total_1180": abs(ev["grand_total"] - 1180) < 0.01,
        "sales_tax_gl_180": abs(ev["tax_account_net_credit"]["sales_tax"] - 180) < 0.01,
        "gl_balanced": ev["gl_balanced"],
        "snapshot_tax_180": abs(_money(snap.get("sales_tax")) - 180) < 0.01,
        "preview_tax_180": abs(ev["fbr_preview"]["items"][0]["salesTaxApplicable"] - 180) < 0.01,
        "no_stock_effect": ev["stock_ledger_entries"] == 0,
    }
    return _case("ordinary_taxable_item", ev, checks)


def _inclusive_case(accounts: dict) -> dict:
    doc = _make_invoice(
        _marker("inclusive"),
        [{"item_code": ITEMS["inclusive"], "qty": 1, "uom": "Nos", "rate": 1180}],
        price_includes_tax=True,
    )
    ev = _invoice_evidence(doc, accounts)
    snap = _line_snapshot(doc)
    checks = {
        "submitted": doc.docstatus == 1,
        "net_total_1000": abs(ev["net_total"] - 1000) < 0.01,
        "included_tax_180": abs(ev["total_taxes_and_charges"] - 180) < 0.01,
        "grand_total_stays_1180": abs(ev["grand_total"] - 1180) < 0.01,
        "snapshot_marks_inclusive": cint(snap.get("price_includes_tax")) == 1,
        "sales_tax_gl_180": abs(ev["tax_account_net_credit"]["sales_tax"] - 180) < 0.01,
        "gl_balanced": ev["gl_balanced"],
    }
    return _case("tax_inclusive_price", ev, checks)


def _zero_or_exempt_case(accounts: dict, key: str, label: str) -> dict:
    doc = _make_invoice(
        _marker(key),
        [{"item_code": ITEMS[key], "qty": 1, "uom": "Nos", "rate": 1000}],
    )
    ev = _invoice_evidence(doc, accounts)
    snap = _line_snapshot(doc)
    expected_flag = "is_zero_rated" if key == "zero" else "is_exempt"
    checks = {
        "submitted": doc.docstatus == 1,
        "tax_zero": abs(ev["total_taxes_and_charges"]) < 0.01,
        "grand_total_1000": abs(ev["grand_total"] - 1000) < 0.01,
        "no_sales_tax_gl": abs(ev["tax_account_net_credit"]["sales_tax"]) < 0.01,
        "classification_flag": cint(snap.get(expected_flag)) == 1,
        "preview_tax_zero": abs(ev["fbr_preview"]["items"][0]["salesTaxApplicable"]) < 0.01,
    }
    return _case(label, ev, checks)


def _third_schedule_case(accounts: dict) -> dict:
    doc = _make_invoice(
        _marker("third_schedule"),
        [{"item_code": ITEMS["third_schedule"], "qty": 1, "uom": "Nos", "rate": 1000}],
    )
    ev = _invoice_evidence(doc, accounts)
    snap = _line_snapshot(doc)
    preview = ev["fbr_preview"]["items"][0]
    checks = {
        "submitted": doc.docstatus == 1,
        "transaction_net_1000": abs(ev["net_total"] - 1000) < 0.01,
        "tax_uses_notified_1200_basis": abs(_money(snap.get("taxable_amount")) - 1200) < 0.01,
        "sales_tax_216": abs(ev["total_taxes_and_charges"] - 216) < 0.01,
        "grand_total_1216": abs(ev["grand_total"] - 1216) < 0.01,
        "preview_notified_price_1200": abs(preview["fixedNotifiedValueOrRetailPrice"] - 1200) < 0.01,
        "sales_tax_gl_216": abs(ev["tax_account_net_credit"]["sales_tax"] - 216) < 0.01,
    }
    return _case("third_schedule_notified_retail_price", ev, checks)


def _special_component_case(accounts: dict, key: str, component: str, amount: float, label: str) -> dict:
    doc = _make_invoice(
        _marker(key),
        [{"item_code": ITEMS[key], "qty": 1, "uom": "Nos", "rate": 1000}],
    )
    ev = _invoice_evidence(doc, accounts)
    snap = _line_snapshot(doc)
    expected_tax = 180 + amount
    checks = {
        "submitted": doc.docstatus == 1,
        "ordinary_plus_component_total": abs(ev["total_taxes_and_charges"] - expected_tax) < 0.01,
        "grand_total_correct": abs(ev["grand_total"] - (1000 + expected_tax)) < 0.01,
        "component_snapshot_correct": abs(_money(snap.get(component)) - amount) < 0.01,
        "component_gl_correct": abs(ev["tax_account_net_credit"][component] - amount) < 0.01,
        "sales_tax_gl_180": abs(ev["tax_account_net_credit"]["sales_tax"] - 180) < 0.01,
        "gl_balanced": ev["gl_balanced"],
    }
    return _case(label, ev, checks)


def _withheld_case(accounts: dict) -> dict:
    doc = _make_invoice(
        _marker("withheld"),
        [{"item_code": ITEMS["withheld"], "qty": 1, "uom": "Nos", "rate": 1000}],
    )
    ev = _invoice_evidence(doc, accounts)
    snap = _line_snapshot(doc)
    preview = ev["fbr_preview"]["items"][0]
    checks = {
        "submitted": doc.docstatus == 1,
        "withheld_snapshot_40": abs(_money(snap.get("sales_tax_withheld_at_source")) - 40) < 0.01,
        "withheld_preview_40": abs(preview["salesTaxWithheldAtSource"] - 40) < 0.01,
        "withheld_not_added_to_payable": abs(ev["grand_total"] - 1180) < 0.01,
        "withheld_not_posted_as_invoice_tax": abs(ev["tax_account_net_credit"]["sales_tax_withheld_at_source"]) < 0.01,
        "ordinary_tax_still_180": abs(ev["tax_account_net_credit"]["sales_tax"] - 180) < 0.01,
    }
    return _case("sales_tax_withheld_at_source", ev, checks)


def _mixed_case(accounts: dict) -> dict:
    doc = _make_invoice(
        _marker("mixed"),
        [
            {"item_code": ITEMS["mixed_a"], "qty": 1, "uom": "Nos", "rate": 1000},
            {"item_code": ITEMS["mixed_b"], "qty": 1, "uom": "Nos", "rate": 500},
        ],
    )
    ev = _invoice_evidence(doc, accounts)
    preview = ev["fbr_preview"]["items"]
    checks = {
        "submitted": doc.docstatus == 1,
        "net_total_1500": abs(ev["net_total"] - 1500) < 0.01,
        "tax_total_359": abs(ev["total_taxes_and_charges"] - 359) < 0.01,
        "grand_total_1859": abs(ev["grand_total"] - 1859) < 0.01,
        "sales_tax_gl_324": abs(ev["tax_account_net_credit"]["sales_tax"] - 324) < 0.01,
        "extra_gl_20": abs(ev["tax_account_net_credit"]["extra_tax"] - 20) < 0.01,
        "further_gl_10": abs(ev["tax_account_net_credit"]["further_tax"] - 10) < 0.01,
        "fed_gl_5": abs(ev["tax_account_net_credit"]["fed_payable"] - 5) < 0.01,
        "withheld_7_not_in_gl": abs(ev["tax_account_net_credit"]["sales_tax_withheld_at_source"]) < 0.01,
        "preview_has_two_lines": len(preview) == 2,
        "second_line_notified_basis": abs(preview[1]["fixedNotifiedValueOrRetailPrice"] - 800) < 0.01,
        "gl_balanced": ev["gl_balanced"],
    }
    return _case("mixed_tax_invoice", ev, checks)


def _return_cases(accounts: dict) -> tuple[dict, dict]:
    full_source = _make_invoice(
        _marker("full_return_source"),
        [{"item_code": ITEMS["return"], "qty": 1, "uom": "Nos", "rate": 1000}],
    )
    full_return = _make_return(full_source, _marker("full_return"), qty=-1)
    full_ev = _invoice_evidence(full_return, accounts)
    full_checks = {
        "submitted": full_return.docstatus == 1,
        "linked_to_source": full_return.return_against == full_source.name,
        "grand_total_negative_1180": abs(full_ev["grand_total"] + 1180) < 0.01,
        "sales_tax_reversed_180": abs(full_ev["tax_account_net_credit"]["sales_tax"] + 180) < 0.01,
        "gl_balanced": full_ev["gl_balanced"],
        "no_stock_effect": full_ev["stock_ledger_entries"] == 0,
    }

    partial_source = _make_invoice(
        _marker("partial_return_source"),
        [{"item_code": ITEMS["return"], "qty": 4, "uom": "Nos", "rate": 1000}],
    )
    partial_return = _make_return(partial_source, _marker("partial_return"), qty=-1)
    partial_ev = _invoice_evidence(partial_return, accounts)
    partial_checks = {
        "submitted": partial_return.docstatus == 1,
        "linked_to_source": partial_return.return_against == partial_source.name,
        "return_qty_minus_one": abs(flt(partial_return.items[0].qty) + 1) < 0.001,
        "grand_total_negative_1180": abs(partial_ev["grand_total"] + 1180) < 0.01,
        "sales_tax_reversed_180": abs(partial_ev["tax_account_net_credit"]["sales_tax"] + 180) < 0.01,
        "gl_balanced": partial_ev["gl_balanced"],
    }
    return (
        _case("full_return", full_ev, full_checks),
        _case("partial_return", partial_ev, partial_checks),
    )


def _price_only_credit_case(accounts: dict) -> dict:
    source = _make_invoice(
        _marker("price_credit_source"),
        [{"item_code": ITEMS["price_credit"], "qty": 1, "uom": "Nos", "rate": 1000}],
    )
    credit = _make_return(
        source,
        _marker("price_only_credit"),
        qty=0,
        rate=100,
    )
    ev = _invoice_evidence(credit, accounts)
    checks = {
        "submitted": credit.docstatus == 1,
        "linked_to_source": credit.return_against == source.name,
        "zero_quantity_financial_credit": abs(flt(credit.items[0].qty)) < 0.001,
        "credit_net_minus_100": abs(ev["net_total"] + 100) < 0.01,
        "credit_tax_minus_18": abs(ev["total_taxes_and_charges"] + 18) < 0.01,
        "credit_grand_total_minus_118": abs(ev["grand_total"] + 118) < 0.01,
        "tax_gl_reversed_18": abs(ev["tax_account_net_credit"]["sales_tax"] + 18) < 0.01,
        "no_stock_effect": ev["stock_ledger_entries"] == 0,
        "gl_balanced": ev["gl_balanced"],
    }
    return _case("price_only_credit_note", ev, checks)


def _foundation_contract(accounts: dict) -> dict:
    meta = frappe.get_meta("Company", cached=False)
    fields = {
        definition["fieldname"]: bool(meta.get_field(definition["fieldname"]))
        for definition in tax_foundation.COMPANY_TAX_FIELDS
    }
    configured = tax_foundation.get_company_tax_accounts(TEST_COMPANY, require_financial=True)
    return {
        "company_custom_fields": fields,
        "company_accounts": configured,
        "expected_accounts": accounts,
        "checks": {
            "all_company_tax_fields_exist": all(fields.values()),
            "all_financial_accounts_configured": all(configured.get(key) for key in tax_foundation.FINANCIAL_COMPONENTS),
            "withheld_account_reserved": bool(configured.get("sales_tax_withheld_at_source")),
            "adapter_does_not_own_grand_total": "grand_total" not in tax_foundation.COMPONENT_ACCOUNT_FIELDS,
        },
    }


def run() -> dict:
    """Run the mandatory Phase 4 ERPNext tax/accounting parity matrix."""

    _assert_safe_site()
    frappe.set_user("Administrator")

    sync = tax_foundation.sync_all()
    _ensure_customer()
    fixture_data = _ensure_fixture_data()
    accounts = _ensure_tax_accounts()

    cases = {}
    cases["ordinary_taxable_item"] = _standard_case(accounts)
    cases["tax_inclusive_price"] = _inclusive_case(accounts)
    cases["zero_rated_item"] = _zero_or_exempt_case(accounts, "zero", "zero_rated_item")
    cases["exempt_item"] = _zero_or_exempt_case(accounts, "exempt", "exempt_item")
    cases["third_schedule_notified_retail_price"] = _third_schedule_case(accounts)
    cases["further_tax"] = _special_component_case(accounts, "further_tax", "further_tax", 50, "further_tax")
    cases["extra_tax"] = _special_component_case(accounts, "extra_tax", "extra_tax", 25, "extra_tax")
    cases["fed"] = _special_component_case(accounts, "fed", "fed_payable", 30, "fed")
    cases["sales_tax_withheld_at_source"] = _withheld_case(accounts)
    cases["mixed_tax_invoice"] = _mixed_case(accounts)
    full_return, partial_return = _return_cases(accounts)
    cases["full_return"] = full_return
    cases["partial_return"] = partial_return
    cases["price_only_credit_note"] = _price_only_credit_case(accounts)

    foundation = _foundation_contract(accounts)
    matrix_passed = all(case["passed"] for case in cases.values())
    foundation_passed = all(foundation["checks"].values())
    failed_cases = [name for name, case in cases.items() if not case["passed"]]

    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": TEST_COMPANY,
        "sync": sync,
        "fixture_data": fixture_data,
        "foundation": foundation,
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed_cases,
        "decisions": {
            "erpnext_owns_invoice_totals": True,
            "erpnext_owns_tax_gl": True,
            "ordinary_sales_tax": "ERPNext Sales Taxes and Charges row",
            "extra_tax": "ERPNext Sales Taxes and Charges row",
            "further_tax": "ERPNext Sales Taxes and Charges row",
            "fed": "ERPNext Sales Taxes and Charges row",
            "sales_tax_withheld_at_source": (
                "Ledgix immutable/FBR snapshot only in Phase 4; excluded from invoice payable and not blindly mapped to ERPNext supplier TDS"
            ),
            "third_schedule": "Ledgix legal tax-basis metadata -> ERPNext Actual tax row -> ERPNext totals/GL",
            "fbr_payload_source_cutover_performed": False,
            "legacy_ledgix_tax_engine_retired": False,
            "network_fbr_submission_performed": False,
        },
        "phase4_complete": bool(matrix_passed and foundation_passed and len(cases) == 13),
        "phase5_ready": bool(matrix_passed and foundation_passed and len(cases) == 13),
        "next_phase": "Phase 5 — Master Data Migration",
        "passed": bool(matrix_passed and foundation_passed and len(cases) == 13),
    }
    frappe.db.commit()
    return result
