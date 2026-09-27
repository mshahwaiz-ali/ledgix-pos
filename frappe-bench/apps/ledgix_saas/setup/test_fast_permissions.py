import unittest
from pathlib import Path

from ledgix_saas.setup import fast_permissions


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
