import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe

from ledgix_saas.setup import fast_permissions, permissions


class TestFastPermissionSync(unittest.TestCase):
	def test_unchanged_permission_row_is_noop(self):
		current = {key: 0 for key in fast_permissions.PERM_KEYS}
		current.update({"read": 1, "write": 1})
		desired = {key: 0 for key in fast_permissions.PERM_KEYS}
		desired.update({"role": "Ledgix Manager", "read": 1, "write": 1})

		self.assertEqual(fast_permissions._permission_updates(current, desired), {})

	def test_only_changed_permission_flags_are_returned(self):
		current = {key: 0 for key in fast_permissions.PERM_KEYS}
		current.update({"read": 1, "write": 0})
		desired = {key: 0 for key in fast_permissions.PERM_KEYS}
		desired.update({"role": "Ledgix Manager", "read": 1, "write": 1, "print": 1})

		self.assertEqual(
			fast_permissions._permission_updates(current, desired),
			{"write": 1, "print": 1},
		)

	def test_hook_uses_fast_executor(self):
		hooks_source = (Path(__file__).resolve().parents[1] / "hooks.py").read_text(encoding="utf-8")
		self.assertIn("ledgix_saas.setup.fast_permissions.after_migrate", hooks_source)

	def test_submission_log_schema_matches_read_only_policy(self):
		schema_path = (
			Path(__file__).resolve().parents[1]
			/ "ledgix"
			/ "doctype"
			/ "ledgix_fbr_submission_log"
			/ "ledgix_fbr_submission_log.json"
		)
		schema = json.loads(schema_path.read_text(encoding="utf-8"))
		policy_rows = permissions.DOCTYPE_PERMISSIONS["Ledgix FBR Submission Log"]

		def normalized(rows):
			return {
				row["role"]: {
					key: int(row.get(key, 0) or 0)
					for key in permissions.PERM_KEYS
				}
				for row in rows
			}

		self.assertEqual(normalized(schema.get("permissions") or []), normalized(policy_rows))
		for row in policy_rows:
			self.assertEqual(row.get("write", 0), 0)
			self.assertEqual(row.get("create", 0), 0)
			self.assertEqual(row.get("delete", 0), 0)
			self.assertEqual(row.get("submit", 0), 0)
			self.assertEqual(row.get("cancel", 0), 0)
			self.assertEqual(row.get("amend", 0), 0)

	def test_fast_sync_removes_old_submission_log_mutation_rights(self):
		def current(role, **overrides):
			row = {key: 0 for key in fast_permissions.PERM_KEYS}
			row.update(
				{
					"name": f"PERM-{role}",
					"role": role,
					"read": 1,
					"print": 1,
				}
			)
			row.update(overrides)
			return frappe._dict(row)

		rows = [
			current(
				"System Manager",
				write=1,
				create=1,
				delete=1,
				submit=1,
				cancel=1,
				amend=1,
				report=1,
				export=1,
				share=1,
				email=1,
			),
			current(
				"Ledgix Admin",
				write=1,
				create=1,
				delete=1,
				submit=1,
				cancel=1,
				amend=1,
				report=1,
				export=1,
				share=1,
				email=1,
			),
			current("Ledgix Manager"),
		]

		db = MagicMock()
		db.exists.side_effect = lambda doctype, name=None: (
			doctype == "DocType" and name == "Ledgix FBR Submission Log"
		)

		with patch.object(fast_permissions.frappe, "db", db, create=True), patch.object(
			fast_permissions.frappe, "get_all", return_value=rows
		), patch.object(
			fast_permissions, "setup_custom_perms"
		), patch.object(
			fast_permissions, "validate_permissions_for_doctype"
		) as validate:
			fast_permissions.sync_doctype_permissions()

		self.assertEqual(db.set_value.call_count, 2)
		for call in db.set_value.call_args_list:
			updates = call.args[2]
			for key in ("write", "create", "delete", "submit", "cancel", "amend"):
				self.assertEqual(updates.get(key), 0)
		validate.assert_called_once_with("Ledgix FBR Submission Log")
