import json
from pathlib import Path

from frappe.tests.utils import FrappeTestCase


APP_ROOT = Path(__file__).resolve().parents[3]


class TestV2WorkspaceAndIntelligence(FrappeTestCase):
    def test_workspace_is_two_column_and_covers_user_facing_navigation(self):
        path = APP_ROOT / "ledgix" / "workspace" / "ledgix" / "ledgix.json"
        workspace = json.loads(path.read_text(encoding="utf-8"))
        content = json.loads(workspace.get("content") or "[]")

        cards = [row for row in content if row.get("type") == "card"]
        self.assertEqual(len(cards), 8)
        self.assertTrue(all((row.get("data") or {}).get("col") == 6 for row in cards))
        self.assertEqual(workspace.get("shortcuts"), [])

        targets = {
            row.get("link_to")
            for row in workspace.get("links", [])
            if row.get("type") == "Link" and row.get("link_to")
        }
        required_targets = {
            "ledgix-pos",
            "ledgix-tax-center",
            "business-intelligence-center",
            "Ledgix POS Hold",
            "Ledgix Stock Lot Allocation",
            "Ledgix Tax Audit Log",
            "Ledgix User Profile",
            "Inventory Intelligence Report",
            "Ledgix Stock Movement Report",
        }
        self.assertTrue(required_targets.issubset(targets))
        self.assertNotIn("Item Intelligence Legacy", targets)

    def test_inventory_timeline_renders_returns_as_inbound_activity(self):
        path = APP_ROOT / "ledgix" / "page" / "business_intelligence_center" / "business_intelligence_center.js"
        text = path.read_text(encoding="utf-8")

        self.assertIn('const isReturn = ["Return", "Partial Return"].includes(event);', text)
        self.assertIn('if (event === "Sale") qty = -Number(', text)
        self.assertIn('else if (isReturn) qty = Number(', text)
        self.assertIn('row.sales_return || row.reference || row.sale', text)
        self.assertIn('["Return", "Partial Return"].includes(event)) doctype = "Ledgix Sales Return";', text)
        self.assertIn('style="align-items: start;"', text)
