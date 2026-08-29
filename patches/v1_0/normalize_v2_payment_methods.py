from __future__ import annotations

import frappe


CANONICAL_PAYMENT_METHODS = (
	("Cash", "Cash", 0, 1, 10),
	("Card", "Card", 1, 0, 20),
	("EasyPaisa", "Wallet", 1, 0, 30),
	("JazzCash", "Wallet", 1, 0, 40),
	("Bank Transfer", "Bank Transfer", 1, 0, 50),
	("Other", "Other", 1, 0, 90),
)


def execute():
	"""Normalize built-in V2 tender semantics once without changing enable/disable choices."""
	if not frappe.db.exists("DocType", "Ledgix Payment Method"):
		return

	for name, method_type, requires_reference, allow_change, sort_order in CANONICAL_PAYMENT_METHODS:
		values = {
			"method_type": method_type,
			"requires_reference": requires_reference,
			"allow_change": allow_change,
			"sort_order": sort_order,
		}
		if frappe.db.exists("Ledgix Payment Method", name):
			frappe.db.set_value(
				"Ledgix Payment Method",
				name,
				values,
				update_modified=False,
			)
			continue

		doc = frappe.new_doc("Ledgix Payment Method")
		doc.payment_method_name = name
		doc.enabled = 1
		for fieldname, value in values.items():
			setattr(doc, fieldname, value)
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
