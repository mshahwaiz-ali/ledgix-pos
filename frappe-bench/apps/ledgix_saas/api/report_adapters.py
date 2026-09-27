# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

# ============================================================
# REPORT ADAPTER APIs
# ============================================================

import frappe
from frappe import _
from frappe.utils import cint, flt
from ledgix_saas.api.security import require_ledgix_manager_or_above


STRICT_INVENTORY_MODE = "Strict Inventory"
BILLING_ONLY_MODE = "Billing Only"


@frappe.whitelist()
def get_item_intelligence_report_data(
	from_date=None,
	to_date=None,
	search=None,
	status=None,
	type=None,
	party=None,
	item=None,
	min_amount=None,
	max_amount=None,
	page=1,
	page_size=15,
	sort_by=None,
	sort_order="asc",
	view_mode=None,
):
	"""Adapter for the Inventory Intelligence Script Report.

	The Ledgix Reports page expects paginated rows + dict summary.
	The Script Report returns raw rows + report_summary list.
	This wrapper keeps the existing Script Report intact and safely exposes
	the same full item-cycle data inside the Reports module.
	"""

	require_ledgix_manager_or_above()

	selected_item = item or party
	selected_view_mode = view_mode or type or STRICT_INVENTORY_MODE

	if not selected_item:
		return {
			"rows": [],
			"summary": get_empty_item_intelligence_summary(),
			"total_count": 0,
			"page": cint(page) or 1,
			"page_size": cint(page_size) or 15,
			"requires_party": 1,
			"chart_data": [],
		}

	if selected_view_mode not in (STRICT_INVENTORY_MODE, BILLING_ONLY_MODE):
		selected_view_mode = STRICT_INVENTORY_MODE

	filters = frappe._dict({
		"item": selected_item,
		"from_date": from_date,
		"to_date": to_date,
		"view_mode": selected_view_mode,
	})

	execute = get_inventory_intelligence_execute()
	columns, rows, _message, _chart, report_summary = execute(filters)

	rows = normalize_item_intelligence_rows(rows or [])
	rows = apply_item_intelligence_filters(rows, search, status, min_amount, max_amount)
	rows = sort_item_intelligence_rows(rows, sort_by, sort_order)

	total_count = len(rows)
	page = max(cint(page) or 1, 1)
	page_size = max(cint(page_size) or 15, 1)
	start = (page - 1) * page_size
	end = start + page_size

	paged_rows = rows[start:end]
	summary = report_summary_to_dict(report_summary)

	return {
		"rows": paged_rows,
		"summary": summary,
		"total_count": total_count,
		"page": page,
		"page_size": page_size,
		"requires_party": 0,
		"chart_data": [],
	}


def get_inventory_intelligence_execute():
	from ledgix_saas.ledgix.report.inventory_intelligence_report.inventory_intelligence_report import execute

	return execute


def normalize_item_intelligence_rows(rows):
	normalized = []

	for index, row in enumerate(rows or []):
		row = frappe._dict(row or {})
		normalized_row = {
			"name": row.get("name") or row.get("lot_no") or f"item-intelligence-{index + 1}",
			"lot_no": row.get("lot_no"),
			"lot_status": row.get("lot_status"),
			"row_type": row.get("row_type"),
			"cycle_status": row.get("cycle_status"),
			"profit": flt(row.get("profit")),
			"loss": flt(row.get("loss")),
			"current_lot_qty": flt(row.get("current_lot_qty")),
			"purchased_qty": flt(row.get("purchased_qty")),
			"sale_qty": flt(row.get("sale_qty")),
			"return_qty": flt(row.get("return_qty")),
			"net_sold_qty": flt(row.get("net_sold_qty")),
			"unit_cost": flt(row.get("unit_cost")),
			"total_cost": flt(row.get("total_cost")),
			"selling_amount": flt(row.get("selling_amount")),
			"return_amount": flt(row.get("return_amount")),
			"purchase_no": row.get("purchase_no"),
			"purchase_invoice": row.get("purchase_invoice"),
			"purchase_date": row.get("purchase_date"),
			"supplier": row.get("supplier"),
			"purchase_rate": flt(row.get("purchase_rate")),
			"purchase_amount": flt(row.get("purchase_amount")),
			"sale_no": row.get("sale_no"),
			"sale_invoice": row.get("sale_invoice"),
			"sale_date": row.get("sale_date"),
			"customer": row.get("customer"),
			"return_no": row.get("return_no"),
			"return_date": row.get("return_date"),
			"return_reason": row.get("return_reason"),
		}

		normalized_row["reference"] = (
			normalized_row.get("sale_no")
			or normalized_row.get("return_no")
			or normalized_row.get("purchase_no")
			or normalized_row.get("lot_no")
		)
		normalized_row["party"] = normalized_row.get("customer") or normalized_row.get("supplier")
		normalized_row["date"] = (
			normalized_row.get("sale_date")
			or normalized_row.get("return_date")
			or normalized_row.get("purchase_date")
		)

		normalized.append(normalized_row)

	return normalized


def apply_item_intelligence_filters(rows, search=None, status=None, min_amount=None, max_amount=None):
	filtered = rows

	if status:
		status_value = str(status).strip().lower()
		filtered = [
			row for row in filtered
			if status_value in {
				str(row.get("cycle_status") or "").strip().lower(),
				str(row.get("lot_status") or "").strip().lower(),
				str(row.get("row_type") or "").strip().lower(),
			}
		]

	if search:
		search_value = str(search).strip().lower()
		search_fields = (
			"lot_no",
			"lot_status",
			"row_type",
			"cycle_status",
			"purchase_no",
			"purchase_invoice",
			"supplier",
			"sale_no",
			"sale_invoice",
			"customer",
			"return_no",
			"return_reason",
		)
		filtered = [
			row for row in filtered
			if any(search_value in str(row.get(fieldname) or "").lower() for fieldname in search_fields)
		]

	if min_amount not in (None, ""):
		min_profit = flt(min_amount)
		filtered = [row for row in filtered if flt(row.get("profit")) >= min_profit]

	if max_amount not in (None, ""):
		max_profit = flt(max_amount)
		filtered = [row for row in filtered if flt(row.get("profit")) <= max_profit]

	return filtered


def sort_item_intelligence_rows(rows, sort_by=None, sort_order="asc"):
	if not sort_by:
		return rows

	reverse = str(sort_order or "asc").lower() == "desc"

	def sort_key(row):
		value = row.get(sort_by)

		if value is None:
			return ""

		if sort_by in {
			"profit",
			"loss",
			"current_lot_qty",
			"purchased_qty",
			"sale_qty",
			"return_qty",
			"net_sold_qty",
			"unit_cost",
			"total_cost",
			"selling_amount",
			"return_amount",
			"purchase_rate",
			"purchase_amount",
		}:
			return flt(value)

		return str(value).lower()

	return sorted(rows, key=sort_key, reverse=reverse)


def report_summary_to_dict(report_summary):
	summary = get_empty_item_intelligence_summary()

	for item in report_summary or []:
		label = str(item.get("label") or "").strip().lower()
		value = item.get("value")

		if label == "purchased qty":
			summary["purchased_qty"] = flt(value)
		elif label == "current lot qty":
			summary["current_lot_qty"] = flt(value)
		elif label == "sold qty":
			summary["sold_qty"] = flt(value)
		elif label == "returned qty":
			summary["returned_qty"] = flt(value)
		elif label == "selling amount":
			summary["selling_amount"] = flt(value)
		elif label == "profit":
			summary["profit"] = flt(value)
		elif label == "loss":
			summary["loss"] = flt(value)
		elif label == "net sold qty":
			summary["net_sold_qty"] = flt(value)

	return summary


def get_empty_item_intelligence_summary():
	return {
		"purchased_qty": 0,
		"current_lot_qty": 0,
		"sold_qty": 0,
		"returned_qty": 0,
		"net_sold_qty": 0,
		"selling_amount": 0,
		"profit": 0,
		"loss": 0,
	}
