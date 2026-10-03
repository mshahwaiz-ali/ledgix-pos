"""Retired capture boundary and unchanged, read-only historical evidence."""
import json
from pathlib import Path
from unittest.mock import patch

import frappe
from fbr_v1.setup.v1_test_support import Row
from ledgix_saas.services import historical_fbr_evidence as history
from ledgix_saas.setup.fbr_retirement_test_support import RetirementCase


class TestHistoricalSnapshotBoundary(RetirementCase):
    def test_old_snapshot_service_rejects_all_entry_points(self):
        self.assert_module_retired('ledgix_saas.services.fbr_v2_snapshot_persistence')

    def test_fresh_v1_schema_preserves_but_does_not_provision_v2_fields(self):
        from fbr_v1.setup.erpnext_fbr_schema import CUSTOM_FIELDS, LEGACY_FISCAL_FIELDS
        for dt in ('Sales Invoice', 'POS Invoice', 'Sales Invoice Item', 'POS Invoice Item'):
            self.assertFalse(any('fbr_v2_snapshot' in row['fieldname'] for row in CUSTOM_FIELDS[dt]))
        self.assertIn('custom_ledgix_fbr_v2_snapshot_json', LEGACY_FISCAL_FIELDS)
        app = Path(__file__).resolve().parents[1]
        self.assertNotIn('fbr_v2_snapshot_persistence.before_submit_capture', (app / 'hooks.py').read_text())
        self.assertEqual((app.parent / 'fbr_v1/fbr_v1/hooks.py').read_text().count(
            'fbr_v1.services.fbr_v1_snapshot_persistence.before_submit_capture'), 2)

    def historical_document(self):
        line = {'identity': 'original line', 'amount': '123.45'}
        line_hash = history._digest_json(line)
        header = {'identity': {'seller': 'original seller'}, 'line_count': 1,
            'line_hashes': [{'item_row': 'ROW-1', 'sha256': line_hash}]}
        item = Row(name='ROW-1', doctype='Sales Invoice Item',
            custom_ledgix_fbr_v2_snapshot_version=2,
            custom_ledgix_fbr_v2_snapshot_json=json.dumps(line),
            custom_ledgix_fbr_v2_snapshot_hash=line_hash)
        doc = Row(name='OLD-INV', doctype='Sales Invoice', items=[item],
            custom_ledgix_fbr_v2_snapshot_version=2,
            custom_ledgix_fbr_v2_snapshot_json=json.dumps(header),
            custom_ledgix_fbr_v2_snapshot_hash=history._digest_json(header))
        return doc, header, line

    def test_historical_reader_verifies_original_evidence_without_rebuilding(self):
        doc, header, line = self.historical_document()
        before = json.dumps(dict(doc), default=str)
        self.db.exists.return_value = True
        with patch.object(frappe, 'get_doc', return_value=doc):
            result = history.read_persisted_v2_snapshot('Sales Invoice', 'OLD-INV')
        self.assertEqual(result['header'], header)
        self.assertEqual(result['lines'], {'ROW-1': line})
        self.assertTrue(result['hash_verified'])
        self.assertFalse(result['fbr_network_call'])
        self.assertEqual(json.dumps(dict(doc), default=str), before)
        for method in ('set_value', 'sql', 'insert', 'commit', 'rollback'):
            getattr(self.db, method).assert_not_called()

    def test_tampered_historical_evidence_fails_without_repair(self):
        doc, _, _ = self.historical_document()
        doc.get('items')[0].custom_ledgix_fbr_v2_snapshot_json = '{"amount": "changed"}'
        self.db.exists.return_value = True
        with patch.object(frappe, 'get_doc', return_value=doc):
            with self.assertRaises(frappe.ValidationError):
                history.read_persisted_v2_snapshot('Sales Invoice', 'OLD-INV')
        self.db.set_value.assert_not_called()
