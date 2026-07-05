import frappe
from frappe.utils import flt, get_datetime, getdate, now_datetime, today, date_diff
from ledgix_saas.api.security import require_ledgix_manager_or_above


LOT_FIELDS = [
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
]

ALLOCATION_FIELDS = [
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
]

SERIAL_FIELDS = [
	"name",
	"serial_no",
	"item",
	"status",
	"purchase",
	"purchase_item_row",
	"supplier",
	"purchase_date",
	"cost_rate",
	"sale",
	"sale_item_row",
	"customer",
	"sold_date",
	"sales_return",
	"return_item_row",
	"return_date",
	"creation",
]

TRACKING_FILTERS = ("All", "Normal Stock", "Lot Based", "Serial Based")
NORMAL_TRACKING_ALIASES = ("Normal", "Item Based", "Normal Stock")


def normalize_tracking_type(value):
	value = (value or "All").strip()
	if value in NORMAL_TRACKING_ALIASES:
		return "Normal Stock"
	if value in TRACKING_FILTERS:
		return value
	return "All"


def item_tracking_to_ui(value):
	value = (value or "").strip()
	if value in NORMAL_TRACKING_ALIASES:
		return "Normal Stock"
	return value


def get_item_tracking_type(item):
	if not item:
		return None
	return frappe.db.get_value("Ledgix Item", item, "tracking_type")


@frappe.whitelist()
def get_business_intelligence_data(
	item=None,
	from_date=None,
	to_date=None,
	mode="Overview",
	search=None,
	tracking_type="All",
	entity_type=None,
	entity_value=None,
):
	require_ledgix_manager_or_above()

	filters = normalize_filters(
		item=item,
		from_date=from_date,
		to_date=to_date,
		mode=mode,
		search=search,
		tracking_type=tracking_type,
		entity_type=entity_type,
		entity_value=entity_value,
	)

	try:
		if should_use_serial_intelligence(filters):
			return build_serial_data_response(filters)

		if should_use_normal_stock_intelligence(filters):
			return build_normal_stock_data_response(filters)

		if should_use_mixed_intelligence(filters):
			return build_mixed_data_response(filters)

		return build_lot_data_response(filters)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Business Intelligence Center API")
		return empty_response(filters)


def normalize_filters(
	item=None,
	from_date=None,
	to_date=None,
	mode="Overview",
	search=None,
	tracking_type="All",
	entity_type=None,
	entity_value=None,
):
	mode = mode if mode in ("Overview", "Item Intelligence", "Lot Intelligence", "Risk View") else "Overview"
	from_date = getdate(from_date) if from_date else None
	to_date = getdate(to_date) if to_date else None

	if from_date and to_date and from_date > to_date:
		from_date, to_date = to_date, from_date

	tracking_type = normalize_tracking_type(tracking_type)
	entity_type = (entity_type or "").strip().lower() or None
	entity_value = (entity_value or "").strip() or None

	if entity_type == "item" and entity_value:
		item = entity_value

	return {
		"item": item or None,
		"from_date": str(from_date) if from_date else None,
		"to_date": str(to_date) if to_date else None,
		"mode": mode,
		"search": (search or "").strip() or None,
		"tracking_type": tracking_type,
		"entity_type": entity_type,
		"entity_value": entity_value,
	}

def empty_response(filters):
	return {
		"filters": filters,
		"summary": empty_summary(),
		"story": {
			"title": "No activity found",
			"text": "No stock lot activity matched the current filters.",
			"tone": "neutral",
			"signals": [],
		},
		"lots": [],
		"timeline": [],
		"cycle_rows": [],
		"risks": [],
		"meta": {
			"generated_at": str(now_datetime()),
			"row_count": 0,
			"cycle_row_count": 0,
		},
	}


def empty_summary():
	return {
		"current_qty": 0,
		"purchased_qty": 0,
		"remaining_qty": 0,
		"sold_qty": 0,
		"returned_qty": 0,
		"net_sold_qty": 0,
		"gross_revenue": 0,
		"return_amount": 0,
		"net_revenue": 0,
		"gross_profit": 0,
		"return_profit_impact": 0,
		"net_profit": 0,
		"total_cost_sold": 0,
		"margin_percent": 0,
		"sell_through_percent": 0,
		"return_rate_percent": 0,
		"risk_level": "Low",
		"lot_count": 0,
	}


def get_lots(filters):
	lot_filters = {}

	tracking_type = filters.get("tracking_type") or "All"
	entity_type = filters.get("entity_type")
	entity_value = filters.get("entity_value")

	# Normal Stock and Serial Based are handled by their own intelligence branches.
	if tracking_type in ("Normal Stock", "Serial Based"):
		return []

	if entity_type == "lot" and entity_value:
		lot_filters["name"] = entity_value
	elif entity_type == "purchase" and entity_value:
		lot_filters["purchase"] = entity_value
	elif entity_type == "sale" and entity_value:
		lot_names = frappe.get_all(
			"Ledgix Stock Lot Allocation",
			filters={
				"sale": entity_value,
				"is_reversed": 0,
			},
			pluck="stock_lot",
			limit_page_length=5000,
		)
		lot_names = unique(lot_names)
		if not lot_names:
			return []
		lot_filters["name"] = ["in", lot_names]
	elif filters.get("item"):
		lot_filters["item"] = filters.get("item")

	if tracking_type in ("All", "Lot Based"):
		item_tracking_value = "Lot Based"

		item_names = frappe.get_all(
			"Ledgix Item",
			filters={"tracking_type": item_tracking_value},
			pluck="name",
			limit_page_length=5000,
		)

		if not item_names:
			return []

		if lot_filters.get("item") and lot_filters.get("item") not in item_names:
			return []

		if not lot_filters.get("item"):
			lot_filters["item"] = ["in", item_names]

	if filters.get("from_date") and filters.get("to_date"):
		lot_filters["purchase_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		lot_filters["purchase_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		lot_filters["purchase_date"] = ["<=", filters.get("to_date")]

	lots = frappe.get_all(
		"Ledgix Stock Lot",
		filters=lot_filters,
		fields=LOT_FIELDS,
		order_by="purchase_date desc, creation desc",
		limit_page_length=500,
	)

	search = (filters.get("search") or "").lower()
	if search and entity_type not in ("lot", "purchase", "sale"):
		lots = [
			lot for lot in lots
			if search in " ".join(str(lot.get(field) or "") for field in ("name", "item", "supplier", "purchase", "status")).lower()
		]

	return lots

# ============================================================
# SERIAL BASED BUSINESS INTELLIGENCE
# ============================================================

def should_use_serial_intelligence(filters):
	if filters.get("tracking_type") == "Serial Based" or filters.get("entity_type") == "serial":
		return True

	if filters.get("entity_type") == "item" and filters.get("item"):
		return get_item_tracking_type(filters.get("item")) == "Serial Based"

	return False


def should_use_normal_stock_intelligence(filters):
	if filters.get("entity_type") in ("lot", "serial"):
		return False

	if filters.get("tracking_type") == "Normal Stock":
		return True

	if filters.get("entity_type") == "item" and filters.get("item"):
		return get_item_tracking_type(filters.get("item")) == "Normal"

	return False


def should_use_mixed_intelligence(filters):
	return (
		filters.get("tracking_type") == "All"
		and filters.get("entity_type") not in ("item", "lot", "serial")
	)


def build_serial_data_response(filters):
	serials = get_serials(filters)
	submitted = get_serial_reference_maps(serials)
	items = get_items_by_names(unique([row.item for row in serials if row.item]))

	serial_rows = build_serial_rows(serials, submitted, items, filters)
	timeline = build_serial_timeline(serials, submitted, items, filters)
	summary = build_serial_summary(serial_rows, filters)
	story = build_serial_story(summary, serial_rows, filters)
	risks = build_serial_risks(serials, submitted)

	return {
		"filters": filters,
		"summary": summary,
		"story": story,
		"lots": [],
		"timeline": timeline,
		"cycle_rows": timeline,
		"risks": risks,
		"meta": {
			"generated_at": str(now_datetime()),
			"row_count": len(serial_rows),
			"cycle_row_count": len(timeline),
		},
	}


def build_lot_data_response(filters):
	lots = get_lots(filters)
	allocations = get_allocations(lots)
	submitted = get_submitted_reference_maps(lots, allocations)
	items = get_item_map(lots, allocations)

	lot_rows = build_lot_rows(lots, allocations, submitted, items, filters)
	timeline = build_timeline(lots, allocations, submitted, items, filters)
	cycle_rows = build_cycle_rows(lots, allocations, submitted, items, filters)
	risks = build_risks(lots, allocations, submitted, items, lot_rows)
	summary = build_summary(lot_rows, items, filters)
	story = build_story(summary, lot_rows, filters)

	return {
		"filters": filters,
		"summary": summary,
		"story": story,
		"lots": lot_rows,
		"timeline": timeline,
		"cycle_rows": cycle_rows,
		"risks": risks,
		"meta": {
			"generated_at": str(now_datetime()),
			"row_count": len(lot_rows),
			"cycle_row_count": len(cycle_rows),
		},
	}


def get_serials(filters):
	serial_filters = {}

	entity_type = filters.get("entity_type")
	entity_value = filters.get("entity_value")

	if entity_type == "serial" and entity_value:
		serial_filters["name"] = entity_value
	elif entity_type == "purchase" and entity_value:
		serial_filters["purchase"] = entity_value
	elif entity_type == "sale" and entity_value:
		serial_filters["sale"] = entity_value
	elif filters.get("item"):
		serial_filters["item"] = filters.get("item")
	elif filters.get("tracking_type") == "Serial Based":
		serial_item_names = frappe.get_all(
			"Ledgix Item",
			filters={"tracking_type": "Serial Based"},
			pluck="name",
			limit_page_length=5000,
		)

		if not serial_item_names:
			return []

		serial_filters["item"] = ["in", serial_item_names]

	serials = frappe.get_all(
		"Ledgix Stock Serial",
		filters=serial_filters,
		fields=SERIAL_FIELDS,
		order_by="purchase_date desc, creation desc",
		limit_page_length=1000,
	)

	if entity_type == "serial" and entity_value:
		serials = [
			row for row in serials
			if row.name == entity_value or row.serial_no == entity_value
		]

	search = (filters.get("search") or "").lower()
	if search and entity_type != "serial":
		serials = [
			row for row in serials
			if search in " ".join(str(row.get(field) or "") for field in (
				"name",
				"serial_no",
				"item",
				"status",
				"purchase",
				"supplier",
				"sale",
				"customer",
				"sales_return",
			)).lower()
		]

	serials = [
		row for row in serials
		if serial_matches_date_range(row, filters)
	]

	return serials


def serial_matches_date_range(row, filters):
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else None

	if not from_date and not to_date:
		return True

	dates = []
	for fieldname in ("purchase_date", "sold_date", "return_date"):
		value = row.get(fieldname)
		if value:
			dates.append(getdate(value))

	if not dates:
		return False

	for value in dates:
		if from_date and value < from_date:
			continue
		if to_date and value > to_date:
			continue
		return True

	return False


def get_serial_reference_maps(serials):
	purchase_names = unique([row.purchase for row in serials if row.purchase])
	sale_names = unique([row.sale for row in serials if row.sale])
	return_names = unique([row.sales_return for row in serials if row.sales_return])

	return_map = get_submitted_docs(
		"Ledgix Sales Return",
		return_names,
		["name", "original_sale", "customer", "docstatus", "creation"],
	)

	sale_names = unique(sale_names + [row.original_sale for row in return_map.values() if row.get("original_sale")])

	return {
		"purchases": get_submitted_docs("Ledgix Purchase", purchase_names, ["name", "supplier", "purchase_date", "invoice_number", "docstatus"]),
		"sales": get_submitted_docs("Ledgix Sale", sale_names, ["name", "sale_date", "invoice_number", "customer", "docstatus"]),
		"returns": return_map,
	}


def get_items_by_names(item_names):
	item_names = unique(item_names)
	if not item_names:
		return {}

	rows = frappe.get_all(
		"Ledgix Item",
		filters={"name": ["in", item_names]},
		fields=[
			"name",
			"item_code",
			"item_name",
			"barcode",
			"category",
			"unit",
			"current_stock",
			"minimum_stock",
			"stock_status",
			"active",
			"sku",
			"tracking_type",
		],
		limit_page_length=len(item_names),
	)

	return {row.name: row for row in rows}


def build_serial_rows(serials, submitted, items, filters):
	rows = []

	for serial in serials:
		item = items.get(serial.item, frappe._dict())
		purchase = submitted["purchases"].get(serial.purchase, frappe._dict())
		sale = submitted["sales"].get(serial.sale, frappe._dict())
		return_doc = submitted["returns"].get(serial.sales_return, frappe._dict())

		sold_qty = 1 if serial.sale else 0
		returned_qty = 1 if serial.sales_return or serial.status == "Returned" else 0
		remaining_qty = 1 if serial.status in ("Available", "Returned") else 0
		net_sold_qty = max(sold_qty - returned_qty, 0)

		rows.append({
			"serial_no": serial.serial_no or serial.name,
			"lot_number": serial.serial_no or serial.name,
			"item": serial.item,
			"item_name": item.get("item_name") or serial.item,
			"supplier": serial.supplier or purchase.get("supplier"),
			"customer": serial.customer or sale.get("customer") or return_doc.get("customer"),
			"purchase": serial.purchase,
			"sale": serial.sale,
			"sales_return": serial.sales_return,
			"purchase_date": serial.purchase_date or purchase.get("purchase_date"),
			"sold_date": serial.sold_date or sale.get("sale_date"),
			"return_date": serial.return_date or return_doc.get("creation"),
			"purchased_qty": 1,
			"sold_qty": sold_qty,
			"returned_qty": returned_qty,
			"remaining_qty": remaining_qty,
			"net_sold_qty": net_sold_qty,
			"cost_rate": flt(serial.cost_rate),
			"total_cost": flt(serial.cost_rate),
			"gross_revenue": 0,
			"return_amount": 0,
			"net_revenue": 0,
			"gross_profit": 0,
			"profit": 0,
			"margin_percent": 0,
			"sell_through_percent": 100 if sold_qty else 0,
			"return_rate_percent": 100 if returned_qty and sold_qty else 0,
			"tracking_type": "Serial Based",
			"serial_status": serial.status,
			"lot_status": serial.status or "Available",
			"reference_status": "Submitted" if purchase else "Missing or Draft",
		})

	return rows


def build_serial_timeline(serials, submitted, items, filters):
	events = []

	for serial in serials:
		serial_no = serial.serial_no or serial.name
		item = items.get(serial.item, frappe._dict())
		item_name = item.get("item_name") or serial.item or ""
		purchase = submitted["purchases"].get(serial.purchase, frappe._dict())

		if serial.purchase or serial.purchase_date:
			events.append({
				"date": serial.purchase_date or purchase.get("purchase_date") or serial.creation,
				"row_type": "Mother",
				"event_type": "Purchase",
				"cycle_status": "Purchase",
				"lot_status": serial.status or "",
				"lot_number": serial_no,
				"serial_no": serial_no,
				"item": serial.item or "",
				"item_name": item_name,
				"purchase": serial.purchase or "",
				"purchase_invoice": purchase.get("invoice_number") or "",
				"purchase_date": serial.purchase_date or purchase.get("purchase_date") or "",
				"sale": "",
				"sale_invoice": "",
				"sale_date": "",
				"sales_return": "",
				"return_date": "",
				"reference": serial.purchase or serial_no,
				"supplier": serial.supplier or purchase.get("supplier") or "",
				"customer": "",
				"purchased_qty": 1,
				"sale_qty": 0,
				"return_qty": 0,
				"net_sold_qty": 0,
				"current_lot_qty": 1,
				"unit_cost": flt(serial.cost_rate),
				"cost_rate": flt(serial.cost_rate),
				"sale_rate": 0,
				"total_cost": flt(serial.cost_rate),
				"selling_amount": 0,
				"return_amount": 0,
				"profit": 0,
				"loss": 0,
				"tracking_type": "Serial Based",
				"serial_status": serial.status or "",
				"reference_status": "Submitted" if purchase else "Missing or Draft",
				"_sort_creation": serial.creation,
				"_sort_name": serial.name,
			})

		sale = submitted["sales"].get(serial.sale, frappe._dict())
		if serial.sale or serial.sold_date:
			events.append({
				"date": serial.sold_date or sale.get("sale_date") or serial.creation,
				"row_type": "Child",
				"event_type": "Sale",
				"cycle_status": "Sale",
				"lot_status": serial.status or "",
				"lot_number": serial_no,
				"serial_no": serial_no,
				"item": serial.item or "",
				"item_name": item_name,
				"purchase": serial.purchase or "",
				"purchase_invoice": purchase.get("invoice_number") or "",
				"purchase_date": serial.purchase_date or purchase.get("purchase_date") or "",
				"sale": serial.sale or "",
				"sale_invoice": sale.get("invoice_number") or "",
				"sale_date": serial.sold_date or sale.get("sale_date") or "",
				"sales_return": "",
				"return_date": "",
				"reference": serial.sale or serial_no,
				"supplier": serial.supplier or purchase.get("supplier") or "",
				"customer": serial.customer or sale.get("customer") or "",
				"purchased_qty": 1,
				"sale_qty": 1,
				"return_qty": 0,
				"net_sold_qty": 1,
				"current_lot_qty": 0,
				"unit_cost": flt(serial.cost_rate),
				"cost_rate": flt(serial.cost_rate),
				"sale_rate": 0,
				"total_cost": flt(serial.cost_rate),
				"selling_amount": 0,
				"return_amount": 0,
				"profit": 0,
				"loss": 0,
				"tracking_type": "Serial Based",
				"serial_status": serial.status or "",
				"reference_status": "Submitted" if sale else "Missing or Draft",
				"_sort_creation": serial.creation,
				"_sort_name": serial.name,
			})

		return_doc = submitted["returns"].get(serial.sales_return, frappe._dict())
		if serial.sales_return or serial.return_date or serial.status == "Returned":
			events.append({
				"date": serial.return_date or return_doc.get("creation") or serial.creation,
				"row_type": "Child",
				"event_type": "Return",
				"cycle_status": "Return",
				"lot_status": serial.status or "",
				"lot_number": serial_no,
				"serial_no": serial_no,
				"item": serial.item or "",
				"item_name": item_name,
				"purchase": serial.purchase or "",
				"purchase_invoice": purchase.get("invoice_number") or "",
				"purchase_date": serial.purchase_date or purchase.get("purchase_date") or "",
				"sale": serial.sale or return_doc.get("original_sale") or "",
				"sale_invoice": sale.get("invoice_number") or "",
				"sale_date": serial.sold_date or sale.get("sale_date") or "",
				"sales_return": serial.sales_return or "",
				"return_date": serial.return_date or return_doc.get("creation") or "",
				"reference": serial.sales_return or serial_no,
				"supplier": serial.supplier or purchase.get("supplier") or "",
				"customer": serial.customer or sale.get("customer") or return_doc.get("customer") or "",
				"purchased_qty": 1,
				"sale_qty": 0,
				"return_qty": 1,
				"net_sold_qty": 0,
				"current_lot_qty": 1,
				"unit_cost": flt(serial.cost_rate),
				"cost_rate": flt(serial.cost_rate),
				"sale_rate": 0,
				"total_cost": flt(serial.cost_rate),
				"selling_amount": 0,
				"return_amount": 0,
				"profit": 0,
				"loss": 0,
				"tracking_type": "Serial Based",
				"serial_status": serial.status or "",
				"reference_status": "Submitted" if return_doc else "Missing or Draft",
				"_sort_creation": serial.creation,
				"_sort_name": serial.name,
			})

		if serial.status == "Cancelled":
			events.append({
				"date": serial.creation,
				"row_type": "Child",
				"event_type": "Cancel",
				"cycle_status": "Cancel",
				"lot_status": serial.status or "",
				"lot_number": serial_no,
				"serial_no": serial_no,
				"item": serial.item or "",
				"item_name": item_name,
				"purchase": serial.purchase or "",
				"purchase_invoice": purchase.get("invoice_number") or "",
				"purchase_date": serial.purchase_date or purchase.get("purchase_date") or "",
				"sale": serial.sale or "",
				"sale_invoice": sale.get("invoice_number") or "",
				"sale_date": serial.sold_date or sale.get("sale_date") or "",
				"sales_return": serial.sales_return or "",
				"return_date": serial.return_date or "",
				"reference": serial_no,
				"supplier": serial.supplier or purchase.get("supplier") or "",
				"customer": serial.customer or sale.get("customer") or "",
				"purchased_qty": 1,
				"sale_qty": 0,
				"return_qty": 0,
				"net_sold_qty": 0,
				"current_lot_qty": 0,
				"unit_cost": flt(serial.cost_rate),
				"cost_rate": flt(serial.cost_rate),
				"sale_rate": 0,
				"total_cost": 0,
				"selling_amount": 0,
				"return_amount": 0,
				"profit": 0,
				"loss": 0,
				"tracking_type": "Serial Based",
				"serial_status": serial.status or "",
				"reference_status": "Cancelled",
				"_sort_creation": serial.creation,
				"_sort_name": serial.name,
			})

	events.sort(key=lambda row: (
		normalize_datetime(row.get("date")),
		timeline_serial_rank(row),
		row.get("_sort_creation") or "",
		row.get("_sort_name") or "",
	))

	cleaned_events = []
	for row in events[:500]:
		cleaned = clean_cycle_row(row)
		cleaned["serial_no"] = row.get("serial_no") or ""
		cleaned["tracking_type"] = "Serial Based"
		cleaned["serial_status"] = row.get("serial_status") or ""
		cleaned_events.append(cleaned)

	return cleaned_events


def timeline_serial_rank(row):
	event = row.get("cycle_status") or row.get("event_type")
	if event == "Purchase":
		return 0
	if event == "Sale":
		return 1
	if event == "Return":
		return 2
	if event == "Cancel":
		return 3
	return 9


def build_serial_summary(serial_rows, filters):
	summary = empty_summary()

	for row in serial_rows:
		summary["purchased_qty"] += flt(row.get("purchased_qty"))
		summary["remaining_qty"] += flt(row.get("remaining_qty"))
		summary["sold_qty"] += flt(row.get("sold_qty"))
		summary["returned_qty"] += flt(row.get("returned_qty"))
		summary["net_sold_qty"] += flt(row.get("net_sold_qty"))
		summary["total_cost_sold"] += flt(row.get("cost_rate")) if flt(row.get("net_sold_qty")) else 0

	summary["current_qty"] = summary["remaining_qty"]
	summary["lot_count"] = len(serial_rows)
	summary["sell_through_percent"] = (summary["net_sold_qty"] / summary["purchased_qty"] * 100) if summary["purchased_qty"] > 0 else 0
	summary["return_rate_percent"] = (summary["returned_qty"] / summary["sold_qty"] * 100) if summary["sold_qty"] > 0 else 0
	summary["risk_level"] = "Medium" if summary["return_rate_percent"] >= 30 else "Low"

	return summary


def build_serial_story(summary, serial_rows, filters):
	if not serial_rows:
		return {
			"title": "No serial activity found",
			"text": "No serial-based stock activity matched the current filters.",
			"tone": "neutral",
			"signals": [],
		}

	signals = [
		f"Serials {len(serial_rows)}",
		f"Available {summary['remaining_qty']:.0f}",
		f"Sold {summary['net_sold_qty']:.0f}",
	]

	if summary["return_rate_percent"] > 0:
		signals.append(f"Return rate {summary['return_rate_percent']:.1f}%")

	return {
		"title": "Serial Lifecycle Story",
		"text": "Serial-based inventory is now shown by individual serial lifecycle: purchase, sale, return, and cancelled status where available.",
		"tone": "neutral" if summary["risk_level"] == "Low" else "warning",
		"signals": signals,
	}


def build_serial_risks(serials, submitted):
	risks = []

	for serial in serials:
		serial_no = serial.serial_no or serial.name

		if not serial.serial_no:
			add_risk(risks, "Warning", "Missing serial number", f"Serial record {serial.name} has no serial number value.", serial.name)

		if serial.purchase and serial.purchase not in submitted["purchases"]:
			add_risk(risks, "Warning", "Serial purchase not submitted", f"Serial {serial_no} is linked to a missing or unsubmitted purchase.", serial_no)

		if serial.sale and serial.sale not in submitted["sales"]:
			add_risk(risks, "Warning", "Serial sale not submitted", f"Serial {serial_no} is linked to a missing or unsubmitted sale.", serial_no)

		if serial.sales_return and serial.sales_return not in submitted["returns"]:
			add_risk(risks, "Warning", "Serial return not submitted", f"Serial {serial_no} is linked to a missing or unsubmitted return.", serial_no)

		if serial.status == "Sold" and not serial.sale:
			add_risk(risks, "Warning", "Sold serial without sale", f"Serial {serial_no} is marked Sold but has no sale reference.", serial_no)

	return risks[:100]



# ============================================================
# NORMAL STOCK BUSINESS INTELLIGENCE
# ============================================================

def build_normal_stock_data_response(filters):
	items = get_normal_stock_item_map(filters)
	if not items:
		response = empty_response(filters)
		response["story"] = {
			"title": "No normal stock found",
			"text": "No quantity-only Normal Stock items matched the current filters.",
			"tone": "neutral",
			"signals": [],
		}
		return response

	item_names = list(items.keys())
	purchases = get_normal_purchase_rows(item_names, filters)
	sales = get_normal_sale_rows(item_names, filters)
	returns = get_normal_return_rows(item_names, filters)

	if filters.get("entity_type") in ("purchase", "sale"):
		event_items = unique(
			[row.item for row in purchases if row.item]
			+ [row.item for row in sales if row.item]
			+ [row.item for row in returns if row.item]
		)
		items = {item_name: items[item_name] for item_name in event_items if item_name in items}

	timeline = build_normal_stock_timeline(purchases, sales, returns, items)
	summary = build_normal_stock_summary(purchases, sales, returns, items, filters)
	story = build_normal_stock_story(summary, timeline, filters)
	risks = build_normal_stock_risks(items, summary, timeline)

	return {
		"filters": filters,
		"summary": summary,
		"story": story,
		"lots": [],
		"timeline": timeline,
		"cycle_rows": timeline,
		"risks": risks,
		"meta": {
			"generated_at": str(now_datetime()),
			"row_count": len(items),
			"cycle_row_count": len(timeline),
		},
	}


def get_normal_stock_item_map(filters):
	if filters.get("item"):
		rows = frappe.get_all(
			"Ledgix Item",
			filters={"name": filters.get("item"), "tracking_type": "Normal"},
			fields=[
				"name",
				"item_code",
				"item_name",
				"barcode",
				"category",
				"unit",
				"current_stock",
				"minimum_stock",
				"stock_status",
				"active",
				"sku",
				"tracking_type",
			],
			limit_page_length=1,
		)
		return {row.name: row for row in rows}

	item_filters = {"tracking_type": "Normal"}
	rows = frappe.get_all(
		"Ledgix Item",
		filters=item_filters,
		fields=[
			"name",
			"item_code",
			"item_name",
			"barcode",
			"category",
			"unit",
			"current_stock",
			"minimum_stock",
			"stock_status",
			"active",
			"sku",
			"tracking_type",
		],
		order_by="modified desc",
		limit_page_length=5000,
	)

	search = (filters.get("search") or "").lower()
	if search and filters.get("entity_type") not in ("purchase", "sale"):
		rows = [
			row for row in rows
			if search in " ".join(str(row.get(field) or "") for field in ("name", "item_code", "item_name", "sku", "barcode", "stock_status")).lower()
		]

	return {row.name: row for row in rows}


def get_normal_purchase_rows(item_names, filters):
	if not item_names:
		return []
	if filters.get("entity_type") == "sale":
		return []

	conditions = ["p.docstatus = 1", "pi.item IN %(item_names)s"]
	params = {"item_names": tuple(item_names)}

	if filters.get("entity_type") == "purchase" and filters.get("entity_value"):
		conditions.append("p.name = %(purchase)s")
		params["purchase"] = filters.get("entity_value")

	append_sql_date_condition(conditions, params, "p.purchase_date", filters)
	append_sql_search_condition(
		conditions,
		params,
		filters,
		("p.name", "p.supplier", "p.invoice_number", "pi.item"),
		allow_for_entities=(None, "item"),
	)

	return frappe.db.sql(f"""
		SELECT
			pi.name AS row_name,
			pi.parent AS purchase,
			p.supplier AS supplier,
			p.purchase_date AS purchase_date,
			p.invoice_number AS purchase_invoice,
			pi.item AS item,
			pi.quantity AS quantity,
			pi.rate AS rate,
			pi.amount AS amount,
			pi.total_amount AS total_amount,
			pi.creation AS creation
		FROM `tabLedgix Purchase Item` pi
		INNER JOIN `tabLedgix Purchase` p ON p.name = pi.parent
		WHERE {' AND '.join(conditions)}
		ORDER BY p.purchase_date ASC, pi.creation ASC
		LIMIT 2000
	""", params, as_dict=True)


def get_normal_sale_rows(item_names, filters):
	if not item_names:
		return []
	if filters.get("entity_type") == "purchase":
		return []

	conditions = ["s.docstatus = 1", "si.item IN %(item_names)s"]
	params = {"item_names": tuple(item_names)}

	if filters.get("entity_type") == "sale" and filters.get("entity_value"):
		conditions.append("s.name = %(sale)s")
		params["sale"] = filters.get("entity_value")

	append_sql_date_condition(conditions, params, "s.sale_date", filters)
	append_sql_search_condition(
		conditions,
		params,
		filters,
		("s.name", "s.customer", "s.invoice_number", "si.item"),
		allow_for_entities=(None, "item"),
	)

	return frappe.db.sql(f"""
		SELECT
			si.name AS row_name,
			si.parent AS sale,
			s.customer AS customer,
			s.sale_date AS sale_date,
			s.invoice_number AS sale_invoice,
			si.item AS item,
			si.quantity AS quantity,
			si.rate AS rate,
			si.amount AS amount,
			si.cost_price AS cost_price,
			si.item_total_profit AS item_total_profit,
			si.creation AS creation
		FROM `tabLedgix Sale Item` si
		INNER JOIN `tabLedgix Sale` s ON s.name = si.parent
		WHERE {' AND '.join(conditions)}
		ORDER BY s.sale_date ASC, si.creation ASC
		LIMIT 2000
	""", params, as_dict=True)


def get_normal_return_rows(item_names, filters):
	if not item_names:
		return []
	if filters.get("entity_type") == "purchase":
		return []

	conditions = ["r.docstatus = 1", "ri.item IN %(item_names)s"]
	params = {"item_names": tuple(item_names)}

	if filters.get("entity_type") == "sale" and filters.get("entity_value"):
		conditions.append("r.original_sale = %(sale)s")
		params["sale"] = filters.get("entity_value")

	append_sql_date_condition(conditions, params, "DATE(r.creation)", filters)
	append_sql_search_condition(
		conditions,
		params,
		filters,
		("r.name", "r.original_sale", "r.customer", "ri.item"),
		allow_for_entities=(None, "item"),
	)

	return frappe.db.sql(f"""
		SELECT
			ri.name AS row_name,
			ri.parent AS sales_return,
			r.original_sale AS original_sale,
			r.customer AS customer,
			DATE(r.creation) AS return_date,
			ri.item AS item,
			ri.quantity AS quantity,
			ri.rate AS rate,
			ri.amount AS amount,
			ri.cost_price AS cost_price,
			ri.item_total_profit AS item_total_profit,
			ri.creation AS creation
		FROM `tabLedgix Sales Return Item` ri
		INNER JOIN `tabLedgix Sales Return` r ON r.name = ri.parent
		WHERE {' AND '.join(conditions)}
		ORDER BY r.creation ASC, ri.creation ASC
		LIMIT 2000
	""", params, as_dict=True)


def append_sql_date_condition(conditions, params, fieldname, filters):
	if filters.get("from_date") and filters.get("to_date"):
		conditions.append(f"{fieldname} BETWEEN %(from_date)s AND %(to_date)s")
		params["from_date"] = filters.get("from_date")
		params["to_date"] = filters.get("to_date")
	elif filters.get("from_date"):
		conditions.append(f"{fieldname} >= %(from_date)s")
		params["from_date"] = filters.get("from_date")
	elif filters.get("to_date"):
		conditions.append(f"{fieldname} <= %(to_date)s")
		params["to_date"] = filters.get("to_date")


def append_sql_search_condition(conditions, params, filters, fields, allow_for_entities=(None, "item")):
	search = (filters.get("search") or "").strip()
	entity_type = filters.get("entity_type")
	if not search or entity_type not in allow_for_entities:
		return

	params["search"] = f"%{search}%"
	conditions.append("(" + " OR ".join(f"{field} LIKE %(search)s" for field in fields) + ")")


def build_normal_stock_timeline(purchases, sales, returns, items):
	rows = []
	sale_map = {row.sale: row for row in sales if row.get("sale")}

	for row in purchases:
		item = items.get(row.item, frappe._dict())
		qty = flt(row.quantity)
		rate = flt(row.rate)
		rows.append({
			"date": row.purchase_date or row.creation,
			"row_type": "Mother",
			"event_type": "Purchase",
			"cycle_status": "Purchase",
			"lot_status": item.get("stock_status") or "Normal Stock",
			"item": row.item or "",
			"item_name": item.get("item_name") or row.item or "",
			"lot_number": row.item or "",
			"purchase": row.purchase or "",
			"purchase_invoice": row.purchase_invoice or "",
			"purchase_date": row.purchase_date or "",
			"sale": "",
			"sale_invoice": "",
			"sale_date": "",
			"sales_return": "",
			"return_date": "",
			"reference": row.purchase or row.row_name or "",
			"supplier": row.supplier or "",
			"customer": "",
			"purchased_qty": qty,
			"sale_qty": 0,
			"return_qty": 0,
			"net_sold_qty": 0,
			"current_lot_qty": 0,
			"unit_cost": rate,
			"cost_rate": rate,
			"sale_rate": 0,
			"total_cost": flt(row.total_amount) or flt(row.amount) or qty * rate,
			"selling_amount": 0,
			"return_amount": 0,
			"profit": 0,
			"loss": 0,
			"tracking_type": "Normal Stock",
			"reference_status": "Submitted",
			"_sort_creation": row.creation,
			"_sort_name": row.row_name,
		})

	for row in sales:
		item = items.get(row.item, frappe._dict())
		qty = flt(row.quantity)
		rate = flt(row.rate)
		cost_rate = flt(row.cost_price)
		profit = flt(row.item_total_profit)
		rows.append({
			"date": row.sale_date or row.creation,
			"row_type": "Child",
			"event_type": "Sale",
			"cycle_status": "Sale",
			"lot_status": item.get("stock_status") or "Normal Stock",
			"item": row.item or "",
			"item_name": item.get("item_name") or row.item or "",
			"lot_number": row.item or "",
			"purchase": "",
			"purchase_invoice": "",
			"purchase_date": "",
			"sale": row.sale or "",
			"sale_invoice": row.sale_invoice or "",
			"sale_date": row.sale_date or "",
			"sales_return": "",
			"return_date": "",
			"reference": row.sale or row.row_name or "",
			"supplier": "",
			"customer": row.customer or "",
			"purchased_qty": 0,
			"sale_qty": qty,
			"return_qty": 0,
			"net_sold_qty": qty,
			"current_lot_qty": 0,
			"unit_cost": cost_rate,
			"cost_rate": cost_rate,
			"sale_rate": rate,
			"total_cost": qty * cost_rate,
			"selling_amount": flt(row.amount) or qty * rate,
			"return_amount": 0,
			"profit": profit,
			"loss": abs(profit) if profit < 0 else 0,
			"tracking_type": "Normal Stock",
			"reference_status": "Submitted",
			"_sort_creation": row.creation,
			"_sort_name": row.row_name,
		})

	for row in returns:
		item = items.get(row.item, frappe._dict())
		sale = sale_map.get(row.original_sale, frappe._dict())
		qty = flt(row.quantity)
		rate = flt(row.rate)
		cost_rate = flt(row.cost_price)
		profit_impact = -abs(flt(row.item_total_profit))
		rows.append({
			"date": row.return_date or row.creation,
			"row_type": "Child",
			"event_type": "Return",
			"cycle_status": "Return",
			"lot_status": item.get("stock_status") or "Normal Stock",
			"item": row.item or "",
			"item_name": item.get("item_name") or row.item or "",
			"lot_number": row.item or "",
			"purchase": "",
			"purchase_invoice": "",
			"purchase_date": "",
			"sale": row.original_sale or "",
			"sale_invoice": sale.get("sale_invoice") or "",
			"sale_date": sale.get("sale_date") or "",
			"sales_return": row.sales_return or "",
			"return_date": row.return_date or "",
			"reference": row.sales_return or row.original_sale or row.row_name or "",
			"supplier": "",
			"customer": row.customer or sale.get("customer") or "",
			"purchased_qty": 0,
			"sale_qty": 0,
			"return_qty": qty,
			"net_sold_qty": 0,
			"current_lot_qty": 0,
			"unit_cost": cost_rate,
			"cost_rate": cost_rate,
			"sale_rate": rate,
			"total_cost": qty * cost_rate,
			"selling_amount": 0,
			"return_amount": flt(row.amount) or qty * rate,
			"profit": profit_impact,
			"loss": abs(profit_impact) if profit_impact < 0 else 0,
			"tracking_type": "Normal Stock",
			"reference_status": "Submitted",
			"_sort_creation": row.creation,
			"_sort_name": row.row_name,
		})

	rows.sort(key=lambda row: (normalize_datetime(row.get("date")), normal_event_rank(row.get("event_type")), row.get("_sort_creation") or row.get("_sort_name") or ""))
	apply_normal_running_qty(rows)
	return [clean_normal_row(row) for row in rows[:500]]


def normal_event_rank(event):
	if event == "Purchase":
		return 0
	if event == "Sale":
		return 1
	if event == "Return":
		return 2
	return 9


def apply_normal_running_qty(rows):
	balances = {}
	for row in rows:
		item = row.get("item")
		if not item:
			continue
		current = balances.get(item, 0)
		if row.get("event_type") == "Purchase":
			current += flt(row.get("purchased_qty"))
		elif row.get("event_type") == "Sale":
			current -= flt(row.get("sale_qty"))
		elif row.get("event_type") == "Return":
			current += flt(row.get("return_qty"))
		if abs(current) < 0.0001:
			current = 0
		balances[item] = current
		row["current_lot_qty"] = current


def clean_normal_row(row):
	cleaned = clean_cycle_row(row)
	cleaned["tracking_type"] = "Normal Stock"
	return cleaned


def build_normal_stock_summary(purchases, sales, returns, items, filters):
	summary = empty_summary()
	summary["current_qty"] = sum(flt(item.get("current_stock")) for item in items.values())
	summary["remaining_qty"] = summary["current_qty"]
	summary["purchased_qty"] = sum(flt(row.quantity) for row in purchases)
	summary["sold_qty"] = sum(flt(row.quantity) for row in sales)
	summary["returned_qty"] = sum(flt(row.quantity) for row in returns)
	summary["net_sold_qty"] = summary["sold_qty"] - summary["returned_qty"]
	summary["gross_revenue"] = sum(flt(row.amount) or flt(row.quantity) * flt(row.rate) for row in sales)
	summary["return_amount"] = sum(flt(row.amount) or flt(row.quantity) * flt(row.rate) for row in returns)
	summary["net_revenue"] = summary["gross_revenue"] - summary["return_amount"]
	summary["gross_profit"] = sum(flt(row.item_total_profit) for row in sales)
	summary["return_profit_impact"] = -abs(sum(flt(row.item_total_profit) for row in returns))
	summary["net_profit"] = summary["gross_profit"] + summary["return_profit_impact"]
	summary["total_cost_sold"] = sum(flt(row.quantity) * flt(row.cost_price) for row in sales)
	summary["margin_percent"] = (summary["net_profit"] / summary["net_revenue"] * 100) if summary["net_revenue"] > 0 else 0
	summary["sell_through_percent"] = (summary["net_sold_qty"] / summary["purchased_qty"] * 100) if summary["purchased_qty"] > 0 else 0
	summary["return_rate_percent"] = (summary["returned_qty"] / summary["sold_qty"] * 100) if summary["sold_qty"] > 0 else 0
	summary["lot_count"] = len(items)
	summary["risk_level"] = get_normal_stock_risk_level(summary, items)
	return summary


def get_normal_stock_risk_level(summary, items):
	if summary["net_profit"] < 0 or summary["margin_percent"] < 0:
		return "Critical"
	if summary["return_rate_percent"] >= 30:
		return "High"
	if any((item.get("stock_status") or "") == "Out of Stock" for item in items.values()):
		return "Medium"
	if any((item.get("stock_status") or "") == "Low Stock" for item in items.values()):
		return "Medium"
	return "Low"


def build_normal_stock_story(summary, timeline, filters):
	signals = [
		f"Current qty {summary['current_qty']:.0f}",
		f"Sold {summary['net_sold_qty']:.0f}",
	]
	if summary["margin_percent"] != 0:
		signals.append(f"Margin {summary['margin_percent']:.1f}%")
	if summary["return_rate_percent"] > 0:
		signals.append(f"Return rate {summary['return_rate_percent']:.1f}%")

	scope = filters.get("item") or "Normal Stock"
	if not timeline:
		text = "No quantity-only stock activity matched the current filters."
		tone = "neutral"
	elif summary["net_profit"] < 0 or summary["margin_percent"] < 0:
		text = f"{scope} is showing loss risk. Review pricing, cost price, and returns."
		tone = "critical"
	elif summary["return_rate_percent"] >= 30:
		text = f"{scope} has high return activity. Review sale quality, cashier workflow, or customer issue patterns."
		tone = "warning"
	else:
		text = f"{scope} is using quantity-only tracking. Timeline shows purchases, sales, and returns without lot or serial identity rows."
		tone = "neutral"

	return {
		"title": "Normal Stock Story",
		"text": text,
		"tone": tone,
		"signals": signals,
	}


def build_normal_stock_risks(items, summary, timeline):
	risks = []
	for item in items.values():
		status = item.get("stock_status") or ""
		if status == "Out of Stock":
			add_risk(risks, "Warning", "Normal stock out of stock", f"{item.name} has no available quantity.", item.name)
		elif status == "Low Stock":
			add_risk(risks, "Info", "Normal stock low", f"{item.name} is below or near minimum stock.", item.name)

	if summary["net_profit"] < 0:
		add_risk(risks, "Critical", "Negative normal stock profit", "Normal Stock activity has negative realized profit in the selected range.", None)
	if summary["return_rate_percent"] >= 30:
		add_risk(risks, "Warning", "High normal stock return rate", f"Normal Stock return rate is {summary['return_rate_percent']:.2f}%.", None)

	return risks[:100]


def build_mixed_data_response(filters):
	lot_response = build_lot_data_response(dict(filters))

	normal_filters = dict(filters)
	normal_filters["tracking_type"] = "Normal Stock"
	normal_response = build_normal_stock_data_response(normal_filters)

	serial_filters = dict(filters)
	serial_filters["tracking_type"] = "Serial Based"
	serial_response = build_serial_data_response(serial_filters)

	responses = [normal_response, lot_response, serial_response]
	timeline = []
	for response in responses:
		timeline.extend(response.get("cycle_rows") or response.get("timeline") or [])
	timeline.sort(key=lambda row: normalize_datetime(row.get("date") or row.get("purchase_date") or row.get("sale_date") or row.get("return_date")), reverse=True)

	summary = merge_summaries([response.get("summary") or {} for response in responses])
	risks = []
	for response in responses:
		risks.extend(response.get("risks") or [])

	return {
		"filters": filters,
		"summary": summary,
		"story": build_mixed_story(summary, responses),
		"lots": lot_response.get("lots") or [],
		"timeline": timeline[:500],
		"cycle_rows": timeline[:500],
		"risks": risks[:100],
		"meta": {
			"generated_at": str(now_datetime()),
			"row_count": summary.get("lot_count", 0),
			"cycle_row_count": len(timeline[:500]),
		},
	}


def merge_summaries(summaries):
	merged = empty_summary()
	numeric_fields = [field for field, value in merged.items() if isinstance(value, (int, float))]
	for summary in summaries:
		for field in numeric_fields:
			merged[field] += flt(summary.get(field))

	merged["margin_percent"] = (merged["net_profit"] / merged["net_revenue"] * 100) if merged["net_revenue"] > 0 else 0
	merged["sell_through_percent"] = (merged["net_sold_qty"] / merged["purchased_qty"] * 100) if merged["purchased_qty"] > 0 else 0
	merged["return_rate_percent"] = (merged["returned_qty"] / merged["sold_qty"] * 100) if merged["sold_qty"] > 0 else 0
	merged["risk_level"] = highest_risk_level([summary.get("risk_level") for summary in summaries])
	return merged


def highest_risk_level(levels):
	order = ["Critical", "High", "Medium", "Low"]
	clean = [level for level in levels if level]
	for level in order:
		if level in clean:
			return level
	return "Low"


def build_mixed_story(summary, responses):
	active_parts = []
	labels = (("Normal Stock", responses[0]), ("Lot Based", responses[1]), ("Serial Based", responses[2]))
	for label, response in labels:
		count = len(response.get("cycle_rows") or response.get("timeline") or [])
		if count:
			active_parts.append(f"{label}: {count} events")

	if not active_parts:
		return {
			"title": "No activity found",
			"text": "No Normal Stock, Lot Based, or Serial Based activity matched the current filters.",
			"tone": "neutral",
			"signals": [],
		}

	return {
		"title": "Mixed Stock Story",
		"text": "All tracking types are combined here: Normal Stock quantity flow, Lot Based purchase batches, and Serial Based unit lifecycle.",
		"tone": "neutral" if summary.get("risk_level") == "Low" else "warning",
		"signals": active_parts,
	}


def get_allocations(lots):
	lot_names = [lot.name for lot in lots if lot.name]
	if not lot_names:
		return []

	return frappe.get_all(
		"Ledgix Stock Lot Allocation",
		filters={
			"stock_lot": ["in", lot_names],
			"is_reversed": 0,
		},
		fields=ALLOCATION_FIELDS,
		order_by="transaction_date asc, creation asc",
		limit_page_length=2000,
	)


def get_submitted_reference_maps(lots, allocations):
	purchase_names = unique([lot.purchase for lot in lots if lot.purchase])
	sale_names = unique([row.sale for row in allocations if row.sale])
	return_names = unique([row.sales_return for row in allocations if row.sales_return])
	return_map = get_submitted_docs("Ledgix Sales Return", return_names, ["name", "original_sale", "customer", "docstatus", "creation"])
	sale_names = unique(sale_names + [row.original_sale for row in return_map.values() if row.get("original_sale")])

	return {
		"purchases": get_submitted_docs("Ledgix Purchase", purchase_names, ["name", "supplier", "purchase_date", "invoice_number", "docstatus"]),
		"sales": get_submitted_docs("Ledgix Sale", sale_names, ["name", "sale_date", "invoice_number", "customer", "docstatus"]),
		"returns": return_map,
	}


def get_submitted_docs(doctype, names, fields):
	if not names:
		return {}

	rows = frappe.get_all(
		doctype,
		filters={"name": ["in", names], "docstatus": 1},
		fields=fields,
		limit_page_length=len(names),
	)
	return {row.name: row for row in rows}


def get_item_map(lots, allocations):
	item_names = unique([lot.item for lot in lots if lot.item] + [row.item for row in allocations if row.item])
	if not item_names:
		return {}

	rows = frappe.get_all(
		"Ledgix Item",
		filters={"name": ["in", item_names]},
		fields=[
			"name",
			"item_code",
			"item_name",
			"barcode",
			"category",
			"unit",
			"current_stock",
			"minimum_stock",
			"stock_status",
			"active",
			"sku",
			"tracking_type",
		],
		limit_page_length=len(item_names),
	)
	return {row.name: row for row in rows}


def build_lot_rows(lots, allocations, submitted, items, filters):
	allocations_by_lot = {}
	for allocation in allocations:
		allocations_by_lot.setdefault(allocation.stock_lot, []).append(allocation)

	rows = []
	for lot in lots:
		lot_allocations = allocations_by_lot.get(lot.name, [])
		valid_sale_allocations = [
			row for row in lot_allocations
			if row.allocation_type == "Sale" and row.sale and row.sale in submitted["sales"]
		]
		valid_return_allocations = [
			row for row in lot_allocations
			if row.allocation_type == "Return" and row.sales_return and row.sales_return in submitted["returns"]
		]

		purchased_qty = flt(lot.purchased_qty)
		sold_qty = sum(flt(row.qty) for row in valid_sale_allocations)
		returned_qty = sum(flt(row.qty) for row in valid_return_allocations)
		remaining_qty = flt(lot.remaining_qty)
		net_sold_qty = sold_qty - returned_qty
		gross_revenue = sum(flt(row.qty) * flt(row.sale_rate) for row in valid_sale_allocations)
		return_amount = sum(flt(row.qty) * flt(row.sale_rate) for row in valid_return_allocations)
		net_revenue = gross_revenue - return_amount
		gross_profit = sum(flt(row.profit_amount) for row in valid_sale_allocations)
		return_profit_impact = sum(flt(row.profit_amount) for row in valid_return_allocations)
		net_profit = gross_profit + return_profit_impact
		total_cost_sold = sum(flt(row.qty) * flt(row.cost_rate) for row in valid_sale_allocations)
		margin_percent = (net_profit / net_revenue * 100) if net_revenue > 0 else 0
		sell_through_percent = (net_sold_qty / purchased_qty * 100) if purchased_qty > 0 else 0
		return_rate_percent = (returned_qty / sold_qty * 100) if sold_qty > 0 else 0

		row = {
			"lot_number": lot.name,
			"item": lot.item,
			"item_name": (items.get(lot.item) or {}).get("item_name"),
			"supplier": lot.supplier or (submitted["purchases"].get(lot.purchase) or {}).get("supplier"),
			"purchase": lot.purchase,
			"purchase_item_row": lot.purchase_item_row,
			"purchase_date": lot.purchase_date,
			"purchased_qty": purchased_qty,
			"sold_qty": sold_qty,
			"returned_qty": returned_qty,
			"remaining_qty": remaining_qty,
			"net_sold_qty": net_sold_qty,
			"cost_rate": flt(lot.cost_rate),
			"total_cost": flt(lot.total_cost),
			"gross_revenue": gross_revenue,
			"return_amount": return_amount,
			"return_profit_impact": return_profit_impact,
			"net_revenue": net_revenue,
			"gross_profit": gross_profit,
			"profit": net_profit,
			"margin_percent": margin_percent,
			"sell_through_percent": sell_through_percent,
			"return_rate_percent": return_rate_percent,
			"total_cost_sold": total_cost_sold,
			"source_status": lot.status,
		}
		row["lot_status"] = get_lot_status(row, lot)
		rows.append(row)

	search = (filters.get("search") or "").lower()
	if search:
		rows = [
			row for row in rows
			if search in " ".join(str(row.get(field) or "") for field in ("lot_number", "item", "item_name", "supplier", "purchase", "lot_status")).lower()
		]

	return rows


def get_lot_status(row, lot):
	if row["profit"] < 0 or row["margin_percent"] < 0:
		return "Loss Risk"
	if row["return_rate_percent"] >= 30:
		return "High Return"
	if row["sold_qty"] == 0 and lot.purchase_date and date_diff(today(), lot.purchase_date) >= 90:
		return "Dead Stock"
	if row["purchased_qty"] > 0 and row["remaining_qty"] <= max(row["purchased_qty"] * 0.1, 1) and row["profit"] > 0:
		return "Nearly Sold"
	if row["sell_through_percent"] < 25 and row["purchased_qty"] > 0:
		return "Slow Moving"
	if row["sell_through_percent"] >= 50 and row["profit"] > 0 and row["return_rate_percent"] < 15:
		return "Healthy"
	return "Open"


def build_timeline(lots, allocations, submitted, items, filters):
	lot_map = {lot.name: lot for lot in lots}
	events = []

	for lot in lots:
		purchase = submitted["purchases"].get(lot.purchase)
		events.append({
			"date": lot.purchase_date or lot.creation,
			"event_type": "Purchase",
			"lot": lot.name,
			"item": lot.item,
			"item_name": (items.get(lot.item) or {}).get("item_name"),
			"reference": lot.purchase,
			"qty": flt(lot.purchased_qty),
			"cost_rate": flt(lot.cost_rate),
			"sale_rate": None,
			"profit_impact": 0,
			"running_qty": None,
			"reference_status": "Submitted" if purchase else "Missing or Draft",
		})

	for allocation in allocations:
		lot = lot_map.get(allocation.stock_lot, frappe._dict())
		event_type = normalize_event_type(allocation.allocation_type)
		if event_type == "Sale" and (not allocation.sale or allocation.sale not in submitted["sales"]):
			continue
		if event_type == "Return" and (not allocation.sales_return or allocation.sales_return not in submitted["returns"]):
			continue

		events.append({
			"date": allocation.transaction_date or allocation.creation,
			"event_type": event_type,
			"lot": allocation.stock_lot,
			"item": allocation.item or lot.get("item"),
			"item_name": (items.get(allocation.item or lot.get("item")) or {}).get("item_name"),
			"reference": get_event_reference(allocation),
			"qty": flt(allocation.qty),
			"cost_rate": flt(allocation.cost_rate),
			"sale_rate": flt(allocation.sale_rate) if allocation.sale_rate is not None else None,
			"profit_impact": flt(allocation.profit_amount),
			"running_qty": None,
			"reference_status": "Submitted",
		})

	events.sort(key=lambda row: (normalize_datetime(row.get("date")), row.get("event_type") or "", row.get("reference") or ""))
	apply_running_qty(events)

	search = (filters.get("search") or "").lower()
	if search:
		events = [
			row for row in events
			if search in " ".join(str(row.get(field) or "") for field in ("event_type", "lot", "item", "item_name", "reference")).lower()
		]

	return events[:500]


def build_cycle_rows(lots, allocations, submitted, items, filters):
	allocations_by_lot = {}
	for allocation in allocations:
		allocations_by_lot.setdefault(allocation.stock_lot, []).append(allocation)

	rows = []
	for lot in lots:
		lot_allocations = allocations_by_lot.get(lot.name, [])
		sale_allocations = [
			row for row in lot_allocations
			if row.allocation_type == "Sale" and row.sale and row.sale in submitted["sales"]
		]
		return_allocations = [
			row for row in lot_allocations
			if row.allocation_type == "Return" and row.sales_return and row.sales_return in submitted["returns"]
		]
		cancel_allocations = [row for row in lot_allocations if row.allocation_type == "Cancel"]

		rows.append(build_cycle_mother_row(lot, submitted, items))
		sale_rows = [build_cycle_sale_row(lot, allocation, submitted, items) for allocation in sale_allocations]
		merge_cycle_returns(lot, sale_rows, sale_allocations, return_allocations, submitted, items)

		child_rows = sale_rows + [
			build_cycle_cancel_row(lot, allocation, submitted, items)
			for allocation in cancel_allocations
		]
		child_rows.sort(key=lambda row: (
			normalize_datetime(row.get("date")),
			row.get("_sort_creation") or "",
			row.get("_sort_name") or "",
		))
		apply_cycle_running_qty(lot, child_rows)
		rows.extend(child_rows)

	search = (filters.get("search") or "").lower()
	if search:
		rows = [
			row for row in rows
			if search in " ".join(str(row.get(field) or "") for field in (
				"event_type",
				"cycle_status",
				"lot_number",
				"item",
				"item_name",
				"reference",
				"supplier",
				"customer",
			)).lower()
		]

	return [clean_cycle_row(row) for row in rows[:500]]


def build_cycle_mother_row(lot, submitted, items):
	purchase = submitted["purchases"].get(lot.purchase, frappe._dict())
	item_name = (items.get(lot.item) or {}).get("item_name")
	return {
		"date": lot.purchase_date or lot.creation,
		"row_type": "Mother",
		"event_type": "Purchase",
		"cycle_status": "Purchase",
		"lot_status": lot.status or "",
		"item": lot.item or "",
		"item_name": item_name or "",
		"lot_number": lot.name or "",
		"purchase": lot.purchase or "",
		"purchase_invoice": purchase.get("invoice_number") or "",
		"purchase_date": lot.purchase_date or purchase.get("purchase_date") or "",
		"sale": "",
		"sale_invoice": "",
		"sale_date": "",
		"sales_return": "",
		"return_date": "",
		"reference": lot.purchase or lot.name or "",
		"supplier": lot.supplier or purchase.get("supplier") or "",
		"customer": "",
		"purchased_qty": flt(lot.purchased_qty),
		"sale_qty": 0,
		"return_qty": 0,
		"net_sold_qty": 0,
		"current_lot_qty": flt(lot.purchased_qty),
		"unit_cost": flt(lot.cost_rate),
		"cost_rate": flt(lot.cost_rate),
		"sale_rate": 0,
		"total_cost": flt(lot.total_cost) or flt(lot.purchased_qty) * flt(lot.cost_rate),
		"selling_amount": 0,
		"return_amount": 0,
		"profit": 0,
		"loss": 0,
		"reference_status": "Submitted" if purchase else "Missing or Draft",
		"_sort_creation": lot.creation,
		"_sort_name": lot.name,
	}


def build_cycle_sale_row(lot, allocation, submitted, items):
	sale = submitted["sales"].get(allocation.sale, frappe._dict())
	purchase = submitted["purchases"].get(lot.purchase, frappe._dict())
	qty = flt(allocation.qty)
	cost_rate = flt(allocation.cost_rate)
	sale_rate = flt(allocation.sale_rate)
	profit_amount = flt(allocation.profit_amount)
	sale_date = sale.get("sale_date") or allocation.transaction_date or allocation.creation
	return {
		"date": sale_date,
		"row_type": "Child",
		"event_type": "Sale",
		"cycle_status": "Sale",
		"lot_status": lot.status or "",
		"item": allocation.item or lot.item or "",
		"item_name": (items.get(allocation.item or lot.item) or {}).get("item_name") or "",
		"lot_number": lot.name or "",
		"purchase": lot.purchase or "",
		"purchase_invoice": purchase.get("invoice_number") or "",
		"purchase_date": lot.purchase_date or purchase.get("purchase_date") or "",
		"sale": allocation.sale or "",
		"sale_invoice": sale.get("invoice_number") or "",
		"sale_date": sale_date,
		"sales_return": "",
		"return_date": "",
		"reference": allocation.sale or "",
		"supplier": lot.supplier or purchase.get("supplier") or "",
		"customer": sale.get("customer") or "",
		"purchased_qty": flt(lot.purchased_qty),
		"sale_qty": qty,
		"return_qty": 0,
		"net_sold_qty": qty,
		"current_lot_qty": flt(lot.remaining_qty),
		"unit_cost": cost_rate,
		"cost_rate": cost_rate,
		"sale_rate": sale_rate,
		"total_cost": qty * cost_rate,
		"selling_amount": qty * sale_rate,
		"_gross_selling_amount": qty * sale_rate,
		"return_amount": 0,
		"profit": profit_amount if profit_amount > 0 else 0,
		"loss": abs(profit_amount) if profit_amount < 0 else 0,
		"reference_status": "Submitted",
		"_allocation_name": allocation.name,
		"_sale_item_row": allocation.sale_item_row,
		"_sale_key": allocation.sale,
		"_sort_creation": allocation.creation,
		"_sort_name": allocation.name,
	}


def merge_cycle_returns(lot, sale_rows, sale_allocations, return_allocations, submitted, items):
	for allocation in return_allocations:
		return_doc = submitted["returns"].get(allocation.sales_return, frappe._dict())
		matched = find_cycle_sale_row(allocation, return_doc, sale_rows)
		if matched:
			merge_cycle_return_into_sale(matched, allocation, return_doc)
		else:
			sale_rows.append(build_cycle_return_row(lot, allocation, sale_allocations, submitted, items, return_doc))


def find_cycle_sale_row(allocation, return_doc, sale_rows):
	if not sale_rows:
		return None
	if allocation.sale_item_row:
		matches = [row for row in sale_rows if row.get("_sale_item_row") == allocation.sale_item_row]
		if len(matches) == 1:
			return matches[0]
	if allocation.sale:
		matches = [row for row in sale_rows if row.get("_sale_key") == allocation.sale]
		if len(matches) == 1:
			return matches[0]
	original_sale = return_doc.get("original_sale")
	if original_sale:
		matches = [row for row in sale_rows if row.get("_sale_key") == original_sale]
		if len(matches) == 1:
			return matches[0]
	if len(sale_rows) == 1:
		return sale_rows[0]
	return None


def merge_cycle_return_into_sale(sale_row, allocation, return_doc):
	return_qty = flt(allocation.qty)
	return_amount = return_qty * flt(allocation.sale_rate)
	sale_row["sales_return"] = join_unique(sale_row.get("sales_return"), allocation.sales_return)
	sale_row["return_date"] = latest_value(sale_row.get("return_date"), allocation.transaction_date)
	sale_row["return_qty"] = flt(sale_row.get("return_qty")) + return_qty
	sale_row["return_amount"] = flt(sale_row.get("return_amount")) + return_amount
	sale_row["customer"] = sale_row.get("customer") or return_doc.get("customer") or ""
	sale_row["date"] = latest_value(sale_row.get("date"), allocation.transaction_date)
	sale_row["event_type"] = "Partial Return" if sale_row["return_qty"] + 0.0001 < flt(sale_row.get("sale_qty")) else "Return"
	sale_row["cycle_status"] = sale_row["event_type"]
	recalculate_cycle_sale_row(sale_row)


def recalculate_cycle_sale_row(sale_row):
	sale_qty = flt(sale_row.get("sale_qty"))
	return_qty = flt(sale_row.get("return_qty"))
	net_qty = max(sale_qty - return_qty, 0)
	unit_cost = flt(sale_row.get("unit_cost"))
	selling_amount = max(flt(sale_row.get("_gross_selling_amount")) - flt(sale_row.get("return_amount")), 0)
	total_cost = net_qty * unit_cost
	net_profit = selling_amount - total_cost
	sale_row["net_sold_qty"] = net_qty
	sale_row["selling_amount"] = selling_amount
	sale_row["total_cost"] = total_cost
	sale_row["profit"] = net_profit if net_profit > 0 else 0
	sale_row["loss"] = abs(net_profit) if net_profit < 0 else 0


def build_cycle_return_row(lot, allocation, sale_allocations, submitted, items, return_doc=None):
	return_doc = return_doc or submitted["returns"].get(allocation.sales_return, frappe._dict())
	sale_no = allocation.sale or return_doc.get("original_sale") or ""
	sale = submitted["sales"].get(sale_no, frappe._dict())
	purchase = submitted["purchases"].get(lot.purchase, frappe._dict())
	qty = flt(allocation.qty)
	linked_sale_qty = get_linked_sale_qty(allocation, sale_no, sale_allocations)
	cost_rate = flt(allocation.cost_rate)
	sale_rate = flt(allocation.sale_rate)
	return_date = allocation.transaction_date or return_doc.get("creation") or allocation.creation
	return {
		"date": return_date,
		"row_type": "Child",
		"event_type": "Return",
		"cycle_status": "Return",
		"lot_status": lot.status or "",
		"item": allocation.item or lot.item or "",
		"item_name": (items.get(allocation.item or lot.item) or {}).get("item_name") or "",
		"lot_number": lot.name or "",
		"purchase": lot.purchase or "",
		"purchase_invoice": purchase.get("invoice_number") or "",
		"purchase_date": lot.purchase_date or purchase.get("purchase_date") or "",
		"sale": sale_no,
		"sale_invoice": sale.get("invoice_number") or "",
		"sale_date": sale.get("sale_date") or "",
		"sales_return": allocation.sales_return or "",
		"return_date": return_date,
		"reference": allocation.sales_return or sale_no,
		"supplier": lot.supplier or purchase.get("supplier") or "",
		"customer": sale.get("customer") or return_doc.get("customer") or "",
		"purchased_qty": flt(lot.purchased_qty),
		"sale_qty": linked_sale_qty,
		"return_qty": qty,
		"net_sold_qty": max(linked_sale_qty - qty, 0) if linked_sale_qty else 0,
		"current_lot_qty": flt(lot.remaining_qty),
		"unit_cost": cost_rate,
		"cost_rate": cost_rate,
		"sale_rate": sale_rate,
		"total_cost": qty * cost_rate,
		"selling_amount": 0,
		"return_amount": qty * sale_rate,
		"profit": 0,
		"loss": 0,
		"reference_status": "Submitted",
		"_sort_creation": allocation.creation,
		"_sort_name": allocation.name,
	}


def get_linked_sale_qty(return_allocation, sale_no, sale_allocations):
	if return_allocation.sale_item_row:
		matches = [row for row in sale_allocations if row.sale_item_row == return_allocation.sale_item_row]
		if matches:
			return sum(flt(row.qty) for row in matches)
	if sale_no:
		matches = [row for row in sale_allocations if row.sale == sale_no]
		if matches:
			return sum(flt(row.qty) for row in matches)
	return 0


def build_cycle_cancel_row(lot, allocation, submitted, items):
	return_doc = submitted["returns"].get(allocation.sales_return, frappe._dict())
	sale_no = allocation.sale or return_doc.get("original_sale") or ""
	sale = submitted["sales"].get(sale_no, frappe._dict())
	purchase = submitted["purchases"].get(lot.purchase, frappe._dict())
	activity_date = allocation.transaction_date or allocation.creation
	return {
		"date": activity_date,
		"row_type": "Child",
		"event_type": "Cancel",
		"cycle_status": "Cancel",
		"lot_status": lot.status or "",
		"item": allocation.item or lot.item or "",
		"item_name": (items.get(allocation.item or lot.item) or {}).get("item_name") or "",
		"lot_number": lot.name or "",
		"purchase": lot.purchase or "",
		"purchase_invoice": purchase.get("invoice_number") or "",
		"purchase_date": lot.purchase_date or purchase.get("purchase_date") or "",
		"sale": sale_no,
		"sale_invoice": sale.get("invoice_number") or "",
		"sale_date": sale.get("sale_date") or activity_date,
		"sales_return": allocation.sales_return or "",
		"return_date": activity_date if allocation.sales_return else "",
		"reference": sale_no or allocation.sales_return or lot.name or "",
		"supplier": lot.supplier or purchase.get("supplier") or "",
		"customer": sale.get("customer") or return_doc.get("customer") or "",
		"purchased_qty": flt(lot.purchased_qty),
		"sale_qty": 0,
		"return_qty": 0,
		"net_sold_qty": 0,
		"current_lot_qty": flt(lot.remaining_qty),
		"unit_cost": flt(allocation.cost_rate),
		"cost_rate": flt(allocation.cost_rate),
		"sale_rate": flt(allocation.sale_rate),
		"total_cost": 0,
		"selling_amount": 0,
		"return_amount": 0,
		"profit": 0,
		"loss": 0,
		"reference_status": "Submitted",
		"_sort_creation": allocation.creation,
		"_sort_name": allocation.name,
	}


def apply_cycle_running_qty(lot, child_rows):
	running_qty = flt(lot.purchased_qty)
	for row in child_rows:
		if row.get("cycle_status") in ("Sale", "Partial Return", "Return"):
			running_qty -= flt(row.get("sale_qty"))
			running_qty += flt(row.get("return_qty"))
		elif row.get("cycle_status") == "Cancel":
			running_qty += flt(row.get("return_qty"))
		if abs(running_qty) < 0.0001:
			running_qty = 0
		row["current_lot_qty"] = running_qty


def clean_cycle_row(row):
	numeric_fields = (
		"purchased_qty",
		"sale_qty",
		"return_qty",
		"net_sold_qty",
		"current_lot_qty",
		"unit_cost",
		"cost_rate",
		"sale_rate",
		"total_cost",
		"selling_amount",
		"return_amount",
		"profit",
		"loss",
	)
	text_fields = (
		"date",
		"row_type",
		"event_type",
		"cycle_status",
		"lot_status",
		"item",
		"item_name",
		"lot_number",
		"purchase",
		"purchase_invoice",
		"purchase_date",
		"sale",
		"sale_invoice",
		"sale_date",
		"sales_return",
		"return_date",
		"reference",
		"supplier",
		"customer",
		"reference_status",
	)
	cleaned = {}
	for field in text_fields:
		cleaned[field] = row.get(field) or ""
	for field in numeric_fields:
		cleaned[field] = flt(row.get(field))
	return cleaned


def join_unique(existing, value):
	values = [part.strip() for part in str(existing or "").split(",") if part.strip()]
	if value and value not in values:
		values.append(value)
	return ", ".join(values)


def latest_value(current, candidate):
	if not candidate:
		return current
	if not current:
		return candidate
	return candidate if normalize_datetime(candidate) >= normalize_datetime(current) else current


def normalize_event_type(value):
	if value == "Sale":
		return "Sale"
	if value == "Return":
		return "Return"
	if value == "Cancel":
		return "Cancel"
	return "Purchase"


def get_event_reference(allocation):
	if allocation.allocation_type == "Sale":
		return allocation.sale
	if allocation.allocation_type == "Return":
		return allocation.sales_return
	return allocation.sale or allocation.sales_return or allocation.stock_lot


def normalize_datetime(value):
	if not value:
		return get_datetime("1900-01-01 00:00:00")
	return get_datetime(value)


def apply_running_qty(events):
	balances = {}
	for row in events:
		lot = row.get("lot")
		if not lot:
			continue
		current = balances.get(lot, 0)
		event_type = row.get("event_type")
		if event_type == "Purchase":
			current += flt(row.get("qty"))
		elif event_type == "Sale":
			current -= flt(row.get("qty"))
		elif event_type == "Return":
			current += flt(row.get("qty"))
		elif event_type == "Cancel":
			current -= flt(row.get("qty"))
		balances[lot] = current
		row["running_qty"] = current


def build_risks(lots, allocations, submitted, items, lot_rows):
	risks = []
	lot_names = {lot.name for lot in lots}

	for lot in lots:
		if not lot.name:
			add_risk(risks, "Critical", "Missing stock lot", "A stock lot row is missing its document name.", None)
		if lot.purchase and lot.purchase not in submitted["purchases"]:
			add_risk(risks, "Warning", "Purchase not submitted", f"Lot {lot.name} is linked to a missing or unsubmitted purchase.", lot.name)

	for allocation in allocations:
		if not allocation.stock_lot or allocation.stock_lot not in lot_names:
			add_risk(risks, "Critical", "Allocation with missing lot", f"Allocation {allocation.name} has no valid stock lot.", allocation.name)
		if allocation.allocation_type == "Sale" and not allocation.sale:
			add_risk(risks, "Warning", "Sale allocation without sale reference", f"Allocation {allocation.name} has no sale reference.", allocation.stock_lot)
		if allocation.allocation_type == "Return" and not allocation.sales_return:
			add_risk(risks, "Warning", "Return allocation without return reference", f"Allocation {allocation.name} has no sales return reference.", allocation.stock_lot)

	for row in lot_rows:
		expected_remaining = row["purchased_qty"] - row["sold_qty"] + row["returned_qty"]
		if abs(expected_remaining - row["remaining_qty"]) > 0.001:
			add_risk(risks, "Warning", "Lot qty mismatch", f"{row['lot_number']} remaining qty differs from allocation totals.", row["lot_number"])
		if row["profit"] < 0:
			add_risk(risks, "Critical", "Negative profit", f"{row['lot_number']} has negative realized profit.", row["lot_number"])
		if row["return_rate_percent"] >= 30:
			add_risk(risks, "Warning", "High return rate", f"{row['lot_number']} return rate is {row['return_rate_percent']:.2f}%.", row["lot_number"])
		if row["net_revenue"] > 0 and row["margin_percent"] <= 0:
			add_risk(risks, "Warning", "Zero or negative margin", f"{row['lot_number']} has no realized margin.", row["lot_number"])
		if row["sell_through_percent"] < 25 and row["purchased_qty"] > 0:
			add_risk(risks, "Info", "Low sell-through lots", f"{row['lot_number']} is moving slowly.", row["lot_number"])

	for item_name, grouped in group_lots_by_item(lot_rows).items():
		item_doc = items.get(item_name)
		if not item_doc:
			continue
		remaining = sum(flt(row.get("remaining_qty")) for row in grouped)
		current_stock = flt(item_doc.get("current_stock"))
		if abs(remaining - current_stock) > 0.001:
			add_risk(risks, "Info", "Item current stock mismatch", f"{item_name} current stock differs from open lot balance.", item_name)

	return risks[:100]


def add_risk(risks, severity, title, message, reference):
	risks.append({
		"severity": severity,
		"title": title,
		"message": message,
		"reference": reference,
	})


def group_lots_by_item(lot_rows):
	grouped = {}
	for row in lot_rows:
		if row.get("item"):
			grouped.setdefault(row["item"], []).append(row)
	return grouped


def build_summary(lot_rows, items, filters):
	summary = empty_summary()
	for row in lot_rows:
		for field in (
			"purchased_qty",
			"remaining_qty",
			"sold_qty",
			"returned_qty",
			"net_sold_qty",
			"gross_revenue",
			"return_amount",
			"net_revenue",
			"gross_profit",
			"return_profit_impact",
			"profit",
			"total_cost_sold",
		):
			target = "net_profit" if field == "profit" else field
			summary[target] += flt(row.get(field))

	summary["current_qty"] = get_current_qty(lot_rows, items, filters)
	summary["lot_count"] = len(lot_rows)
	summary["margin_percent"] = (summary["net_profit"] / summary["net_revenue"] * 100) if summary["net_revenue"] > 0 else 0
	summary["sell_through_percent"] = (summary["net_sold_qty"] / summary["purchased_qty"] * 100) if summary["purchased_qty"] > 0 else 0
	summary["return_rate_percent"] = (summary["returned_qty"] / summary["sold_qty"] * 100) if summary["sold_qty"] > 0 else 0
	summary["risk_level"] = get_risk_level(summary, lot_rows)
	return summary


def get_current_qty(lot_rows, items, filters):
	if filters.get("item") and filters.get("item") in items:
		return flt(items[filters["item"]].get("current_stock"))
	return sum(flt(row.get("remaining_qty")) for row in lot_rows)


def get_risk_level(summary, lot_rows):
	if summary["net_profit"] < 0 or summary["margin_percent"] < 0:
		return "Critical"
	if summary["return_rate_percent"] >= 30:
		return "High"
	if any(row.get("lot_status") in ("Loss Risk", "Dead Stock", "High Return") for row in lot_rows):
		return "Medium"
	if summary["sell_through_percent"] < 25 and summary["purchased_qty"] > 0:
		return "Medium"
	return "Low"


def build_story(summary, lot_rows, filters):
	signals = []
	if summary["sell_through_percent"] > 0:
		signals.append(f"Sell-through {summary['sell_through_percent']:.1f}%")
	if summary["margin_percent"] != 0:
		signals.append(f"Margin {summary['margin_percent']:.1f}%")
	if summary["return_rate_percent"] > 0:
		signals.append(f"Return rate {summary['return_rate_percent']:.1f}%")

	scope = filters.get("item") or "Selected stock"
	if not lot_rows:
		text = "No stock lot activity matched the current filters."
		tone = "neutral"
	elif summary["net_profit"] < 0 or summary["margin_percent"] < 0:
		text = f"{scope} is showing loss risk. Review pricing, supplier cost, and return handling before restocking."
		tone = "critical"
	elif summary["return_rate_percent"] >= 30:
		text = f"{scope} has high return activity that is reducing realized profit. Check quality, supplier, or cashier workflow."
		tone = "warning"
	elif summary["sell_through_percent"] < 25 and summary["purchased_qty"] > 0:
		text = f"{scope} is moving slowly. Consider promotion, reorder delay, or supplier review."
		tone = "warning"
	elif summary["sell_through_percent"] >= 60 and summary["net_profit"] > 0 and summary["return_rate_percent"] < 15:
		text = f"{scope} is selling through well with positive margin and low return activity."
		tone = "positive"
	else:
		text = f"{scope} is stable. Monitor sell-through, margin, and return activity before the next purchase decision."
		tone = "neutral"

	return {
		"title": "Business Story",
		"text": text,
		"tone": tone,
		"signals": signals,
	}


def unique(values):
	seen = []
	for value in values:
		if value and value not in seen:
			seen.append(value)
	return seen


# ============================================================
# BUSINESS INTELLIGENCE SMART ENTITY SEARCH
# ============================================================

@frappe.whitelist()
def search_business_intelligence_entities(query=None, tracking_type="All", limit=20):
	require_ledgix_manager_or_above()

	query = (query or "").strip()
	tracking_type = normalize_tracking_type(tracking_type)
	limit = frappe.utils.cint(limit) or 20
	limit = max(1, min(limit, 50))

	if not query:
		return []

	results = []
	like_query = f"%{query}%"

	tracking_map = {
		"All": None,
		"Normal Stock": "Normal",
		"Lot Based": "Lot Based",
		"Serial Based": "Serial Based",
	}
	item_tracking_filter = tracking_map.get(tracking_type)

	def has_doctype(doctype):
		return bool(frappe.db.exists("DocType", doctype))

	def add_result(label, subtitle, entity_type, entity_value, result_tracking_type=None, status=None):
		if not label or not entity_value:
			return

		results.append({
			"label": str(label),
			"subtitle": str(subtitle or ""),
			"entity_type": entity_type,
			"entity_value": str(entity_value),
			"tracking_type": result_tracking_type or "",
			"status": str(status or ""),
		})

	def join_parts(*parts):
		return " • ".join([str(part) for part in parts if part not in (None, "", [])])

	# Items
	item_filters = {}
	if item_tracking_filter:
		item_filters["tracking_type"] = item_tracking_filter

	item_rows = frappe.get_all(
		"Ledgix Item",
		filters=item_filters,
		or_filters=[
			["Ledgix Item", "name", "like", like_query],
			["Ledgix Item", "item_code", "like", like_query],
			["Ledgix Item", "item_name", "like", like_query],
			["Ledgix Item", "sku", "like", like_query],
			["Ledgix Item", "barcode", "like", like_query],
		],
		fields=[
			"name",
			"item_code",
			"item_name",
			"sku",
			"barcode",
			"tracking_type",
			"current_stock",
			"stock_status",
		],
		order_by="modified desc",
		limit_page_length=limit,
	)

	for row in item_rows:
		display_tracking = item_tracking_to_ui(row.tracking_type)
		add_result(
			label=row.item_name or row.item_code or row.name,
			subtitle=join_parts(row.item_code, row.sku, f"Stock: {row.current_stock}"),
			entity_type="item",
			entity_value=row.name,
			result_tracking_type=display_tracking,
			status=row.stock_status,
		)

	# Lots: only All or Lot Based
	if tracking_type in ("All", "Lot Based") and has_doctype("Ledgix Stock Lot"):
		lot_item_names = []
		if tracking_type == "Lot Based":
			lot_item_names = frappe.get_all(
				"Ledgix Item",
				filters={"tracking_type": "Lot Based"},
				pluck="name",
				limit_page_length=5000,
			)

		lot_filters = {}
		if tracking_type == "Lot Based":
			if not lot_item_names:
				lot_filters["item"] = ["in", ["__none__"]]
			else:
				lot_filters["item"] = ["in", lot_item_names]

		lot_rows = frappe.get_all(
			"Ledgix Stock Lot",
			filters=lot_filters,
			or_filters=[
				["Ledgix Stock Lot", "name", "like", like_query],
				["Ledgix Stock Lot", "item", "like", like_query],
				["Ledgix Stock Lot", "purchase", "like", like_query],
				["Ledgix Stock Lot", "supplier", "like", like_query],
				["Ledgix Stock Lot", "status", "like", like_query],
			],
			fields=[
				"name",
				"item",
				"purchase",
				"supplier",
				"purchase_date",
				"remaining_qty",
				"purchased_qty",
				"status",
			],
			order_by="modified desc",
			limit_page_length=limit,
		)

		for row in lot_rows:
			add_result(
				label=row.name,
				subtitle=join_parts(row.item, row.purchase, f"Remaining: {row.remaining_qty}"),
				entity_type="lot",
				entity_value=row.name,
				result_tracking_type="Lot Based",
				status=row.status,
			)

	# Serials: only All or Serial Based
	if tracking_type in ("All", "Serial Based") and has_doctype("Ledgix Stock Serial"):
		serial_item_names = []
		if tracking_type == "Serial Based":
			serial_item_names = frappe.get_all(
				"Ledgix Item",
				filters={"tracking_type": "Serial Based"},
				pluck="name",
				limit_page_length=5000,
			)

		serial_filters = {}
		if tracking_type == "Serial Based":
			if not serial_item_names:
				serial_filters["item"] = ["in", ["__none__"]]
			else:
				serial_filters["item"] = ["in", serial_item_names]

		serial_rows = frappe.get_all(
			"Ledgix Stock Serial",
			filters=serial_filters,
			or_filters=[
				["Ledgix Stock Serial", "name", "like", like_query],
				["Ledgix Stock Serial", "serial_no", "like", like_query],
				["Ledgix Stock Serial", "item", "like", like_query],
				["Ledgix Stock Serial", "purchase", "like", like_query],
				["Ledgix Stock Serial", "sale", "like", like_query],
				["Ledgix Stock Serial", "status", "like", like_query],
			],
			fields=[
				"name",
				"serial_no",
				"item",
				"purchase",
				"sale",
				"sales_return",
				"status",
				"purchase_date",
				"sold_date",
				"return_date",
			],
			order_by="modified desc",
			limit_page_length=limit,
		)

		for row in serial_rows:
			add_result(
				label=row.serial_no or row.name,
				subtitle=join_parts(row.item, row.purchase, row.sale, row.sales_return),
				entity_type="serial",
				entity_value=row.name,
				result_tracking_type="Serial Based",
				status=row.status,
			)

	# Purchases and Sales only under All for now
	if tracking_type == "All":
		purchase_rows = frappe.get_all(
			"Ledgix Purchase",
			or_filters=[
				["Ledgix Purchase", "name", "like", like_query],
				["Ledgix Purchase", "supplier", "like", like_query],
				["Ledgix Purchase", "invoice_number", "like", like_query],
			],
			fields=["name", "supplier", "purchase_date", "invoice_number", "docstatus"],
			order_by="modified desc",
			limit_page_length=8,
		)

		for row in purchase_rows:
			add_result(
				label=row.name,
				subtitle=join_parts(row.invoice_number, row.supplier, row.purchase_date),
				entity_type="purchase",
				entity_value=row.name,
				result_tracking_type="Mixed",
				status="Purchase",
			)

		sale_rows = frappe.get_all(
			"Ledgix Sale",
			or_filters=[
				["Ledgix Sale", "name", "like", like_query],
				["Ledgix Sale", "customer", "like", like_query],
				["Ledgix Sale", "invoice_number", "like", like_query],
			],
			fields=["name", "customer", "sale_date", "invoice_number", "docstatus"],
			order_by="modified desc",
			limit_page_length=8,
		)

		for row in sale_rows:
			add_result(
				label=row.invoice_number or row.name,
				subtitle=join_parts(row.name, row.customer, row.sale_date),
				entity_type="sale",
				entity_value=row.name,
				result_tracking_type="Mixed",
				status="Sale",
			)

	seen = set()
	clean_results = []
	for result in results:
		key = (result.get("entity_type"), result.get("entity_value"))
		if key in seen:
			continue
		seen.add(key)
		clean_results.append(result)

	return clean_results[:limit]