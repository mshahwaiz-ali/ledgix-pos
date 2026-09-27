from contextlib import nullcontext
from unittest.mock import patch, Mock
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row, fixture
from fbr_v1.protocol import transport
from fbr_v1.services.fbr_v1_payload_builder import build_invoice
from fbr_v1.services.fbr_submission_support import sanitize, submission_lock
from fbr_v1.api import fiscalization as api

class TestV1Transport(NoNetworkTest):
    def test_real_network_gate_covers_all_protocol_methods(self):
        self.assertFalse(transport.V1_NETWORK_CUTOVER_ACTIVE)
        for call in (lambda:transport.health_local(),lambda:transport.post_local({}),
                     lambda:transport.post_cloud({},token='fake',environment='Sandbox')):
            with self.assertRaises(transport.TransportUnavailable):call()

    def test_response_matrix_never_fabricates_success(self):
        for http,body,expected in [(200,{'Code':'100','FBRInvoiceNumber':'11000120181112000369'},'Submitted'),
            (200,{'Code':'100','InvoiceNumber':'A'},'Submitted'),(200,{'Code':'100'},'Reconciliation Required'),
            (200,{'Code':'101','Response':'Rejected'},'Failed'),(500,{'Code':'101'},'Reconciliation Required'),
            (403,{'fault':{'code':900908,'message':'Resource forbidden'}},'Failed'),
            (500,{'fault':{'code':900908,'message':'Resource forbidden'}},'Reconciliation Required'),
            (200,{},'Reconciliation Required'),(200,{'invoiceNumber':'DI','validationResponse':{'status':'Valid'}},'Reconciliation Required')]:
            self.assertEqual(api.classify_result({'http_status':http,'body':body})[0],expected)

    def test_durable_intent_rejection_and_ambiguous_history(self):
        doc=Row()
        intent=Row(protocol=api.PROTOCOL,attempt_id='A',transport_outcome='Ambiguous')
        self.assertEqual(api.history_blocker(doc,[intent])['status'],'Reconciliation Required')
        self.assertIsNone(api.history_blocker(doc,[intent,Row(attempt_id='A',protocol=api.PROTOCOL,transport_outcome='Rejected')]))
        self.assertEqual(api.history_blocker(doc,[Row(fbr_invoice_number='N')])['status'],'Already Submitted')

    def test_redaction_recursive_and_literal_secret(self):
        value={'Authorization':'Bearer secret','nested':[{'token':'secret','message':'echo secret Bearer other'}]}
        result=str(sanitize(value,('secret',)))
        self.assertNotIn('secret',result);self.assertNotIn('Bearer other',result)

    def test_database_lock_released_when_redis_fails(self):
        self.db.sql.return_value=[(1,)]
        with patch.object(frappe,'cache',side_effect=RuntimeError('redis down')):
            with submission_lock('Sales Invoice:INV-1'):pass
        self.assertIn('RELEASE_LOCK',self.db.sql.call_args.args[0])

    def test_submission_records_intent_before_fake_send_and_prevents_second_send(self):
        s=fixture();doc=Row(doctype='Sales Invoice',name='INV-1',company='Test Company',docstatus=1)
        profile=Row(mode='Sandbox');profile.get_password=lambda *a,**kw:'TEST-SECRET'
        ready=dict(network_ready=True,invoice=build_invoice(s),profile=profile,device=s['header']['pos_device'],snapshot=s)
        rows=[];sequence=[]
        def log(dt,name,kind,status,**kwargs):
            rows.append(Row(fbr_status=status,**kwargs));sequence.append('log:'+status);return 'LOG'
        def send(*a,**kw):
            sequence.append('send')
            self.assertIn('commit',sequence)
            self.assertEqual(rows[0].transport_outcome,'Ambiguous')
            return {'http_status':200,'body':{'Code':'100','InvoiceNumber':'FBR-123','Response':'TEST-SECRET'}}
        self.db.commit.side_effect=lambda:sequence.append('commit')
        with patch.object(api,'source',return_value=doc),patch.object(api,'is_consolidated',return_value=False),patch.object(api,'submission_lock',return_value=nullcontext()),patch.object(api,'history',side_effect=lambda d:rows),patch.object(api,'inspect_invoice',return_value=ready),patch.object(api,'create_submission_log',side_effect=log),patch.object(transport,'V1_NETWORK_CUTOVER_ACTIVE',True),patch.object(transport,'post_cloud',side_effect=send) as post:
            self.assertEqual(api.submit_internal(doc.doctype,doc.name)['status'],'Submitted')
            self.assertEqual(api.submit_internal(doc.doctype,doc.name)['status'],'Already Submitted')
            self.assertEqual(post.call_count,1)
        self.assertNotIn('TEST-SECRET',str(rows))

    def test_cutover_closed_creates_no_transport_attempt(self):
        doc=Row(doctype='Sales Invoice',name='INV-1',docstatus=1)
        with patch.object(api,'source',return_value=doc),patch.object(api,'is_consolidated',return_value=False),patch.object(api,'submission_lock',return_value=nullcontext()),patch.object(api,'history',return_value=[]),patch.object(api,'inspect_invoice',return_value=dict(network_ready=False,errors=[],network_blockers=['disabled'])),patch.object(transport,'post_cloud') as post:
            self.assertEqual(api.submit_internal(doc.doctype,doc.name)['status'],'Not Attempted')
            post.assert_not_called()

    def test_uncertain_send_never_retries(self):
        s=fixture();doc=Row(doctype='Sales Invoice',name='INV-1',company='Test Company',docstatus=1)
        profile=Row(mode='Sandbox');profile.get_password=lambda *a,**kw:'FAKE'
        ready=dict(network_ready=True,invoice=build_invoice(s),profile=profile,device=s['header']['pos_device'],snapshot=s)
        rows=[]
        def log(dt,name,kind,status,**kw):
            rows.append(Row(fbr_status=status,**kw));return 'LOG'
        with patch.object(api,'source',return_value=doc),patch.object(api,'is_consolidated',return_value=False),patch.object(api,'submission_lock',return_value=nullcontext()),patch.object(api,'history',side_effect=lambda d:rows),patch.object(api,'inspect_invoice',return_value=ready),patch.object(api,'create_submission_log',side_effect=log),patch.object(transport,'V1_NETWORK_CUTOVER_ACTIVE',True),patch.object(transport,'post_cloud',side_effect=TimeoutError('secret response lost')) as post:
            self.assertEqual(api.submit_internal(doc.doctype,doc.name)['status'],'Reconciliation Required')
            self.assertEqual(api.submit_internal(doc.doctype,doc.name)['status'],'Reconciliation Required')
            self.assertEqual(post.call_count,1)
        self.assertNotIn('secret response lost',str(rows))


    def test_pre_send_exception_is_failed_not_reconciliation(self):
        s=fixture();doc=Row(doctype='Sales Invoice',name='INV-1',company='Test Company',docstatus=1)
        profile=Row(mode='Sandbox')
        profile.get_password=Mock(side_effect=RuntimeError('credential store unavailable'))
        ready=dict(network_ready=True,invoice=build_invoice(s),profile=profile,
                   device=s['header']['pos_device'],snapshot=s)
        rows=[]

        def log(dt,name,kind,status,**kw):
            rows.append(Row(fbr_status=status,**kw))
            return 'LOG'

        with patch.object(api,'source',return_value=doc),\
             patch.object(api,'is_consolidated',return_value=False),\
             patch.object(api,'submission_lock',return_value=nullcontext()),\
             patch.object(api,'history',side_effect=lambda d:rows),\
             patch.object(api,'inspect_invoice',return_value=ready),\
             patch.object(api,'create_submission_log',side_effect=log),\
             patch.object(transport,'V1_NETWORK_CUTOVER_ACTIVE',True),\
             patch.object(transport,'post_cloud') as post:

            result=api.submit_internal(doc.doctype,doc.name)

            self.assertEqual(result['status'],'Failed')
            post.assert_not_called()

        self.assertEqual(rows[-1].transport_outcome,'Rejected')
        self.assertIsNone(api.history_blocker(doc,rows))
