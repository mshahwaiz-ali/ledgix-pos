"""In-memory tests for the shared boot/readiness/B2B payment universe."""
from unittest.mock import patch

import frappe
from fbr_v1.services.payment_readiness import get_payment_readiness
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row
from ledgix_saas.api import selling
from ledgix_saas.services import erpnext_pos


class TestB2BCheckoutPayments(NoNetworkTest):
    def setUp(self):
        super().setUp()
        self.profile = Row(name='COUNTER', company='Shop', disabled=0,
            payments=[Row(mode_of_payment='Cash', default=1), Row(mode_of_payment='Card', default=0)])
        self.stack.enter_context(patch.object(erpnext_pos, 'profile_for_user', return_value=self.profile))
        self.stack.enter_context(patch.object(erpnext_pos, '_mode_policy',
            side_effect=lambda mode, company: {'name': mode, 'sort_order': 0, 'type': mode}))
        self.stack.enter_context(patch.object(selling.erpnext_selling, '_resolve_mode_of_payment', side_effect=lambda mode: mode))
        self.stack.enter_context(patch.object(selling.erpnext_selling, '_company', return_value='Shop'))
        self.stack.enter_context(patch.object(frappe, 'get_all', return_value=['COUNTER']))
        self.stack.enter_context(patch.object(frappe, 'get_doc', return_value=self.profile))
        self.codes = {'Cash': '1 - Cash', 'Card': '2 - Card'}
        self.db.get_value.side_effect = lambda dt, mode, *args, **kwargs: Row(enabled=1,
            custom_ledgix_fbr_v1_payment_mode=self.codes.get(mode))

    def assert_read_only(self):
        for name in ('set_value', 'sql', 'insert', 'commit', 'rollback'):
            getattr(self.db, name).assert_not_called()

    def test_configured_mapped_mode_passes_contract_and_readiness(self):
        profile, rows = selling.validate_b2b_checkout_tenders([{'payment_method': 'Cash', 'amount': 100}])
        self.assertIs(profile, self.profile)
        self.assertEqual(rows[0]['mode_of_payment'], 'Cash')
        readiness = get_payment_readiness('Shop', devices=[])
        self.assertTrue(readiness['ready'])
        self.assertEqual(readiness['required_modes'], sorted(row['name'] for row in erpnext_pos.payment_methods(profile)))
        self.assert_read_only()

    def test_configured_unmapped_mode_blocks_readiness(self):
        self.codes.pop('Card')
        readiness = get_payment_readiness('Shop', devices=[])
        self.assertFalse(readiness['ready'])
        self.assertEqual(readiness['missing_modes'], ['Card'])
        self.assert_read_only()

    def test_existing_unoffered_mode_rejected_before_invoice_or_payment(self):
        with patch.object(selling, '_require_manager'), \
             patch.object(selling.erpnext_selling, 'create_sales_invoice') as invoice, \
             patch.object(selling.erpnext_selling, 'post_customer_payment') as payment:
            with self.assertRaises(frappe.ValidationError):
                selling.complete_b2b_sale('Customer', cart_items=[],
                    tenders=[{'mode_of_payment': 'Existing Bank Transfer', 'amount': 100}])
            invoice.assert_not_called()
            payment.assert_not_called()
        self.assert_read_only()

    def test_mixed_configured_mapped_tenders_preserve_amounts_and_reference(self):
        _, rows = selling.validate_b2b_checkout_tenders([
            {'payment_method': 'Cash', 'amount': 40},
            {'mode_of_payment': 'Card', 'amount': 60, 'reference_number': 'CARD-REF'}])
        self.assertEqual(rows, [
            {'mode_of_payment': 'Cash', 'amount': 40, 'reference_no': None},
            {'mode_of_payment': 'Card', 'amount': 60, 'reference_no': 'CARD-REF'}])
        readiness = get_payment_readiness('Shop', devices=[])
        self.assertTrue(readiness['ready'])
        self.assertEqual(readiness['mapped_modes'], ['Card', 'Cash'])
        self.assert_read_only()

    def test_standalone_payment_off_profile_rejected_before_service(self):
        with patch.object(selling,'_require_manager'), patch.object(selling.erpnext_selling,'post_customer_payment') as payment:
            with self.assertRaises(frappe.ValidationError):
                selling.post_customer_payment('Customer','Existing Bank Transfer',100,allocations=[{'invoice':'INV','allocated_amount':100}])
            payment.assert_not_called()
        self.assert_read_only()

    def test_standalone_refund_off_profile_rejected_before_service(self):
        note=Row(company='Shop',docstatus=1,is_return=1)
        with patch.object(selling,'_require_manager'), patch.object(frappe,'get_doc',return_value=note), patch.object(selling.erpnext_selling,'refund_credit_note') as refund:
            with self.assertRaises(frappe.ValidationError):selling.refund_credit_note('NOTE','Existing Bank Transfer',100)
            refund.assert_not_called()
        self.assert_read_only()

    def test_configured_cash_card_payment_and_refund_use_actual_company(self):
        for mode in ('Cash','Card'):
            payment=Row(name='PAY',docstatus=1,paid_amount=100,total_allocated_amount=100,unallocated_amount=0,payment_type='Pay')
            with patch.object(selling,'_require_manager'), patch.object(selling.erpnext_selling,'post_customer_payment',return_value=payment) as post, patch.object(selling.erpnext_selling,'get_customer_receivables',return_value={}):
                selling.post_customer_payment('Customer',mode,100,allocations=[{'invoice':'INV','allocated_amount':100}])
                self.assertEqual(post.call_args.kwargs['company'],'Shop')
                self.assertEqual(post.call_args.kwargs['mode_of_payment'],mode)
            with patch.object(selling,'_require_manager'), patch.object(frappe,'get_doc',return_value=Row(company='Shop',docstatus=1,is_return=1)), patch.object(selling.erpnext_selling,'refund_credit_note',return_value=payment) as refund:
                selling.refund_credit_note('NOTE',mode,100)
                self.assertEqual(refund.call_args.kwargs['mode_of_payment'],mode)
        self.assert_read_only()

    def test_foreign_company_profile_rejected_before_refund(self):
        with patch.object(selling,'_require_manager'), patch.object(frappe,'get_doc',return_value=Row(company='Other',docstatus=1,is_return=1)),patch.object(selling.erpnext_selling,'refund_credit_note') as refund:
            with self.assertRaises(frappe.ValidationError):selling.refund_credit_note('NOTE','Cash',100)
            refund.assert_not_called()
        self.assert_read_only()
