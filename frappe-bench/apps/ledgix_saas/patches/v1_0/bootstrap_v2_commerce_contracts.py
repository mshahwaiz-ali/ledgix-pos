from __future__ import annotations

import frappe
from frappe.utils import flt


DEFAULT_PRICE_LIST = "Retail"
PAYMENT_METHODS = (
	("Cash", "Cash", 0, 1, 10),
	("Card", "Card", 1, 0, 20),
	("EasyPaisa", "Wallet", 1, 0, 30),
	("JazzCash", "Wallet", 1, 0, 40),
	("Bank Transfer", "Bank Transfer", 1, 0, 50),
	("Other", "Other", 1, 0, 90),
)


def _ensure_price_list():
	if frappe.db.exists("Ledgix Price List", DEFAULT_PRICE_LIST):
		frappe.db.set_value(
			"Ledgix Price List",
			DEFAULT_PRICE_LIST,
			{"enabled": 1, "is_default_retail": 1},
			update_modified=False,
		)
		return
	doc = frappe.new_doc("Ledgix Price List")
	doc.price_list_name = DEFAULT_PRICE_LIST
	doc.enabled = 1
	doc.is_default_retail = 1
	doc.currency = "PKR"
	doc.priority = 1
	doc.insert(ignore_permissions=True)


def _ensure_payment_methods():
	for name, method_type, requires_reference, allow_change, sort_order in PAYMENT_METHODS:
		if frappe.db.exists("Ledgix Payment Method", name):
			continue
		doc = frappe.new_doc("Ledgix Payment Method")
		doc.payment_method_name = name
		doc.method_type = method_type
		doc.enabled = 1
		doc.requires_reference = requires_reference
		doc.allow_change = allow_change
		doc.sort_order = sort_order
		doc.insert(ignore_permissions=True)


def _backfill_item_prices():
	for item in frappe.get_all("Ledgix Item", fields=["name", "selling_price"]):
		if frappe.db.exists("Ledgix Item Price", {"item": item.name, "price_list": DEFAULT_PRICE_LIST}):
			continue
		doc = frappe.new_doc("Ledgix Item Price")
		doc.item = item.name
		doc.price_list = DEFAULT_PRICE_LIST
		doc.rate = flt(item.selling_price)
		doc.enabled = 1
		doc.insert(ignore_permissions=True)


def _backfill_customers():
	for customer in frappe.get_all("Ledgix Customer", fields=["name", "default_price_list"]):
		if not customer.default_price_list:
			frappe.db.set_value(
				"Ledgix Customer", customer.name, "default_price_list", DEFAULT_PRICE_LIST, update_modified=False
			)


def _sale_channel(customer):
	customer_type = frappe.db.get_value("Ledgix Customer", customer, "customer_type") if customer else None
	return "B2B" if customer_type in {"Wholesale", "B2B"} else "Retail"


def _ensure_sale_contract_fields():
	for sale in frappe.get_all(
		"Ledgix Sale",
		fields=["name", "customer", "sale_channel", "price_list"],
	):
		values = {}
		if not sale.sale_channel:
			values["sale_channel"] = _sale_channel(sale.customer)
		if not sale.price_list:
			values["price_list"] = (
				frappe.db.get_value("Ledgix Customer", sale.customer, "default_price_list") or DEFAULT_PRICE_LIST
			)
		if values:
			frappe.db.set_value("Ledgix Sale", sale.name, values, update_modified=False)


def _payment_user(sale_owner):
	if sale_owner and frappe.db.exists("User", sale_owner):
		return sale_owner
	return "Administrator"


def _payment_method_type(method):
	if not method or not frappe.db.exists("Ledgix Payment Method", method):
		return "Other"
	return frappe.db.get_value("Ledgix Payment Method", method, "method_type") or "Other"


def _create_legacy_payment(sale, tender, amount, legacy_key):
	method = tender.payment_method or "Other"
	if method == "Credit":
		return 0
	if not frappe.db.exists("Ledgix Payment Method", method):
		method = "Other"

	method_type = _payment_method_type(method)
	reference_number = (tender.reference_no or "").strip()
	if not reference_number and frappe.db.get_value("Ledgix Payment Method", method, "requires_reference"):
		reference_number = f"Legacy:{legacy_key}"

	payment = frappe.new_doc("Ledgix Payment")
	payment.payment_date = sale.sale_date
	payment.customer = sale.customer
	payment.payment_method = method
	payment.amount = amount
	payment.amount_tendered = flt(tender.amount) if method_type == "Cash" else amount
	payment.currency = "PKR"
	payment.reference_number = reference_number
	payment.cashier = _payment_user(sale.owner)
	payment.pos_shift = sale.pos_shift
	payment.legacy_source_key = legacy_key
	payment.append("allocations", {
		"reference_doctype": "Ledgix Sale",
		"reference_name": sale.name,
		"allocated_amount": amount,
		"remarks": "Migrated from legacy Sale Payment row",
	})
	payment.insert(ignore_permissions=True)
	payment.submit()
	return amount


def _backfill_legacy_payments():
	if not frappe.db.exists("DocType", "Ledgix Payment"):
		return

	for sale_name in frappe.get_all("Ledgix Sale", filters={"docstatus": 1}, pluck="name"):
		sale = frappe.get_doc("Ledgix Sale", sale_name)
		payable = flt(sale.grand_total or sale.total_amount)
		allocated = 0.0

		for tender in sale.payments:
			legacy_key = f"sale-payment:{sale.name}:{tender.name}"
			existing = frappe.db.get_value(
				"Ledgix Payment", {"legacy_source_key": legacy_key, "docstatus": 1}, "allocated_amount"
			)
			if existing is not None:
				allocated += flt(existing)
				continue

			remaining = max(payable - allocated, 0)
			amount = min(flt(tender.amount), remaining)
			if amount <= 0:
				continue
			allocated += _create_legacy_payment(sale, tender, amount, legacy_key)

		# Some historical/manual sales may only have paid_amount without tender rows.
		target_paid = min(flt(sale.paid_amount), payable)
		missing_paid = max(target_paid - allocated, 0)
		if missing_paid > 0.005:
			legacy_key = f"sale-paid-summary:{sale.name}"
			if not frappe.db.exists("Ledgix Payment", {"legacy_source_key": legacy_key}):
				class Tender:
					payment_method = "Other"
					amount = missing_paid
					reference_no = ""
				_create_legacy_payment(sale, Tender(), missing_paid, legacy_key)


def execute():
	if not frappe.db.exists("DocType", "Ledgix Price List"):
		return

	_ensure_price_list()
	_ensure_payment_methods()
	_backfill_item_prices()
	_backfill_customers()
	_ensure_sale_contract_fields()
	_backfill_legacy_payments()
	frappe.db.commit()
