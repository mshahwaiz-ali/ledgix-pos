from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from fbr_v12.services import fbr_v2_payload_builder as builder


class TestFBRV12PayloadRuntime(unittest.TestCase):
    def _invoice(self):
        return frappe._dict(
            {
                "doctype": "Sales Invoice",
                "name": "SINV-FBR-V12-PAYLOAD",
                "company": "Standalone FBR Test Company",
                "docstatus": 1,
                "is_return": 0,
                "posting_date": "2026-09-27",
            }
        )

    def _readiness(self, mode="Sandbox"):
        return {
            "errors": [],
            "warnings": [],
            "payload_input_ready": True,
            "profile": {"mode": mode},
            "identity": {
                "ready": True,
                "errors": [],
                "seller": {
                    "ntn_cnic": "1234567-8",
                    "business_name": "Standalone Seller",
                    "province": "Sindh",
                    "address": "Karachi",
                },
                "buyer": {
                    "ntn_cnic": "7654321-0",
                    "business_name": "Standalone Buyer",
                    "province": "Sindh",
                    "address": "Karachi",
                    "registration_type": "Registered",
                },
            },
            "native_snapshot_candidate": {
                "snapshot_source": "persisted_v2",
                "hash_verified": True,
                "snapshot_version": 2,
                "snapshot_hash": "abc123",
                "posting_date": "2026-09-27",
                "grand_total": 118.0,
                "lines": [
                    {
                        "idx": 1,
                        "item_code": "TEST-ITEM",
                        "item_name": "Test Item",
                        "qty": 1,
                        "amount": 100.0,
                        "net_amount": 100.0,
                        "discount_amount": 0,
                        "distributed_discount_amount": 0,
                        "components": {
                            "sales_tax": 18.0,
                            "sales_tax_withheld_at_source": 0,
                            "extra_tax": 0,
                            "further_tax": 0,
                            "fed_payable": 0,
                        },
                        "fbr_mapping": {
                            "name": "MAP-TEST",
                            "needs_review": 0,
                            "hs_code": "0101.21",
                            "fbr_uom": "Numbers, pieces, units",
                            "sales_type": "Goods at standard rate (default)",
                            "fbr_rate_description": "18%",
                            "tax_basis": "Transaction Value",
                            "notified_retail_price": 0,
                            "sro_schedule_number": "",
                            "sro_item_serial_number": "",
                        },
                    }
                ],
            },
        }

    @staticmethod
    def _exists(doctype, name_or_filters):
        if doctype == "Sales Invoice" and name_or_filters == "SINV-FBR-V12-PAYLOAD":
            return "SINV-FBR-V12-PAYLOAD"
        if doctype == "POS Invoice" and isinstance(name_or_filters, dict):
            return None
        return None

    def test_payload_is_deterministic_non_writing_and_non_networked(self):
        invoice = self._invoice()

        with patch.object(frappe.db, "exists", side_effect=self._exists), patch.object(
            frappe, "get_doc", return_value=invoice
        ), patch.object(
            builder.fbr_v2_readiness,
            "evaluate_invoice_readiness",
            return_value=self._readiness(),
        ):
            result = builder.build_payload_candidate(
                "Sales Invoice",
                invoice.name,
                scenario_id="SN001",
            )

        payload = result["payload"]
        self.assertEqual(payload["invoiceType"], "Sale Invoice")
        self.assertEqual(payload["invoiceDate"], "2026-09-27")
        self.assertEqual(payload["sellerNTNCNIC"], "12345678")
        self.assertEqual(payload["buyerNTNCNIC"], "76543210")
        self.assertEqual(payload["scenarioId"], "SN001")
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["totalValues"], 118.0)
        self.assertTrue(result["reconciliation"]["passed"])
        self.assertEqual(result["reconciliation"]["difference"], 0.0)
        self.assertFalse(result["database_write"])
        self.assertFalse(result["fbr_network_call"])
        self.assertFalse(result["contains_secrets"])

    def test_scenario_id_fails_closed_outside_sandbox(self):
        invoice = self._invoice()

        with patch.object(frappe.db, "exists", side_effect=self._exists), patch.object(
            frappe, "get_doc", return_value=invoice
        ), patch.object(
            builder.fbr_v2_readiness,
            "evaluate_invoice_readiness",
            return_value=self._readiness(mode="Production"),
        ):
            with self.assertRaises(frappe.ValidationError):
                builder.build_payload_candidate(
                    "Sales Invoice",
                    invoice.name,
                    scenario_id="SN001",
                )


if __name__ == "__main__":
    unittest.main()
