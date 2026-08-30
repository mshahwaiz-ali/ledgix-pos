from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api.taxation import (
	calculate_tax_breakdown,
	get_tax_profile,
	is_tax_enabled,
	resolve_item_tax_context,
	resolve_tax_rate,
	validate_sale_item_tax_mappings,
)


def _item_tax_mapping(item):
	if not frappe.db.exists("DocType", "Ledgix Item Tax Profile"):
		return None
	return frappe.db.get_value(
		"Ledgix Item Tax Profile",
		{"item": item, "active": 1},
		[
			"name",
			"tax_basis",
			"notified_retail_price",
			"fbr_rate_description",
			"sales_tax_withheld_at_source_per_unit",
			"extra_tax_per_unit",
			"further_tax_per_unit",
			"fed_payable_per_unit",
		],
		as_dict=True,
		order_by="modified desc",
	)


def _format_tax_rate(rate):
	rate = flt(rate)
	if rate == int(rate):
		return f"{int(rate)}%"
	return f"{rate:g}%"


def _component_amount(mapping, fieldname, qty):
	if not mapping:
		return 0.0
	return flt(flt(mapping.get(fieldname)) * flt(qty), 2)


def apply_sale_tax_snapshot(doc):
	"""Apply immutable sale/item tax snapshots used for accounting and FBR DI payloads.

	The ordinary sales-tax amount remains distinct from FBR fields such as Further
	Tax, Extra Tax, FED and sales tax withheld at source. Charged additional taxes
	contribute to the payable total. Withheld tax is reported to FBR but is not
	double-added to what the customer owes.
	"""
	profile = get_tax_profile()
	price_includes_tax = bool(profile.get("price_includes_tax"))

	if not is_tax_enabled():
		doc.tax_amount = 0
		doc.grand_total = flt(getattr(doc, "total_amount", 0), 2)
		if hasattr(doc, "tax_details"):
			doc.set("tax_details", [])
		return {"summary": {"total_tax_amount": 0}, "validation": {"valid": True, "warnings": []}}

	mapping_validation = validate_sale_item_tax_mappings(doc)
	if mapping_validation.get("errors"):
		frappe.throw("; ".join(mapping_validation.get("errors")))

	posting_date = getattr(doc, "sale_date", None)
	tax_rows = []
	total_invoice_tax = 0.0

	for row in doc.get("items") or []:
		qty = flt(row.quantity)
		transaction_amount = flt(row.amount or (qty * flt(row.rate)), 2)
		ctx = resolve_item_tax_context(row.item, profile=profile)
		mapping = _item_tax_mapping(row.item)
		tax_basis = (mapping.tax_basis if mapping else None) or "Transaction Value"
		notified_retail_price = flt(mapping.notified_retail_price if mapping else 0)

		if tax_basis == "Notified Retail Price":
			if notified_retail_price <= 0:
				frappe.throw(f"Notified Retail Price is required for Third Schedule item {row.item}.")
			basis_amount = flt(notified_retail_price * qty, 2)
		else:
			basis_amount = transaction_amount

		tax_rate = 0
		if cint(ctx.get("taxable", 1)):
			tax_rate = resolve_tax_rate(
				ctx.get("tax_category"),
				posting_date=posting_date,
				applies_to="Sales",
			)

		breakdown = calculate_tax_breakdown(
			basis_amount,
			tax_rate,
			price_includes_tax=price_includes_tax,
		)
		sales_tax_applicable = flt(breakdown.get("tax_amount"), 2)
		sales_tax_withheld = _component_amount(mapping, "sales_tax_withheld_at_source_per_unit", qty)
		extra_tax = _component_amount(mapping, "extra_tax_per_unit", qty)
		further_tax = _component_amount(mapping, "further_tax_per_unit", qty)
		fed_payable = _component_amount(mapping, "fed_payable_per_unit", qty)
		charged_special_taxes = flt(extra_tax + further_tax + fed_payable, 2)
		line_invoice_tax = flt(sales_tax_applicable + charged_special_taxes, 2)
		total_invoice_tax += line_invoice_tax

		fbr_rate_description = str((mapping.get("fbr_rate_description") if mapping else "") or "").strip()
		if not fbr_rate_description:
			fbr_rate_description = _format_tax_rate(tax_rate)

		if price_includes_tax:
			net_amount = transaction_amount
		else:
			net_amount = flt(transaction_amount + line_invoice_tax, 2)

		if hasattr(row, "item_tax_profile_snapshot"):
			row.item_tax_profile_snapshot = mapping.name if mapping else None
		if hasattr(row, "tax_basis_snapshot"):
			row.tax_basis_snapshot = tax_basis
		if hasattr(row, "tax_rate_snapshot"):
			row.tax_rate_snapshot = tax_rate
		if hasattr(row, "notified_retail_price_snapshot"):
			row.notified_retail_price_snapshot = notified_retail_price if tax_basis == "Notified Retail Price" else 0

		tax_rows.append({
			"sale": getattr(doc, "name", None),
			"sale_item_row": getattr(row, "name", None),
			"item": row.item,
			"qty": qty,
			"rate": flt(row.rate),
			"gross_amount": transaction_amount,
			"discount_amount": 0,
			"tax_basis": tax_basis,
			"notified_retail_price": notified_retail_price if tax_basis == "Notified Retail Price" else 0,
			"taxable_amount": flt(breakdown.get("taxable_amount"), 2),
			"tax_category": ctx.get("tax_category"),
			"tax_rate": tax_rate,
			"fbr_rate_description": fbr_rate_description,
			"tax_amount": sales_tax_applicable,
			"sales_tax_withheld_at_source": sales_tax_withheld,
			"extra_tax": extra_tax,
			"further_tax": further_tax,
			"fed_payable": fed_payable,
			"net_amount": net_amount,
			"price_includes_tax": 1 if price_includes_tax else 0,
			"hs_code": ctx.get("hs_code"),
			"uom_for_fbr": ctx.get("uom_for_fbr"),
			"sales_type": ctx.get("sales_type"),
			"scenario_id": ctx.get("scenario_id"),
			"sro_schedule_number": ctx.get("sro_schedule_number"),
			"sro_item_serial_number": ctx.get("sro_item_serial_number"),
		})

	doc.tax_amount = flt(total_invoice_tax, 2)
	doc.grand_total = flt(doc.total_amount if price_includes_tax else flt(doc.total_amount) + total_invoice_tax, 2)
	if hasattr(doc, "tax_details"):
		doc.set("tax_details", [])
		for tax_row in tax_rows:
			doc.append("tax_details", tax_row)

	return {
		"summary": {
			"total_tax_amount": doc.tax_amount,
			"price_includes_tax": 1 if price_includes_tax else 0,
		},
		"validation": {
			"valid": True,
			"warnings": mapping_validation.get("warnings") or [],
		},
	}
