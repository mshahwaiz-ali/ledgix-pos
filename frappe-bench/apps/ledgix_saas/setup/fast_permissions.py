"""Fast, idempotent executor for Ledgix post-migrate permission synchronization.

The permission policy remains defined in ``ledgix_saas.setup.permissions``.  This
module only avoids rewriting rows that already match that policy.  The legacy
sync called ``update_permission_property`` once for every permission flag, and
Frappe validates the entire DocType on every such call.  On an unchanged site
that turns a no-op migrate into hundreds of unnecessary writes/validations.
"""

from __future__ import annotations

import json

import frappe
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
from frappe.permissions import setup_custom_perms
from frappe.utils import cint

from ledgix_saas.setup import permissions as policy


PERM_KEYS = policy.PERM_KEYS


def _permission_updates(current, desired_row):
	"""Return only permission flags whose stored value differs from policy."""
	updates = {}
	for key in PERM_KEYS:
		desired = cint(desired_row.get(key, 0))
		current_value = cint((current or {}).get(key, 0))
		if current_value != desired:
			updates[key] = desired
	return updates


def _new_custom_perm(doctype, role, permlevel, desired_row):
	values = {key: cint(desired_row.get(key, 0)) for key in PERM_KEYS}
	frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": permlevel,
			"if_owner": 0,
			**values,
		}
	).insert(ignore_permissions=True)


def sync_doctype_permissions():
	"""Apply only changed permission rows and validate each changed DocType once."""
	for doctype, desired_rows in policy.DOCTYPE_PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			continue

		# Ensure Custom DocPerm exists once per DocType.  Frappe's old helper path
		# performed this check repeatedly for every permission flag.
		setup_custom_perms(doctype)
		current_rows = frappe.get_all(
			"Custom DocPerm",
			filters={"parent": doctype, "permlevel": 0, "if_owner": 0},
			fields=["name", "role", *PERM_KEYS],
		)
		current_by_role = {row.role: row for row in current_rows}
		changed = False

		for desired_row in desired_rows:
			role = desired_row["role"]
			current = current_by_role.get(role)
			if not current:
				_new_custom_perm(doctype, role, 0, desired_row)
				changed = True
				continue

			updates = _permission_updates(current, desired_row)
			if updates:
				frappe.db.set_value(
					"Custom DocPerm",
					current.name,
					updates,
					update_modified=False,
				)
				changed = True

		if changed:
			validate_permissions_for_doctype(doctype)


def _sync_has_roles(parent, parenttype, parentfield, roles):
	"""Replace Has Role children only when the effective role set changed."""
	desired = set(roles)
	current = set(
		frappe.get_all(
			"Has Role",
			filters={"parent": parent, "parenttype": parenttype},
			pluck="role",
		)
	)
	if current == desired:
		return False

	frappe.db.delete("Has Role", {"parent": parent, "parenttype": parenttype})
	for role in roles:
		frappe.get_doc(
			{
				"doctype": "Has Role",
				"parent": parent,
				"parenttype": parenttype,
				"parentfield": parentfield,
				"role": role,
			}
		).insert(ignore_permissions=True)
	return True


def sync_page_roles():
	for page_name, roles in policy.PAGE_ROLES.items():
		if frappe.db.exists("Page", page_name):
			_sync_has_roles(page_name, "Page", "roles", roles)


def sync_role_home_pages():
	for role_name, home_page in policy.ROLE_HOME_PAGES.items():
		if not frappe.db.exists("Role", role_name):
			continue
		if frappe.db.get_value("Role", role_name, "home_page") != home_page:
			frappe.db.set_value("Role", role_name, "home_page", home_page, update_modified=False)


def sync_workspace_roles():
	if frappe.db.exists("Workspace", "Ledgix"):
		_sync_has_roles("Ledgix", "Workspace", "roles", policy.WORKSPACE_ROLES)


def sync_report_roles():
	report_root = policy.APP_ROOT / "ledgix" / "report"
	if not report_root.exists():
		return

	for report_dir in report_root.iterdir():
		if not report_dir.is_dir():
			continue
		json_path = report_dir / f"{report_dir.name}.json"
		if not json_path.exists():
			continue
		report_name = json.loads(json_path.read_text(encoding="utf-8")).get("name")
		if report_name and frappe.db.exists("Report", report_name):
			_sync_has_roles(report_name, "Report", "roles", policy.REPORT_ROLES)


def sync_all():
	# Cleanup routines are already naturally cheap/no-op once retired records are gone.
	policy.cleanup_retired_doctypes()
	policy.cleanup_retired_roles()
	sync_doctype_permissions()
	policy.cleanup_retired_pages()
	sync_page_roles()
	sync_role_home_pages()
	sync_workspace_roles()
	sync_report_roles()
	frappe.db.commit()


def after_migrate():
	sync_all()
