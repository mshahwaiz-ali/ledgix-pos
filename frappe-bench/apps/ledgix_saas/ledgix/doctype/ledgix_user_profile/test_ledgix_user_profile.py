import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
    configure_v2_test_environment,
    make_user_with_roles,
)


LEGACY_BUSINESS_TEST_RETIRED = False
LEGACY_PARTIAL_TEST_RETIREMENT = True
LEGACY_HISTORICAL_SOURCE_COMMIT = "808f384311b0545e1d3e39791f085db5678832bb"
LEGACY_BUSINESS_TEST_RETIREMENT_REASON = (
    "Retired after Phase 12 ERPNext cutover: this test creates frozen "
    "pre-cutover Ledgix business records. Current authority is ERPNext."
)


class TestLedgixUserProfile(FrappeTestCase):
    def setUp(self):
        super().setUp()
        configure_v2_test_environment()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    @unittest.skip(LEGACY_BUSINESS_TEST_RETIREMENT_REASON)
    def test_cashier_is_limited_to_cashier_surface(self):
        self.fail("historical pre-cutover Customer fixture test must remain skipped")

    @unittest.skip(LEGACY_BUSINESS_TEST_RETIREMENT_REASON)
    def test_manager_can_use_b2b_api_but_not_directly_create_sales(self):
        self.fail("historical pre-cutover Customer fixture test must remain skipped")

    def test_v2_pricing_and_payment_permissions_share_main_role_contract(self):
        # Phase 12 is authoritative for frozen legacy business DocTypes:
        # Cashier has no legacy audit access; Manager/Admin are audit-only.
        cashier = make_user_with_roles("Ledgix Cashier")
        frappe.set_user(cashier.name)
        self.assertFalse(frappe.has_permission("Ledgix Price List", ptype="read"))
        self.assertFalse(frappe.has_permission("Ledgix Payment Method", ptype="read"))
        self.assertFalse(frappe.has_permission("Ledgix Payment", ptype="create"))

        manager = make_user_with_roles("Ledgix Manager")
        frappe.set_user(manager.name)
        self.assertTrue(frappe.has_permission("Ledgix Price List", ptype="read"))
        self.assertFalse(frappe.has_permission("Ledgix Price List", ptype="write"))
        self.assertTrue(frappe.has_permission("Ledgix Payment Method", ptype="read"))
        self.assertFalse(frappe.has_permission("Ledgix Payment Method", ptype="write"))
        self.assertTrue(frappe.has_permission("Ledgix Payment", ptype="read"))
        self.assertFalse(frappe.has_permission("Ledgix Payment", ptype="create"))

        admin = make_user_with_roles("Ledgix Admin")
        frappe.set_user(admin.name)
        self.assertTrue(frappe.has_permission("Ledgix Payment", ptype="read"))
        self.assertTrue(frappe.has_permission("Ledgix Payment", ptype="report"))
        self.assertFalse(frappe.has_permission("Ledgix Payment", ptype="create"))
        self.assertFalse(frappe.has_permission("Ledgix Payment", ptype="submit"))
        self.assertFalse(frappe.has_permission("Ledgix Payment", ptype="cancel"))

    def test_page_and_workspace_roles_match_v2_navigation_contract(self):
        def roles_for(parent, parenttype):
            return set(
                frappe.get_all(
                    "Has Role",
                    filters={"parent": parent, "parenttype": parenttype},
                    pluck="role",
                )
            )

        all_business_roles = {
            "System Manager",
            "Ledgix Admin",
            "Ledgix Manager",
            "Ledgix Cashier",
        }
        management_roles = {
            "System Manager",
            "Ledgix Admin",
            "Ledgix Manager",
        }

        self.assertEqual(roles_for("ledgix-pos", "Page"), all_business_roles)
        for page in ("ledgix-tax-center", "business-intelligence-center"):
            self.assertEqual(roles_for(page, "Page"), management_roles)

        self.assertEqual(
            roles_for("ledgix-setup", "Page"),
            {"System Manager", "Ledgix Admin"},
        )
        self.assertEqual(roles_for("Ledgix", "Workspace"), all_business_roles)

    def test_only_four_custom_ledgix_pages_remain(self):
        pages = set(frappe.get_all("Page", filters={"module": "Ledgix"}, pluck="name"))
        self.assertEqual(
            pages,
            {
                "ledgix-pos",
                "ledgix-tax-center",
                "business-intelligence-center",
                "ledgix-setup",
            },
        )

    def test_workspace_shortcuts_resolve_to_real_frappe_targets(self):
        workspace = frappe.get_doc("Workspace", "Ledgix")
        self.assertTrue(workspace.shortcuts)

        for shortcut in workspace.shortcuts:
            target_type = shortcut.type
            target = shortcut.link_to
            if target_type == "DocType":
                exists = frappe.db.exists("DocType", target)
            elif target_type == "Page":
                exists = frappe.db.exists("Page", target)
            elif target_type == "Report":
                exists = frappe.db.exists("Report", target)
            else:
                self.fail(
                    f"Unsupported Workspace shortcut type {target_type}: {target}"
                )
            self.assertTrue(
                exists,
                f"Workspace shortcut target is missing: {target_type} {target}",
            )

    def test_role_home_pages_route_cashier_to_pos_and_management_to_workspace(self):
        self.assertEqual(
            frappe.db.get_value("Role", "Ledgix Cashier", "home_page"),
            "ledgix-pos",
        )
        self.assertEqual(
            frappe.db.get_value("Role", "Ledgix Manager", "home_page"),
            "Ledgix",
        )
        self.assertEqual(
            frappe.db.get_value("Role", "Ledgix Admin", "home_page"),
            "Ledgix",
        )

    def test_retired_product_settings_maintenance_and_role_are_absent(self):
        for doctype in (
            "Ledgix Mode Settings",
            "Ledgix POS Theme Settings",
            "Ledgix Maintenance Tool",
        ):
            self.assertFalse(frappe.db.exists("DocType", doctype))
        self.assertFalse(frappe.db.exists("Role", "Ledgix Super Admin"))

        workspace = frappe.get_doc("Workspace", "Ledgix")
        labels = {row.label for row in workspace.shortcuts}
        self.assertNotIn("POS Settings", labels)
        self.assertNotIn("Maintenance Tool", labels)

        # Current raw Workspace shortcuts are ERPNext-native operational/report
        # targets. Admin-only Brand Settings is exposed by the Phase 11 product
        # shell policy rather than being required as a raw shortcut.
        for required in (
            "Ledgix POS",
            "Sales Invoice",
            "Purchase Invoice",
            "Payment Entry",
        ):
            self.assertIn(required, labels)

    def test_stock_movement_is_a_read_only_business_ledger(self):
        admin = make_user_with_roles("Ledgix Admin")
        frappe.set_user(admin.name)

        self.assertTrue(
            frappe.has_permission("Ledgix Stock Movement", ptype="read")
        )
        self.assertTrue(
            frappe.has_permission("Ledgix Stock Movement", ptype="report")
        )
        self.assertFalse(
            frappe.has_permission("Ledgix Stock Movement", ptype="create")
        )
        self.assertFalse(
            frappe.has_permission("Ledgix Stock Movement", ptype="write")
        )
        self.assertFalse(
            frappe.has_permission("Ledgix Stock Movement", ptype="cancel")
        )
