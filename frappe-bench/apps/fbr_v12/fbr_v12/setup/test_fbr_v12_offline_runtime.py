from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from fbr_v12.api import fbr_native, fbr_offline


class TestFBRV12OfflineRuntime(unittest.TestCase):
    COMPANY = "Standalone FBR Test Company"

    def _state(self):
        return {
            "profile": {
                "exists": True,
                "name": "FBR-PROFILE-RUNTIME",
                "enabled": True,
                "mode": "Production",
                "submit_trigger": "Manual",
                "production_token_configured": True,
                "production_post_armed": True,
            },
            "sandbox_certification": {
                "name": "FBR-CERT-RUNTIME",
                "status": "Complete",
                "evidence_complete": True,
                "complete": True,
            },
            "database_write": False,
            "fbr_network_call": False,
            "contains_secrets": False,
        }

    def _profile(self):
        return frappe._dict(
            {
                "name": "FBR-PROFILE-RUNTIME",
                "offline_policy": "Operator Confirmed",
                "offline_upload_window_hours": 24,
            }
        )

    def test_offline_policy_is_fail_closed_until_global_cutover(self):
        state = self._state()
        profile = self._profile()

        with patch.object(
            fbr_offline.fbr_v2_readiness,
            "get_company_profile_state",
            return_value=state,
        ), patch.object(
            frappe.db,
            "exists",
            return_value=True,
        ), patch.object(
            frappe,
            "get_doc",
            return_value=profile,
        ), patch.object(
            fbr_native,
            "V2_NETWORK_CUTOVER_ACTIVE",
            False,
        ):
            blocked = fbr_offline._offline_policy(self.COMPANY)

        self.assertFalse(blocked["ready"])
        self.assertTrue(
            any("network cutover is not active" in row for row in blocked["blockers"])
        )
        self.assertFalse(blocked["contains_secrets"])

    def test_offline_policy_can_become_ready_without_network_io(self):
        state = self._state()
        profile = self._profile()

        with patch.object(
            fbr_offline.fbr_v2_readiness,
            "get_company_profile_state",
            return_value=state,
        ), patch.object(
            frappe.db,
            "exists",
            return_value=True,
        ), patch.object(
            frappe,
            "get_doc",
            return_value=profile,
        ), patch.object(
            fbr_native,
            "V2_NETWORK_CUTOVER_ACTIVE",
            True,
        ):
            ready = fbr_offline._offline_policy(self.COMPANY)

        self.assertTrue(ready["ready"])
        self.assertEqual(ready["blockers"], [])
        self.assertEqual(ready["offline_policy"], "Operator Confirmed")
        self.assertEqual(ready["upload_window_hours"], 24)
        self.assertTrue(ready["production_post_armed"])
        self.assertTrue(ready["production_token_configured"])
        self.assertTrue(ready["sandbox_certification_complete"])
        self.assertFalse(ready["contains_secrets"])


if __name__ == "__main__":
    unittest.main()
