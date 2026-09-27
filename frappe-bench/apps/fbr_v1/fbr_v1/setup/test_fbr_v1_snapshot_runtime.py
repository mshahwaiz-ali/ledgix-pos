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
