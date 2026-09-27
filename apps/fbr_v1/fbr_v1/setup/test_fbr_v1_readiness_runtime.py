from unittest.mock import patch, Mock
from contextlib import nullcontext
import json
from pathlib import Path
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row, fixture
from fbr_v1.services import pos_identity as identity, fbr_v1_readiness as readiness
from fbr_v1.api import fbr_offline as offline
from fbr_v1.services import fiscal_closing as closing
from fbr_v1.api import fiscalization as fiscal

class TestReadiness(NoNetworkTest):
    def test_device_ambiguity_environment_and_pos_profile(self):
        profile=Row(mode='Sandbox')
        doc=Row(doctype='POS Invoice',company='Test Company',pos_profile='Till')
        device=Row(**fixture()['header']['pos_device'],active=1)
        device.pos_profile='Till'
        with patch.object(frappe,'get_all',return_value=['D1','D2']):
            with self.assertRaisesRegex(frappe.ValidationError,'deterministic'):identity.resolve_device(doc,profile)
        with patch.object(frappe,'get_all',return_value=['DEVICE-1']),patch.object(frappe,'get_doc',return_value=device):
            self.assertEqual(identity.resolve_device(doc,profile)['pos_id'],'123')
            device.environment='Production'
            with self.assertRaisesRegex(frappe.ValidationError,'environment'):identity.resolve_device(doc,profile)

    def test_consolidation_does_not_suppress_native_pos_sales_invoice(self):
        self.db.exists.return_value=False
        self.assertFalse(identity.is_consolidated(Row(doctype='Sales Invoice',name='I',is_pos=1)))
        self.assertTrue(identity.is_consolidated(Row(doctype='Sales Invoice',name='I',is_consolidated=1)))
        self.assertTrue(identity.is_consolidated(Row(doctype='Sales Invoice',name='I',is_consolidated=1,is_return=1)))

    def test_legacy_profile_is_not_active(self):
        self.assertFalse(identity.profile_active(Row(enabled=1,mode='Production',protocol_version='DI API V1.12')))

    def test_readiness_blocks_missing_v1_credentials_and_live_cutover(self):
        s=fixture();doc=Row(doctype='Sales Invoice',name='INV-1',company='Test Company',docstatus=1)
        profile=Row(protocol_version=identity.PROTOCOL,mode='Sandbox',enabled=1,transport_enabled=1)
        profile.get_password=Mock(return_value=None)
        with patch.object(readiness,'get_profile',return_value=profile),patch.object(readiness,'is_consolidated',return_value=False),patch.object(readiness,'read_persisted_v1_snapshot',return_value=s),patch.object(readiness,'resolve_device',return_value=s['header']['pos_device']):
            result=readiness.inspect_invoice(doc)
        self.assertTrue(result['ready']);self.assertFalse(result['network_ready'])
        self.assertEqual(profile.get_password.call_args.args[0],'v1_sandbox_token')
        self.assertTrue(any('credential' in x for x in result['network_blockers']))

    def test_production_remains_blocked_when_armed(self):
        s=fixture();s['header']['pos_device']['environment']='Production'
        from fbr_v1.setup.v1_test_support import rehash
        rehash(s)
        doc=Row(doctype='Sales Invoice',name='INV-1',company='Test Company',docstatus=1)
        profile=Row(protocol_version=identity.PROTOCOL,mode='Production',enabled=1,transport_enabled=1,
                    production_post_armed=1,activation_reference='AUTH',activation_evidence='/private/files/evidence')
        profile.get_password=Mock(return_value='fake')
        with patch.object(readiness,'get_profile',return_value=profile),patch.object(readiness,'is_consolidated',return_value=False),patch.object(readiness,'read_persisted_v1_snapshot',return_value=s),patch.object(readiness,'resolve_device',return_value=s['header']['pos_device']),patch.object(readiness.transport,'V1_NETWORK_CUTOVER_ACTIVE',True):
            result=readiness.inspect_invoice(doc)
        self.assertFalse(result['network_ready'])
        self.assertTrue(any('QR' in b for b in result['network_blockers']))

    def test_restoration_sets_due_only_for_unrestored_pending_invoices(self):
        device=Row(name='DEVICE-1',operational_state='Offline'); device.db_set=Mock()
        pending=[Row(name='NEW',custom_ledgix_fbr_upload_due_at=None),Row(name='OLD',custom_ledgix_fbr_upload_due_at='2026-01-01')]
        with patch.object(offline,'require_operator'),patch.object(frappe,'get_doc',return_value=device),patch.object(offline,'submission_lock',return_value=nullcontext()),patch.object(frappe,'get_all',side_effect=[pending,[]]),patch.object(offline,'append_event',return_value=Row(name='EVENT')):
            result=offline.record_device_event('DEVICE-1','Restoration')
        self.assertEqual(result['pending'],[{'doctype':'Sales Invoice','name':'NEW'}])
        self.assertEqual(self.db.set_value.call_count,1)
        fields=self.db.set_value.call_args.args[2]
        self.assertEqual(fields['custom_ledgix_fbr_upload_due_at'],offline.restoration_due_at(fields['custom_ledgix_fbr_restored_at']))

    def test_closing_repeated_period_reuses_evidence_without_reaggregation(self):
        device=Row(name='DEVICE-1')
        self.db.get_value.return_value='CLOSING-1'
        with patch.object(closing,'require_operator'),patch.object(frappe,'get_doc',return_value=device),patch.object(closing,'submission_lock',return_value=nullcontext()),patch.object(frappe,'get_all') as query:
            result=closing.generate_closing('DEVICE-1','Monthly','2026-01-01')
            query.assert_not_called()
        self.assertEqual(result['name'],'CLOSING-1');self.assertTrue(result['reused'])

    def test_hooks_center_and_schema_have_no_active_di_bindings(self):
        from fbr_v1 import hooks
        for events in hooks.doc_events.values():
            for path in events.values():
                self.assertNotIn('v2',path);self.assertNotIn('fbr_native',path)
        root=Path(__file__).resolve().parents[1]
        js=(root/'fbr_v1/page/fbr_v1_center/fbr_v1_center.js').read_text()
        for retired in ('fbr_v2','scenarioId','fbr_reference_v2'):
            self.assertNotIn(retired,js)
        for p in (root/'fbr_v1/print_format').glob('*/*.json'):
            d=json.loads(p.read_text());self.assertNotIn('25.4',d['css']);self.assertIn('7mm',d['css'])
        from fbr_v1.setup.erpnext_fbr_schema import CUSTOM_FIELDS
        for dt in ('Sales Invoice','POS Invoice'):
            fields={f['fieldname']:f for f in CUSTOM_FIELDS[dt]}
            self.assertIn('custom_ledgix_fbr_snapshot_protocol',fields)
            self.assertIn('custom_ledgix_fbr_v2_snapshot_json',fields)
            self.assertFalse(fields['custom_ledgix_fbr_snapshot_json']['allow_on_submit'])


    def test_offline_policy_disabled_fails_closed(self):
        doc=Row(
            doctype='Sales Invoice',
            name='INV-OFFLINE',
            company='Test Company',
            docstatus=1,
        )
        profile=Row(offline_policy='Disabled')

        with patch.object(offline,'get_profile',return_value=profile):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                'Known-offline issuance is disabled',
            ):
                offline.offline_invoice(doc)


    def test_cancellation_only_blocks_real_fiscal_history(self):
        doc=Row(
            doctype='Sales Invoice',
            name='INV-1',
            custom_ledgix_fbr_snapshot_hash='SNAPSHOT',
            custom_ledgix_fbr_status='Pending',
            custom_ledgix_fbr_reconciliation_required=0,
        )

        # Internal snapshot/Pending evidence alone must not make the
        # ERPNext document permanently uncancellable.
        pending=[
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id=None,
                transport_outcome='Not Attempted',
                fbr_status='Pending',
            )
        ]
        self.assertFalse(fiscal.cancellation_requires_credit(doc,pending))

        # Durable ambiguous intent followed by definite rejection is resolved.
        rejected=[
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id='A',
                transport_outcome='Ambiguous',
                fbr_status='Reconciliation Required',
            ),
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id='A',
                transport_outcome='Rejected',
                fbr_status='Failed',
            ),
        ]
        doc.custom_ledgix_fbr_status='Failed'
        self.assertFalse(fiscal.cancellation_requires_credit(doc,rejected))

        # Unresolved ambiguity is external-risk fiscal history.
        ambiguous=[
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id='B',
                transport_outcome='Ambiguous',
                fbr_status='Reconciliation Required',
            )
        ]
        self.assertTrue(fiscal.cancellation_requires_credit(doc,ambiguous))

        # Offline fiscal issuance is retained and must use a credit/return.
        offline_rows=[
            Row(
                protocol=fiscal.PROTOCOL,
                attempt_id=None,
                transport_outcome='Offline Deferred',
                fbr_status='Offline Pending',
            )
        ]
        self.assertTrue(fiscal.cancellation_requires_credit(doc,offline_rows))
