# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


STRICT_INVENTORY_MODE = "Strict Inventory"
BILLING_ONLY_MODE = "Billing Only"

SALE_STATUSES = {"Sale", "Partial Return", "Returned"}
RETURN_NOTE_FIELDS = ("return_reason", "reason", "note", "remarks")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	data = (
		build_billing_only_rows(filters)
		if filters.view_mode == BILLING_ONLY_MODE
		else build_strict_inventory_rows(filters)
	)

	return get_columns(), data, None, None, get_report_summary(filters, data)


def validate_filters(filters):
	if not filters.get("item"):
		frappe.throw(_("Please select an Item."))

	if not filters.get("view_mode"):
		filters.view_mode = STRICT_INVENTORY_MODE

	if filters.view_mode not in (STRICT_INVENTORY_MODE, BILLING_ONLY_MODE):
		filters.view_mode = STRICT_INVENTORY_MODE

	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
	return [
		{"label": _("Lot No"), "fieldname": "lot_no", "fieldtype": "Link", "options": "Ledgix Stock Lot", "width": 130},
		{"label": _("Lot Status"), "fieldname": "lot_status", "fieldtype": "Data", "width": 95},
		{"label": _("Row Type"), "fieldname": "row_type", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "cycle_status", "fieldtype": "Data", "width": 115},
		{"label": _("Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 115},
		{"label": _("Loss"), "fieldname": "loss", "fieldtype": "Currency", "width": 105},
		{"label": _("Current Lot Qty"), "fieldname": "current_lot_qty", "fieldtype": "Float", "precision": 3, "width": 125},
		{"label": _("Purchased Qty"), "fieldname": "purchased_qty", "fieldtype": "Float", "precision": 3, "width": 118},
		{"label": _("Sale Qty"), "fieldname": "sale_qty", "fieldtype": "Float", "precision": 3, "width": 95},
		{"label": _("Return Qty"), "fieldname": "return_qty", "fieldtype": "Float", "precision": 3, "width": 105},
		{"label": _("Net Sold Qty"), "fieldname": "net_sold_qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("Unit Cost"), "fieldname": "unit_cost", "fieldtype": "Currency", "width": 105},
		{"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 115},
		{"label": _("Selling Amount"), "fieldname": "selling_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Purchase No"), "fieldname": "purchase_no", "fieldtype": "Link", "options": "Ledgix Purchase", "width": 135},
		{"label": _("Purchase Invoice"), "fieldname": "purchase_invoice", "fieldtype": "Data", "width": 135},
		{"label": _("Purchase Date"), "fieldname": "purchase_date", "fieldtype": "Date", "width": 110},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Ledgix Supplier", "width": 145},
		{"label": _("Purchase Rate"), "fieldname": "purchase_rate", "fieldtype": "Currency", "width": 115},
		{"label": _("Purchase Amount"), "fieldname": "purchase_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Sale No"), "fieldname": "sale_no", "fieldtype": "Link", "options": "Ledgix Sale", "width": 135},
		{"label": _("Sale Invoice"), "fieldname": "sale_invoice", "fieldtype": "Data", "width": 120},
		{"label": _("Sale Date"), "fieldname": "sale_date", "fieldtype": "Date", "width": 105},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Ledgix Customer", "width": 145},
		{"label": _("Return No"), "fieldname": "return_no", "fieldtype": "Link", "options": "Ledgix Sales Return", "width": 135},
		{"label": _("Return Date"), "fieldname": "return_date", "fieldtype": "Date", "width": 105},
		{"label": _("Return Reason / Note"), "fieldname": "return_reason", "fieldtype": "Data", "width": 220},
	]


def build_strict_inventory_rows(filters):
	lots = get_stock_lots(filters)
	lot_names = [lot.name for lot in lots]
	allocations = get_lot_allocations(filters, lot_names)

	purchase_map = get_purchase_map([lot.purchase for lot in lots if lot.purchase])
	sales_map = get_sales_map([allocation.sale for allocation in allocations if allocation.sale])
	returns_map = get_returns_map([allocation.sales_return for allocation in allocations if allocation.sales_return])

	for return_doc in returns_map.values():
		if return_doc.get("original_sale") and return_doc.original_sale not in sales_map:
			sales_map.update(get_sales_map([return_doc.original_sale]))

	allocations_by_lot = {}
	for allocation in allocations:
		allocations_by_lot.setdefault(allocation.stock_lot, []).append(allocation)

	rows = []
	for lot in lots:
		lot_allocations = allocations_by_lot.get(lot.name, [])
		sale_allocations = [row for row in lot_allocations if row.allocation_type == "Sale"]
		return_allocations = [row for row in lot_allocations if row.allocation_type == "Return"]
		cancel_allocations = [row for row in lot_allocations if row.allocation_type == "Cancel"]

		rows.append(build_mother_row(lot, purchase_map))
		sale_rows = build_sale_rows(lot, sale_allocations, purchase_map, sales_map)
		merge_return_allocations_into_sale_rows(lot, sale_rows, return_allocations, purchase_map, sales_map, returns_map)

		child_rows = sale_rows + [
			build_cancel_row(lot, allocation, purchase_map, sales_map, returns_map)
			for allocation in cancel_allocations
		]
		child_rows.sort(key=lambda row: (row.get("_sort_date") or "", row.get("_sort_creation") or "", row.get("_sort_name") or ""))
		apply_lot_running_balances(lot, child_rows)
		rows.extend(child_rows)

	return clean_private_fields(rows)


def get_stock_lots(filters):
	lot_filters = {"item": filters.item}

	if filters.get("from_date") and filters.get("to_date"):
		lot_filters["purchase_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		lot_filters["purchase_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		lot_filters["purchase_date"] = ["<=", filters.to_date]

	return frappe.get_all(
		"Ledgix Stock Lot",
		filters=lot_filters,
		fields=[
			"name",
			"item",
			"purchase",
			"purchase_item_row",
			"supplier",
			"purchase_date",
			"purchased_qty",
			"sold_qty",
			"returned_qty",
			"remaining_qty",
			"cost_rate",
			"total_cost",
			"status",
			"creation",
		],
		order_by="purchase_date desc, creation desc",
	)


def get_lot_allocations(filters, lot_names):
	if not lot_names:
		return []

	allocation_filters = {
		"stock_lot": ["in", lot_names],
		"is_reversed": 0,
	}

	return frappe.get_all(
		"Ledgix Stock Lot Allocation",
		filters=allocation_filters,
		fields=[
			"name",
			"stock_lot",
			"item",
			"sale",
			"sale_item_row",
			"sales_return",
			"allocation_type",
			"qty",
			"cost_rate",
			"sale_rate",
			"profit_amount",
			"transaction_date",
			"is_reversed",
			"creation",
		],
		order_by="transaction_date asc, creation asc",
	)


def get_purchase_map(purchase_names):
	purchase_names = unique_non_empty(purchase_names)
	if not purchase_names:
		return {}

	purchases = frappe.get_all(
		"Ledgix Purchase",
		filters={"name": ["in", purchase_names]},
		fields=["name", "supplier", "purchase_date", "invoice_number", "status"],
	)
	return {purchase.name: purchase for purchase in purchases}


def get_sales_map(sale_names):
	sale_names = unique_non_empty(sale_names)
	if not sale_names:
		return {}

	sales = frappe.get_all(
		"Ledgix Sale",
		filters={"name": ["in", sale_names]},
		fields=["name", "customer", "sale_date", "invoice_number", "status"],
	)
	return {sale.name: sale for sale in sales}


def get_returns_map(return_names):
	return_names = unique_non_empty(return_names)
	if not return_names:
		return {}

	fields = ["name", "customer", "original_sale", "total_amount", "total_profit_reversal", "creation"]
	fields.extend(get_optional_fields("Ledgix Sales Return", RETURN_NOTE_FIELDS))

	returns = frappe.get_all(
		"Ledgix Sales Return",
		filters={"name": ["in", return_names]},
		fields=fields,
	)
	return {row.name: row for row in returns}


def build_mother_row(lot, purchase_map):
	purchase = purchase_map.get(lot.purchase, frappe._dict())

	return {
		"lot_no": lot.name,
		"lot_status": lot.status,
		"row_type": "Mother",
		"cycle_status": "Purchase",
		"purchase_no": lot.purchase,
		"purchase_invoice": purchase.get("invoice_number"),
		"purchase_date": lot.purchase_date,
		"supplier": lot.supplier or purchase.get("supplier"),
		"purchased_qty": flt(lot.purchased_qty),
		"current_lot_qty": flt(lot.purchased_qty),
		"actual_current_lot_qty": flt(lot.remaining_qty),
		"purchase_rate": flt(lot.cost_rate),
		"purchase_amount": get_lot_purchase_amount(lot),
		"sale_qty": 0,
		"net_sold_qty": 0,
		"unit_cost": 0,
		"total_cost": 0,
		"selling_amount": 0,
		"profit": 0,
		"loss": 0,
		"return_qty": 0,
		"return_amount": 0,
		"return_reason": "",
		"_sort_date": lot.purchase_date,
		"_sort_creation": lot.creation,
		"_sort_name": lot.name,
	}


def build_sale_rows(lot, sale_allocations, purchase_map, sales_map):
	rows = []

	for allocation in sale_allocations:
		row = build_sale_row(lot, allocation, purchase_map, sales_map)
		row["_allocation_name"] = allocation.name
		row["_sale_item_row"] = allocation.sale_item_row
		row["_sale_key"] = allocation.sale
		rows.append(row)

	return rows


def build_sale_row(lot, allocation, purchase_map, sales_map):
	purchase = purchase_map.get(lot.purchase, frappe._dict())
	sale = sales_map.get(allocation.sale, frappe._dict())
	qty = flt(allocation.qty)
	unit_cost = flt(allocation.cost_rate)
	total_cost = qty * unit_cost
	selling_amount = qty * flt(allocation.sale_rate)
	profit_amount = flt(allocation.profit_amount)

	return {
		"lot_no": lot.name,
		"lot_status": lot.status,
		"row_type": "Child",
		"cycle_status": "Sale",
		"purchase_no": lot.purchase,
		"purchase_invoice": purchase.get("invoice_number"),
		"purchase_date": lot.purchase_date,
		"supplier": lot.supplier or purchase.get("supplier"),
		"purchased_qty": flt(lot.purchased_qty),
		"current_lot_qty": flt(lot.remaining_qty),
		"purchase_rate": flt(lot.cost_rate),
		"purchase_amount": get_lot_purchase_amount(lot),
		"sale_no": allocation.sale,
		"sale_invoice": sale.get("invoice_number"),
		"sale_date": sale.get("sale_date") or allocation.transaction_date,
		"customer": sale.get("customer"),
		"sale_qty": qty,
		"net_sold_qty": qty,
		"unit_cost": unit_cost,
		"total_cost": total_cost,
		"selling_amount": selling_amount,
		"_gross_selling_amount": selling_amount,
		"profit": profit_amount if profit_amount > 0 else 0,
		"loss": abs(profit_amount) if profit_amount < 0 else 0,
		"return_qty": 0,
		"return_amount": 0,
		"return_reason": "",
		"_sort_date": sale.get("sale_date") or allocation.transaction_date,
		"_sort_creation": allocation.creation,
		"_sort_name": allocation.name,
	}


def merge_return_allocations_into_sale_rows(lot, sale_rows, return_allocations, purchase_map, sales_map, returns_map):
	for allocation in return_allocations:
		return_doc = returns_map.get(allocation.sales_return, frappe._dict())
		matched_sale_row = find_matching_sale_row(lot, allocation, return_doc, sale_rows)

		if matched_sale_row:
			merge_return_into_sale_row(matched_sale_row, allocation, return_doc)
		else:
			sale_rows.append(build_unmatched_return_row(lot, allocation, purchase_map, sales_map, returns_map))


def find_matching_sale_row(lot, allocation, return_doc, sale_rows):
	if not sale_rows:
		return None

	if allocation.sale_item_row:
		matches = [row for row in sale_rows if row.get("lot_no") == lot.name and row.get("_sale_item_row") == allocation.sale_item_row]
		if len(matches) == 1:
			return matches[0]

	if allocation.sale:
		matches = [row for row in sale_rows if row.get("lot_no") == lot.name and row.get("_sale_key") == allocation.sale]
		if len(matches) == 1:
			return matches[0]

	original_sale = return_doc.get("original_sale")
	if original_sale:
		matches = [row for row in sale_rows if row.get("lot_no") == lot.name and row.get("_sale_key") == original_sale]
		if len(matches) == 1:
			return matches[0]

	if len(sale_rows) == 1:
		return sale_rows[0]

	return None


def merge_return_into_sale_row(sale_row, allocation, return_doc):
	return_qty = flt(allocation.qty)
	return_amount = return_qty * flt(allocation.sale_rate)
	return_no = allocation.sales_return
	return_date = allocation.transaction_date
	reason = get_return_note(return_doc)

	sale_row["return_qty"] = flt(sale_row.get("return_qty")) + return_qty
	sale_row["return_amount"] = flt(sale_row.get("return_amount")) + return_amount
	sale_row["return_no"] = join_unique(sale_row.get("return_no"), return_no)
	sale_row["return_date"] = latest_date(sale_row.get("return_date"), return_date)
	sale_row["return_reason"] = merge_note(sale_row.get("return_reason"), reason)

	sale_qty = flt(sale_row.get("sale_qty"))
	if sale_row["return_qty"] <= 0:
		sale_row["cycle_status"] = "Sale"
	elif sale_row["return_qty"] + 0.0001 < sale_qty:
		sale_row["cycle_status"] = "Partial Return"
	else:
		sale_row["cycle_status"] = "Returned"

	recalculate_sale_row_after_returns(sale_row)


def recalculate_sale_row_after_returns(sale_row):
	"""Recalculate net sale value, cost and profit after merged returns.

	The row still exposes original sale_qty and separate return_qty for audit,
	but financial columns show the net commercial impact of the sale after returns.
	"""
	sale_qty = flt(sale_row.get("sale_qty"))
	return_qty = flt(sale_row.get("return_qty"))
	net_qty = max(sale_qty - return_qty, 0)
	unit_cost = flt(sale_row.get("unit_cost"))
	gross_selling_amount = flt(sale_row.get("_gross_selling_amount") or sale_row.get("selling_amount"))
	net_selling_amount = max(gross_selling_amount - flt(sale_row.get("return_amount")), 0)
	net_total_cost = net_qty * unit_cost
	net_profit = net_selling_amount - net_total_cost

	sale_row["net_sold_qty"] = net_qty
	sale_row["selling_amount"] = net_selling_amount
	sale_row["total_cost"] = net_total_cost
	sale_row["profit"] = net_profit if net_profit > 0 else 0
	sale_row["loss"] = abs(net_profit) if net_profit < 0 else 0


def build_unmatched_return_row(lot, allocation, purchase_map, sales_map, returns_map):
	purchase = purchase_map.get(lot.purchase, frappe._dict())
	return_doc = returns_map.get(allocation.sales_return, frappe._dict())
	sale_no = allocation.sale or return_doc.get("original_sale")
	sale = sales_map.get(sale_no, frappe._dict())
	return_qty = flt(allocation.qty)
	unit_cost = flt(allocation.cost_rate)

	return {
		"lot_no": lot.name,
		"lot_status": lot.status,
		"row_type": "Child",
		"cycle_status": "Return",
		"purchase_no": lot.purchase,
		"purchase_invoice": purchase.get("invoice_number"),
		"purchase_date": lot.purchase_date,
		"supplier": lot.supplier or purchase.get("supplier"),
		"purchased_qty": flt(lot.purchased_qty),
		"current_lot_qty": flt(lot.remaining_qty),
		"purchase_rate": flt(lot.cost_rate),
		"purchase_amount": get_lot_purchase_amount(lot),
		"sale_no": sale_no,
		"sale_invoice": sale.get("invoice_number"),
		"sale_date": sale.get("sale_date"),
		"customer": sale.get("customer") or return_doc.get("customer"),
		"sale_qty": 0,
		"net_sold_qty": 0,
		"unit_cost": unit_cost,
		"total_cost": return_qty * unit_cost,
		"selling_amount": 0,
		"profit": 0,
		"loss": 0,
		"return_no": allocation.sales_return,
		"return_date": allocation.transaction_date,
		"return_qty": return_qty,
		"return_amount": return_qty * flt(allocation.sale_rate),
		"return_reason": get_return_note(return_doc),
		"_sort_date": allocation.transaction_date,
		"_sort_creation": allocation.creation,
		"_sort_name": allocation.name,
	}


def build_cancel_row(lot, allocation, purchase_map, sales_map, returns_map):
	purchase = purchase_map.get(lot.purchase, frappe._dict())
	return_doc = returns_map.get(allocation.sales_return, frappe._dict())
	sale_no = allocation.sale or return_doc.get("original_sale")
	sale = sales_map.get(sale_no, frappe._dict())

	return {
		"lot_no": lot.name,
		"lot_status": lot.status,
		"row_type": "Child",
		"cycle_status": "Cancel",
		"purchase_no": lot.purchase,
		"purchase_invoice": purchase.get("invoice_number"),
		"purchase_date": lot.purchase_date,
		"supplier": lot.supplier or purchase.get("supplier"),
		"purchased_qty": flt(lot.purchased_qty),
		"current_lot_qty": flt(lot.remaining_qty),
		"purchase_rate": flt(lot.cost_rate),
		"purchase_amount": get_lot_purchase_amount(lot),
		"sale_no": sale_no,
		"sale_invoice": sale.get("invoice_number"),
		"sale_date": sale.get("sale_date") or allocation.transaction_date,
		"customer": sale.get("customer") or return_doc.get("customer"),
		"sale_qty": 0,
		"net_sold_qty": 0,
		"unit_cost": flt(allocation.cost_rate),
		"total_cost": 0,
		"selling_amount": 0,
		"profit": 0,
		"loss": 0,
		"return_no": allocation.sales_return,
		"return_date": allocation.transaction_date,
		"return_qty": 0,
		"return_amount": 0,
		"return_reason": _("Cancellation allocation"),
		"_sort_date": allocation.transaction_date,
		"_sort_creation": allocation.creation,
		"_sort_name": allocation.name,
	}


def apply_lot_running_balances(lot, child_rows):
	"""Show the lot balance after each child activity in chronological order.

	Mother row still shows the actual final lot balance from Ledgix Stock Lot.
	Child rows show the running balance after sale/return activity so older rows
	adjust automatically when an earlier sale gets partially/fully returned.
	"""
	running_qty = flt(lot.purchased_qty)

	for row in child_rows:
		cycle_status = row.get("cycle_status")

		if cycle_status in SALE_STATUSES:
			running_qty -= flt(row.get("sale_qty"))
			running_qty += flt(row.get("return_qty"))
		elif cycle_status == "Return":
			running_qty += flt(row.get("return_qty"))

		if abs(running_qty) < 0.0001:
			running_qty = 0

		row["current_lot_qty"] = running_qty



def build_billing_only_rows(filters):
	rows = []

	for row in get_billing_sale_rows(filters):
		qty = flt(row.quantity)
		unit_cost = flt(row.cost_price)
		profit_amount = flt(row.item_total_profit)
		rows.append({
			"lot_status": "N/A",
			"row_type": "Child",
			"cycle_status": "Sale",
			"sale_no": row.sale_no,
			"sale_invoice": row.sale_invoice,
			"sale_date": row.sale_date,
			"customer": row.customer,
			"sale_qty": qty,
			"net_sold_qty": qty,
			"unit_cost": unit_cost,
			"total_cost": qty * unit_cost,
			"selling_amount": flt(row.amount),
			"profit": profit_amount if profit_amount > 0 else 0,
			"loss": abs(profit_amount) if profit_amount < 0 else 0,
			"return_qty": 0,
			"return_amount": 0,
			"return_reason": "",
			"_sort_date": row.sale_date,
			"_sort_creation": row.creation,
			"_sort_name": row.sale_item_name,
		})

	for row in get_billing_return_rows(filters):
		qty = flt(row.quantity)
		unit_cost = flt(row.cost_price)
		return_date = getdate(row.creation)
		rows.append({
			"lot_status": "N/A",
			"row_type": "Child",
			"cycle_status": "Return",
			"sale_no": row.original_sale,
			"sale_invoice": row.sale_invoice,
			"customer": row.customer,
			"sale_qty": 0,
			"net_sold_qty": 0,
			"unit_cost": unit_cost,
			"total_cost": qty * unit_cost,
			"selling_amount": 0,
			"profit": 0,
			"loss": 0,
			"return_no": row.return_no,
			"return_date": return_date,
			"return_qty": qty,
			"return_amount": flt(row.amount),
			"return_reason": "-",
			"_sort_date": return_date,
			"_sort_creation": row.creation,
			"_sort_name": row.return_item_name,
		})

	rows.sort(key=lambda row: (row.get("_sort_date") or "", row.get("_sort_creation") or "", row.get("_sort_name") or ""), reverse=True)
	return clean_private_fields(rows)


def get_billing_sale_rows(filters):
	conditions = ["si.item = %(item)s", "s.docstatus = 1"]

	if filters.get("from_date"):
		conditions.append("s.sale_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("s.sale_date <= %(to_date)s")

	return frappe.db.sql(
		f"""
		SELECT
			si.name AS sale_item_name,
			s.name AS sale_no,
			s.invoice_number AS sale_invoice,
			s.customer,
			s.sale_date,
			s.creation,
			si.quantity,
			si.rate,
			si.amount,
			si.cost_price,
			si.item_total_profit
		FROM `tabLedgix Sale Item` si
		INNER JOIN `tabLedgix Sale` s ON s.name = si.parent
		WHERE {" AND ".join(conditions)}
		ORDER BY s.sale_date DESC, s.creation DESC
		""",
		filters,
		as_dict=True,
	)


def get_billing_return_rows(filters):
	conditions = ["ri.item = %(item)s", "r.docstatus = 1"]

	if filters.get("from_date"):
		conditions.append("DATE(r.creation) >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("DATE(r.creation) <= %(to_date)s")

	return frappe.db.sql(
		f"""
		SELECT
			ri.name AS return_item_name,
			r.name AS return_no,
			r.customer,
			r.original_sale,
			r.creation,
			s.invoice_number AS sale_invoice,
			ri.quantity,
			ri.rate,
			ri.amount,
			ri.cost_price,
			ri.item_total_profit
		FROM `tabLedgix Sales Return Item` ri
		INNER JOIN `tabLedgix Sales Return` r ON r.name = ri.parent
		LEFT JOIN `tabLedgix Sale` s ON s.name = r.original_sale
		WHERE {" AND ".join(conditions)}
		ORDER BY r.creation DESC
		""",
		filters,
		as_dict=True,
	)


def get_report_summary(filters, data):
	mother_rows = [row for row in data if row.get("row_type") == "Mother"]
	active_mother_rows = [row for row in mother_rows if not is_cancelled_lot_row(row)]
	sale_rows = [
		row for row in data
		if row.get("row_type") == "Child"
		and row.get("cycle_status") in SALE_STATUSES
		and not is_cancelled_lot_row(row)
	]

	purchased_qty = sum(flt(row.get("purchased_qty")) for row in active_mother_rows)
	current_lot_qty = sum(flt(row.get("actual_current_lot_qty", row.get("current_lot_qty"))) for row in active_mother_rows)
	sold_qty = sum(flt(row.get("sale_qty")) for row in sale_rows)
	returned_qty = sum(
		flt(row.get("return_qty"))
		for row in data
		if row.get("cycle_status") != "Cancel" and not is_cancelled_lot_row(row)
	)
	selling_amount = sum(flt(row.get("selling_amount")) for row in sale_rows)
	profit = sum(flt(row.get("profit")) for row in sale_rows)
	loss = sum(flt(row.get("loss")) for row in sale_rows)
	net_sold_qty = sold_qty - returned_qty

	return [
		{"value": purchased_qty, "indicator": "Blue", "label": _("Purchased Qty"), "datatype": "Float"},
		{"value": current_lot_qty, "indicator": "Green" if current_lot_qty else "Red", "label": _("Current Lot Qty"), "datatype": "Float"},
		{"value": sold_qty, "indicator": "Blue", "label": _("Sold Qty"), "datatype": "Float"},
		{"value": returned_qty, "indicator": "Orange" if returned_qty else "Green", "label": _("Returned Qty"), "datatype": "Float"},
		{"value": selling_amount, "indicator": "Green", "label": _("Selling Amount"), "datatype": "Currency"},
		{"value": profit, "indicator": "Green" if profit >= 0 else "Red", "label": _("Profit"), "datatype": "Currency"},
		{"value": loss, "indicator": "Red" if loss else "Green", "label": _("Loss"), "datatype": "Currency"},
		{"value": net_sold_qty, "indicator": "Green" if net_sold_qty >= 0 else "Red", "label": _("Net Sold Qty"), "datatype": "Float"},
	]


def is_cancelled_lot_row(row):
	return str(row.get("lot_status") or "").strip().lower() == "cancelled"


def get_lot_purchase_amount(lot):
	total_cost = flt(lot.get("total_cost"))
	if total_cost:
		return total_cost

	return flt(lot.get("purchased_qty")) * flt(lot.get("cost_rate"))


def get_return_note(return_doc):
	for fieldname in RETURN_NOTE_FIELDS:
		value = safe_get(return_doc, fieldname)
		if value:
			return value

	return "-"


def get_optional_fields(doctype, fieldnames):
	return [fieldname for fieldname in fieldnames if frappe.db.has_column(doctype, fieldname)]


def safe_get(row, fieldname, default=None):
	return row.get(fieldname, default) if row else default


def unique_non_empty(values):
	seen = set()
	result = []
	for value in values:
		if value and value not in seen:
			seen.add(value)
			result.append(value)

	return result


def join_unique(existing, value):
	return ", ".join(unique_non_empty([part.strip() for part in f"{existing or ''}, {value or ''}".split(",")]))


def latest_date(existing, value):
	if not existing:
		return value
	if not value:
		return existing

	return max(getdate(existing), getdate(value))


def merge_note(existing, value):
	if not value:
		return existing or "-"
	if not existing or existing == "-":
		return value
	if value == "-" or value in existing.split(", "):
		return existing

	return f"{existing}, {value}"


def clean_private_fields(rows):
	for row in rows:
		for key in list(row):
			if key.startswith("_"):
				row.pop(key, None)

	return rows
