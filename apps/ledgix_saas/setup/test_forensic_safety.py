"""Executable regressions: mocked transport only, no site or credentials."""
import json
from inspect import unwrap
import unittest
from unittest.mock import MagicMock, patch

import frappe

from ledgix_saas.api import fbr_transport, fbr_v2_transport, stock_ops
from ledgix_saas.api import selling, pos_compat, selling_compat
from ledgix_saas.patches.v1_0 import rename_tax_rate_fields
from ledgix_saas.services import fbr_submission_support as support
from ledgix_saas.services import erpnext_selling
from ledgix_saas.services import erpnext_reporting
from ledgix_saas.services import erpnext_pos


class TestForensicSafety(unittest.TestCase):
    def test_retail_return_retry_reuses_native_document_before_shift_check(self):
        invoice = frappe._dict(name="sale", company="company")
        existing = frappe._dict(name="return", is_return=1, return_against="sale", flags=frappe._dict())
        db = MagicMock()
        db.get_value.return_value = "return"
        with patch.object(erpnext_pos, "_submitted_pos_invoice", return_value=invoice), patch.object(
            erpnext_selling, "_lock_company"
        ) as lock, patch.object(frappe, "db", db, create=True), patch.object(
            frappe, "get_doc", return_value=existing
        ) as get_doc:
            result = erpnext_pos.create_return(original_sale="sale", return_items=[], reason="test", client_return_id="retry")
        self.assertIs(result, existing)
        lock.assert_called_once_with("company")
        get_doc.assert_called_once_with("POS Invoice", "return")

    def test_retired_tax_table_rename_is_safe_on_fresh_site(self):
        db = MagicMock()
        db.table_exists.return_value = False
        with patch.object(frappe, "db", db, create=True):
            rename_tax_rate_fields.rename_or_copy_column("Ledgix Tax Rate", "rate_", "rate")
        db.has_column.assert_not_called()
        db.sql.assert_not_called()

    def test_old_direct_retail_wrapper_uses_native_adapter(self):
        with patch.object(pos_compat, "complete_pos_v2_sale", return_value={"native": True}) as native:
            self.assertEqual(unwrap(selling.complete_pos_v2_sale_compat)(client_sale_id="test"), {"native": True})
        self.assertEqual(native.call_args.kwargs["client_sale_id"], "test")
        with patch.object(pos_compat, "get_pos_v2_boot", return_value={"native": True}) as native:
            self.assertEqual(unwrap(selling_compat.get_pos_v2_boot)(), {"native": True})
        native.assert_called_once()

    def test_b2b_return_accepts_and_preserves_retry_identifier(self):
        invoice = frappe._dict(name="test-sale")
        note = frappe._dict(name="test-return", customer="test", net_total=-1, total_taxes_and_charges=0,
                            grand_total=-1)
        with patch.object(selling, "require_ledgix_cashier_or_above"), patch.object(selling, "_require_manager"), patch.object(
            selling, "_native_invoice_reference", return_value=invoice
        ), patch.object(erpnext_selling, "create_sales_return", return_value=note) as native:
            result = unwrap(selling.create_pos_return_compat)("test-sale", [], "reason", client_return_id="retry-id")
        self.assertEqual(native.call_args.kwargs["client_return_id"], "retry-id")
        self.assertEqual(result["return_id"], "test-return")

    def test_reporting_compat_import_has_no_mutation_and_cost_uses_consolidation(self):
        import importlib
        helper = erpnext_reporting._pos_invoice_rows
        compat = importlib.import_module("ledgix_saas.services.erpnext_reporting_compat")
        importlib.reload(compat)
        self.assertIs(erpnext_reporting._pos_invoice_rows, helper)
        self.assertIs(compat.sales_rows, erpnext_reporting.sales_rows)
        db = MagicMock()
        with patch.object(frappe, "db", db, create=True):
            erpnext_reporting._pos_invoice_rows({}, returns=False)
        query = db.sql.call_args.args[0]
        self.assertIn("sii_cost.pos_invoice_item = pii.name", query)
        self.assertIn("sle.voucher_type = 'Sales Invoice'", query)
        self.assertNotIn("pii.incoming_rate", query)

    def test_missing_native_price_does_not_select_expired_raw_item_price(self):
        with patch.object(erpnext_selling, "_currency", return_value="PKR"), patch.object(
            erpnext_selling, "_price_list_currency", return_value="PKR"
        ), patch("erpnext.stock.get_item_details.get_item_details", return_value={}), patch.object(
            frappe, "get_all", return_value=[frappe._dict(price_list_rate=999)]
        ) as raw_query, patch.object(erpnext_selling, "_", side_effect=lambda value: value), patch.object(
            frappe, "throw", side_effect=frappe.ValidationError
        ):
            with self.assertRaises(frappe.ValidationError):
                erpnext_selling._native_item_rate(item_code="test", customer="test", company="test",
                    price_list="test", qty=1, posting_date="2026-09-26")
            raw_query.assert_not_called()

    def test_post_redacts_nested_echo_but_keeps_official_evidence(self):
        token = "synthetic-test-credential"
        body = {
            "invoiceNumber": "test-invoice", "dated": "2026-09-26 12:00:00",
            "validationResponse": {"status": "Valid", "statusCode": "00"},
            "debug": [{"message": token, "Authorization": "bEaReR other-secret"}],
        }
        response = MagicMock(status_code=200)
        response.json.return_value = body
        with patch.object(fbr_transport, "requests") as requests:
            requests.post.return_value = response
            result = fbr_transport.post_json(url="https://unused.invalid", token=token, payload={})
        serialized = support.serialize_json(result)
        self.assertNotIn(token, serialized)
        self.assertNotIn("other-secret", serialized)
        self.assertEqual(result["response"]["dated"], body["dated"])
        self.assertEqual(support.parse_fbr_response(result)["invoice_number"], "test-invoice")
        self.assertEqual(body["debug"][0]["message"], token)  # no input mutation

    def test_non_json_and_exception_echo_are_redacted(self):
        token = "synthetic-test-credential"
        response = MagicMock(status_code=502, text=f"proxy echo {token}")
        response.json.side_effect = ValueError("not JSON")
        with patch.object(fbr_transport, "requests") as requests:
            requests.post.return_value = response
            result = fbr_transport.post_json(url="https://unused.invalid", token=token, payload={})
            self.assertNotIn(token, json.dumps(result))
            requests.post.side_effect = RuntimeError(f"credential={token}; bearer hidden")
            result = fbr_transport.post_json(url="https://unused.invalid", token=token, payload={})
            self.assertNotIn(token, json.dumps(result))
            self.assertNotIn("hidden", json.dumps(result))
            self.assertTrue(fbr_v2_transport._production_post_is_ambiguous(result, None))

    def test_get_reference_echo_is_redacted(self):
        token = "synthetic-test-credential"
        response = MagicMock(status_code=200)
        response.json.return_value = {"rows": [{"id": 1}], "message": token}
        with patch.object(fbr_transport, "requests") as requests:
            requests.get.return_value = response
            result = fbr_transport.get_json(url="https://unused.invalid", token=token)
            requests.post.assert_not_called()
        self.assertNotIn(token, json.dumps(result))
        self.assertEqual(result["payload"]["rows"], [{"id": 1}])

    def test_failed_redis_lock_releases_database_fallback(self):
        cache = MagicMock()
        cache.lock.return_value.__enter__.side_effect = RuntimeError("Redis unavailable")
        db = MagicMock()
        db.sql.return_value = [(1,)]
        with patch.object(frappe, "cache", return_value=cache), patch.object(frappe, "db", db, create=True):
            with support.submission_lock("Sales Invoice:test"):
                pass
        self.assertEqual(db.sql.call_args_list[-1].args[0], "SELECT RELEASE_LOCK(%s)")
        cache.lock.return_value.__exit__.assert_not_called()

    def test_valuation_never_reads_historical_cost(self):
        db = MagicMock()
        with patch.object(frappe, "db", db, create=True), patch.object(
            stock_ops.erpnext_buying_inventory, "stock_snapshot", return_value={"valuation_rate": 0}
        ), patch.object(frappe, "throw", side_effect=frappe.ValidationError):
            with self.assertRaises(frappe.ValidationError):
                stock_ops._valuation_rate("legacy", "native", "warehouse")
            self.assertEqual(stock_ops._valuation_rate("legacy", "native", "warehouse", 0), 0)
            self.assertEqual(stock_ops._valuation_rate("legacy", "native", "warehouse", 25), 25)
        db.exists.assert_not_called()
        db.get_value.assert_not_called()

    def test_response_classification_and_official_timestamp(self):
        valid = {"invoiceNumber": "test", "dated": "2026-09-26 11:00:00",
                 "validationResponse": {"status": "Valid", "statusCode": "00"}}
        self.assertEqual(support.parse_fbr_response(valid)["dated"], valid["dated"])
        self.assertEqual(fbr_v2_transport._fbr_body_state(valid), "valid")
        valid["validationResponse"]["invoiceStatuses"] = [{"status": "Invalid", "statusCode": "01"}]
        self.assertFalse(support.parse_fbr_response(valid)["valid"])
        self.assertEqual(fbr_v2_transport._fbr_body_state(valid), "invalid")
        for status in (408, 500, 503):
            self.assertTrue(fbr_v2_transport._production_post_is_ambiguous(
                {"network_call": True, "http_status": status}, None))
        self.assertFalse(fbr_v2_transport._production_post_is_ambiguous(
            {"network_call": True, "http_status": 401}, None))


if __name__ == "__main__":
    unittest.main()
