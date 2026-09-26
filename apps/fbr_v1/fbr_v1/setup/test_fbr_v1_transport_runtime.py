from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from fbr_v1.api import fbr_transport, fbr_v2_transport


class TestFBRV1TransportRuntime(unittest.TestCase):
    COMPANY = "Standalone FBR Test Company"

    def _profile(self, *, mode, enabled=1, armed=0):
        return frappe._dict(
            {
                "name": "FBR-PROFILE-RUNTIME",
                "company": self.COMPANY,
                "enabled": enabled,
                "mode": mode,
                "production_post_armed": armed,
            }
        )

    @staticmethod
    def _valid_result(invoice_number=""):
        response = {
            "validationResponse": {
                "status": "Valid",
                "statusCode": "00",
                "invoiceStatuses": [],
            }
        }
        if invoice_number:
            response["invoiceNumber"] = invoice_number
        return {
            "success": True,
            "network_call": True,
            "http_status": 200,
            "status": "HTTP OK",
            "response": response,
            "error": "",
        }

    def test_transport_policy_uses_only_in_memory_fake_http(self):
        state = {
            "profile": self._profile(mode="Sandbox"),
            "certified": False,
            "result": self._valid_result(),
        }
        calls = []

        def fake_post_json(*, url, token, payload, timeout=30):
            calls.append((url, token, payload, timeout))
            return dict(state["result"])

        def fake_certification(profile):
            return {
                "name": "CERT" if state["certified"] else "",
                "status": "Complete" if state["certified"] else "In Progress",
                "evidence_complete": state["certified"],
                "complete": state["certified"],
            }

        with patch.object(
            fbr_v2_transport,
            "_profile_for_company",
            side_effect=lambda company: state["profile"] if company == self.COMPANY else None,
        ), patch.object(
            fbr_v2_transport,
            "_token",
            side_effect=lambda profile, mode: "sandbox-secret"
            if mode == "Sandbox"
            else "production-secret",
        ), patch.object(
            fbr_v2_transport,
            "_production_certification",
            side_effect=fake_certification,
        ), patch.object(
            fbr_transport,
            "requests_available",
            return_value=True,
        ), patch.object(
            fbr_transport,
            "post_json",
            side_effect=fake_post_json,
        ):
            sandbox = fbr_v2_transport.validate_invoice(
                company=self.COMPANY,
                payload={"invoiceType": "Sale Invoice", "items": [{}]},
                mode="Sandbox",
            )
            self.assertTrue(sandbox["success"])
            self.assertEqual(calls[-1][0], fbr_v2_transport.SANDBOX_VALIDATE_URL)
            self.assertEqual(calls[-1][1], "sandbox-secret")

            state["profile"] = self._profile(mode="Production", armed=1)
            state["certified"] = False
            before = len(calls)
            blocked = fbr_v2_transport.post_invoice(
                company=self.COMPANY,
                payload={"invoiceType": "Sale Invoice", "items": [{}]},
                mode="Production",
            )
            self.assertFalse(blocked["network_call"])
            self.assertEqual(len(calls), before)
            self.assertIn("completed Sandbox Certification", blocked["error"])

            state["certified"] = True
            state["result"] = {
                "success": False,
                "network_call": True,
                "http_status": None,
                "status": "Network Error",
                "response": None,
                "error": "simulated timeout",
            }
            ambiguous = fbr_v2_transport.post_invoice(
                company=self.COMPANY,
                payload={"invoiceType": "Sale Invoice", "items": [{}]},
                mode="Production",
            )
            self.assertEqual(calls[-1][0], fbr_v2_transport.PRODUCTION_POST_URL)
            self.assertEqual(calls[-1][1], "production-secret")
            self.assertTrue(ambiguous["ambiguous_outcome"])
            self.assertTrue(ambiguous["requires_reconciliation"])
            self.assertFalse(ambiguous["contains_secrets"])
            self.assertIn("automatic recovery is intentionally disabled", ambiguous["error"])


if __name__ == "__main__":
    unittest.main()
