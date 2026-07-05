"""Sync Ledgix DocType permissions for business roles."""

from __future__ import annotations

import json
from pathlib import Path

import frappe
from frappe.permissions import add_permission, update_permission_property

APP_ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = APP_ROOT / "ledgix" / "doctype"

BUSINESS_ROLES = (
	"Ledgix Cashier",
	"Ledgix Manager",
	"Ledgix Admin",
	"Ledgix Super Admin",
)

PERM_KEYS = (
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"share",
	"print",
	"email",
)


def _perm(role, **values):
	row = {key: 0 for key in PERM_KEYS}
	row.update(values)
	row["role"] = role
	return row


def _full(role):
	return _perm(
		role,
		read=1,
		write=1,
		create=1,
		delete=1,
		report=1,
		export=1,
		share=1,
		print=1,
		email=1,
	)


def _full_submittable(role):
	return _perm(
		role,
		read=1,
		write=1,
		create=1,
		delete=1,
		submit=1,
		cancel=1,
		amend=1,
		report=1,
		export=1,
		share=1,
		print=1,
		email=1,
	)


def _read(role):
	return _perm(role, read=1, print=1)


def _rw(role):
	return _perm(role, read=1, write=1, create=1, print=1, email=1)


def _rws(role):
	return _perm(role, read=1, write=1, create=1, submit=1, print=1, email=1)


def _rows(*rows):
	seen = set()
	ordered = []
	for row in rows:
		role = row["role"]
		if role in seen:
			continue
		seen.add(role)
		ordered.append(row)
	return ordered


# fmt: off
DOCTYPE_PERMISSIONS = {
	"Ledgix Item": _rows(_full("System Manager"), _full("Ledgix Admin"), _rw("Ledgix Manager"), _read("Ledgix Cashier")),
	"Ledgix Category": _rows(_full("System Manager"), _full("Ledgix Admin"), _rw("Ledgix Manager"), _read("Ledgix Cashier")),
	"Ledgix Customer": _rows(_full("System Manager"), _full("Ledgix Admin"), _rw("Ledgix Manager"), _rw("Ledgix Cashier")),
	"Ledgix Supplier": _rows(_full("System Manager"), _full("Ledgix Admin"), _rw("Ledgix Manager")),
	"Ledgix Sale": _rows(_full_submittable("System Manager"), _full_submittable("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Sale Item": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Sale Payment": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Purchase": _rows(_full_submittable("System Manager"), _full_submittable("Ledgix Admin"), _rws("Ledgix Manager")),
	"Ledgix Purchase Item": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Sales Return": _rows(_full_submittable("System Manager"), _full_submittable("Ledgix Admin"), _rws("Ledgix Manager")),
	"Ledgix Sales Return Item": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix POS Shift": _rows(_full_submittable("System Manager"), _full_submittable("Ledgix Admin"), _rw("Ledgix Manager"), _rw("Ledgix Cashier")),
	"Ledgix POS Hold": _rows(_full("System Manager"), _full("Ledgix Admin"), _rw("Ledgix Manager"), _rw("Ledgix Cashier")),
	"Ledgix POS Hold Item": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager"), _read("Ledgix Cashier")),
	"Ledgix Stock Movement": _rows(_full_submittable("System Manager"), _full_submittable("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Stock Serial": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager"), _read("Ledgix Cashier")),
	"Ledgix Stock Lot": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Stock Lot Allocation": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Mode Settings": _rows(_full("System Manager"), _full("Ledgix Admin")),
	"Ledgix POS Theme Settings": _rows(_full("System Manager"), _full("Ledgix Admin")),
	"Ledgix Tax Profile": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Tax Category": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Tax Rate": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix FBR Settings": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Item Tax Profile": _rows(_full("System Manager"), _full("Ledgix Admin"), _rw("Ledgix Manager")),
	"Ledgix FBR Submission Log": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Tax Audit Log": _rows(_full("System Manager"), _full("Ledgix Admin")),
	"Ledgix Invoice Tax Detail": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Return Tax Detail": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix User Profile": _rows(_full("System Manager"), _full("Ledgix Admin"), _read("Ledgix Manager")),
	"Ledgix Brand Settings": _rows(_full("System Manager"), _full("Ledgix Admin")),
	"Ledgix Maintenance Tool": _rows(_full("System Manager"), _full("Ledgix Super Admin")),
}
# fmt: on


REPORT_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager")

PAGE_ROLES = {
	"ledgix-pos": ("System Manager", "Ledgix Admin", "Ledgix Manager", "Ledgix Cashier"),
	"ledgix_operations": ("System Manager", "Ledgix Admin", "Ledgix Manager"),
	"ledgix-reports": ("System Manager", "Ledgix Admin", "Ledgix Manager"),
	"ledgix-tax-center": ("System Manager", "Ledgix Admin", "Ledgix Manager"),
	"business-intelligence-center": ("System Manager", "Ledgix Admin", "Ledgix Manager"),
	"ledgix-dashboard": ("System Manager", "Ledgix Admin", "Ledgix Manager"),
}

ROLE_HOME_PAGES = {
	"Ledgix Cashier": "ledgix-pos",
	"Ledgix Manager": "ledgix_operations",
	"Ledgix Admin": "Ledgix",
}

WORKSPACE_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager", "Ledgix Cashier")


def _doctype_slug(doctype):
	return doctype.lower().replace(" ", "_")


def _doctype_json_path(doctype):
	slug = _doctype_slug(doctype)
	return DOCTYPE_ROOT / slug / f"{slug}.json"


def write_doctype_permission_files():
	for doctype, permissions in DOCTYPE_PERMISSIONS.items():
		path = _doctype_json_path(doctype)
		if not path.exists():
			continue
		data = json.loads(path.read_text(encoding="utf-8"))
		data["permissions"] = permissions
		path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _apply_perm_row(doctype, permlevel, row):
	role = row["role"]
	add_permission(doctype, role, permlevel)
	for key in PERM_KEYS:
		update_permission_property(doctype, role, permlevel, key, row.get(key, 0))


def sync_doctype_permissions():
	for doctype, permissions in DOCTYPE_PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for row in permissions:
			_apply_perm_row(doctype, 0, row)


def sync_page_roles():
	for page_name, roles in PAGE_ROLES.items():
		if not frappe.db.exists("Page", page_name):
			continue
		frappe.db.delete("Has Role", {"parent": page_name, "parenttype": "Page"})
		for role in roles:
			frappe.get_doc(
				{
					"doctype": "Has Role",
					"parent": page_name,
					"parenttype": "Page",
					"parentfield": "roles",
					"role": role,
				}
			).insert(ignore_permissions=True)


def sync_role_home_pages():
	for role_name, home_page in ROLE_HOME_PAGES.items():
		if not frappe.db.exists("Role", role_name):
			continue
		frappe.db.set_value("Role", role_name, "home_page", home_page)


def sync_workspace_roles():
	if not frappe.db.exists("Workspace", "Ledgix"):
		return
	frappe.db.delete("Has Role", {"parent": "Ledgix", "parenttype": "Workspace"})
	for role in WORKSPACE_ROLES:
		frappe.get_doc(
			{
				"doctype": "Has Role",
				"parent": "Ledgix",
				"parenttype": "Workspace",
				"parentfield": "roles",
				"role": role,
			}
		).insert(ignore_permissions=True)


def sync_report_roles():
	report_root = APP_ROOT / "ledgix" / "report"
	if not report_root.exists():
		return

	for report_dir in report_root.iterdir():
		if not report_dir.is_dir():
			continue
		json_path = report_dir / f"{report_dir.name}.json"
		if not json_path.exists():
			continue
		report_name = json.loads(json_path.read_text(encoding="utf-8")).get("name")
		if not report_name or not frappe.db.exists("Report", report_name):
			continue
		frappe.db.delete("Has Role", {"parent": report_name, "parenttype": "Report"})
		for role in REPORT_ROLES:
			frappe.get_doc(
				{
					"doctype": "Has Role",
					"parent": report_name,
					"parenttype": "Report",
					"parentfield": "roles",
					"role": role,
				}
			).insert(ignore_permissions=True)


def ensure_super_admin_role():
	if frappe.db.exists("Role", "Ledgix Super Admin"):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": "Ledgix Super Admin",
			"desk_access": 1,
			"is_custom": 0,
		}
	).insert(ignore_permissions=True)


def sync_all():
	ensure_super_admin_role()
	sync_doctype_permissions()
	sync_page_roles()
	sync_role_home_pages()
	sync_workspace_roles()
	sync_report_roles()
	frappe.db.commit()


def after_migrate():
	sync_all()
