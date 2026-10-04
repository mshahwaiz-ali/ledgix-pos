"""Adversarial current POS boundaries; no site, accounting or network writes."""
import ast
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row
from ledgix_saas.api import pos_compat, selling as api
from ledgix_saas.services import erpnext_pos as pos, erpnext_selling as selling


class Support(NoNetworkTest):
    def setUp(self):
        super().setUp()
        self.roles = ['Ledgix Cashier']
        self.stack.enter_context(patch.object(frappe, 'get_roles', side_effect=lambda *args: self.roles))
        self.stack.enter_context(patch.object(pos, '_', side_effect=lambda m: m))
        self.stack.enter_context(patch.object(selling, '_', side_effect=lambda m: m))
        self.stack.enter_context(patch.object(api, '_', side_effect=lambda m: m))

    def no_writes(self):
        for method in ('sql','set_value','commit','updatedb'):
            getattr(self.db, method).assert_not_called()


class AuthorityTest(Support):
    def test_every_direct_channel_rpc_blocks_cashier_b2b_before_service(self):
        for name in ('get_pos_v2_boot','search_pos_v2_items','get_pos_v2_customer_context',
                     'preview_pos_v2_checkout','complete_pos_v2_sale','hold_pos_v2_sale'):
            with self.subTest(name=name), patch.object(pos, 'profile_for_user', side_effect=AssertionError('No context lookup before permission')):
                with self.assertRaises(frappe.PermissionError):
                    getattr(pos_compat,name)(sale_channel='B2B')
        self.no_writes()

    def test_cashier_retail_and_manager_b2b_read_delegation(self):
        for roles,channel in ((['Ledgix Cashier'],'Retail'),(['Ledgix Manager'],'B2B')):
            self.roles=roles
            for name,service in (('search_pos_v2_items','search_items'),('get_pos_v2_customer_context','customer_context'),('get_pos_v2_boot','boot')):
                with patch.object(pos, service, return_value={'channel':channel}) as call:
                    self.assertEqual(getattr(pos_compat,name)(sale_channel=channel), {'channel':channel})
                    call.assert_called_once()
        self.no_writes()

    def test_cashier_discount_rpc_matrix_rejects_before_draft_or_lock(self):
        for name in ('preview_pos_v2_checkout','complete_pos_v2_sale','hold_pos_v2_sale'):
            for kind in ('Amount','Percent'):
                with self.subTest(name=name,kind=kind), patch.object(pos,'profile_for_user', side_effect=AssertionError('No lookup before permission')):
                    with self.assertRaises(frappe.PermissionError):
                        getattr(pos_compat,name)(discount_type=kind,discount_value=10)
        self.no_writes()

    def test_zero_discount_retail_delegates_preview_complete_and_hold(self):
        with patch.object(pos, 'preview_checkout', return_value={'ok':True}):
            self.assertEqual(pos_compat.preview_pos_v2_checkout(discount_value=0), {'ok':True})
        invoice=Row(name='POS',doctype='POS Invoice',custom_ledgix_hold_id='H',customer='C',selling_price_list='P',grand_total=100)
        with patch.object(pos, 'complete_sale', return_value=invoice), patch.object(pos, 'sale_result', return_value={}), patch.object(pos_compat, '_native_print_target', return_value={'ok':True}):
            self.assertEqual(pos_compat.complete_pos_v2_sale(discount_value=0), {'ok':True})
        with patch.object(pos,'create_hold',return_value=invoice):
            self.assertTrue(pos_compat.hold_pos_v2_sale(discount_value=0)['success'])
        self.no_writes()

    def test_manager_discount_and_rate_override_preserve_policy(self):
        self.roles=['Ledgix Manager']
        rows=[{'qty':2,'rate':100}]
        result=selling._apply_checkout_discount(rows,'Percent',10)
        self.assertEqual(result['amount'],20)
        self.assertEqual(rows[0]['rate'],90)
        with patch.object(pos,'preview_checkout',return_value={}) as service:
            pos_compat.preview_pos_v2_checkout(discount_value=10)
            self.assertTrue(service.call_args.kwargs['allow_rate_override'])

    def test_manager_admin_b2b_preview_checkout_and_hold_are_preserved(self):
        invoice=Row(name='INV',doctype='Sales Invoice',custom_ledgix_hold_id='H',customer='C',selling_price_list='P',grand_total=100)
        for role in ('Ledgix Manager','Ledgix Admin','System Manager'):
            self.roles=[role]
            with patch.object(pos_compat.selling_compat,'preview_b2b_invoice',return_value={'native':True}) as preview:
                self.assertEqual(pos_compat.preview_pos_v2_checkout(sale_channel='B2B',discount_value=5),{'native':True});preview.assert_called_once()
            with patch.object(pos_compat.selling_compat,'complete_b2b_sale',return_value={'invoice':'INV'}) as complete,patch.object(pos_compat,'_native_print_target',return_value={'native':True}):
                self.assertEqual(pos_compat.complete_pos_v2_sale(sale_channel='B2B',discount_value=5),{'native':True});complete.assert_called_once()
            with patch.object(pos,'create_hold',return_value=invoice) as hold:
                self.assertEqual(pos_compat.hold_pos_v2_sale(sale_channel='B2B',discount_value=5)['sale_channel'],'B2B');hold.assert_called_once()
        self.no_writes()

    def test_bad_discount_numbers_and_type_fail_closed(self):
        self.roles=['Ledgix Manager']
        for value in ('bad', float('nan'), float('inf'), -1):
            with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
                selling.validate_checkout_discount_authority('Amount',value)
        with self.assertRaises(frappe.ValidationError):
            selling.validate_checkout_discount_authority('Invalid',1)
        self.no_writes()

    def test_cashier_cannot_list_fetch_resume_cancel_b2b_hold(self):
        self.db.get_value.side_effect=lambda d,*a,**k:'INV' if d=='Sales Invoice' else None
        with patch.object(frappe,'get_doc',side_effect=AssertionError('Do not expose B2B hold')):
            for name in ('resume_pos_v2_hold','cancel_pos_v2_hold'):
                with self.assertRaises(frappe.PermissionError):getattr(pos_compat,name)('HOLD')
        with patch.object(frappe,'get_all',return_value=[]) as query:
            self.assertEqual(pos_compat.get_pos_v2_holds()['holds'],[])
            self.assertEqual([c.args[0] for c in query.call_args_list],['POS Invoice'])
        self.no_writes()

    def test_manager_can_access_other_users_b2b_hold_and_cashier_own_retail(self):
        for role,doctype,owner in (('Ledgix Manager','Sales Invoice','another@example.invalid'),('Ledgix Cashier','POS Invoice','test@example.invalid')):
            self.roles=[role]
            self.db.get_value.side_effect=lambda d,*a,**k:'INV' if d==doctype else None
            doc=Row(doctype=doctype,owner=owner)
            with patch.object(frappe,'get_doc',return_value=doc):self.assertIs(pos._hold_by_id('H'),doc)
        self.no_writes()

    def test_resumed_discount_rejected_before_db_set(self):
        doc=Row(doctype='POS Invoice',custom_ledgix_hold_request_json='{"discount_type":"Amount","discount_value":5}',db_set=Mock())
        with patch.object(pos,'_hold_by_id',return_value=doc):
            with self.assertRaises(frappe.PermissionError):pos.resume_hold('H')
        doc.db_set.assert_not_called();self.no_writes()

    def test_direct_native_build_rechecks_override_role(self):
        with patch.object(selling,'_resolve_item',return_value='SKU'), patch.object(selling,'_native_item_rate',return_value=Row(rate=10,price_list_rate=10,uom='Nos')):
            with self.assertRaises(frappe.PermissionError):
                selling._normalize_items([{'item':'SKU','qty':1,'override_rate':5}],customer='C',company='Shop',price_list='P',posting_date='2026-10-04',allow_rate_override=True)
        self.no_writes()


class PricingStockTest(Support):
    def test_native_positive_rule_rate_wins_no_item_price_query(self):
        with patch.object(selling,'_currency',return_value='PKR'), patch.object(selling,'_price_list_currency',return_value='PKR'), patch('erpnext.stock.get_item_details.get_item_details',return_value={'rate':80,'price_list_rate':100,'uom':'Nos'}) as native, patch.object(frappe,'get_all',side_effect=AssertionError('Fallback forbidden')):
            result=selling._native_item_rate(item_code='SKU',customer='C',company='Shop',price_list='P',qty=2,posting_date='2026-10-04')
            self.assertEqual(result.rate,80);self.assertEqual(result.price_list_rate,100)
            self.assertEqual(native.call_args.args[0].ignore_pricing_rule,0)

    def test_native_plain_price_list_response_without_pricing_rule_is_accepted(self):
        with patch.object(selling,'_currency',return_value='PKR'),patch.object(selling,'_price_list_currency',return_value='PKR'),patch('erpnext.stock.get_item_details.get_item_details',return_value={'price_list_rate':100,'uom':'Nos'}),patch.object(frappe,'get_all',side_effect=AssertionError('No second price lookup')):
            result=selling._native_item_rate(item_code='SKU',customer='C',company='Shop',price_list='P',qty=1,posting_date='2026-10-04')
            self.assertEqual(result.rate,100)

    def test_no_native_effective_rate_never_resurrects_any_item_price(self):
        with patch.object(selling,'_currency',return_value='PKR'), patch.object(selling,'_price_list_currency',return_value='PKR'), patch.object(frappe,'get_all',side_effect=AssertionError('Expired/future/UOM/party price resurrection forbidden')):
            for result in ({'rate':0,'price_list_rate':100},{'rate':None},{'rate':-1},{'rate':float('nan')}):
                with patch('erpnext.stock.get_item_details.get_item_details',return_value=result), self.assertRaises(frappe.ValidationError):
                    selling._native_item_rate(item_code='SKU',customer='C',company='Shop',price_list='P',qty=1,posting_date='2026-10-04')
        self.no_writes()

    def test_native_uom_only_and_normal_manager_override(self):
        with patch.object(selling,'_resolve_item',return_value='SKU'), patch.object(selling,'_native_item_rate',return_value=Row(rate=10,price_list_rate=10,uom='Nos',discount_percentage=0)):
            for uom in (None,'','Nos',' Nos '):
                rows=selling._normalize_items([{'item':'SKU','qty':1,'uom':uom}],customer='C',company='Shop',price_list='P',posting_date='2026-10-04')
                self.assertEqual(rows[0]['uom'],'Nos');self.assertEqual(rows[0]['rate'],10)
            with self.assertRaises(frappe.ValidationError):selling._normalize_items([{'item':'SKU','qty':1,'uom':'Box'}],customer='C',company='Shop',price_list='P',posting_date='2026-10-04')
            self.roles=['Ledgix Manager']
            rows=selling._normalize_items([{'item':'SKU','qty':1,'override_rate':12}],customer='C',company='Shop',price_list='P',posting_date='2026-10-04',allow_rate_override=True)
            self.assertEqual(rows[0]['rate'],12)
        self.no_writes()

    def test_retail_warehouse_injection_rejected_before_pricing_or_document(self):
        self.stack.enter_context(patch.object(pos.erpnext_phase8_extensions,'require_schema_ready'))
        self.stack.enter_context(patch.object(pos,'_company',return_value='Shop'))
        for name,value in (('profile_for_user',Row(name='P')),('_profile_customer','C'),('_price_list','P'),('_profile_warehouse','POS-WH')):
            self.stack.enter_context(patch.object(pos,name,return_value=value))
        with patch.object(selling,'_normalize_items',side_effect=AssertionError('No pricing on invalid warehouse')),patch.object(frappe,'get_doc',side_effect=AssertionError('No invoice')):
            for wh in ('Other same-company','Other company'):
                with self.assertRaises(frappe.ValidationError):pos.build_pos_invoice(cart_items=[{'item':'SKU','qty':1,'warehouse':wh}])
        self.no_writes()

    def test_missing_and_matching_warehouse_are_canonicalized(self):
        for name,value in (('_company','Shop'),('profile_for_user',Row(name='P')),('_profile_customer','C'),('_price_list','P'),('_profile_warehouse','POS-WH')):
            self.stack.enter_context(patch.object(pos,name,return_value=value))
        self.stack.enter_context(patch.object(pos.erpnext_phase8_extensions,'require_schema_ready'))
        self.stack.enter_context(patch.object(selling,'_currency',return_value='PKR'))
        self.stack.enter_context(patch.object(pos.erpnext_tax_authority,'apply_sales_tax_authority'))
        for wh in (None,'POS-WH'):
            row={'item_code':'SKU','qty':1,'rate':100,'warehouse':wh}
            invoice=Mock()
            with patch.object(selling,'_normalize_items',return_value=[row]),patch.object(frappe,'get_doc',return_value=invoice) as get:
                pos.build_pos_invoice(cart_items=[{'item':'SKU','qty':1,'warehouse':wh}])
                self.assertEqual(get.call_args.args[0]['items'][0]['warehouse'],'POS-WH')
        self.no_writes()


class TenderTest(Support):
    def setUp(self):
        super().setUp()
        self.profile=Row(name='P',company='Shop',allow_partial_payment=0)
        self.policies=[dict(name=name,type=kind,account=name+'-ACCOUNT',default=0,allow_change=change,requires_reference=reference) for name,kind,change,reference in [('Cash','Cash',True,False),('Other Cash','Cash',True,False),('No Change','Cash',False,False),('Card','Bank',False,True)]]
        self.stack.enter_context(patch.object(pos,'payment_methods',return_value=self.policies))
        self.stack.enter_context(patch.object(selling,'_resolve_mode_of_payment',side_effect=lambda mode:mode))

    def normalize(self,pairs):
        return pos._normalize_tenders([{'payment_method':mode,'amount':amount,'reference_number':'REF'} for mode,amount in pairs],self.profile,100)

    def test_exact_split_and_actual_cash_excess_matrix(self):
        for pairs,change in [([('Cash',100)],0),([('Card',100)],0),([('Card',60),('Cash',40)],0),([('Cash',150)],50),([('Card',60),('Cash',50)],10)]:
            rows=self.normalize(pairs);self.assertEqual(sum(r['change_amount'] for r in rows),change)
            if change:self.assertEqual(next(r for r in rows if r['change_amount'])['account'],'Cash-ACCOUNT')
        self.no_writes()

    def test_hostile_over_tenders_and_bad_numbers_fail(self):
        for pairs in ([('Card',150)],[('Card',150),('Cash',1)],[('Card',101),('Cash',99)],[('No Change',150)],[('Cash',150),('Card',1)],[('Cash',-1)],[('Cash',float('nan'))],[('Cash',float('inf'))],[('Unconfigured',100)]):
            with self.subTest(pairs=pairs),self.assertRaises(frappe.ValidationError):self.normalize(pairs)
        self.no_writes()

    def test_partial_reference_policy_and_specific_change_account(self):
        self.profile.allow_partial_payment=1
        self.assertEqual(self.normalize([('Card',60)])[0]['amount'],60)
        with self.assertRaises(frappe.ValidationError):pos._normalize_tenders([{'mode_of_payment':'Card','amount':100}],self.profile,100)
        rows=self.normalize([('Cash',60),('Other Cash',50)])
        self.assertEqual(next(r for r in rows if r['change_amount'])['account'],'Other Cash-ACCOUNT')

    def test_complete_assigns_actual_cash_excess_account_before_native_submit(self):
        invoice=Mock(name='invoice');invoice.rounded_total=100;invoice.grand_total=100;invoice.flags=Row()
        for name,value in (('_company','Shop'),('profile_for_user',self.profile),('active_opening',True),('_existing_pos_sale',None),('build_pos_invoice',invoice)):
            self.stack.enter_context(patch.object(pos,name,return_value=value))
        self.stack.enter_context(patch.object(selling,'_lock_company'))
        self.stack.enter_context(patch.object(pos.erpnext_phase8_extensions,'require_schema_ready'))
        pos.complete_sale(cart_items=[],tenders=[{'payment_method':'Cash','amount':60},{'payment_method':'Other Cash','amount':50}])
        self.assertEqual(invoice.account_for_change_amount,'Other Cash-ACCOUNT')
        invoice.insert.assert_called_once();invoice.submit.assert_called_once()


class SchemaAndLegacyTest(Support):
    def test_schema_assertions_are_read_only_and_missing_schema_blocks_runtime(self):
        for module in (selling.erpnext_phase6_extensions,pos.erpnext_phase8_extensions):
            with patch.object(frappe,'get_meta',return_value=Mock(has_field=lambda f:True)):
                self.assertTrue(module.schema_ready());module.require_schema_ready()
            with patch.object(frappe,'get_meta',return_value=Mock(has_field=lambda f:False)):
                with self.assertRaisesRegex(frappe.ValidationError,'bench migrate'):module.require_schema_ready()
        with patch.object(pos.erpnext_phase8_extensions,'schema_ready',return_value=False),patch.object(frappe,'get_doc',side_effect=AssertionError('No invoice')):
            with self.assertRaisesRegex(frappe.ValidationError,'bench migrate'):pos.build_pos_invoice(cart_items=[])
        with patch.object(selling.erpnext_phase6_extensions,'schema_ready',return_value=False),patch.object(frappe,'get_doc',side_effect=AssertionError('No payment')):
            with self.assertRaisesRegex(frappe.ValidationError,'bench migrate'):selling.post_customer_payment(customer='C',mode_of_payment='Cash',amount=1,allocations=[])
        self.no_writes()

    def test_direct_original_routes_all_delegate_without_shadow_engine(self):
        from ledgix_saas import hooks
        for original,target in hooks.override_whitelisted_methods.items():
            if not target.startswith('ledgix_saas.api.pos_compat.'):continue
            module,name=original.rsplit('.',1);function=getattr(importlib.import_module(module),name)
            with patch.object(pos_compat,target.rsplit('.',1)[1],return_value='native') as native:
                import inspect
                kwargs={k:p.default for k,p in inspect.signature(function).parameters.items() if p.kind not in (p.VAR_POSITIONAL,p.VAR_KEYWORD) and p.default is not p.empty}
                # Required original parameters are supplied without making a real service call.
                kwargs.update({k:'ARG' for k,p in inspect.signature(function).parameters.items() if p.default is p.empty and p.kind not in (p.VAR_POSITIONAL,p.VAR_KEYWORD)})
                self.assertEqual(function(**kwargs),'native',original);native.assert_called_once()
        self.no_writes()

    def test_migrate_remains_schema_authority_and_is_repeatable(self):
        for module in (selling.erpnext_phase6_extensions,pos.erpnext_phase8_extensions):
            self.db.exists.return_value=True
            with patch.object(module,'create_custom_fields') as create,patch.object(frappe,'clear_cache'):
                module.after_migrate();module.after_migrate()
                self.assertEqual(create.call_count,2)
                self.assertTrue(all(c.kwargs.get('update') for c in create.call_args_list))
        self.db.updatedb.assert_not_called()
