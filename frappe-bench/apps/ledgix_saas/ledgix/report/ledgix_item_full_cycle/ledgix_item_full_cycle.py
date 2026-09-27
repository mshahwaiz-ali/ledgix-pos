# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import flt, date_diff, getdate, today, get_datetime

STRICT_INVENTORY_MODE = "Strict Inventory"
BILLING_ONLY_MODE = "Billing Only"


def execute(filters=None):
	filters = filters or {}
	mode = get_report_mode()
	is_billing_only = mode == BILLING_ONLY_MODE
	columns = get_columns(mode)

	if not filters.get("item"):
		message = """
			<div style="padding: 20px; text-align: center; color: #667085;">
				Please select an item to view inventory intelligence.
			</div>
		"""
		return columns, [], message, None, []

	item_doc = frappe.get_doc("Ledgix Item", filters.get("item"))
	data = get_data(filters, item_doc, mode)
	summary = get_report_summary(data, item_doc, filters, mode)

	message = None
	if not data:
		message = """
			<div style="padding: 20px; text-align: center; color: #667085;">
				No item lifecycle activity found for selected filters.
			</div>
		"""

	return columns, data, message, None, summary


# ============================================================
# MODE / SECURITY
# ============================================================

def get_report_mode():
	try:
		from ledgix_saas.api.reports import get_stock_control_mode
		mode = get_stock_control_mode()
	except Exception:
		mode = STRICT_INVENTORY_MODE

	if mode == BILLING_ONLY_MODE:
		return BILLING_ONLY_MODE

	return STRICT_INVENTORY_MODE


# ============================================================
# COLUMNS
# ============================================================

def get_columns(mode=None):
	mode = mode or get_report_mode()

	if mode == BILLING_ONLY_MODE:
		return [
			{"label": "Step", "fieldname": "flow_step", "fieldtype": "Data", "width": 75},
			{"label": "Date", "fieldname": "posting_date", "fieldtype": "Datetime", "width": 150},
			{"label": "Event", "fieldname": "event_type", "fieldtype": "Data", "width": 115},
			{"label": "Reference", "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 145},
			{"label": "Customer", "fieldname": "party", "fieldtype": "Data", "width": 170},
			{"label": "Qty Out", "fieldname": "qty_out", "fieldtype": "Float", "width": 95},
			{"label": "Returned", "fieldname": "qty_returned", "fieldtype": "Float", "width": 95},
			{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 115},
			{"label": "Actions", "fieldname": "open_action", "fieldtype": "HTML", "width": 70},
		]

	return [
		{"label": "Step", "fieldname": "flow_step", "fieldtype": "Data", "width": 75},
		{"label": "Date", "fieldname": "posting_date", "fieldtype": "Datetime", "width": 150},
		{"label": "Event", "fieldname": "event_type", "fieldtype": "Data", "width": 115},
		{"label": "Reference", "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 145},
		{"label": "Party", "fieldname": "party", "fieldtype": "Data", "width": 170},
		{"label": "Stock Flow", "fieldname": "stock_flow", "fieldtype": "Data", "width": 115},
		{"label": "Qty In", "fieldname": "qty_in", "fieldtype": "Float", "width": 95},
		{"label": "Qty Out", "fieldname": "qty_out", "fieldtype": "Float", "width": 95},
		{"label": "Returned", "fieldname": "qty_returned", "fieldtype": "Float", "width": 95},
		{"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 105},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 115},
		{"label": "Profit", "fieldname": "profit", "fieldtype": "Currency", "width": 115},
		{"label": "Impact", "fieldname": "impact_type", "fieldtype": "Data", "width": 105},
		{"label": "Actions", "fieldname": "open_action", "fieldtype": "HTML", "width": 70},
	]


# ============================================================
# DATA
# ============================================================

def get_data(filters, item_doc, mode=None):
	mode = mode or get_report_mode()
	is_billing_only = mode == BILLING_ONLY_MODE
	rows = []

	if not is_billing_only:
		rows.extend(get_purchase_rows(filters))

	rows.extend(get_sale_rows(filters, is_billing_only=is_billing_only))
	rows.extend(get_return_rows(filters, is_billing_only=is_billing_only))

	if not is_billing_only:
		rows.extend(get_adjustment_rows(filters))

	rows.sort(key=lambda row: (
		normalize_sort_datetime(row.get("posting_date")),
		normalize_sort_datetime(row.get("sort_time")),
		row.get("event_sort") or 0,
		row.get("reference_name") or "",
	))

	apply_lifecycle_flow(rows, include_stock_flow=not is_billing_only)

	for row in rows:
		row["report_mode_snapshot"] = mode
		row["open_action"] = row.get("reference_name")

	if is_billing_only:
		clean_rows = sanitize_billing_rows(rows, item_doc)
		attach_billing_intelligence(clean_rows)
		return clean_rows

	enrich_lifecycle_with_lot_intelligence(rows, item_doc, filters)
	intelligence_context = get_inventory_intelligence_context(item_doc, filters, rows)

	for row in rows:
		row["intelligence_context"] = intelligence_context

	for row in rows:
		row.update(get_item_snapshot(item_doc, filters, rows, mode))

	return rows


def apply_lifecycle_flow(rows, include_stock_flow=True):
	balance_qty = 0

	for index, row in enumerate(rows, start=1):
		row["flow_step"] = f"#{index:03d}"

		if not include_stock_flow:
			continue

		stock_before = balance_qty

		if row.get("event_type") == "ADJUSTMENT":
			stock_after = flt(row.get("qty_in"))
		else:
			stock_after = stock_before + flt(row.get("qty_in")) - flt(row.get("qty_out")) + flt(row.get("qty_returned"))

		row["stock_before"] = stock_before
		row["stock_after"] = stock_after
		row["stock_flow"] = f"{format_stock_number(stock_before)} → {format_stock_number(stock_after)}"
		row["balance_qty"] = stock_after
		row["impact_type"] = get_impact_type(row, stock_before, stock_after)
		balance_qty = stock_after


def sanitize_billing_rows(rows, item_doc):
	clean_rows = []

	for row in rows:
		clean_rows.append({
			"flow_step": row.get("flow_step"),
			"posting_date": row.get("posting_date"),
			"event_type": row.get("event_type"),
			"reference_doctype": row.get("reference_doctype"),
			"reference_name": row.get("reference_name"),
			"party": row.get("party"),
			"qty_out": flt(row.get("qty_out")),
			"qty_returned": flt(row.get("qty_returned")),
			"amount": flt(row.get("amount")),
			"open_action": row.get("open_action"),
			"report_mode_snapshot": BILLING_ONLY_MODE,
			"item_code_snapshot": item_doc.name,
			"item_name_snapshot": item_doc.item_name,
		})

	return clean_rows


def get_impact_type(row, stock_before, stock_after):
	if row.get("event_type") == "RETURN":
		return "REVERSAL"

	if stock_after > stock_before:
		return "INCREASE"

	if stock_after < stock_before:
		return "DECREASE"

	return "NEUTRAL"


def format_stock_number(value):
	value = flt(value)
	return str(int(value)) if value == int(value) else str(value)


def normalize_sort_datetime(value):
	if not value:
		return get_datetime("1900-01-01 00:00:00")

	return get_datetime(value)


# ============================================================
# ROW SOURCES
# ============================================================

def get_purchase_rows(filters):
	date_conditions = get_date_conditions("p.purchase_date", filters)

	return frappe.db.sql(
		f"""
		SELECT
			CONCAT(p.purchase_date, ' 00:00:00') AS posting_date,
			'PURCHASE' AS event_type,
			10 AS event_sort,
			'Ledgix Purchase' AS reference_doctype,
			p.name AS reference_name,
			p.supplier AS party,
			IFNULL(pi.quantity, 0) AS qty_in,
			0 AS qty_out,
			0 AS qty_returned,
			IFNULL(pi.rate, 0) AS rate,
			IFNULL(pi.amount, 0) AS amount,
			0 AS profit,
			CONCAT('Purchased from ', IFNULL(p.supplier, '-')) AS details,
			p.creation AS sort_time
		FROM `tabLedgix Purchase Item` pi
		INNER JOIN `tabLedgix Purchase` p
			ON p.name = pi.parent
		WHERE p.docstatus = 1
			AND pi.item = %(item)s
			{date_conditions}
		""",
		filters,
		as_dict=True,
	)


def get_sale_rows(filters, is_billing_only=False):
	date_conditions = get_date_conditions("s.sale_date", filters)
	profit_expr = "0" if is_billing_only else "IFNULL(si.item_total_profit, 0)"
	details_expr = "''" if is_billing_only else "CONCAT('Invoice ', IFNULL(s.invoice_number, '-'), ' • ', IFNULL(s.payment_status, '-'))"

	return frappe.db.sql(
		f"""
		SELECT
			CONCAT(s.sale_date, ' 00:00:00') AS posting_date,
			'SALE' AS event_type,
			20 AS event_sort,
			'Ledgix Sale' AS reference_doctype,
			s.name AS reference_name,
			s.customer AS party,
			0 AS qty_in,
			IFNULL(si.quantity, 0) AS qty_out,
			0 AS qty_returned,
			IFNULL(si.rate, 0) AS rate,
			IFNULL(si.amount, 0) AS amount,
			{profit_expr} AS profit,
			{details_expr} AS details,
			s.creation AS sort_time
		FROM `tabLedgix Sale Item` si
		INNER JOIN `tabLedgix Sale` s
			ON s.name = si.parent
		WHERE s.docstatus = 1
			AND si.item = %(item)s
			{date_conditions}
		""",
		filters,
		as_dict=True,
	)


def get_return_rows(filters, is_billing_only=False):
	date_conditions = get_date_conditions("DATE(sr.creation)", filters)
	profit_expr = "0" if is_billing_only else "-IFNULL(sri.item_total_profit, 0)"
	details_expr = "''" if is_billing_only else "CONCAT('Return against ', IFNULL(sr.original_sale, '-'))"

	return frappe.db.sql(
		f"""
		SELECT
			sr.creation AS posting_date,
			'RETURN' AS event_type,
			30 AS event_sort,
			'Ledgix Sales Return' AS reference_doctype,
			sr.name AS reference_name,
			sr.customer AS party,
			0 AS qty_in,
			0 AS qty_out,
			IFNULL(sri.quantity, 0) AS qty_returned,
			IFNULL(sri.rate, 0) AS rate,
			IFNULL(sri.amount, 0) AS amount,
			{profit_expr} AS profit,
			{details_expr} AS details,
			sr.creation AS sort_time
		FROM `tabLedgix Sales Return Item` sri
		INNER JOIN `tabLedgix Sales Return` sr
			ON sr.name = sri.parent
		WHERE sr.docstatus = 1
			AND sri.item = %(item)s
			{date_conditions}
		""",
		filters,
		as_dict=True,
	)


def get_adjustment_rows(filters):
	date_conditions = get_date_conditions("DATE(sm.movement_date)", filters)

	return frappe.db.sql(
		f"""
		SELECT
			sm.movement_date AS posting_date,
			'ADJUSTMENT' AS event_type,
			40 AS event_sort,
			'Ledgix Stock Movement' AS reference_doctype,
			sm.name AS reference_name,
			sm.owner AS party,
			IFNULL(sm.quantity, 0) AS qty_in,
			0 AS qty_out,
			0 AS qty_returned,
			0 AS rate,
			0 AS amount,
			0 AS profit,
			CONCAT('Stock adjustment • ', IFNULL(sm.reference_note, '-')) AS details,
			sm.creation AS sort_time
		FROM `tabLedgix Stock Movement` sm
		WHERE sm.docstatus = 1
			AND sm.item = %(item)s
			AND sm.movement_type = 'ADJUSTMENT'
			{date_conditions}
		""",
		filters,
		as_dict=True,
	)


def get_date_conditions(field, filters):
	conditions = []

	if filters.get("from_date"):
		conditions.append(f"AND {field} >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append(f"AND {field} <= %(to_date)s")

	return "\n".join(conditions)


# ============================================================
# INTELLIGENCE CONTEXT
# ============================================================

def attach_billing_intelligence(rows):
	if not rows:
		return

	customers = {}
	for row in rows:
		customer = row.get("party") or "Unknown Customer"
		customers.setdefault(customer, {
			"customer": customer,
			"qty_bought": 0,
			"revenue": 0,
			"return_qty": 0,
			"latest_invoice": None,
			"last_purchase_date": None,
		})

		if row.get("event_type") == "SALE":
			customers[customer]["qty_bought"] += flt(row.get("qty_out"))
			customers[customer]["revenue"] += flt(row.get("amount"))
			customers[customer]["latest_invoice"] = row.get("reference_name")
			customers[customer]["last_purchase_date"] = row.get("posting_date")

		if row.get("event_type") == "RETURN":
			customers[customer]["return_qty"] += flt(row.get("qty_returned"))

	for customer in customers.values():
		customer["return_ratio"] = (
			customer["return_qty"] / customer["qty_bought"] * 100
			if customer["qty_bought"] else 0
		)

	context = {
		"mode": BILLING_ONLY_MODE,
		"customers": sorted(
			customers.values(),
			key=lambda row: (flt(row.get("revenue")), flt(row.get("qty_bought"))),
			reverse=True,
		)[:20],
		"warnings": [],
		"lots": [],
		"suppliers": [],
	}

	rows[0]["intelligence_context"] = safe_json(context)


def enrich_lifecycle_with_lot_intelligence(rows, item_doc, filters):
	if not rows or not is_lot_based_item_doc(item_doc):
		return

	purchase_names = [row.get("reference_name") for row in rows if row.get("event_type") == "PURCHASE"]
	sale_names = [row.get("reference_name") for row in rows if row.get("event_type") == "SALE"]
	return_names = [row.get("reference_name") for row in rows if row.get("event_type") == "RETURN"]

	lots_by_purchase = get_lots_by_purchase(purchase_names, item_doc.name)
	sale_allocations = get_allocations_by_reference("sale", sale_names, item_doc.name, "Sale")
	return_allocations = get_allocations_by_reference("sales_return", return_names, item_doc.name, "Return")

	for row in rows:
		if row.get("event_type") == "PURCHASE":
			lots = lots_by_purchase.get(row.get("reference_name")) or []
			row.update(build_lifecycle_lot_snapshot(lots, "Created Lot", "No Lot Trace"))

		if row.get("event_type") == "SALE":
			allocations = sale_allocations.get(row.get("reference_name")) or []
			row.update(build_lifecycle_lot_snapshot(allocations, "FIFO Lot", "Allocation Missing"))

		if row.get("event_type") == "RETURN":
			allocations = return_allocations.get(row.get("reference_name")) or []
			row.update(build_lifecycle_lot_snapshot(allocations, "Restored Lot", "No FIFO Trace"))


def build_lifecycle_lot_snapshot(records, single_label, missing_label):
	if not records:
		return {
			"lot_status": missing_label,
			"lot_label": missing_label,
			"lot_details_json": "[]",
		}

	if len(records) == 1:
		lot_name = records[0].get("stock_lot") or records[0].get("name")
		label = f"{single_label}: {lot_name}" if lot_name else single_label
	else:
		label = f"Multiple Lots ({len(records)})"

	return {
		"lot_status": "Traceable",
		"lot_label": label,
		"lot_details_json": safe_json(records[:20]),
	}


def get_inventory_intelligence_context(item_doc, filters, rows):
	lots = get_lot_intelligence_rows(item_doc.name, filters)
	suppliers = get_supplier_intelligence_rows(lots)
	customers = get_customer_intelligence_rows(item_doc.name, filters)
	warnings = get_inventory_warnings(item_doc, rows, lots)

	return safe_json({
		"mode": STRICT_INVENTORY_MODE,
		"is_lot_based": is_lot_based_item_doc(item_doc),
		"lots": lots[:50],
		"suppliers": suppliers[:20],
		"customers": customers[:20],
		"warnings": warnings[:20],
		"metrics": {
			"remaining_lot_qty": sum(flt(lot.get("remaining_qty")) for lot in lots),
			"open_lots": len([lot for lot in lots if flt(lot.get("remaining_qty")) > 0]),
			"days_since_last_sale": get_days_since_last_event(rows, "SALE"),
			"days_since_last_movement": get_days_since_last_event(rows),
		},
	})


def get_lots_by_purchase(purchase_names, item_code):
	if not purchase_names:
		return {}

	lots = frappe.get_all(
		"Ledgix Stock Lot",
		filters={
			"item": item_code,
			"purchase": ["in", purchase_names],
		},
		fields=[
			"name", "purchase", "supplier", "purchase_date", "purchased_qty",
			"sold_qty", "returned_qty", "remaining_qty", "cost_rate", "status",
		],
		order_by="purchase_date asc, creation asc",
		limit_page_length=100,
	)

	grouped = {}
	for lot in lots:
		grouped.setdefault(lot.purchase, []).append(lot)

	return grouped


def get_allocations_by_reference(reference_field, reference_names, item_code, allocation_type):
	if not reference_names:
		return {}

	allocations = frappe.get_all(
		"Ledgix Stock Lot Allocation",
		filters={
			"item": item_code,
			reference_field: ["in", reference_names],
			"allocation_type": allocation_type,
			"is_reversed": 0,
		},
		fields=[
			"name", "stock_lot", "sale", "sales_return", "qty", "cost_rate",
			"sale_rate", "profit_amount", "transaction_date",
		],
		order_by="creation asc",
		limit_page_length=200,
	)

	grouped = {}
	for allocation in allocations:
		grouped.setdefault(allocation.get(reference_field), []).append(allocation)

	return grouped


def get_lot_intelligence_rows(item_code, filters):
	date_conditions = get_date_conditions("l.purchase_date", filters)

	return frappe.db.sql(
		f"""
		SELECT
			l.name,
			l.purchase,
			l.supplier,
			l.purchase_date,
			IFNULL(l.purchased_qty, 0) AS original_qty,
			IFNULL(l.sold_qty, 0) AS sold_qty,
			IFNULL(l.returned_qty, 0) AS returned_qty,
			IFNULL(l.remaining_qty, 0) AS remaining_qty,
			IFNULL(l.cost_rate, 0) AS purchase_cost,
			IFNULL(AVG(CASE WHEN a.allocation_type = 'Sale' AND a.is_reversed = 0 THEN a.sale_rate END), 0) AS avg_sale_rate,
			IFNULL(SUM(CASE WHEN a.is_reversed = 0 THEN a.profit_amount ELSE 0 END), 0) AS profit,
			l.status
		FROM `tabLedgix Stock Lot` l
		LEFT JOIN `tabLedgix Stock Lot Allocation` a
			ON a.stock_lot = l.name
			AND a.item = l.item
		WHERE l.item = %(item)s
			{date_conditions}
		GROUP BY
			l.name, l.purchase, l.supplier, l.purchase_date, l.purchased_qty,
			l.sold_qty, l.returned_qty, l.remaining_qty, l.cost_rate, l.status
		ORDER BY l.purchase_date DESC, l.creation DESC
		LIMIT 80
		""",
		filters,
		as_dict=True,
	)


def get_supplier_intelligence_rows(lots):
	suppliers = {}
	for lot in lots:
		supplier = lot.get("supplier") or "Unknown Supplier"
		suppliers.setdefault(supplier, {
			"supplier": supplier,
			"total_purchased_qty": 0,
			"lots_supplied": 0,
			"purchase_cost_total": 0,
			"qty_sold_from_lots": 0,
			"revenue_from_lots": 0,
			"profit_from_lots": 0,
			"return_qty": 0,
			"remaining_stock": 0,
			"age_total": 0,
		})

		row = suppliers[supplier]
		original_qty = flt(lot.get("original_qty"))
		avg_sale_rate = flt(lot.get("avg_sale_rate"))
		lot_age = get_lot_age(lot.get("purchase_date"))

		row["total_purchased_qty"] += original_qty
		row["lots_supplied"] += 1
		row["purchase_cost_total"] += original_qty * flt(lot.get("purchase_cost"))
		row["qty_sold_from_lots"] += flt(lot.get("sold_qty"))
		row["revenue_from_lots"] += flt(lot.get("sold_qty")) * avg_sale_rate
		row["profit_from_lots"] += flt(lot.get("profit"))
		row["return_qty"] += flt(lot.get("returned_qty"))
		row["remaining_stock"] += flt(lot.get("remaining_qty"))
		row["age_total"] += lot_age

	for supplier in suppliers.values():
		supplier["avg_purchase_cost"] = (
			supplier["purchase_cost_total"] / supplier["total_purchased_qty"]
			if supplier["total_purchased_qty"] else 0
		)
		supplier["return_ratio"] = (
			supplier["return_qty"] / supplier["qty_sold_from_lots"] * 100
			if supplier["qty_sold_from_lots"] else 0
		)
		supplier["avg_lot_age"] = (
			supplier["age_total"] / supplier["lots_supplied"]
			if supplier["lots_supplied"] else 0
		)

	return sorted(
		suppliers.values(),
		key=lambda row: (flt(row.get("total_purchased_qty")), flt(row.get("remaining_stock"))),
		reverse=True,
	)


def get_customer_intelligence_rows(item_code, filters):
	date_conditions = get_date_conditions("s.sale_date", filters)

	sales = frappe.db.sql(
		f"""
		SELECT
			s.customer,
			SUM(IFNULL(si.quantity, 0)) AS qty_bought,
			SUM(IFNULL(si.amount, 0)) AS revenue,
			SUM(IFNULL(si.item_total_profit, 0)) AS profit,
			MAX(s.sale_date) AS last_purchase_date,
			SUBSTRING_INDEX(GROUP_CONCAT(s.name ORDER BY s.sale_date DESC, s.creation DESC), ',', 1) AS latest_invoice
		FROM `tabLedgix Sale Item` si
		INNER JOIN `tabLedgix Sale` s
			ON s.name = si.parent
		WHERE s.docstatus = 1
			AND si.item = %(item)s
			{date_conditions}
		GROUP BY s.customer
		ORDER BY revenue DESC
		LIMIT 50
		""",
		filters,
		as_dict=True,
	)

	returns = get_return_qty_by_customer(item_code, filters)

	for sale in sales:
		return_qty = flt(returns.get(sale.get("customer")))
		sale["return_qty"] = return_qty
		sale["return_ratio"] = (
			return_qty / flt(sale.get("qty_bought")) * 100
			if flt(sale.get("qty_bought")) else 0
		)

	return sales


def get_return_qty_by_customer(item_code, filters):
	date_conditions = get_date_conditions("DATE(sr.creation)", filters)

	rows = frappe.db.sql(
		f"""
		SELECT
			sr.customer,
			SUM(IFNULL(sri.quantity, 0)) AS return_qty
		FROM `tabLedgix Sales Return Item` sri
		INNER JOIN `tabLedgix Sales Return` sr
			ON sr.name = sri.parent
		WHERE sr.docstatus = 1
			AND sri.item = %(item)s
			{date_conditions}
		GROUP BY sr.customer
		""",
		filters,
		as_dict=True,
	)

	return {row.customer: flt(row.return_qty) for row in rows}


def get_inventory_warnings(item_doc, rows, lots):
	warnings = []
	current_stock = flt(item_doc.get("current_stock"))
	total_sold = sum(flt(row.get("qty_out")) for row in rows if row.get("event_type") == "SALE")
	total_returned = sum(flt(row.get("qty_returned")) for row in rows if row.get("event_type") == "RETURN")

	if current_stock < 0:
		warnings.append(build_warning("Negative Stock", "Current stock is below zero.", "critical"))
	elif current_stock == 0:
		warnings.append(build_warning("Out of Stock", "Current stock is zero.", "warning"))

	for row in rows:
		if row.get("event_type") == "SALE" and row.get("lot_status") == "Allocation Missing":
			warnings.append(build_warning("Allocation Missing", f"Sale {row.get('reference_name')} has no FIFO lot trace.", "warning"))

		if row.get("event_type") == "RETURN" and row.get("lot_status") == "No FIFO Trace":
			warnings.append(build_warning("Return Without Trace", f"Return {row.get('reference_name')} has no restored lot trace.", "warning"))

	if total_sold and total_returned > total_sold:
		warnings.append(build_warning("Return Quantity Exceeds Sold", "Returned quantity is greater than sold quantity in this period.", "critical"))

	for lot in lots:
		if flt(lot.get("remaining_qty")) < 0:
			warnings.append(build_warning("Negative Lot Balance", f"Lot {lot.get('name')} has negative remaining quantity.", "critical"))

		expected_remaining = flt(lot.get("original_qty")) - flt(lot.get("sold_qty")) + flt(lot.get("returned_qty"))
		if abs(expected_remaining - flt(lot.get("remaining_qty"))) > 0.001:
			warnings.append(build_warning("Lot Balance Mismatch", f"Lot {lot.get('name')} remaining quantity differs from its movement totals.", "warning"))

	return warnings


def build_warning(title, message, level="warning"):
	return {
		"title": title,
		"message": message,
		"level": level,
	}


def get_days_since_last_event(rows, event_type=None):
	dates = [
		getdate(row.get("posting_date"))
		for row in rows
		if row.get("posting_date") and (not event_type or row.get("event_type") == event_type)
	]

	if not dates:
		return 0

	return date_diff(getdate(today()), max(dates))


def get_lot_age(purchase_date):
	if not purchase_date:
		return 0

	return max(date_diff(getdate(today()), getdate(purchase_date)), 0)


def is_lot_based_item_doc(item_doc):
	return item_doc.get("tracking_type") == "Lot Based"


def safe_json(value):
	try:
		return json.dumps(value, default=str)
	except Exception:
		return "{}"


# ============================================================
# SNAPSHOTS / INTELLIGENCE
# ============================================================

def get_item_snapshot(item_doc, filters, rows, mode=None):
	mode = mode or get_report_mode()

	if mode == BILLING_ONLY_MODE:
		return {
			"report_mode_snapshot": BILLING_ONLY_MODE,
			"item_code_snapshot": item_doc.name,
			"item_name_snapshot": item_doc.item_name,
		}

	total_purchased = sum(flt(row.get("qty_in")) for row in rows if row.get("event_type") == "PURCHASE")
	total_sold = sum(flt(row.get("qty_out")) for row in rows if row.get("event_type") == "SALE")
	total_returned = sum(flt(row.get("qty_returned")) for row in rows if row.get("event_type") == "RETURN")
	total_revenue = sum(flt(row.get("amount")) for row in rows if row.get("event_type") == "SALE")
	total_purchase_cost = sum(flt(row.get("amount")) for row in rows if row.get("event_type") == "PURCHASE")
	total_profit = sum(flt(row.get("profit")) for row in rows)
	current_stock = flt(item_doc.get("current_stock"))
	expected_profit_per_unit = flt(item_doc.get("selling_price")) - flt(item_doc.get("cost_price"))
	context_metrics = get_context_metrics(rows)

	return {
		"report_mode_snapshot": STRICT_INVENTORY_MODE,
		"item_code_snapshot": item_doc.name,
		"item_name_snapshot": item_doc.item_name,
		"category_snapshot": item_doc.category,
		"current_stock_snapshot": current_stock,
		"minimum_stock_snapshot": flt(item_doc.get("minimum_stock")),
		"cost_price_snapshot": flt(item_doc.get("cost_price")),
		"selling_price_snapshot": flt(item_doc.get("selling_price")),
		"stock_status_snapshot": item_doc.stock_status,
		"total_purchased_snapshot": total_purchased,
		"total_sold_snapshot": total_sold,
		"total_returned_snapshot": total_returned,
		"total_revenue_snapshot": total_revenue,
		"total_purchase_cost_snapshot": total_purchase_cost,
		"total_profit_snapshot": total_profit,
		"profit_margin_snapshot": (total_profit / total_revenue * 100) if total_revenue else 0,
		"avg_buy_rate_snapshot": (total_purchase_cost / total_purchased) if total_purchased else 0,
		"avg_sell_rate_snapshot": (total_revenue / total_sold) if total_sold else 0,
		"remaining_stock_value_snapshot": current_stock * flt(item_doc.get("cost_price")),
		"future_profit_potential_snapshot": current_stock * expected_profit_per_unit,
		"return_ratio_snapshot": (total_returned / total_sold * 100) if total_sold else 0,
		"days_to_stockout_snapshot": get_days_to_stockout(total_sold, current_stock, filters),
		"health_score_snapshot": get_stock_health_state(item_doc, total_sold, total_returned, rows, context_metrics),
		"remaining_lot_qty_snapshot": flt(context_metrics.get("remaining_lot_qty")),
		"open_lots_snapshot": flt(context_metrics.get("open_lots")),
		"days_since_last_sale_snapshot": flt(context_metrics.get("days_since_last_sale")),
		"days_since_last_movement_snapshot": flt(context_metrics.get("days_since_last_movement")),
		"adjustment_count_snapshot": len([row for row in rows if row.get("event_type") == "ADJUSTMENT"]),
	}


def get_days_to_stockout(total_sold, current_stock, filters):
	if not total_sold or not current_stock:
		return 0

	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else getdate(today())

	if not from_date:
		return 0

	days = max(date_diff(to_date, from_date) + 1, 1)
	avg_daily_sales = total_sold / days

	if not avg_daily_sales:
		return 0

	return current_stock / avg_daily_sales


def get_stock_health_state(item_doc, total_sold, total_returned, rows=None, context_metrics=None):
	current_stock = flt(item_doc.get("current_stock"))
	minimum_stock = flt(item_doc.get("minimum_stock"))
	return_ratio = (total_returned / total_sold * 100) if total_sold else 0
	days_since_last_movement = flt((context_metrics or {}).get("days_since_last_movement"))

	if current_stock < 0:
		return "Negative Stock"

	if current_stock == 0:
		return "Out of Stock"

	if minimum_stock and current_stock <= minimum_stock:
		return "Low Stock"

	if current_stock > 0 and days_since_last_movement >= 90:
		return "Aging Inventory"

	if return_ratio >= 20:
		return "High Return Item"

	return "Healthy"


def get_health_score(item_doc, total_sold, total_returned, total_revenue, total_profit):
	return get_stock_health_state(item_doc, total_sold, total_returned)


def get_context_metrics(rows):
	if not rows:
		return {}

	context = rows[0].get("intelligence_context")
	if not context:
		return {}

	try:
		return (json.loads(context) or {}).get("metrics") or {}
	except Exception:
		return {}


def get_report_summary(data, item_doc, filters, mode=None):
	mode = mode or get_report_mode()

	if mode == BILLING_ONLY_MODE:
		total_sold = sum(flt(row.get("qty_out")) for row in data if row.get("event_type") == "SALE")
		total_returned = sum(flt(row.get("qty_returned")) for row in data if row.get("event_type") == "RETURN")
		total_revenue = sum(flt(row.get("amount")) for row in data if row.get("event_type") == "SALE")
		return [
			{"value": total_sold, "label": "Sold", "datatype": "Float"},
			{"value": total_returned, "label": "Returned", "datatype": "Float"},
			{"value": total_revenue, "label": "Revenue", "datatype": "Currency"},
		]

	snapshot = get_item_snapshot(item_doc, filters, data, mode)

	return [
		{"value": snapshot.get("current_stock_snapshot"), "label": "Current Stock", "datatype": "Float"},
		{"value": snapshot.get("total_purchased_snapshot"), "label": "Purchased", "datatype": "Float"},
		{"value": snapshot.get("total_sold_snapshot"), "label": "Sold", "datatype": "Float"},
		{"value": snapshot.get("total_returned_snapshot"), "label": "Returned", "datatype": "Float"},
		{"value": snapshot.get("remaining_lot_qty_snapshot"), "label": "Remaining Lot Qty", "datatype": "Float"},
		{"value": snapshot.get("total_revenue_snapshot"), "label": "Revenue", "datatype": "Currency"},
		{"value": snapshot.get("total_profit_snapshot"), "label": "Profit", "datatype": "Currency"},
		{"value": snapshot.get("profit_margin_snapshot"), "label": "Margin %", "datatype": "Percent"},
		{"value": snapshot.get("open_lots_snapshot"), "label": "Open Lots", "datatype": "Float"},
	]
