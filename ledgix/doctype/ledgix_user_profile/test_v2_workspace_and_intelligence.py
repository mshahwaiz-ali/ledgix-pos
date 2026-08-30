import json
from pathlib import Path

from frappe.tests.utils import FrappeTestCase

from ledgix_saas.api.inventory_intelligence import add_scope_meta, filter_normal_stock_search


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

    def test_inventory_page_has_bounded_pagination_and_interactive_risks(self):
        path = APP_ROOT / "ledgix" / "page" / "business_intelligence_center" / "business_intelligence_center.js"
        text = path.read_text(encoding="utf-8")

        self.assertIn(
            'this.method = "ledgix_saas.api.inventory_intelligence.get_inventory_intelligence_data";',
            text,
        )
        self.assertIn("this.timelinePageSize = 25;", text)
        self.assertIn("this.lotPageSize = 20;", text)
        self.assertIn("lx-ii-risk-toggle", text)
        self.assertIn("lx-ii-timeline-prev", text)
        self.assertIn("lx-ii-timeline-next", text)
        self.assertIn("lx-ii-timeline-page-size", text)
        self.assertIn("lx-ii-lot-prev", text)
        self.assertIn("lx-ii-lot-next", text)
        self.assertIn("loaded events", text)
        self.assertIn("loaded lots", text)
        self.assertIn("timeline_cap_reached", text)
        self.assertIn("lot_cap_reached", text)
        self.assertIn("meta.load_error", text)
        self.assertIn("requestId !== this.requestSerial", text)
        self.assertIn('this.fromControl?.$input?.on("change", reloadFromControl);', text)
        self.assertIn('this.toControl?.$input?.on("change", reloadFromControl);', text)
        self.assertNotIn("lx-ii-timeline-more", text)
        self.assertNotIn("lx-ii-timeline-less", text)
        self.assertNotIn('+${risks.length - 8} more signal(s)', text)
        self.assertLess(text.index("<h3>Lot performance</h3>"), text.index("<h3>Transaction timeline</h3>"))

    def test_normal_stock_search_matches_activity_not_only_item_text(self):
        items = {
            "ITEM-A": {
                "name": "ITEM-A",
                "item_code": "A-001",
                "item_name": "Cake Rusk",
                "sku": "RUSK-001",
                "barcode": "111",
                "category": "Bakery",
                "stock_status": "In Stock",
            },
            "ITEM-B": {
                "name": "ITEM-B",
                "item_code": "B-001",
                "item_name": "Gulab Jamun",
                "sku": "GJ-001",
                "barcode": "222",
                "category": "Sweets",
                "stock_status": "In Stock",
            },
        }
        purchases = [
            {
                "purchase": "PUR-TEST-001",
                "supplier": "Heritage Sweets Production",
                "purchase_invoice": "PI-001",
                "item": "ITEM-A",
                "row_name": "PUR-ROW-1",
            }
        ]
        sales = [
            {
                "sale": "SAL-TEST-001",
                "customer": "Noor Event Planners",
                "sale_invoice": "INV-001",
                "item": "ITEM-B",
                "row_name": "SALE-ROW-1",
            }
        ]
        returns = [
            {
                "sales_return": "RET-TEST-001",
                "original_sale": "SAL-TEST-001",
                "customer": "Noor Event Planners",
                "item": "ITEM-B",
                "row_name": "RET-ROW-1",
            }
        ]

        matched_items, matched_purchases, matched_sales, matched_returns = filter_normal_stock_search(
            items,
            purchases,
            sales,
            returns,
            {"search": "Noor Event Planners", "entity_type": None},
        )

        self.assertEqual(set(matched_items), {"ITEM-B"})
        self.assertEqual(matched_purchases, [])
        self.assertEqual([row["sale"] for row in matched_sales], ["SAL-TEST-001"])
        self.assertEqual([row["sales_return"] for row in matched_returns], ["RET-TEST-001"])

        matched_items, matched_purchases, matched_sales, matched_returns = filter_normal_stock_search(
            items,
            purchases,
            sales,
            returns,
            {"search": "Heritage Sweets", "entity_type": None},
        )

        self.assertEqual(set(matched_items), {"ITEM-A"})
        self.assertEqual([row["purchase"] for row in matched_purchases], ["PUR-TEST-001"])
        self.assertEqual(matched_sales, [])
        self.assertEqual(matched_returns, [])

    def test_lot_search_narrows_after_activity_matching(self):
        path = APP_ROOT / "api" / "inventory_intelligence.py"
        text = path.read_text(encoding="utf-8")

        self.assertIn("matching_cycle_rows = core.build_cycle_rows", text)
        self.assertIn('row.get("lot_number")', text)
        self.assertIn("matched_lot_names", text)
        self.assertIn("matched_allocations", text)
        self.assertIn("show its complete submitted", text.lower())
        self.assertIn('response["meta"]["load_error"] = True', text)

    def test_inventory_scope_meta_discloses_result_caps(self):
        response = {
            "cycle_rows": [{} for _ in range(500)],
            "lots": [{} for _ in range(500)],
            "meta": {},
        }

        meta = add_scope_meta(response)["meta"]

        self.assertEqual(meta["timeline_loaded_count"], 500)
        self.assertEqual(meta["timeline_result_cap"], 500)
        self.assertTrue(meta["timeline_cap_reached"])
        self.assertEqual(meta["lot_loaded_count"], 500)
        self.assertEqual(meta["lot_result_cap"], 500)
        self.assertTrue(meta["lot_cap_reached"])
