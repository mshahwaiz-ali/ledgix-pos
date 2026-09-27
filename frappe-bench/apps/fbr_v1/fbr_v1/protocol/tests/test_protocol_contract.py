from __future__ import annotations

import unittest

from fbr_v1.protocol.constants import (
    CLOUD_PRODUCTION_URL,
    CLOUD_SANDBOX_URL,
    LOCAL_HEALTH_URL,
    LOCAL_POST_URL,
)
from fbr_v1.protocol.models import Invoice, InvoiceItem, ProtocolValidationError
from fbr_v1.protocol.response import parse_fiscal_response
from fbr_v1.protocol.transport import health_local, post_cloud, post_local


class _FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = "" if isinstance(body, dict) else str(body)

    def json(self):
        if isinstance(self._body, dict):
            return self._body
        raise ValueError("not json")


class _FakeHTTP:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return _FakeResponse("Service is responding.")

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return _FakeResponse({
            "FBRInvoiceNumber": "11000120181112000369",
            "Response": "Invoice received successfully",
            "Code": "100",
        })


class TestDocumentedFBRV1Protocol(unittest.TestCase):
    def _invoice(self):
        item = InvoiceItem(
            item_code="TEST-1",
            item_name="Test Item",
            quantity=1,
            pct_code="11001010",
            tax_rate=18,
            sale_value=100,
            total_amount=118,
            tax_charged=18,
            invoice_type=1,
        )
        return Invoice(
            pos_id=110014,
            usin="SINV-0001",
            date_time="2026-09-27 12:00:00",
            buyer_ntn="1234567-8",
            buyer_name="Buyer",
            total_bill_amount=118,
            total_quantity=1,
            total_sale_value=100,
            total_tax_charged=18,
            payment_mode=1,
            invoice_type=1,
            items=(item,),
        )

    def test_nonfinite_wire_amounts_are_rejected(self):
        from dataclasses import replace
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ProtocolValidationError):
                replace(self._invoice(), total_bill_amount=value)

    def test_exact_documented_payload_shape(self):
        payload = self._invoice().to_payload()
        self.assertEqual(payload["InvoiceNumber"], "")
        self.assertEqual(payload["POSID"], 110014)
        self.assertEqual(payload["USIN"], "SINV-0001")
        self.assertEqual(payload["PaymentMode"], 1)
        self.assertEqual(payload["InvoiceType"], 1)
        self.assertEqual(payload["Items"][0]["PCTCode"], "11001010")
        self.assertNotIn("sellerNTNCNIC", payload)
        self.assertNotIn("scenarioId", payload)

    def test_documented_third_schedule_item_types(self):
        new = InvoiceItem(
            item_code="TS-1", item_name="Third Schedule", quantity=1,
            pct_code="11001010", tax_rate=18, sale_value=100,
            total_amount=118, tax_charged=18, invoice_type=11,
        )
        credit = InvoiceItem(
            item_code="TS-1", item_name="Third Schedule Return", quantity=1,
            pct_code="11001010", tax_rate=18, sale_value=100,
            total_amount=118, tax_charged=18, invoice_type=12,
            ref_usin="SINV-ORIG",
        )
        self.assertEqual(new.to_payload()["InvoiceType"], 11)
        self.assertEqual(credit.to_payload()["InvoiceType"], 12)

    def test_undocumented_item_debit_fails_closed(self):
        with self.assertRaises(ProtocolValidationError):
            InvoiceItem(
                item_code="D-1", item_name="Debit", quantity=1,
                pct_code="11001010", tax_rate=18, sale_value=100,
                total_amount=118, tax_charged=18, invoice_type=2,
            )

    def test_parser_accepts_number_key_variants(self):
        federal = parse_fiscal_response(
            {"FBRInvoiceNumber": "FBR-1", "Code": "100", "Response": "ok"}
        )
        later = parse_fiscal_response(
            {"InvoiceNumber": "FBR-2", "Code": "100", "Response": "ok"}
        )
        self.assertTrue(federal.success)
        self.assertEqual(federal.invoice_number, "FBR-1")
        self.assertTrue(later.success)
        self.assertEqual(later.invoice_number, "FBR-2")

    def test_transports_use_only_in_memory_fake_http(self):
        fake = _FakeHTTP()
        payload = self._invoice().to_payload()

        health_local(http_client=fake)
        self.assertEqual(fake.calls[-1][1], LOCAL_HEALTH_URL)

        local = post_local(payload, http_client=fake)
        self.assertEqual(fake.calls[-1][1], LOCAL_POST_URL)
        self.assertTrue(local["fiscal"].success)

        sandbox = post_cloud(
            payload, token="sandbox-secret", environment="sandbox", http_client=fake
        )
        self.assertEqual(fake.calls[-1][1], CLOUD_SANDBOX_URL)
        self.assertNotIn("sandbox-secret", str(sandbox))

        production = post_cloud(
            payload, token="production-secret", environment="production", http_client=fake
        )
        self.assertEqual(fake.calls[-1][1], CLOUD_PRODUCTION_URL)
        self.assertNotIn("production-secret", str(production))


if __name__ == "__main__":
    unittest.main()
