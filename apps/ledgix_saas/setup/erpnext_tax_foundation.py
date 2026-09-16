from __future__ import annotations

"""Phase 4 bridge between Ledgix FBR classification and ERPNext accounting.

This module deliberately does *not* maintain a second grand-total engine. Ledgix
resolves the legal/FBR tax components for each invoice line, persists immutable
classification snapshots, and writes those monetary components into ERPNext
Sales Taxes and Charges rows. ERPNext remains responsible for invoice totals,
GL posting, returns and payment/accounting behavior.

The functions are not wired to Sales Invoice hooks yet. Phase 4 proves parity on
an isolated integration site first; authority cutover happens only in a later
migration phase.
"""

import json
from typing import Any

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt

CUSTOM_FIELD_MODULE = "Ledgix"
SNAPSHOT_VERSION = 2
MANAGED_TAX_DESCRIPTION_PREFIX = "[LEDGIX-TAX]"


def _cf(fieldname: str, fieldtype: str, label: str = "", **values) -> dict:
    row = {
        "fieldname": fieldname,
        "fieldtype": fieldtype,
        "module": CUSTOM_FIELD_MODULE,
    }
    if label:
        row["label"] = label
    row.update(values)
    return row


COMPANY_TAX_FIELDS = [
    _cf(
        "custom_ledgix_tax_accounts_section",
        "Section Break",
        "Ledgix Tax Accounting",
        insert_after="default_income_account",
        collapsible=1,
    ),
    _cf(
        "custom_ledgix_sales_tax_account",
        "Link",
        "Sales Tax Payable Account",
        insert_after="custom_ledgix_tax_accounts_section",
        options="Account",
    ),
    _cf(
        "custom_ledgix_extra_tax_account",
        "Link",
        "Extra Tax Payable Account",
        insert_after="custom_ledgix_sales_tax_account",
        options="Account",
    ),
    _cf(
        "custom_ledgix_further_tax_account",
        "Link",
        "Further Tax Payable Account",
        insert_after="custom_ledgix_extra_tax_account",
        options="Account",
    ),
    _cf(
        "custom_ledgix_fed_account",
        "Link",
        "FED Payable Account",
        insert_after="custom_ledgix_further_tax_account",
        options="Account",
    ),
    _cf(
        "custom_ledgix_tax_accounts_column",
        "Column Break",
        insert_after="custom_ledgix_fed_account",
    ),
    _cf(
        "custom_ledgix_sales_tax_withheld_account",
        "Link",
        "Sales Tax Withheld Account (Reserved)",
        insert_after="custom_ledgix_tax_accounts_column",
        options="Account",
        description=(
            "Reserved for a future legally verified withholding posting model. "
            "Phase 4 keeps salesTaxWithheldAtSource outside invoice payable totals."
        ),
    ),
]

CUSTOM_FIELDS = {"Company": COMPANY_TAX_FIELDS}

COMPONENT_ACCOUNT_FIELDS = {
    "sales_tax": "custom_ledgix_sales_tax_account",
    "extra_tax": "custom_ledgix_extra_tax_account",
    "further_tax": "custom_ledgix_further_tax_account",
    "fed_payable": "custom_ledgix_fed_account",
    "sales_tax_withheld_at_source": "custom_ledgix_sales_tax_withheld_account",
}

FINANCIAL_COMPONENTS = ("sales_tax", "extra_tax", "further_tax", "fed_payable")


def sync_custom_fields() -> int:
    if not frappe.db.exists("DocType", "Company"):
        frappe.throw("ERPNext Company DocType is required for Ledgix tax accounting foundation.")
    create_custom_fields(CUSTOM_FIELDS, update=True)
    frappe.clear_cache(doctype="Company")
    return len(COMPANY_TAX_FIELDS)


def sync_all() -> dict:
    return {"company_tax_fields_expected": sync_custom_fields()}


def after_migrate() -> None:
    sync_all()


def _money(value: Any) -> float:
    return flt(value, 2)


def _format_tax_rate(rate: Any) -> str:
    value = flt(rate)
    if value == int(value):
        return f"{int(value)}%"
    return f"{value:g}%"


def _profile_for_item(item_code: str):
    if not item_code or not frappe.db.exists("DocType", "Ledgix Item Tax Profile"):
        return None
    name = frappe.db.get_value(
        "Ledgix Item Tax Profile",
        {"erpnext_item": item_code, "active": 1},
        "name",
        order_by="modified desc",
    )
    return frappe.get_doc("Ledgix Item Tax Profile", name) if name else None


def _category_values(category_name: str | None) -> dict:
    if not category_name or not frappe.db.exists("Ledgix Tax Category", category_name):
        return {
            "name": category_name or "",
            "default_rate": 0.0,
            "is_exempt": 0,
            "is_zero_rated": 0,
        }
    row = frappe.db.get_value(
        "Ledgix Tax Category",
        category_name,
        ["name", "default_rate", "is_exempt", "is_zero_rated", "active"],
        as_dict=True,
    )
    return dict(row or {})


def _line_transaction_amount(doc, row) -> float:
    qty = flt(row.get("qty"))
    rate = flt(row.get("rate"))
    if qty:
        return _money(qty * rate)
    # ERPNext supports financial-only credit-note lines: for a return with zero
    # quantity the controller treats amount as -rate. Mirror that input basis
    # only; ERPNext still computes the authoritative document total.
    if cint(doc.get("is_return")):
        return _money(-1 * rate)
    return _money(row.get("amount"))


def _ordinary_tax_values(*, amount: float, basis_amount: float, rate: float, included: bool) -> tuple[float, float]:
    if not rate:
        return _money(basis_amount if basis_amount else amount), 0.0
    if included:
        # Inclusive mode is valid for the transaction-value path. For Third
        # Schedule/notified-retail-price the notified value is an external tax
        # basis, so the tax remains an additional ERPNext tax row.
        taxable = _money(amount / (1 + rate / 100.0))
        return taxable, _money(amount - taxable)
    return _money(basis_amount), _money(basis_amount * rate / 100.0)


def build_line_snapshot(doc, row, *, price_includes_tax: bool = False) -> dict:
    """Resolve one immutable Ledgix/FBR line snapshot from ERPNext Item data."""

    item_code = row.get("item_code")
    profile = _profile_for_item(item_code)
    category = _category_values(profile.get("tax_category") if profile else None)

    qty = flt(row.get("qty"))
    transaction_amount = _line_transaction_amount(doc, row)
    taxable = bool(profile and cint(profile.get("taxable")))
    exempt = bool(cint(category.get("is_exempt")))
    zero_rated = bool(cint(category.get("is_zero_rated")))
    tax_rate = 0.0 if (not taxable or exempt or zero_rated) else flt(category.get("default_rate"))

    tax_basis = (profile.get("tax_basis") if profile else None) or "Transaction Value"
    notified_retail_price = _money(profile.get("notified_retail_price") if profile else 0)
    third_schedule = tax_basis == "Notified Retail Price"
    if third_schedule and notified_retail_price <= 0:
        frappe.throw(f"Notified Retail Price is required for Third Schedule ERPNext item {item_code}.")

    if third_schedule:
        # Preserve sign for returns/credit notes. Zero-qty financial credits do
        # not use notified-retail-price basis.
        sign = -1.0 if transaction_amount < 0 else 1.0
        basis_amount = _money(notified_retail_price * abs(qty) * sign) if qty else transaction_amount
    else:
        basis_amount = transaction_amount

    ordinary_included = bool(price_includes_tax and not third_schedule and tax_rate)
    taxable_amount, sales_tax = _ordinary_tax_values(
        amount=transaction_amount,
        basis_amount=basis_amount,
        rate=tax_rate,
        included=ordinary_included,
    )

    per_unit_sign_qty = qty
    extra_tax = _money(flt(profile.get("extra_tax_per_unit") if profile else 0) * per_unit_sign_qty)
    further_tax = _money(flt(profile.get("further_tax_per_unit") if profile else 0) * per_unit_sign_qty)
    fed_payable = _money(flt(profile.get("fed_payable_per_unit") if profile else 0) * per_unit_sign_qty)
    sales_tax_withheld = _money(
        flt(profile.get("sales_tax_withheld_at_source_per_unit") if profile else 0) * per_unit_sign_qty
    )

    rate_description = str((profile.get("fbr_rate_description") if profile else "") or "").strip()
    if not rate_description:
        rate_description = _format_tax_rate(tax_rate)

    charged_special = _money(extra_tax + further_tax + fed_payable)
    charged_tax = _money(sales_tax + charged_special)
    # In inclusive mode only ordinary sales tax is inside the selling rate.
    # Additional legal components remain payable and are explicit ERPNext rows.
    erpnext_line_total = _money(transaction_amount + charged_special) if ordinary_included else _money(
        transaction_amount + charged_tax
    )

    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "item_code": item_code,
        "item_profile": profile.name if profile else "",
        "qty": qty,
        "rate": _money(row.get("rate")),
        "gross_amount": transaction_amount,
        "taxable_amount": taxable_amount,
        "tax_category": category.get("name") or "",
        "taxable": 1 if taxable else 0,
        "is_exempt": 1 if exempt else 0,
        "is_zero_rated": 1 if zero_rated else 0,
        "tax_rate": flt(tax_rate),
        "fbr_rate_description": rate_description,
        "tax_basis": tax_basis,
        "notified_retail_price": notified_retail_price if third_schedule else 0.0,
        "sales_tax": sales_tax,
        "sales_tax_withheld_at_source": sales_tax_withheld,
        "extra_tax": extra_tax,
        "further_tax": further_tax,
        "fed_payable": fed_payable,
        "charged_tax": charged_tax,
        "price_includes_tax": 1 if ordinary_included else 0,
        "erpnext_line_total": erpnext_line_total,
        "hs_code": (profile.get("hs_code") if profile else "") or "",
        "uom_for_fbr": (profile.get("uom_for_fbr") if profile else "") or "",
        "sales_type": (profile.get("sales_type") if profile else "") or "",
        "scenario_id": (profile.get("scenario_id") if profile else "") or "",
        "sro_schedule_number": (profile.get("sro_schedule_number") if profile else "") or "",
        "sro_item_serial_number": (profile.get("sro_item_serial_number") if profile else "") or "",
    }


def build_tax_plan(doc, *, price_includes_tax: bool = False) -> dict:
    lines = [build_line_snapshot(doc, row, price_includes_tax=price_includes_tax) for row in doc.get("items") or []]
    totals = {
        "sales_tax": _money(sum(row["sales_tax"] for row in lines)),
        "extra_tax": _money(sum(row["extra_tax"] for row in lines)),
        "further_tax": _money(sum(row["further_tax"] for row in lines)),
        "fed_payable": _money(sum(row["fed_payable"] for row in lines)),
        "sales_tax_withheld_at_source": _money(sum(row["sales_tax_withheld_at_source"] for row in lines)),
    }
    totals["charged_tax"] = _money(
        totals["sales_tax"] + totals["extra_tax"] + totals["further_tax"] + totals["fed_payable"]
    )
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "price_includes_tax": 1 if price_includes_tax else 0,
        "lines": lines,
        "totals": totals,
    }


def _account_is_valid(company: str, account: str | None) -> bool:
    if not account:
        return False
    row = frappe.db.get_value("Account", account, ["company", "is_group", "disabled"], as_dict=True)
    return bool(row and row.company == company and not cint(row.is_group) and not cint(row.disabled))


def get_company_tax_accounts(company: str, *, require_financial: bool = True) -> dict:
    if not frappe.db.exists("Company", company):
        frappe.throw(f"Company {company!r} does not exist.")
    company_doc = frappe.get_cached_doc("Company", company)
    accounts = {
        component: company_doc.get(fieldname) or ""
        for component, fieldname in COMPONENT_ACCOUNT_FIELDS.items()
    }
    invalid = [
        component
        for component in FINANCIAL_COMPONENTS
        if require_financial and not _account_is_valid(company, accounts.get(component))
    ]
    if invalid:
        frappe.throw(
            "Ledgix ERPNext tax account mapping is missing/invalid for: " + ", ".join(invalid)
        )
    return accounts


def _managed_tax_row(description: str) -> bool:
    return str(description or "").startswith(MANAGED_TAX_DESCRIPTION_PREFIX)


def _tax_row(component: str, amount: float, account: str, *, included: bool = False) -> dict:
    labels = {
        "sales_tax": "Sales Tax",
        "extra_tax": "Extra Tax",
        "further_tax": "Further Tax",
        "fed_payable": "FED Payable",
    }
    return {
        "charge_type": "Actual",
        "account_head": account,
        "description": f"{MANAGED_TAX_DESCRIPTION_PREFIX} {labels[component]}",
        "tax_amount": _money(amount),
        "included_in_print_rate": 1 if included else 0,
    }


def _write_line_snapshot(row, snapshot: dict) -> None:
    field_values = {
        "custom_ledgix_fbr_item_profile": snapshot["item_profile"],
        "custom_ledgix_fbr_hs_code": snapshot["hs_code"],
        "custom_ledgix_fbr_uom": snapshot["uom_for_fbr"],
        "custom_ledgix_fbr_sales_type": snapshot["sales_type"],
        "custom_ledgix_fbr_rate_description": snapshot["fbr_rate_description"],
        "custom_ledgix_fbr_scenario_id": snapshot["scenario_id"],
        "custom_ledgix_fbr_sro_schedule_number": snapshot["sro_schedule_number"],
        "custom_ledgix_fbr_sro_item_serial_number": snapshot["sro_item_serial_number"],
        "custom_ledgix_fbr_tax_basis": snapshot["tax_basis"],
        "custom_ledgix_fbr_notified_retail_price": snapshot["notified_retail_price"],
        "custom_ledgix_fbr_sales_tax_withheld": snapshot["sales_tax_withheld_at_source"],
        "custom_ledgix_fbr_extra_tax": snapshot["extra_tax"],
        "custom_ledgix_fbr_further_tax": snapshot["further_tax"],
        "custom_ledgix_fbr_fed_payable": snapshot["fed_payable"],
        "custom_ledgix_fbr_snapshot_version": SNAPSHOT_VERSION,
        "custom_ledgix_fbr_snapshot_json": json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
    }
    for fieldname, value in field_values.items():
        if row.meta.has_field(fieldname):
            row.set(fieldname, value)


def apply_tax_plan(
    doc,
    *,
    price_includes_tax: bool = False,
    replace_managed_rows: bool = True,
) -> dict:
    """Write a Ledgix tax plan into an ERPNext draft invoice.

    The adapter writes tax inputs only. It intentionally does not assign net_total,
    total_taxes_and_charges or grand_total; ERPNext calculates those values.
    """

    if doc.doctype not in {"Sales Invoice", "POS Invoice"}:
        frappe.throw(f"Unsupported tax adapter target: {doc.doctype}")
    if cint(doc.docstatus) != 0:
        frappe.throw("Ledgix ERPNext tax plan can only be applied to a draft transaction.")

    sync_custom_fields()
    accounts = get_company_tax_accounts(doc.company, require_financial=True)
    plan = build_tax_plan(doc, price_includes_tax=price_includes_tax)

    if replace_managed_rows:
        kept = [row.as_dict() for row in (doc.get("taxes") or []) if not _managed_tax_row(row.get("description"))]
        doc.set("taxes", [])
        for row in kept:
            for key in ("name", "owner", "creation", "modified", "modified_by", "parent", "parentfield", "parenttype", "idx", "docstatus"):
                row.pop(key, None)
            doc.append("taxes", row)

    totals = plan["totals"]
    ordinary_included = bool(price_includes_tax and totals["sales_tax"])
    for component in FINANCIAL_COMPONENTS:
        amount = totals[component]
        if not amount:
            continue
        doc.append(
            "taxes",
            _tax_row(
                component,
                amount,
                accounts[component],
                included=ordinary_included if component == "sales_tax" else False,
            ),
        )

    for row, snapshot in zip(doc.get("items") or [], plan["lines"], strict=True):
        _write_line_snapshot(row, snapshot)

    header_snapshot = {
        "snapshot_version": SNAPSHOT_VERSION,
        "doctype": doc.doctype,
        "company": doc.company,
        "customer": doc.get("customer") or "",
        "is_return": cint(doc.get("is_return")),
        "return_against": doc.get("return_against") or "",
        "price_includes_tax": plan["price_includes_tax"],
        "tax_totals": totals,
    }
    if doc.meta.has_field("custom_ledgix_fbr_snapshot_version"):
        doc.custom_ledgix_fbr_snapshot_version = SNAPSHOT_VERSION
    if doc.meta.has_field("custom_ledgix_fbr_snapshot_json"):
        doc.custom_ledgix_fbr_snapshot_json = json.dumps(
            header_snapshot, sort_keys=True, separators=(",", ":")
        )

    return plan


def build_fbr_tax_preview(doc) -> dict:
    """Build the tax/classification portion of the future ERPNext FBR payload.

    This is preview-only and never submits to FBR. Phase 9 will switch the real
    FBR datasource after the wider migration is complete.
    """

    items = []
    for row in doc.get("items") or []:
        raw = row.get("custom_ledgix_fbr_snapshot_json")
        snapshot = json.loads(raw) if raw else build_line_snapshot(doc, row)
        items.append(
            {
                "hsCode": snapshot.get("hs_code") or "",
                "productDescription": row.get("description") or row.get("item_name") or row.get("item_code") or "",
                "rate": snapshot.get("fbr_rate_description") or _format_tax_rate(snapshot.get("tax_rate")),
                "uoM": snapshot.get("uom_for_fbr") or "",
                "quantity": abs(flt(snapshot.get("qty"))),
                "totalValues": abs(_money(snapshot.get("erpnext_line_total"))),
                "valueSalesExcludingST": abs(_money(snapshot.get("taxable_amount"))),
                "fixedNotifiedValueOrRetailPrice": abs(_money(snapshot.get("notified_retail_price")))
                if snapshot.get("tax_basis") == "Notified Retail Price"
                else 0.0,
                "salesTaxApplicable": abs(_money(snapshot.get("sales_tax"))),
                "salesTaxWithheldAtSource": abs(_money(snapshot.get("sales_tax_withheld_at_source"))),
                "extraTax": abs(_money(snapshot.get("extra_tax"))),
                "furtherTax": abs(_money(snapshot.get("further_tax"))),
                "sroScheduleNo": snapshot.get("sro_schedule_number") or "",
                "fedPayable": abs(_money(snapshot.get("fed_payable"))),
                "discount": abs(_money(row.get("discount_amount"))),
                "saleType": snapshot.get("sales_type") or "",
                "sroItemSerialNo": snapshot.get("sro_item_serial_number") or "",
            }
        )
    return {
        "source_doctype": doc.doctype,
        "source_name": doc.get("name") or "",
        "is_return": bool(cint(doc.get("is_return"))),
        "items": items,
    }
