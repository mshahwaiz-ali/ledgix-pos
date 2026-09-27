from pathlib import Path
import unittest
from unittest.mock import patch

import frappe

from fbr_v1.api import center
from fbr_v1.api.client_readiness import PROFILE_STATE_FIELDS
from fbr_v1.setup.v1_test_support import Row


class TestFbrV1CenterContract(unittest.TestCase):
    def test_center_boot_is_read_only_status_projection(self):
        readiness = {
            "mode": "Disabled",
            "enabled": False,
            "profile": None,
            "profile_state": None,
            "seller_identity": {},
            "source_accounting_ready": False,
            "source_blockers": ["Seller missing"],
            "setup_ready": False,
            "setup_blockers": ["Seller missing"],
            "sandbox_configuration_ready": False,
            "production_configuration_ready": False,
            "configuration": {"sandbox": {"devices": [], "blockers": []}, "production": {"devices": [], "blockers": []}},
            "network_cutover_active": False,
            "production_cutover_active": False,
            "production_ready": False,
            "blockers": [],
            "unresolved_contracts": [],
            "network_call": False,
        }

        def fake_get_list(doctype, *args, **kwargs):
            if doctype == "Company":
                return ["Test Company"]
            if doctype == "Ledgix FBR POS Device":
                return [Row(name="DEVICE-1", display_label="Counter", pos_id="123", environment="Sandbox",
                            operational_state="Unresolved", transport_topology="Cloud API", pos_profile="Main Counter POS",
                            outlet_address=None, active=1)]
            if doctype == "Ledgix FBR Item Mapping":
                return [Row(name="ITEM-1", needs_review=0), Row(name="ITEM-2", needs_review=1)]
            if doctype == "Ledgix FBR Tax Component Mapping":
                return [Row(name="TAX-1", component="Sales Tax Applicable", account_head="Sales Tax")]
            if doctype == "Mode of Payment":
                return [Row(name="Cash", custom_ledgix_fbr_v1_payment_mode="1 - Cash")]
            raise AssertionError(f"Unexpected get_list doctype: {doctype}")

        with patch.object(center, "get_client_readiness", return_value=readiness), patch.object(frappe, "get_list", side_effect=fake_get_list):
            result = center.get_center_boot("Test Company")

        self.assertFalse(result["network_call"])
        self.assertEqual(result["company"], "Test Company")
        self.assertEqual(result["devices"][0]["name"], "DEVICE-1")
        self.assertEqual(result["mapping_summary"]["active_item_mappings"], 2)
        self.assertEqual(result["mapping_summary"]["reviewed_item_mappings"], 1)
        self.assertEqual(result["mapping_summary"]["active_tax_component_mappings"], 1)
        self.assertEqual(result["mapping_summary"]["payment_mappings"], 1)


    def test_sandbox_cutover_enable_is_general_gate_only(self):
        profile = Row(
            name="FBR-PROFILE-00001",
            company="Test Company",
            protocol_version="Federal POS/IMS V1",
            enabled=1,
            mode="Sandbox",
            submit_trigger="Manual",
            transport_enabled=1,
            production_post_armed=0,
        )

        with (
            patch.object(frappe, "get_roles", return_value=["System Manager"]),
            patch.object(
                frappe,
                "get_doc",
                return_value=Row(name="Test Company"),
            ),
            patch(
                "fbr_v1.services.pos_identity.get_profile",
                return_value=profile,
            ),
            patch.object(
                center,
                "_raw_site_gate_enabled",
                return_value=False,
            ),
            patch.object(frappe, "get_all", return_value=[]),
            patch.object(center, "_write_site_gate") as write_gate,
            patch(
                "fbr_v1.protocol.transport.network_cutover_active",
                return_value=True,
            ),
            patch(
                "fbr_v1.protocol.transport.production_cutover_active",
                return_value=False,
            ),
        ):
            result = center.set_sandbox_network_cutover(
                "Test Company",
                1,
            )

        write_gate.assert_called_once_with(
            "fbr_v1_network_cutover_active",
            True,
        )
        self.assertTrue(result["network_cutover_active"])
        self.assertFalse(result["production_cutover_active"])
        self.assertFalse(result["network_call"])

    def test_sandbox_cutover_refuses_raw_production_gate(self):
        profile = Row(
            name="FBR-PROFILE-00001",
            company="Test Company",
            protocol_version="Federal POS/IMS V1",
            enabled=1,
            mode="Sandbox",
            submit_trigger="Manual",
            transport_enabled=1,
            production_post_armed=0,
        )

        with (
            patch.object(frappe, "get_roles", return_value=["System Manager"]),
            patch.object(
                frappe,
                "get_doc",
                return_value=Row(name="Test Company"),
            ),
            patch(
                "fbr_v1.services.pos_identity.get_profile",
                return_value=profile,
            ),
            patch.object(
                center,
                "_raw_site_gate_enabled",
                return_value=True,
            ),
            patch.object(center, "_write_site_gate") as write_gate,
        ):
            with self.assertRaises(frappe.ValidationError):
                center.set_sandbox_network_cutover(
                    "Test Company",
                    1,
                )

        write_gate.assert_not_called()

    def test_sandbox_cutover_refuses_automatic_submit(self):
        profile = Row(
            name="FBR-PROFILE-00001",
            company="Test Company",
            protocol_version="Federal POS/IMS V1",
            enabled=1,
            mode="Sandbox",
            submit_trigger="On Submit",
            transport_enabled=1,
            production_post_armed=0,
        )

        with (
            patch.object(frappe, "get_roles", return_value=["System Manager"]),
            patch.object(
                frappe,
                "get_doc",
                return_value=Row(name="Test Company"),
            ),
            patch(
                "fbr_v1.services.pos_identity.get_profile",
                return_value=profile,
            ),
            patch.object(center, "_write_site_gate") as write_gate,
        ):
            with self.assertRaises(frappe.ValidationError):
                center.set_sandbox_network_cutover(
                    "Test Company",
                    1,
                )

        write_gate.assert_not_called()

    def test_sandbox_cutover_disable_is_always_available_to_manager(self):
        with (
            patch.object(frappe, "get_roles", return_value=["System Manager"]),
            patch.object(center, "_write_site_gate") as write_gate,
            patch(
                "fbr_v1.protocol.transport.network_cutover_active",
                return_value=False,
            ),
            patch(
                "fbr_v1.protocol.transport.production_cutover_active",
                return_value=False,
            ),
        ):
            result = center.set_sandbox_network_cutover(
                "Test Company",
                0,
            )

        write_gate.assert_called_once_with(
            "fbr_v1_network_cutover_active",
            False,
        )
        self.assertFalse(result["network_cutover_active"])
        self.assertFalse(result["production_cutover_active"])
        self.assertFalse(result["network_call"])

    def test_profile_projection_never_exposes_password_fields(self):
        self.assertFalse(any("token" in field for field in PROFILE_STATE_FIELDS))
        self.assertIn("transport_enabled", PROFILE_STATE_FIELDS)
        self.assertIn("production_post_armed", PROFILE_STATE_FIELDS)
        self.assertIn("submit_trigger", PROFILE_STATE_FIELDS)
        self.assertIn("offline_policy", PROFILE_STATE_FIELDS)

    def test_center_frontend_is_status_driven_and_fail_closed(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "fbr_v1/page/fbr_v1_center/fbr_v1_center.js").read_text(encoding="utf-8")
        css = (root / "fbr_v1/page/fbr_v1_center/fbr_v1_center.css").read_text(encoding="utf-8")

        for marker in (
            "/assets/ledgix_saas/images/brand/fbr_v1.png",
            "Seller Identity",
            "Integration Profile",
            "POS Device / POSID",
            "Item & Tax Mapping",
            "Safety & Transport",
            "Readiness Blockers",
            "Invoice Readiness",
            "Local IMS Health",
            "Fiscalize Invoice",
            "Enable Sandbox Network",
            "Disable Sandbox Network",
            "fbr_v1.api.center.get_center_boot",
            "fbr_v1.api.center.set_sandbox_network_cutover",
            "fbr_v1.api.fiscalization.invoice_readiness",
        ):
            self.assertIn(marker, js)

        self.assertIn("canFiscalize", js)
        self.assertIn("canManageCutover", js)
        self.assertIn("network_cutover_active", js)
        self.assertIn("production_cutover_active", js)
        self.assertNotIn("set-config", js)
        self.assertNotIn("frappe.db.set_value", js)
        self.assertNotIn("fbr_v1_network_cutover_active", js)
        self.assertNotIn("fbr_v1_production_cutover_active", js)

        for marker in (".lx-fbr-status-grid", ".lx-fbr-safety-grid", ".lx-fbr-blocker-group", ".lx-fbr-danger-action", ".lx-fbr-readiness-head", ".lx-fbr-operation-grid", ".lx-fbr-card-identity"):
            self.assertIn(marker, css)
