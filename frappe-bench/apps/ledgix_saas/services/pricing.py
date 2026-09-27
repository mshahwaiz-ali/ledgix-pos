from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today


def _active_price_list(name):
	if not name:
		return None
	return frappe.db.get_value(
		"Ledgix Price List",
		{"name": name, "enabled": 1},
		["name", "currency"],
		as_dict=True,
	)


def get_default_retail_price_list():
	return frappe.db.get_value(
		"Ledgix Price List",
		{"enabled": 1, "is_default_retail": 1},
		"name",
		order_by="priority asc, modified desc",
	)


def resolve_price_list(customer=None, explicit_price_list=None, sale_channel="Retail"):
	price_list = _active_price_list(explicit_price_list)
	if price_list:
		return price_list.name

	if customer and sale_channel == "B2B" and frappe.db.exists("Ledgix Customer", customer):
		customer_price_list = frappe.db.get_value("Ledgix Customer", customer, "default_price_list")
		price_list = _active_price_list(customer_price_list)
		if price_list:
			return price_list.name

	return get_default_retail_price_list()


def _find_item_price(item, price_list, transaction_date=None):
	if not price_list:
		return None
	transaction_date = getdate(transaction_date or today())
	rows = frappe.get_all(
		"Ledgix Item Price",
		filters={"item": item, "price_list": price_list, "enabled": 1},
		fields=["name", "rate", "currency", "effective_from", "effective_to"],
		order_by="effective_from desc, modified desc",
		limit_page_length=50,
	)
	for row in rows:
		if row.effective_from and getdate(row.effective_from) > transaction_date:
			continue
		if row.effective_to and getdate(row.effective_to) < transaction_date:
			continue
		return row
	return None


def _can_override_price():
	roles = set(frappe.get_roles(frappe.session.user))
	return bool(roles.intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}))


def resolve_item_price(
	item,
	*,
	customer=None,
	price_list=None,
	sale_channel="Retail",
	transaction_date=None,
	requested_rate=None,
	allow_override=False,
	override_reason=None,
):
	if not frappe.db.exists("Ledgix Item", item):
		frappe.throw(_("Item not found: {0}").format(item))

	resolved_price_list = resolve_price_list(customer, price_list, sale_channel)
	item_price = _find_item_price(item, resolved_price_list, transaction_date)
	legacy_rate = flt(frappe.db.get_value("Ledgix Item", item, "selling_price"))
	list_rate = flt(item_price.rate if item_price else legacy_rate)
	if list_rate < 0:
		frappe.throw(_("Configured selling price cannot be negative."))

	final_rate = list_rate
	is_override = False
	if requested_rate is not None and abs(flt(requested_rate) - list_rate) > 0.005:
		if not allow_override or not _can_override_price():
			frappe.throw(_("Price override is not permitted for item {0}.").format(item))
		if not (override_reason or "").strip():
			frappe.throw(_("Price override reason is required."))
		final_rate = flt(requested_rate)
		is_override = True

	return {
		"item": item,
		"price_list": resolved_price_list,
		"item_price_reference": item_price.name if item_price else None,
		"list_rate": list_rate,
		"rate": final_rate,
		"price_override": is_override,
		"price_override_reason": (override_reason or "").strip() if is_override else "",
		"currency": item_price.currency if item_price else None,
	}
