"""Read-only native tax coherence and Federal V1 item coverage, not legal advice.

No rates, taxes or totals are calculated here. Invoice-time ERPNext resolution
and immutable capture remain the authority for each actual transaction.
"""
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import cint, getdate

SALES_TAX = "Sales Tax Applicable"
SUPPORTED_COMPONENTS = {SALES_TAX, "Further Tax"}
BASES = {"Transaction Value", "Notified Retail Price"}
CHARGE_TYPE = "On Notified Retail Price"
RESOLVER = "fbr_v1.services.erpnext_taxable_base.resolve_notified_retail_price"


def _positive(value):
    try:
        number = Decimal(str(value or 0))
        return number.is_finite() and number > 0
    except (InvalidOperation, ValueError):
        return False


def _rows(doctype, filters, fields):
    return frappe.get_all(doctype, filters=filters, fields=fields,
                          order_by="name asc", limit_page_length=0)


def _effective(mapping, date):
    return (not mapping.get("effective_from") or getdate(mapping["effective_from"]) <= date) and (
        not mapping.get("effective_to") or getdate(mapping["effective_to"]) >= date)


def _required_items(company, warnings):
    items = _rows("Item", {"disabled": 0, "is_sales_item": 1}, ["name"])
    if frappe.db.count("Company") == 1:
        return [row["name"] for row in items]
    owned = {row["parent"] for row in _rows("Item Default", {"company": company}, ["name", "parent"])}
    # Standard company-specific invoice usage provides evidence for shared Items.
    for parent, child in (("Sales Invoice", "Sales Invoice Item"), ("POS Invoice", "POS Invoice Item")):
        invoices = [row["name"] for row in _rows(parent, {"company": company, "docstatus": ["!=", 2]}, ["name"])]
        if invoices:
            owned.update(row["item_code"] for row in _rows(child,
                {"parent": ["in", invoices], "parenttype": parent}, ["name", "item_code"]))
    unscoped = sorted(row["name"] for row in items if row["name"] not in owned)
    if unscoped:
        warnings.append("Shared sellable Items with undetermined Company scope: " + ", ".join(unscoped))
    return [row["name"] for row in items if row["name"] in owned]


def get_company_tax_readiness(company):
    blockers, warnings = [], []
    result = {"ready": False, "company": company, "authority": "ERPNext Native",
              "component_mappings": [], "sales_tax_templates": [], "item_tax_templates": [],
              "item_coverage": {}, "third_schedule": {}, "blockers": blockers,
              "warnings": warnings, "database_write": False, "fbr_network_call": False}
    if not company or not frappe.db.exists("Company", company):
        blockers.append("Select an existing ERPNext Company.")
        return result
    account_cache = {}

    def account_errors(name):
        if name not in account_cache:
            row = frappe.db.get_value("Account", name, ["company", "is_group", "disabled"], as_dict=True) if name else None
            account_cache[name] = ([] if row and row.get("company") == company
                and not cint(row.get("is_group")) and not cint(row.get("disabled"))
                else [f"Account {name or '(missing)'} must be an enabled leaf Account in {company}."])
        return list(account_cache[name])

    meanings, valid_sales = {}, set()
    for row in _rows("Ledgix FBR Tax Component Mapping", {"company": company, "active": 1},
                     ["name", "account_head", "component"]):
        errors = account_errors(row.get("account_head"))
        component, account = row.get("component"), row.get("account_head")
        if component not in SUPPORTED_COMPONENTS:
            errors.append(f"Component {component} is not supported by the current Federal V1 wire payload.")
        if account in meanings and meanings[account] != component:
            errors.append(f"Account {account} has conflicting active FBR component meanings.")
            valid_sales.discard(account)
        meanings[account] = component
        if not errors and component == SALES_TAX:
            valid_sales.add(account)
        result["component_mappings"].append({**dict(row), "ready": not errors, "blockers": errors})
        blockers.extend(errors)

    def templates(doctype):
        reports = []
        for row in _rows(doctype, {"company": company, "disabled": 0}, ["name"]):
            doc = frappe.get_doc(doctype, row["name"])
            taxes, errors = [], []
            for tax in doc.get("taxes") or []:
                account = tax.get("account_head") if doctype == "Sales Taxes and Charges Template" else tax.get("tax_type")
                errors.extend(account_errors(account))
                charge = tax.get("charge_type") if doctype == "Sales Taxes and Charges Template" else None
                rate = tax.get("rate") if doctype == "Sales Taxes and Charges Template" else tax.get("tax_rate")
                if charge == "Actual" and account in meanings:
                    errors.append(f"Template {doc.name} uses Actual for a mapped fiscal tax; Federal V1 cannot capture its native per-line allocation.")
                taxes.append({"account_head": account, "rate": rate, "charge_type": charge})
            reports.append({"name": doc.name, "tax_category": doc.get("tax_category"),
                            "is_default": bool(doc.get("is_default")), "taxes": taxes,
                            "ready": not errors, "blockers": errors,
                            "zero_rate": bool(taxes) and all(str(t["rate"] or 0) in ("0", "0.0", "0.00") for t in taxes),
                            "no_financial_tax_rows": not taxes})
            blockers.extend(errors)
        return reports

    result["sales_tax_templates"] = templates("Sales Taxes and Charges Template")
    result["item_tax_templates"] = templates("Item Tax Template")
    date = getdate()
    mappings = _rows("Ledgix FBR Item Mapping", {"company": company, "active": 1},
                     ["name", "erpnext_item", "needs_review", "hs_code", "tax_basis",
                      "notified_retail_price", "effective_from", "effective_to"])
    current = [row for row in mappings if _effective(row, date)]
    required = sorted(_required_items(company, warnings))
    coverage = []
    for item in required:
        found = [row for row in current if row.get("erpnext_item") == item]
        errors = []
        if len(found) != 1:
            errors.append(f"Item {item} requires exactly one effective active Federal V1 mapping; found {len(found)}.")
        else:
            mapping = found[0]
            if cint(mapping.get("needs_review")):
                errors.append(f"Item {item} mapping Needs Review.")
            pct = str(mapping.get("hs_code") or "").strip()
            if not pct or len(pct) > 8:
                errors.append(f"Item {item} requires HS / PCT code of 1 to 8 characters.")
            if mapping.get("tax_basis") not in BASES:
                errors.append(f"Item {item} has an unsupported Tax Basis.")
            if mapping.get("tax_basis") == "Notified Retail Price" and not _positive(mapping.get("notified_retail_price")):
                errors.append(f"Item {item} requires positive Notified Retail Price.")
        coverage.append({"item": item, "mappings": [m["name"] for m in found], "ready": not errors, "blockers": errors})
        blockers.extend(errors)
    result["item_coverage"] = {"as_of": str(date), "required_items": required,
        "required_count": len(required), "covered_count": sum(row["ready"] for row in coverage),
        "items": coverage, "ready": all(row["ready"] for row in coverage)}
    reviewed = [row for row in current if not cint(row.get("needs_review"))]
    reviewed_sellable = [row for row in reviewed if row.get("erpnext_item") in required]
    if reviewed_sellable and not valid_sales:
        blockers.append("A valid active Sales Tax Applicable component mapping is required for reviewed sellable FBR Items.")
    paths = [template for template in result["sales_tax_templates"] if template["ready"]
             and any(tax["account_head"] in valid_sales and tax["charge_type"] != "Actual" for tax in template["taxes"])]
    if reviewed_sellable and not paths:
        blockers.append("A valid ERPNext native sales-tax template path using a mapped Sales Tax Applicable Account is required.")
    third = [row for row in reviewed if row.get("tax_basis") == "Notified Retail Price"]
    third_errors = []
    if third:
        for row in third:
            if not _positive(row.get("notified_retail_price")):
                third_errors.append(f"Third Schedule Item {row['erpnext_item']} requires positive Notified Retail Price.")
        field = frappe.get_meta("Sales Taxes and Charges").get_field("charge_type")
        if not field or CHARGE_TYPE not in str(field.options or "").splitlines():
            third_errors.append("Effective Sales Taxes and Charges metadata is missing On Notified Retail Price.")
        registered = frappe.get_hooks("erpnext_taxable_base_resolvers") or {}
        resolvers = registered.get(CHARGE_TYPE) or []
        if isinstance(resolvers, str):
            resolvers = [resolvers]
        if resolvers != [RESOLVER]:
            third_errors.append("Federal V1 must be the sole registered Third Schedule server resolver.")
        if not any(tax["charge_type"] == CHARGE_TYPE and tax["account_head"] in valid_sales
                   for template in paths for tax in template["taxes"]):
            third_errors.append("Third Schedule requires a native On Notified Retail Price sales-tax path using a mapped Account.")
    result["third_schedule"] = {"not_required": not third,
        "third_schedule_items": sorted(row["erpnext_item"] for row in third),
        "ready": not third_errors, "blockers": third_errors}
    blockers.extend(third_errors)
    warnings.append("Template rates are reported configuration, not verified legal classifications; invoice-time native resolution remains required.")
    result["blockers"] = list(dict.fromkeys(blockers))
    result["ready"] = not result["blockers"]
    return result
