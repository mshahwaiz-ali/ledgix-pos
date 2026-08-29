from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, today

from ledgix_saas.api.security import require_ledgix_cashier_or_above
from ledgix_saas.services.pricing import resolve_item_price, resolve_price_list
from ledgix_saas.services.receivables import get_customer_receivables
from ledgix_saas.services.sales import infer_sale_channel
from ledgix_saas.services.tax import apply_sale_tax_snapshot


def _parse(value):
	return frappe.parse_json(value) if isinstance(value, str) else value


def _manager_or_above():
	roles = set(frappe.get_roles(frappe.session.user))
	return bool(roles.intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}))


def _require_manager(message):
	if not _manager_or_above():
		frappe.throw(message, frappe.PermissionError)


def _open_shift():
	filters = {"status": "Open", "docstatus": 0}
	if frappe.get_meta("Ledgix POS Shift").has_field("opened_by"):
		filters["opened_by"] = frappe.session.user
	return frappe.db.get_value("Ledgix POS Shift", filters, "name", order_by="creation desc")


def _customer_name(customer, sale_channel):
	customer = (customer or "").strip()
	if customer and frappe.db.exists("Ledgix Customer", customer):
		return customer
	if sale_channel == "B2B":
		frappe.throw(_("Select a business customer for B2B checkout."))
	if frappe.db.exists("Ledgix Customer", "Walk-in Customer"):
		return "Walk-in Customer"
	customer = frappe.db.get_value("Ledgix Customer", {}, "name", order_by="creation asc")
	if not customer:
		frappe.throw(_("Create at least one Ledgix Customer before checkout."))
	return customer


def _customer_context(customer, sale_channel):
	if not customer:
		return None
	row = frappe.db.get_value(
		"Ledgix Customer",
		customer,
		["name", "customer_name", "customer_type", "default_price_list", "payment_terms_days", "credit_limit", "buyer_ntn_cnic", "buyer_strn"],
		as_dict=True,
	)
	if not row:
		return None
	credit = get_customer_receivables(customer) if sale_channel == "B2B" else None
	return {
		**row,
		"outstanding": flt((credit or {}).get("outstanding")),
		"available_credit": flt((credit or {}).get("available_credit")),
		"overdue": flt((credit or {}).get("overdue")),
	}


def _payment_methods():
	if not frappe.db.exists("DocType", "Ledgix Payment Method"):
		return []
	return frappe.get_all(
		"Ledgix Payment Method",
		filters={"enabled": 1},
		fields=["name", "payment_method_name", "method_type", "requires_reference", "allow_change"],
		order_by="sort_order asc, payment_method_name asc",
	)


def _categories():
	return frappe.get_all(
		"Ledgix Category",
		filters={"is_active": 1},
		fields=["name", "category_name", "category_icon", "custom_icon_image", "accent_color"],
		order_by="category_name asc",
	)


def _resolve_catalog_item(item_name, customer, sale_channel, price_list, transaction_date=None):
	item = frappe.db.get_value(
		"Ledgix Item",
		item_name,
		["name", "item_code", "item_name", "sku", "barcode", "category", "unit", "tracking_type", "cost_price", "current_stock", "active"],
		as_dict=True,
	)
	if not item or not item.active:
		return None
	price = resolve_item_price(
		item.name,
		customer=customer,
		price_list=price_list,
		sale_channel=sale_channel,
		transaction_date=transaction_date,
	)
	return {**item, **price}


@frappe.whitelist()
def get_pos_v2_boot(customer=None, sale_channel="Retail"):
	require_ledgix_cashier_or_above()
	sale_channel = sale_channel if sale_channel in {"Retail", "B2B"} else "Retail"
	if sale_channel == "B2B":
		_require_manager(_("B2B checkout requires Manager or Admin access."))
		customer = (customer or "").strip() or None
		if customer and not frappe.db.exists("Ledgix Customer", customer):
			frappe.throw(_("Customer not found."))
	else:
		customer = _customer_name(customer, "Retail")
	price_list = resolve_price_list(customer, None, sale_channel)
	return {
		"sale_channel": sale_channel,
		"customer": _customer_context(customer, sale_channel),
		"price_list": price_list,
		"price_lists": frappe.get_all("Ledgix Price List", filters={"enabled": 1}, fields=["name", "price_list_name", "currency"], order_by="priority asc, price_list_name asc") if frappe.db.exists("DocType", "Ledgix Price List") else [],
		"payment_methods": _payment_methods(),
		"categories": _categories(),
		"active_shift": _open_shift(),
		"can_b2b": _manager_or_above(),
		"can_discount": _manager_or_above(),
		"can_override_price": _manager_or_above(),
	}


@frappe.whitelist()
def search_pos_v2_items(query=None, category=None, customer=None, sale_channel="Retail", price_list=None, limit=80):
	require_ledgix_cashier_or_above()
	sale_channel = sale_channel if sale_channel in {"Retail", "B2B"} else "Retail"
	customer = _customer_name(customer, sale_channel)
	price_list = resolve_price_list(customer, price_list, sale_channel)
	filters = {"active": 1}
	if category and category != "All":
		filters["category"] = category
	or_filters = []
	if query:
		query = query.strip()
		or_filters = [
			["Ledgix Item", "item_name", "like", f"%{query}%"],
			["Ledgix Item", "item_code", "like", f"%{query}%"],
			["Ledgix Item", "sku", "like", f"%{query}%"],
			["Ledgix Item", "barcode", "like", f"%{query}%"],
		]
	items = frappe.get_all(
		"Ledgix Item",
		filters=filters,
		or_filters=or_filters,
		pluck="name",
		order_by="item_name asc",
		limit_page_length=min(max(int(limit or 80), 1), 200),
	)
	return {
		"price_list": price_list,
		"items": [row for row in (_resolve_catalog_item(name, customer, sale_channel, price_list) for name in items) if row],
	}


def _prepare_lines(cart_items, customer, sale_channel, price_list, discount_type, discount_value):
	cart_items = _parse(cart_items) or []
	if not cart_items:
		frappe.throw(_("Cart is empty."))

	prepared = []
	subtotal = 0.0
	for row in cart_items:
		item_name = row.get("item")
		qty = flt(row.get("qty") or row.get("quantity"))
		if not item_name or qty <= 0:
			frappe.throw(_("Every cart line requires an item and quantity greater than zero."))

		requested_override = row.get("override_rate")
		price = resolve_item_price(
			item_name,
			customer=customer,
			price_list=price_list,
			sale_channel=sale_channel,
			transaction_date=today(),
			requested_rate=requested_override if requested_override not in (None, "") else None,
			allow_override=requested_override not in (None, ""),
			override_reason=row.get("override_reason"),
		)
		item = frappe.db.get_value(
			"Ledgix Item", item_name, ["item_name", "cost_price", "current_stock"], as_dict=True
		)
		if flt(item.current_stock) < qty:
			frappe.throw(_("Not enough stock for {0}.").format(item.item_name))
		subtotal += qty * flt(price["rate"])
		prepared.append({"item": item_name, "qty": qty, "item_meta": item, **price, "serial_numbers": row.get("serial_numbers") or ""})

	discount_value = max(flt(discount_value), 0)
	if discount_value and not _manager_or_above():
		frappe.throw(_("Discounts require Manager or Admin access."), frappe.PermissionError)
	if discount_type == "Percent":
		discount_value = min(discount_value, 100)
		discount_amount = subtotal * discount_value / 100
	else:
		discount_type = "Amount"
		discount_amount = min(discount_value, subtotal)
	ratio = (discount_amount / subtotal) if subtotal else 0
	for row in prepared:
		row["effective_rate"] = flt(row["rate"] * (1 - ratio), 2)
	return prepared, flt(subtotal, 2), discount_type, flt(discount_value, 2), flt(discount_amount, 2)


def _build_sale(customer, sale_channel, price_list, cart_items, discount_type, discount_value, pos_shift=None, client_sale_id=None):
	prepared, subtotal, discount_type, discount_value, discount_amount = _prepare_lines(
		cart_items, customer, sale_channel, price_list, discount_type, discount_value
	)
	sale = frappe.new_doc("Ledgix Sale")
	sale.customer = customer
	sale.sale_channel = sale_channel
	sale.price_list = price_list
	sale.sale_date = today()
	sale.pos_shift = pos_shift
	sale.status = "Draft"
	sale.client_sale_id = client_sale_id or None
	sale.subtotal_before_discount = subtotal
	sale.discount_type = discount_type
	sale.discount_value = discount_value
	sale.discount_amount = discount_amount
	sale.allow_partial_payment = 1 if sale_channel == "B2B" else 0
	for row in prepared:
		sale.append("items", {
			"item": row["item"],
			"quantity": row["qty"],
			"serial_numbers": row["serial_numbers"],
			"price_list_snapshot": row["price_list"],
			"item_price_reference": row["item_price_reference"],
			"list_rate": row["list_rate"],
			"rate": row["effective_rate"],
			"price_override": 1 if row["price_override"] else 0,
			"price_override_reason": row["price_override_reason"],
			"cost_price": flt(row["item_meta"].cost_price),
		})
	sale.calculate_totals()
	apply_sale_tax_snapshot(sale)
	return sale


@frappe.whitelist()
def preview_pos_v2_checkout(cart_items=None, customer=None, sale_channel="Retail", price_list=None, discount_type="Amount", discount_value=0):
	require_ledgix_cashier_or_above()
	sale_channel = sale_channel if sale_channel in {"Retail", "B2B"} else "Retail"
	if sale_channel == "B2B":
		_require_manager(_("B2B checkout requires Manager or Admin access."))
	customer = _customer_name(customer, sale_channel)
	price_list = resolve_price_list(customer, price_list, sale_channel)
	sale = _build_sale(customer, sale_channel, price_list, cart_items, discount_type, discount_value, pos_shift=_open_shift())
	credit = get_customer_receivables(customer) if sale_channel == "B2B" else None
	return {
		"subtotal": flt(sale.subtotal_before_discount),
		"discount_amount": flt(sale.discount_amount),
		"total_amount": flt(sale.total_amount),
		"tax_amount": flt(sale.tax_amount),
		"grand_total": flt(sale.grand_total),
		"price_list": price_list,
		"sale_channel": sale_channel,
		"credit": credit,
		"items": [{
			"item": row.item,
			"quantity": flt(row.quantity),
			"list_rate": flt(row.list_rate),
			"rate": flt(row.rate),
			"amount": flt(row.amount),
			"tax_basis": row.tax_basis_snapshot,
			"tax_rate": flt(row.tax_rate_snapshot),
			"notified_retail_price": flt(row.notified_retail_price_snapshot),
		} for row in sale.items],
	}


@frappe.whitelist()
def complete_pos_v2_sale(
	cart_items=None,
	tenders=None,
	customer=None,
	sale_channel="Retail",
	price_list=None,
	discount_type="Amount",
	discount_value=0,
	client_sale_id=None,
):
	require_ledgix_cashier_or_above()
	sale_channel = sale_channel if sale_channel in {"Retail", "B2B"} else "Retail"
	if sale_channel == "B2B":
		_require_manager(_("B2B checkout requires Manager or Admin access."))
	customer = _customer_name(customer, sale_channel)
	price_list = resolve_price_list(customer, price_list, sale_channel)
	shift = _open_shift()
	if sale_channel == "Retail" and not shift:
		frappe.throw(_("Open a POS shift before retail checkout."))

	client_sale_id = (client_sale_id or "").strip()
	if client_sale_id:
		existing = frappe.db.get_value("Ledgix Sale", {"client_sale_id": client_sale_id, "docstatus": 1}, "name")
		if existing:
			return {"success": True, "sale": existing, "duplicate": True}

	sale = _build_sale(customer, sale_channel, price_list, cart_items, discount_type, discount_value, pos_shift=shift, client_sale_id=client_sale_id)
	tenders = _parse(tenders) or []
	for tender in tenders:
		amount = flt(tender.get("amount"))
		method = tender.get("payment_method")
		if amount <= 0 or not method:
			continue
		method_meta = frappe.db.get_value(
			"Ledgix Payment Method",
			method,
			["method_type", "enabled"],
			as_dict=True,
		)
		if not method_meta:
			frappe.throw(_("Payment Method {0} is not configured.").format(method))
		if not method_meta.enabled:
			frappe.throw(_("Payment Method {0} is disabled.").format(method))
		sale.append("payments", {
			"payment_method": method,
			"amount": amount,
			"is_cash_payment": 1 if method_meta.method_type == "Cash" else 0,
			"reference_no": tender.get("reference_number") or tender.get("reference_no") or "",
			"notes": tender.get("notes") or "",
		})

	sale.insert(ignore_permissions=True)
	sale.submit()
	return {
		"success": True,
		"sale": sale.name,
		"invoice_number": sale.invoice_number,
		"sale_channel": sale.sale_channel,
		"price_list": sale.price_list,
		"grand_total": flt(sale.grand_total),
		"paid_amount": flt(sale.paid_amount),
		"remaining_amount": flt(sale.remaining_amount),
		"change_amount": flt(sale.change_amount),
		"payment_status": sale.payment_status,
		"fbr_status": sale.fbr_status,
		"print_mode": "A4" if sale.sale_channel == "B2B" else "Thermal",
	}


@frappe.whitelist()
def get_pos_v2_customer_context(customer, sale_channel=None):
	require_ledgix_cashier_or_above()
	if not frappe.db.exists("Ledgix Customer", customer):
		frappe.throw(_("Customer not found."))
	sale_channel = infer_sale_channel(customer, sale_channel)
	return {
		"sale_channel": sale_channel,
		"customer": _customer_context(customer, sale_channel),
		"price_list": resolve_price_list(customer, None, sale_channel),
	}
