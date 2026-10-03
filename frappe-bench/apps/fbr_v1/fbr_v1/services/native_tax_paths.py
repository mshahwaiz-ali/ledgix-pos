"""Inspect reachable ERPNext paths without rates, totals, writes, or FBR calls.

Uses the installed ERPNext item resolver/map and AccountsController tax-row
population. Unknown customer/net-rate conditions are never supplied as zeroes.
"""
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import cint

from fbr_v1.services.payment_readiness import current_pos_profiles

SALES_TAX = "Sales Tax Applicable"
THIRD = "On Notified Retail Price"


def native_contexts(company):
    profiles, errors = current_pos_profiles(company)
    # Native B2B Sales Invoice uses party/default resolution. This projection
    # checks the blank-category default; customer-specific Tax Rules remain
    # invoice-time authority and are not treated as universal coverage.
    contexts = [{"source": "Sales Invoice default", "doctype": "Sales Invoice", "tax_category": ""}]
    contexts.extend({"source": "POS Profile " + p.name, "doctype": "POS Invoice",
        "tax_category": p.get("tax_category") or "", "taxes_and_charges": p.get("taxes_and_charges")}
        for p in profiles)
    return contexts, errors


def default_sales_tax_rule(company, date):
    from erpnext.accounts.doctype.tax_rule.tax_rule import get_tax_template

    # Match only the default blank-party/category path. Supplying every native
    # sales condition excludes rules for unknown customers/addresses instead of
    # accidentally selecting them because their filter keys were omitted.
    args = {"company": company, "tax_type": "Sales", "tax_category": "",
            "customer": "", "customer_group": "", "use_for_shopping_cart": 0}
    args.update({prefix + "_" + field: "" for prefix in ("billing", "shipping")
                 for field in ("city", "county", "state", "zipcode", "country")})
    return get_tax_template(str(date), args)


def resolve_item_template(company, item_code, context, date):
    from erpnext.stock.get_item_details import _get_item_tax_template, get_item_tax_map
    from frappe.utils.nestedset import get_ancestors_of

    item = frappe.get_cached_doc("Item", item_code)
    args = frappe._dict(company=company, item_code=item_code, posting_date=str(date),
                        tax_category=context.get("tax_category") or "")
    warnings = []
    sources = [("Item " + item_code, item.get("taxes") or [])]
    # Keep ERPNext's exact Item -> Item Group -> ancestor order.
    groups = [item.item_group, *get_ancestors_of("Item Group", item.item_group)]
    sources.extend(("Item Group " + group, frappe.get_cached_doc("Item Group", group).get("taxes") or []) for group in groups)
    for source, rows in sources:
        unconditional = []
        for row in rows:
            if row.get("maximum_net_rate"):
                warnings.append(f"Item {item_code}: {source} has net-rate-dependent tax configuration; invoice-time resolution is required.")
            else:
                unconditional.append(row)
            if row.get("tax_category") != args.tax_category and row.get("tax_category"):
                warnings.append(f"Item {item_code}: {source} has another Tax Category path; coverage here is limited to the configured/default category.")
        template = _get_item_tax_template(args, unconditional)
        if template:
            return template, source, get_item_tax_map(company, template, as_json=False), warnings
    return None, None, {}, warnings


def _rate(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def inspect_item_path(company, item, context, date, mapping, meanings, account_errors):
    template, source, tax_map, warnings = resolve_item_template(company, item, context, date)
    errors = []
    report = {"context": context["source"], "native_tax_state": "Unresolved",
              "native_source": source or context["source"], "native_template": template,
              "native_accounts": [], "ready": False, "blockers": errors, "warnings": warnings}
    sales_template = context.get("taxes_and_charges")
    if context["doctype"] == "Sales Invoice":
        sales_template = default_sales_tax_rule(company, date) or sales_template
        if sales_template:
            report["sales_source"] = "ERPNext default Tax Rule"
    # Unsaved native documents run only ERPNext tax-row population helpers.
    # Neither set_missing_values (which calculates) nor totals are invoked.
    doc = frappe.get_doc({"doctype": context["doctype"], "company": company,
        "is_pos": int(context["doctype"] == "POS Invoice"),
        "tax_category": context.get("tax_category"), "taxes_and_charges": sales_template,
        "items": [{"item_code": item, "item_tax_template": template, "item_tax_rate": tax_map}], "taxes": []})
    doc.set_taxes()
    if context["doctype"] == "Sales Invoice":
        doc.set_taxes_and_charges()
        warnings.append("Sales Invoice coverage checks the default category only; customer/Tax Rule and net-rate conditions remain invoice-time authority.")
    sales_template = doc.get("taxes_and_charges")
    report["sales_template"] = sales_template
    report.setdefault("sales_source", context["source"])
    if sales_template:
        master = frappe.get_cached_doc("Sales Taxes and Charges Template", sales_template)
        if master.get("company") != company or cint(master.get("disabled")):
            errors.append(f"Item {item}: native sales-tax template {sales_template} must be enabled in {company}.")
    if template:
        master = frappe.get_cached_doc("Item Tax Template", template)
        if master.get("company") != company or cint(master.get("disabled")):
            errors.append(f"Item {item}: Item Tax Template {template} must be enabled in {company}.")
        for row in master.get("taxes") or []:
            errors.extend(account_errors(row.get("tax_type")))
    financial = {row.get("account_head"): row for row in doc.get("taxes") or []}
    for account in financial:
        errors.extend(account_errors(account))
    values = []
    third_required = bool(mapping and mapping.get("tax_basis") == "Notified Retail Price")
    for account in sorted(set(financial) | set(tax_map)):
        row = financial.get(account)
        value = tax_map.get(account, row.get("rate") if row else None)
        report["native_accounts"].append({"account": account, "native_rate": value,
            "charge_type": row.get("charge_type") if row else None, "component": meanings.get(account)})
        if value == "N/A":
            values.append("N/A")
            continue
        number = _rate(value)
        if number is None:
            errors.append(f"Item {item}: Account {account} has an unresolved native rate.")
            continue
        # All numerical fiscal paths need explicit component classification.
        # An N/A-only map needs no Sales Tax Applicable financial row.
        if meanings.get(account) == SALES_TAX:
            if not row:
                errors.append(f"Item {item}: native Account {account} has no reachable financial tax row.")
            elif row.get("charge_type") == "Actual":
                errors.append(f"Item {item}: Actual fiscal tax cannot be captured per line by Federal V1.")
            elif third_required and row.get("charge_type") != THIRD:
                errors.append(f"Item {item}: Third Schedule requires a native On Notified Retail Price sales-tax path.")
            values.append("Zero Rate" if number == 0 else "Taxable")
        elif number != 0 and account in tax_map and not row:
            errors.append(f"Item {item}: positive Item Tax Template Account {account} has no native financial row.")
    if third_required:
        if not any(row.get("charge_type") == THIRD and meanings.get(account) == SALES_TAX
                   and tax_map.get(account) != "N/A" for account, row in financial.items()):
            errors.append(f"Item {item}: Third Schedule requires a native On Notified Retail Price sales-tax path using a mapped Account.")
        if not errors:
            report["native_tax_state"] = "Third Schedule"
    elif "Taxable" in values:
        report["native_tax_state"] = "Taxable"
    elif "Zero Rate" in values:
        report["native_tax_state"] = "Zero Rate"
    elif values and all(v == "N/A" for v in values) and all(
            tax_map.get(a) == "N/A" for a in financial):
        report["native_tax_state"] = "N/A"
    if report["native_tax_state"] == "Unresolved":
        errors.append(f"Item {item}: missing/unresolved ERPNext native sales-tax template path (Sales Tax Applicable or explicit N/A).")
    report["blockers"] = list(dict.fromkeys(errors))
    report["ready"] = not report["blockers"]
    return report
