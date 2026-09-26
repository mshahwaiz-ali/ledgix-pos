from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from fbr_v1.services import fbr_v2_snapshot_persistence as snapshots


class _Meta:
    def has_field(self, fieldname):
        return True


class _Row:
    def __init__(self, name: str):
        self.doctype = "Sales Invoice Item"
        self.name = name
        self.idx = 1
        self.meta = _Meta()
        self._data = {
            "name": name,
            "idx": 1,
        }

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


class _Invoice:
    def __init__(self):
        self.doctype = "Sales Invoice"
        self.name = "SINV-FBR-V12-RUNTIME"
        self.company = "Standalone FBR Test Company"
        self.docstatus = 1
        self._action = "submit"
        self.meta = _Meta()
        self.items = [_Row("ROW-1")]
        self._data = {
            "is_return": 0,
            "return_against": "",
            "items": self.items,
        }

    def get(self, key, default=None):
        if key == "items":
            return self.items
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def as_dict(self):
        return {
            "doctype": self.doctype,
            "name": self.name,
            "company": self.company,
            "docstatus": self.docstatus,
        }


class TestFBRV1SnapshotRuntime(unittest.TestCase):
    def _payloads(self):
        header = {
            "snapshot_version": snapshots.SNAPSHOT_VERSION,
            "authority": "ERPNext Native",
            "source_doctype": "Sales Invoice",
            "source_name": "SINV-FBR-V12-RUNTIME",
            "company": "Standalone FBR Test Company",
            "posting_date": "2026-09-27",
            "currency": "PKR",
            "is_return": False,
            "return_against": "",
            "net_total": 100.0,
            "total_taxes_and_charges": 18.0,
            "grand_total": 118.0,
            "identity": {"ready": True},
            "component_mappings": {},
            "reconciliation": {"passed": True},
            "line_count": 1,
            "line_hashes": [],
        }
        line = {
            "snapshot_version": snapshots.SNAPSHOT_VERSION,
            "authority": "ERPNext Native",
            "source_doctype": "Sales Invoice",
            "source_name": "SINV-FBR-V12-RUNTIME",
            "company": "Standalone FBR Test Company",
            "posting_date": "2026-09-27",
            "is_return": False,
            "return_against": "",
            "line": {
                "item_row": "ROW-1",
                "idx": 1,
                "item_code": "TEST-ITEM",
                "qty": 1,
                "net_amount": 100.0,
                "amount": 100.0,
            },
        }
        header["line_hashes"] = [
            {
                "item_row": "ROW-1",
                "sha256": snapshots._digest_json(line),
            }
        ]
        return header, {"ROW-1": line}

    def test_capture_reuse_and_tamper_refusal_are_in_memory_only(self):
        doc = _Invoice()
        payloads = self._payloads()

        with patch.object(snapshots, "_assert_snapshot_fields", return_value=None), patch.object(
            snapshots, "_build_snapshot_payloads", return_value=payloads
        ):
            first = snapshots.capture_v2_snapshot(doc, force=True)

            self.assertTrue(first["captured"])
            self.assertFalse(first["reused_existing"])
            self.assertEqual(first["snapshot_version"], 2)
            self.assertEqual(first["line_count"], 1)
            self.assertFalse(first["database_write"])
            self.assertFalse(first["fbr_network_call"])

            second = snapshots.capture_v2_snapshot(doc, force=True)
            self.assertTrue(second["captured"])
            self.assertTrue(second["reused_existing"])
            self.assertEqual(second["snapshot_hash"], first["snapshot_hash"])
            self.assertFalse(second["database_write"])
            self.assertFalse(second["fbr_network_call"])

            doc.items[0].set(snapshots.LINE_JSON_FIELD, '{"tampered":true}')
            with self.assertRaises(frappe.ValidationError):
                snapshots.capture_v2_snapshot(doc, force=True)


if __name__ == "__main__":
    unittest.main()
