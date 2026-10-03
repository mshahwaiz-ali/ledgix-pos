from unittest.mock import patch
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row, fixture
from fbr_v1.services import fbr_v1_snapshot_persistence as snapshots
from fbr_v1.services import erpnext_fbr_snapshot as native_snapshot

class TestV1Snapshot(NoNetworkTest):
    def doc(self):
        return Row(doctype='Sales Invoice',name='INV-1',company='Test Company',docstatus=1,
                   _action='submit',items=[Row(name='ROW-1',idx=1,doctype='Sales Invoice Item')])

    def test_capture_read_reuse_and_tamper_refusal(self):
        doc=self.doc(); s=fixture()
        with patch.object(snapshots,'_build_snapshot_payloads',return_value=(s['header'],s['lines'])), patch.object(snapshots,'is_consolidated',return_value=False):
            first=snapshots.capture_v1_snapshot(doc,force=True)
            self.assertEqual(first['snapshot_version'],1)
            self.assertTrue(snapshots.capture_v1_snapshot(doc,force=True)['reused_existing'])
        with patch.object(frappe,'get_doc',return_value=doc):
            persisted=snapshots.read_persisted_v1_snapshot(doc.doctype,doc.name)
            self.assertEqual(persisted['snapshot_hash'],first['snapshot_hash'])
            doc["items"][0][snapshots.LINE_JSON_FIELD]='{}'
            with self.assertRaisesRegex(frappe.ValidationError,'hash verification'):
                snapshots.read_persisted_v1_snapshot(doc.doctype,doc.name)

    def test_authoritative_tax_row_rounding_is_applied_to_line_evidence(self):
        doc = Row(
            taxes=[
                Row(
                    name="TAX-1",
                    account_head="GST - TEST",
                    tax_amount_after_discount_amount=0.15,
                )
            ],
            items=[Row(name="ROW-1")],
        )
        collector = Row(
            line_tax_capture={
                "ROW-1": {
                    "TAX-1": {
                        "account_head": "GST - TEST",
                        "tax_amount": 0.153,
                    }
                }
            }
        )

        native_snapshot._apply_authoritative_tax_rounding(
            doc,
            collector,
            {"GST - TEST": "Sales Tax Applicable"},
        )

        capture = collector.line_tax_capture["ROW-1"]["TAX-1"]
        self.assertAlmostEqual(capture["raw_tax_amount"], 0.153)
        self.assertAlmostEqual(capture["rounding_adjustment"], -0.003)
        self.assertAlmostEqual(capture["tax_amount"], 0.15)

    def test_historical_or_v2_evidence_is_never_reconstructed(self):
        doc=self.doc();doc._action='save'
        with self.assertRaisesRegex(frappe.ValidationError,'before_submit'):
            snapshots.capture_v1_snapshot(doc,force=True)
        doc.custom_ledgix_fbr_v2_snapshot_version=2
        with patch.object(frappe,'get_doc',return_value=doc):
            with self.assertRaises(frappe.ValidationError):
                snapshots.read_persisted_v1_snapshot(doc.doctype,doc.name)

    def test_full_capture_builder_uses_native_collector_and_device_payment(self):
        s=fixture();doc=self.doc();doc.update(net_total=100,total_taxes_and_charges=18,grand_total=118,posting_time='12:34:56')
        candidate={**s['header'],'lines':[s['lines']['ROW-1']['line']]}
        profile=Row(protocol_version='Federal POS/IMS V1',enabled=1,mode='Sandbox')
        with patch.object(snapshots,'get_profile',return_value=profile), patch.object(snapshots,'resolve_device',return_value=s['header']['pos_device']), patch.object(snapshots,'capture_payment',return_value={'payment_mode':1}), patch.object(frappe,'get_doc',return_value=doc), patch.object(snapshots,'collect_native_tax_breakdown',return_value=candidate), patch.object(snapshots.erpnext_fbr_identity,'resolve_invoice_identity',return_value=s['header']['identity']):
            h,lines=snapshots._build_snapshot_payloads(doc)
            self.assertEqual(h['usin'],'INV-1')
            self.assertEqual(h['payment']['payment_mode'],1)
            candidate['grand_total']=119
            with self.assertRaisesRegex(frappe.ValidationError,'differs'):
                snapshots._build_snapshot_payloads(doc)


class TestV1SchemaOwnership(NoNetworkTest):
    def test_fresh_schema_has_no_legacy_provisioning_or_ledgix_id(self):
        from fbr_v1.setup.erpnext_fbr_schema import CUSTOM_FIELDS, LEGACY_FISCAL_FIELDS
        for dt in ('Sales Invoice', 'POS Invoice', 'Sales Invoice Item', 'POS Invoice Item'):
            fields = {row['fieldname']: row for row in CUSTOM_FIELDS[dt]}
            self.assertFalse(set(fields) & set(LEGACY_FISCAL_FIELDS))
            self.assertNotIn('custom_ledgix_client_sale_id', fields)
            self.assertIn('custom_ledgix_fbr_snapshot_json', fields)
            for row in fields.values():
                after = row.get('insert_after')
                if after and after.startswith('custom_ledgix_'):
                    self.assertIn(after, fields)
            if dt.endswith(' Item'):
                self.assertIn('custom_ledgix_fbr_notified_retail_price', fields)

    def test_existing_legacy_hardening_updates_metadata_only(self):
        from fbr_v1.setup import erpnext_fbr_schema as schema
        self.db.get_value.side_effect = lambda dt, filters, field: (
            'existing-field' if filters['dt'] == 'Sales Invoice' and filters['fieldname'] == 'custom_ledgix_fbr_v2_snapshot_json' else None)
        with patch.object(frappe, 'clear_cache'), patch.object(schema, 'create_custom_fields') as create:
            self.assertEqual(schema.harden_existing_legacy_fields(), 1)
        create.assert_not_called()
        self.db.set_value.assert_called_once_with('Custom Field', 'existing-field',
            {'hidden': 1, 'read_only': 1, 'no_copy': 1, 'allow_on_submit': 0}, update_modified=False)
        for method in ('delete', 'sql', 'commit'):
            getattr(self.db, method).assert_not_called()

    def test_missing_legacy_fields_are_not_created(self):
        from fbr_v1.setup import erpnext_fbr_schema as schema
        self.db.get_value.return_value = None
        with patch.object(frappe, 'clear_cache'), patch.object(schema, 'create_custom_fields') as create:
            self.assertEqual(schema.harden_existing_legacy_fields(), 0)
        create.assert_not_called()
        self.db.set_value.assert_not_called()

    def test_dependency_direction_is_explicit_without_cycle(self):
        from fbr_v1 import hooks
        from ledgix_saas import hooks as ledgix_hooks
        self.assertEqual(hooks.required_apps, ['erpnext', 'ledgix_saas'])
        self.assertNotIn('fbr_v1', getattr(ledgix_hooks, 'required_apps', []))
