from copy import deepcopy
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row, fixture, rehash
from fbr_v1.services.fbr_v1_payload_builder import build_invoice
from fbr_v1.services.payment_snapshot import capture_payment

class TestV1Payload(NoNetworkTest):
    def test_sales_pos_credit_and_third_schedule_matrix(self):
        for dt in ("Sales Invoice", "POS Invoice"):
            for credit in (False, True):
                for third in (False, True):
                    with self.subTest(dt=dt, credit=credit, third=third):
                        invoice = build_invoice(fixture(dt, credit, third))
                        self.assertEqual(invoice.invoice_type, 3 if credit else 1)
                        self.assertEqual(invoice.items[0].invoice_type, (12 if third else 3) if credit else (11 if third else 1))
                        self.assertEqual(invoice.total_bill_amount, 118)
                        self.assertEqual(invoice.items[0].quantity, 1)
                        self.assertEqual(invoice.ref_usin, "ORIGINAL" if credit else None)

    def test_hash_tamper_rejected_even_with_hash_verified_flag(self):
        s = fixture(); s['hash_verified'] = True; s['lines']['ROW-1']['line']['net_amount'] = 999
        with self.assertRaisesRegex(ValueError, "manifest"):
            build_invoice(s)

    def test_unsupported_tax_debit_and_missing_reference(self):
        for key in ('extra_tax', 'fed_payable', 'sales_tax_withheld_at_source'):
            s = fixture(); s['lines']['ROW-1']['line']['components'][key] = 1
            with self.assertRaisesRegex(ValueError, 'Unresolved'):
                build_invoice(rehash(s))
        s = fixture(); s['header']['note_type'] = 'Debit'
        with self.assertRaisesRegex(ValueError, 'Debit'):
            build_invoice(rehash(s))
        s = fixture(credit=True); s['header']['ref_usin'] = ''
        with self.assertRaisesRegex(ValueError, 'original'):
            build_invoice(rehash(s))

    def test_totals_signs_pct_and_mapping_fail_closed(self):
        cases = [lambda s: s['header'].update(grand_total=119),
                 lambda s: s['lines']['ROW-1']['line'].update(qty=-1),
                 lambda s: s['lines']['ROW-1']['line']['fbr_mapping'].update(hs_code='123456789'),
                 lambda s: s['lines']['ROW-1']['line']['fbr_mapping'].update(needs_review=1)]
        for mutate in cases:
            s=fixture(); mutate(s)
            with self.assertRaises(ValueError): build_invoice(rehash(s))

    def test_native_discount_and_further_tax_serialize_without_tax_recalculation(self):
        s=fixture(); line=s['lines']['ROW-1']['line']
        line.update(net_amount=90, distributed_discount_amount=10)
        line['components'].update(sales_tax=16.2, further_tax=3.6)
        s['header'].update(net_total=90, total_taxes_and_charges=19.8, grand_total=109.8)
        inv=build_invoice(rehash(s))
        self.assertEqual((inv.total_sale_value, inv.discount, inv.total_bill_amount), (100,10,109.8))
        self.assertEqual(inv.further_tax,3.6)

    def test_statutory_pos_service_fee_reconciles_without_new_wire_field(self):
        s = fixture()
        s['header'].update(pos_service_fee=1, total_taxes_and_charges=19, grand_total=119)
        invoice = build_invoice(rehash(s))
        payload = invoice.to_payload()
        self.assertEqual(invoice.total_bill_amount, 119)
        self.assertEqual(invoice.total_tax_charged, 18)
        self.assertNotIn('ServiceFee', payload)
        self.assertNotIn('POSServiceFee', payload)

        bad = fixture()
        bad['header'].update(pos_service_fee=0.5, total_taxes_and_charges=18.5, grand_total=118.5)
        with self.assertRaisesRegex(ValueError, 'Service Fee'):
            build_invoice(rehash(bad))

    def test_payment_single_mixed_zero_and_missing(self):
        lookup=lambda mode: {'Cash':'1 - Cash','Card':'2 - Card','Other Cash':'1 - Cash'}.get(mode)
        doc=Row(doctype='POS Invoice',payments=[Row(mode_of_payment='Cash', amount=100),Row(mode_of_payment='Card',amount=0)])
        self.assertEqual(capture_payment(doc,lookup)['payment_mode'],1)
        doc.payments[1].amount=10
        self.assertEqual(capture_payment(doc,lookup)['payment_mode'],5)
        doc.payments[1].mode_of_payment='Other Cash'
        self.assertEqual(capture_payment(doc,lookup)['payment_mode'],1)
        doc.payments[1].mode_of_payment='Unknown'
        with self.assertRaises(frappe.ValidationError):capture_payment(doc,lookup)
        doc=Row(doctype='Sales Invoice',payments=[])
        with self.assertRaises(frappe.ValidationError):capture_payment(doc,lookup)
        doc.custom_ledgix_fbr_mode_of_payment='Card'
        self.assertEqual(capture_payment(doc,lookup)['payment_mode'],2)

    def test_fully_tendered_transient_b2b_payment_evidence(self):
        lookup=lambda mode: {'Cash':'1 - Cash','Card':'2 - Card'}.get(mode)
        evidence=lambda rows: Row(source='Ledgix B2B Checkout',require_full_coverage=True,rows=rows)
        doc=Row(doctype='Sales Invoice',is_return=0,payments=[],grand_total=118,
                flags=Row(ledgix_fbr_v1_payment_evidence=evidence([
                    {'mode_of_payment':'Cash','amount':118,'reference_no':''}
                ])))
        payment=capture_payment(doc,lookup)
        self.assertEqual(payment['payment_mode'],1)
        self.assertEqual(payment['evidence'][0]['source'],'Ledgix B2B Checkout')

        doc.flags.ledgix_fbr_v1_payment_evidence=evidence([
            {'mode_of_payment':'Cash','amount':50},
            {'mode_of_payment':'Card','amount':68,'reference_no':'CARD-1'},
        ])
        self.assertEqual(capture_payment(doc,lookup)['payment_mode'],5)

    def test_transient_b2b_payment_evidence_fails_closed(self):
        lookup=lambda mode: {'Cash':'1 - Cash'}.get(mode)
        def doc(rows):
            return Row(doctype='Sales Invoice',is_return=0,payments=[],grand_total=118,
                       flags=Row(ledgix_fbr_v1_payment_evidence=Row(
                           source='Ledgix B2B Checkout',require_full_coverage=True,rows=rows)))
        with self.assertRaisesRegex(frappe.ValidationError,'fully tendered'):
            capture_payment(doc([]),lookup)
        with self.assertRaisesRegex(frappe.ValidationError,'fully cover'):
            capture_payment(doc([{'mode_of_payment':'Cash','amount':100}]),lookup)
        with self.assertRaisesRegex(frappe.ValidationError,'Missing Federal V1 payment mapping'):
            capture_payment(doc([{'mode_of_payment':'Unmapped','amount':118}]),lookup)
        credit=doc([{'mode_of_payment':'Cash','amount':118}]); credit.is_return=1
        with self.assertRaisesRegex(frappe.ValidationError,'Credit Note payment semantics are unresolved'):
            capture_payment(credit,lookup)
