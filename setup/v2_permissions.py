"""Permissions for Ledgix V2 additive business doctypes."""

import frappe
from frappe.permissions import add_permission, update_permission_property


PERMISSIONS = {
	"Ledgix Price List": {
		"System Manager": (1, 1, 1, 1),
		"Ledgix Admin": (1, 1, 1, 1),
		"Ledgix Manager": (1, 1, 1, 0),
		"Ledgix Cashier": (1, 0, 0, 0),
	},
	"Ledgix Item Price": {
		"System Manager": (1, 1, 1, 1),
		"Ledgix Admin": (1, 1, 1, 1),
		"Ledgix Manager": (1, 1, 1, 0),
		"Ledgix Cashier": (1, 0, 0, 0),
	},
	"Ledgix Payment Method": {
		"System Manager": (1, 1, 1, 1),
		"Ledgix Admin": (1, 1, 1, 1),
		"Ledgix Manager": (1, 0, 0, 0),
		"Ledgix Cashier": (1, 0, 0, 0),
	},
	"Ledgix Payment": {
		"System Manager": (1, 1, 1, 1),
		"Ledgix Admin": (1, 1, 1, 1),
		"Ledgix Manager": (1, 0, 0, 0),
		"Ledgix Cashier": (1, 0, 0, 0),
	},
	"Ledgix Payment Allocation": {
		"System Manager": (1, 1, 1, 1),
		"Ledgix Admin": (1, 1, 1, 1),
		"Ledgix Manager": (1, 0, 0, 0),
		"Ledgix Cashier": (1, 0, 0, 0),
	},
}


def _sync(doctype, role, values):
	read, write, create, delete = values
	add_permission(doctype, role, 0)
	for key, value in {
		"read": read,
		"write": write,
		"create": create,
		"delete": delete,
		"submit": 1 if doctype == "Ledgix Payment" and role in {"System Manager", "Ledgix Admin"} else 0,
		"cancel": 0,
		"amend": 0,
		"report": read,
		"export": read if role != "Ledgix Cashier" else 0,
		"share": 0,
		"print": read,
		"email": 0,
	}.items():
		update_permission_property(doctype, role, 0, key, value)


def sync_v2_permissions():
	for doctype, roles in PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for role, values in roles.items():
			if frappe.db.exists("Role", role):
				_sync(doctype, role, values)
	frappe.clear_cache()


def after_migrate():
	sync_v2_permissions()
