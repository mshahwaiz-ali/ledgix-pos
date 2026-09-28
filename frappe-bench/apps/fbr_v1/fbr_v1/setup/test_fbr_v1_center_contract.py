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
            "configuration": {
                "sandbox": {"devices": [], "blockers": []},
                "production": {"devices": [], "blockers": []},
            },
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
                return [
                    Row(
                        name="DEVICE-1",
                        display_label="Counter",
                        pos_id="123",
                        environment="Sandbox",
                        operational_state="Unresolved",
                        transport_topology="Cloud API",
                        pos_profile="Main Counter POS",
                        outlet_address=None,
                        active=1,
                    )
                ]
            if doctype == "Ledgix FBR Item Mapping":
                return [
                    Row(name="ITEM-1", needs_review=0),
                    Row(name="ITEM-2", needs_review=1),
                ]
            if doctype == "Ledgix FBR Tax Component Mapping":
                return [
                    Row(
                        name="TAX-1",
                        component="Sales Tax Applicable",
                        account_head="Sales Tax",
                    )
                ]
            if doctype == "Mode of Payment":
                return [
                    Row(
                        name="Cash",
                        custom_ledgix_fbr_v1_payment_mode="1 - Cash",
                    )
                ]
            if doctype == "Ledgix FBR Submission Log":
                self.assertEqual(
                    kwargs["filters"],
                    {"pos_device": ["in", ["DEVICE-1"]]},
                )
                self.assertEqual(kwargs["order_by"], "modified desc")
                self.assertEqual(kwargs["limit_page_length"], 1)
                return [
                    Row(
                        name="FBR-LOG-2026-00001",
                        reference_doctype="POS Invoice",
                        reference_name="ACC-PSINV-2026-00002",
                        fbr_status="Pending",
                        fbr_invoice_number="",
                        attempt_count=0,
                        attempt_id=None,
                        source_snapshot_hash="snapshot-hash",
                        request_hash=None,
                        transport_started_at=None,
                        transport_finished_at=None,
                        transport_outcome="Not Attempted",
                        reconciliation_required=0,
                        error_code=None,
                        error_message=None,
                        modified="2026-09-28 00:00:00",
                    )
                ]
            raise AssertionError(f"Unexpected get_list doctype: {doctype}")

        with (
            patch.object(center, "get_client_readiness", return_value=readiness),
            patch.object(frappe, "get_list", side_effect=fake_get_list),
        ):
            result = center.get_center_boot("Test Company")

        self.assertFalse(result["network_call"])
        self.assertEqual(result["company"], "Test Company")
        self.assertEqual(result["devices"][0]["name"], "DEVICE-1")
        self.assertEqual(result["mapping_summary"]["active_item_mappings"], 2)
        self.assertEqual(result["mapping_summary"]["reviewed_item_mappings"], 1)
        self.assertEqual(
            result["mapping_summary"]["active_tax_component_mappings"],
            1,
        )
        self.assertEqual(result["mapping_summary"]["payment_mappings"], 1)
        self.assertEqual(
            result["latest_submission"]["name"],
            "FBR-LOG-2026-00001",
        )
        self.assertEqual(
            result["latest_submission"]["transport_outcome"],
            "Not Attempted",
        )

    def test_submission_summary_projection_excludes_payloads_and_credentials(self):
        sensitive = {
            "request_json",
            "response_json",
            "credential",
            "credentials",
            "token",
            "sandbox_token",
            "production_token",
            "authorization",
        }
        normalized = {field.lower() for field in center.SUBMISSION_SUMMARY_FIELDS}
        self.assertTrue(sensitive.isdisjoint(normalized))
        self.assertIn("attempt_id", normalized)
        self.assertIn("request_hash", normalized)
        self.assertIn("source_snapshot_hash", normalized)
        self.assertIn("transport_outcome", normalized)
        self.assertIn("reconciliation_required", normalized)

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

    def test_center_frontend_is_compact_tabbed_and_fail_closed(self):
        root = Path(__file__).resolve().parents[1]
        js = (
            root / "fbr_v1/page/fbr_v1_center/fbr_v1_center.js"
        ).read_text(encoding="utf-8")
        css = (
            root / "fbr_v1/page/fbr_v1_center/fbr_v1_center.css"
        ).read_text(encoding="utf-8")

        for marker in (
            "/assets/ledgix_saas/images/brand/fbr_v1.png",
            "Federal FBR POS / IMS V1",
            "Overview",
            "Sandbox",
            "Setup",
            "Evidence",
            "Production",
            "Seller Identity",
            "Integration Profile",
            "POS Device / POSID",
            "Mappings",
            "Sandbox Environment",
            "Latest Submission / Evidence",
            "Invoice Test",
            "Check Readiness",
            "Fiscalize Invoice",
            "Enable Sandbox Network",
            "Disable Sandbox Network",
            "Production transport is locked",
            "Production cutover cannot be enabled from FBR V1 Center.",
            "Production Invoice",
            "Fiscalize Production Invoice",
            "This performs one REAL FBR Production POST",
            "Advanced diagnostics",
            "Advanced evidence actions",
            "fbr_v1.api.center.get_center_boot",
            "fbr_v1.api.center.set_sandbox_network_cutover",
            "fbr_v1.api.fiscalization.invoice_readiness",
            "fbr_v1.api.fiscalization.submit_invoice",
        ):
            self.assertIn(marker, js)

        self.assertNotIn(
            "/assets/ledgix_saas/images/brand/fbr-logo-1.png",
            js,
        )
        self.assertIn("danger: gateOn", js)
        self.assertIn(".lx-fbr-danger-action:not(:disabled)", css)
        self.assertIn("control.set_value(data.company)", js)
        self.assertIn("typeControl.set_value(invoiceType)", js)
        self.assertIn("ready_for_fiscalize", js)
        self.assertIn("Run Check Readiness first.", js)
        self.assertIn("typeControl.df.change = () =>", js)
        self.assertIn("invoiceControl.df.change = () =>", js)
        self.assertIn("productionInvoiceName", js)
        self.assertIn("productionActionResult", js)
        self.assertIn("checkProductionInvoiceReadiness", js)
        self.assertIn("fiscalizeProductionInvoice", js)
        self.assertNotIn("...(state.externalBlockers || [])", js)
        self.assertIn(".lx-fbr-invoice-test-panel", css)
        self.assertIn(".lx-fbr-latest-evidence", css)
        self.assertNotIn("Authority / external requirements", js)

        for forbidden in (
            "This Center never switches cutover gates.",
            "Enable Production",
            "set-config",
            "frappe.db.set_value",
            "fbr_v1_network_cutover_active",
            "fbr_v1_production_cutover_active",
        ):
            self.assertNotIn(forbidden, js)

        for marker in (
            ".lx-fbr-console-header",
            ".lx-fbr-tabs",
            ".lx-fbr-status-grid",
            ".lx-fbr-fact-grid",
            ".lx-fbr-action-grid",
            ".lx-fbr-invoice-fields",
            ".lx-fbr-advanced",
            ".lx-fbr-production-panel",
            ".lx-fbr-sandbox-top-grid",
            ".lx-fbr-requirements",
            ".lx-fbr-v1-wrapper .page-head",
        ):
            self.assertIn(marker, css)
