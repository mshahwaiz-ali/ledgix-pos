import frappe

from ledgix_saas.api import business_intelligence as core
from ledgix_saas.api.security import require_ledgix_manager_or_above


TIMELINE_RESULT_CAP = 500


@frappe.whitelist()
def get_inventory_intelligence_data(
	item=None,
	from_date=None,
	to_date=None,
	mode="Overview",
	search=None,
	tracking_type="All",
	entity_type=None,
	entity_value=None,
):
	"""Inventory Intelligence endpoint with global Normal Stock activity search.

	The original engine remains authoritative for stock math, lot/serial lifecycle,
	story generation, and risk rules. This wrapper fixes Normal Stock search so a
	transaction/customer/supplier query is not discarded by the item master
	prefilter before transaction rows are inspected.
	"""
	require_ledgix_manager_or_above()

	filters = core.normalize_filters(
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
		if core.should_use_serial_intelligence(filters):
			return add_timeline_meta(core.build_serial_data_response(filters))

		if core.should_use_normal_stock_intelligence(filters):
			return add_timeline_meta(build_normal_stock_data_response(filters))

		if core.should_use_mixed_intelligence(filters):
			return build_mixed_data_response(filters)

		return add_timeline_meta(core.build_lot_data_response(filters))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Inventory Intelligence API")
		return add_timeline_meta(core.empty_response(filters))


def build_normal_stock_data_response(filters):
	base_filters = dict(filters)
	base_filters["search"] = None

	items = core.get_normal_stock_item_map(base_filters)
	if not items:
		return empty_normal_response(filters)

	item_names = list(items.keys())
	purchases = core.get_normal_purchase_rows(item_names, base_filters)
	sales = core.get_normal_sale_rows(item_names, base_filters)
	returns = core.get_normal_return_rows(item_names, base_filters)

	items, purchases, sales, returns = filter_normal_stock_search(
		items,
		purchases,
		sales,
		returns,
		filters,
	)

	if not items:
		return empty_normal_response(filters, search_miss=True)

	if filters.get("entity_type") in ("purchase", "sale"):
		event_items = core.unique(
			[row.item for row in purchases if row.item]
			+ [row.item for row in sales if row.item]
			+ [row.item for row in returns if row.item]
		)
		items = {item_name: items[item_name] for item_name in event_items if item_name in items}

	if not items:
		return empty_normal_response(filters, search_miss=bool(filters.get("search")))

	timeline = core.build_normal_stock_timeline(purchases, sales, returns, items)
	summary = core.build_normal_stock_summary(purchases, sales, returns, items, filters)
	story = core.build_normal_stock_story(summary, timeline, filters)
	risks = core.build_normal_stock_risks(items, summary, timeline)

	return {
		"filters": filters,
		"summary": summary,
		"story": story,
		"lots": [],
		"timeline": timeline,
		"cycle_rows": timeline,
		"risks": risks,
		"meta": {
			"generated_at": str(core.now_datetime()),
			"row_count": len(items),
			"cycle_row_count": len(timeline),
		},
	}


def filter_normal_stock_search(items, purchases, sales, returns, filters):
	"""Apply one search term across item identity and Normal Stock activity."""
	search = str(filters.get("search") or "").strip().lower()
	entity_type = filters.get("entity_type")
	if not search or entity_type not in (None, "item"):
		return items, purchases, sales, returns

	item_fields = (
		"name",
		"item_code",
		"item_name",
		"sku",
		"barcode",
		"category",
		"stock_status",
	)
	item_matches = {
		name
		for name, row in items.items()
		if row_matches_search(row, item_fields, search)
	}

	purchases = filter_activity_rows(
		purchases,
		("purchase", "supplier", "purchase_invoice", "item", "row_name"),
		search,
		item_matches,
	)
	sales = filter_activity_rows(
		sales,
		("sale", "customer", "sale_invoice", "item", "row_name"),
		search,
		item_matches,
	)
	returns = filter_activity_rows(
		returns,
		("sales_return", "original_sale", "customer", "item", "row_name"),
		search,
		item_matches,
	)

	matched_items = set(item_matches)
	for row in purchases + sales + returns:
		if row.get("item"):
			matched_items.add(row.get("item"))

	items = {name: row for name, row in items.items() if name in matched_items}
	return items, purchases, sales, returns


def filter_activity_rows(rows, fields, search, item_matches):
	return [
		row
		for row in rows
		if row.get("item") in item_matches or row_matches_search(row, fields, search)
	]


def row_matches_search(row, fields, search):
	return search in " ".join(str(row.get(field) or "") for field in fields).lower()


def empty_normal_response(filters, search_miss=False):
	response = core.empty_response(filters)
	response["story"] = {
		"title": "No normal stock activity found" if search_miss else "No normal stock found",
		"text": (
			"No Normal Stock item or submitted purchase, sale, return, customer, or supplier activity matched the current search."
			if search_miss
			else "No quantity-only Normal Stock items matched the current filters."
		),
		"tone": "neutral",
		"signals": [],
	}
	return response


def build_mixed_data_response(filters):
	lot_response = add_timeline_meta(core.build_lot_data_response(dict(filters)))

	normal_filters = dict(filters)
	normal_filters["tracking_type"] = "Normal Stock"
	normal_response = add_timeline_meta(build_normal_stock_data_response(normal_filters))

	serial_filters = dict(filters)
	serial_filters["tracking_type"] = "Serial Based"
	serial_response = add_timeline_meta(core.build_serial_data_response(serial_filters))

	responses = [normal_response, lot_response, serial_response]
	timeline = []
	for response in responses:
		timeline.extend(response.get("cycle_rows") or response.get("timeline") or [])
	timeline.sort(
		key=lambda row: core.normalize_datetime(
			row.get("date") or row.get("purchase_date") or row.get("sale_date") or row.get("return_date")
		),
		reverse=True,
	)

	summary = core.merge_summaries([response.get("summary") or {} for response in responses])
	risks = []
	for response in responses:
		risks.extend(response.get("risks") or [])

	loaded_timeline = timeline[:TIMELINE_RESULT_CAP]
	return {
		"filters": filters,
		"summary": summary,
		"story": core.build_mixed_story(summary, responses),
		"lots": lot_response.get("lots") or [],
		"timeline": loaded_timeline,
		"cycle_rows": loaded_timeline,
		"risks": risks[:100],
		"meta": {
			"generated_at": str(core.now_datetime()),
			"row_count": summary.get("lot_count", 0),
			"cycle_row_count": len(loaded_timeline),
			"timeline_loaded_count": len(loaded_timeline),
			"timeline_result_cap": TIMELINE_RESULT_CAP,
			"timeline_cap_reached": len(timeline) > TIMELINE_RESULT_CAP,
		},
	}


def add_timeline_meta(response):
	response = response or {}
	rows = response.get("cycle_rows") or response.get("timeline") or []
	meta = response.setdefault("meta", {})
	meta["timeline_loaded_count"] = len(rows)
	meta["timeline_result_cap"] = TIMELINE_RESULT_CAP
	# Existing engines cap their activity collections at 500 rows. At exactly the
	# cap we cannot prove whether older matching activity exists, so expose this as
	# a conservative cap-reached signal rather than pretending it is a lifetime total.
	meta["timeline_cap_reached"] = len(rows) >= TIMELINE_RESULT_CAP
	return response
