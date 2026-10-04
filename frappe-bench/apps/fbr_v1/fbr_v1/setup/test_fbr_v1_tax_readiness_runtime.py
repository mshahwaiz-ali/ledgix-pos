from contextlib import ExitStack
from unittest.mock import Mock, patch
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json

import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row
from fbr_v1.services import erpnext_tax_readiness as readiness
from fbr_v1.services import native_tax_paths, payment_readiness
from fbr_v1.fbr_v1.doctype.ledgix_fbr_item_mapping import ledgix_fbr_item_mapping as controller
from fbr_v1.fbr_v1.doctype.ledgix_fbr_item_mapping.ledgix_fbr_item_mapping import LedgixFBRItemMapping


class NativeInvoice(Row):
    @property
    def items(self):
        return self["items"]
    @property
    def meta(self):
        return Mock(get_field=lambda field: Row(options='Sales Taxes and Charges Template'))
    def is_new(self):
        return True
    def extend(self, field, rows):
        self[field].extend(Row(r) for r in rows or [])
    def append(self, field, row):
        self[field].append(Row(row))
    def get_tax_row(self, account):
        return next((r for r in self.taxes if r.account_head == account), None)
    def set_taxes(self):
        from erpnext.controllers.accounts_controller import AccountsController
        AccountsController.set_taxes(self)
    def append_taxes_from_master(self, *args):
        from erpnext.controllers.accounts_controller import AccountsController
        AccountsController.append_taxes_from_master(self, *args)
    def append_taxes_from_item_tax_template(self):
        from erpnext.controllers.accounts_controller import AccountsController
        AccountsController.append_taxes_from_item_tax_template(self)
    def set_taxes_and_charges(self):
        from erpnext.controllers.accounts_controller import AccountsController
        AccountsController.set_taxes_and_charges(self)


class TestTaxReadiness(NoNetworkTest):
    def setUp(self):
        super().setUp()
        self.db.exists.return_value = True
        self.db.count.return_value = 1
        self.account = Row(company='Shop', is_group=0, disabled=0)
        self.db.get_value.side_effect = self.value
        self.items = [Row(name='SKU')]
        self.mappings = [Row(name='MAP', erpnext_item='SKU', needs_review=0,
            hs_code='12345678', tax_basis='Transaction Value', notified_retail_price=0)]
        self.components = [Row(name='TAX-MAP', account_head='GST', component=readiness.SALES_TAX)]
        self.sales = [Row(name='SALES')]
        self.item_templates = []
        self.docs = {'SALES': Row(name='SALES', company='Shop', disabled=0, is_default=1,
            taxes=[Row(account_head='GST', rate=12.5, charge_type='On Net Total')])}
        self.scope = []
        self.rules = []
        self.item = Row(name='SKU', item_group='Group', taxes=[])
        self.group = Row(name='Group', taxes=[])
        self.auto_item_rows = False
        self.default_sales = True
        self.default_rule = self.stack.enter_context(patch.object(native_tax_paths, 'default_sales_tax_rule', return_value=None))
        self.stack.enter_context(patch.object(frappe, 'get_all', side_effect=self.query))
        self.stack.enter_context(patch.object(frappe, 'get_doc', side_effect=self.doc))
        self.stack.enter_context(patch.object(frappe, 'get_cached_doc', side_effect=self.cached))
        self.stack.enter_context(patch.object(frappe, 'get_cached_value', side_effect=lambda dt, name, fields: (0, 'Shop') if dt == 'Item Tax Template' else 'Shop'))
        self.stack.enter_context(patch('frappe.utils.nestedset.get_ancestors_of', return_value=[]))
        self.stack.enter_context(patch.object(frappe, 'get_single_value', side_effect=lambda dt, field: self.auto_item_rows if field == 'add_taxes_from_item_tax_template' else True))
        self.db.get_single_value.side_effect = lambda dt, field: self.auto_item_rows
        self.meta = Mock(get_field=Mock(return_value=Row(options='On Net Total\nOn Notified Retail Price')))
        self.stack.enter_context(patch.object(frappe, 'get_meta', return_value=self.meta))
        self.hooks = {readiness.CHARGE_TYPE: [readiness.RESOLVER]}
        self.stack.enter_context(patch.object(frappe, 'get_hooks', side_effect=lambda *a: self.hooks))

    def value(self, doctype, name, *args, **kwargs):
        if doctype == 'Account':
            return self.account
        if doctype == 'Sales Taxes and Charges Template':
            return 'SALES' if self.sales and self.default_sales else None
        if doctype == 'Item':
            return 0
        return None

    def doc(self, doctype, name=None):
        if isinstance(doctype, dict):
            return NativeInvoice(**doctype, flags=Row())
        return self.docs[name]

    def cached(self, doctype, name):
        if doctype == 'Item':
            return self.item
        if doctype == 'Item Group':
            return self.group
        return self.docs[name]

    def query(self, doctype, **kwargs):
        if doctype == 'Item':
            self.assertEqual(kwargs['filters']['has_variants'], 0)
            return [row for row in self.items if not row.get('has_variants') and not row.get('disabled') and row.get('is_sales_item', 1)]
        return {'Tax Rule': self.rules, 'Ledgix FBR Item Mapping': self.mappings,
            'Ledgix FBR Tax Component Mapping': self.components,
            'Sales Taxes and Charges Template': self.sales, 'Item Tax Template': self.item_templates,
            'Item Default': self.scope, 'Sales Invoice': [], 'POS Invoice': [],
            'POS Profile': [], 'Ledgix FBR POS Device': []}[doctype]

    def inspect(self):
        return readiness.get_company_tax_readiness('Shop')

    def assert_blocked(self, text):
        result = self.inspect()
        self.assertFalse(result['ready'])
        self.assertIn(text, ' '.join(result['blockers']))
        return result

    def third(self):
        self.mappings[0].update(tax_basis='Notified Retail Price', notified_retail_price=125)
        self.docs['SALES'].taxes[0].charge_type = readiness.CHARGE_TYPE

    def test_valid_company_account_component_and_native_path(self):
        result = self.inspect()
        self.assertTrue(result['ready'], result['blockers'])
        self.assertEqual(result['authority'], 'ERPNext Native')
        self.assertEqual(result['sales_tax_templates'][0]['taxes'][0]['rate'], 12.5)
        self.assertTrue(result['third_schedule']['not_required'])

    def test_missing_sales_tax_mapping(self):
        self.components = []
        self.assert_blocked('Sales Tax Applicable')

    def test_invalid_accounts(self):
        for attributes in ({'disabled': 1}, {'is_group': 1}, {'company': 'Other'}):
            with self.subTest(attributes=attributes):
                self.account = Row(company='Shop', is_group=0, disabled=0)
                self.account.update(attributes)
                self.assert_blocked('enabled leaf Account')

    def test_missing_account(self):
        self.account = None
        self.assert_blocked('enabled leaf Account')

    def test_conflicting_components(self):
        self.components.append(Row(name='SECOND', account_head='GST', component='Further Tax'))
        self.assert_blocked('conflicting')

    def test_unsupported_components_fail_closed(self):
        for component in ('Extra Tax', 'FED Payable', 'Sales Tax Withheld At Source', 'Unknown'):
            with self.subTest(component=component):
                self.components[0].component = component
                self.assert_blocked('not supported')

    def test_one_mapping_cannot_cover_several_sellable_items(self):
        self.items.extend([Row(name='SKU2'), Row(name='SKU3')])
        result = self.assert_blocked('SKU2')
        self.assertEqual(result['item_coverage']['required_count'], 3)
        self.assertEqual(result['item_coverage']['covered_count'], 1)

    def test_missing_mapping(self):
        self.mappings = []
        self.assert_blocked('found 0')

    def test_needs_review(self):
        self.mappings[0].needs_review = 1
        self.assert_blocked('Needs Review')

    def test_missing_or_long_pct(self):
        for code in ('', '123456789'):
            with self.subTest(code=code):
                self.mappings[0].hs_code = code
                self.assert_blocked('1 to 8 characters')

    def test_invalid_basis(self):
        self.mappings[0].tax_basis = 'DI Sale Type'
        self.assert_blocked('unsupported Tax Basis')

    def test_standard_template_does_not_require_item_template(self):
        self.assertTrue(self.inspect()['ready'])
        self.assertEqual(self.inspect()['item_tax_templates'], [])

    def test_missing_native_sales_path(self):
        self.sales = []
        self.assert_blocked('native sales-tax template path')

    def test_actual_mapped_tax_fails_closed(self):
        self.docs['SALES'].taxes[0].charge_type = 'Actual'
        self.assert_blocked('Actual')

    def test_positive_notified_price(self):
        self.third()
        self.assertTrue(self.inspect()['third_schedule']['ready'])
        self.assertTrue(self.inspect()['ready'])

    def test_missing_or_nonfinite_notified_price(self):
        self.third()
        for price in (0, -1, 'NaN', 'Infinity'):
            with self.subTest(price=price):
                self.mappings[0].notified_retail_price = price
                self.assert_blocked('positive Notified Retail Price')

    def test_missing_effective_charge_type(self):
        self.third()
        self.meta.get_field.return_value.options = 'On Net Total'
        self.assert_blocked('metadata is missing')

    def test_missing_or_duplicate_resolver(self):
        self.third()
        for hooks in ({}, {readiness.CHARGE_TYPE: [readiness.RESOLVER, 'legacy.resolver']}):
            self.hooks = hooks
            self.assert_blocked('sole registered')

    def test_third_schedule_requires_native_charge_path(self):
        self.third()
        self.docs['SALES'].taxes[0].charge_type = 'On Net Total'
        self.assert_blocked('native On Notified Retail Price')

    def test_effective_dates_and_ambiguity(self):
        self.mappings[0].effective_from = '2999-01-01'
        self.assert_blocked('found 0')
        self.mappings[0].effective_from = None
        self.mappings.append(Row(**{**self.mappings[0], 'name': 'MAP2'}))
        self.assert_blocked('found 2')

    def test_multi_company_new_shared_catalog_item_cannot_disappear(self):
        from ledgix_saas.services import erpnext_pos
        self.db.count.return_value = 2
        self.scope = []
        self.rules = []  # No Item Default and no historical invoice.
        self.items = [Row(name='SHARED', item_code='SHARED', item_name='New shared item',
            item_group='Group', stock_uom='Nos', is_stock_item=0)]
        with ExitStack() as stack:
            stack.enter_context(patch.object(erpnext_pos, '_company', return_value='Shop'))
            stack.enter_context(patch.object(erpnext_pos, 'profile_for_user', return_value=Row(name='COUNTER')))
            stack.enter_context(patch.object(erpnext_pos, '_profile_customer', return_value='CUSTOMER'))
            stack.enter_context(patch.object(erpnext_pos, '_price_list', return_value='RETAIL'))
            stack.enter_context(patch.object(erpnext_pos, '_profile_warehouse', return_value='WAREHOUSE'))
            stack.enter_context(patch.object(erpnext_pos, '_barcode', return_value=''))
            stack.enter_context(patch.object(erpnext_pos.erpnext_selling, '_native_item_rate', return_value=Row(rate=100, price_list_rate=100)))
            catalog = erpnext_pos.search_items(company='Shop')
        self.assertEqual([item['item_code'] for item in catalog['items']], ['SHARED'])
        result = self.inspect()
        self.assertFalse(result['ready'])
        self.assertEqual(result['item_coverage']['required_items'], ['SHARED'])
        self.assertIn('SHARED', ' '.join(result['blockers']))
        for call in frappe.get_all.call_args_list:
            self.assertNotIn(call.args[0], ('Item Default', 'Sales Invoice', 'POS Invoice'))
        self.db.set_value.assert_not_called()

    def test_disabled_and_non_sales_items_are_excluded(self):
        self.items.extend([Row(name='DISABLED', disabled=1), Row(name='NON-SALES', is_sales_item=0)])
        self.assertEqual(self.inspect()['item_coverage']['required_items'], ['SKU'])

    def test_zero_rate_visibility_does_not_invent_exemption(self):
        self.item_templates = [Row(name='ZERO')]
        self.docs['ZERO'] = Row(name='ZERO', company='Shop', taxes=[Row(tax_type='GST', tax_rate=0)])
        result = self.inspect()
        self.assertTrue(result['item_tax_templates'][0]['zero_rate'])
        self.assertNotIn('exempt', result['item_tax_templates'][0])

    def test_readiness_never_writes_or_calculates(self):
        result = self.inspect()
        self.assertFalse(result['database_write'])
        self.assertFalse(result['fbr_network_call'])
        for method in ('set_value', 'sql', 'commit', 'rollback', 'insert'):
            getattr(self.db, method).assert_not_called()
        for doc in self.docs.values():
            self.assertNotIn('calculate_taxes_and_totals', doc)

    def native_map(self, rate=0, na=False):
        self.item_templates = [Row(name='ITEM-TAX')]
        self.docs['ITEM-TAX'] = Row(name='ITEM-TAX', company='Shop', disabled=0,
            taxes=[Row(tax_type='GST', tax_rate=rate, not_applicable=na)])
        self.item.taxes = [Row(item_tax_template='ITEM-TAX', tax_category='', valid_from=None,
            maximum_net_rate=0)]

    def test_variant_template_excluded_actual_variant_required(self):
        self.items.extend([Row(name='PARENT', has_variants=1), Row(name='VARIANT', has_variants=0)])
        result = self.inspect()
        self.assertNotIn('PARENT', result['item_coverage']['required_items'])
        self.assertIn('VARIANT', result['item_coverage']['required_items'])

    def test_dormant_third_mapping_does_not_block(self):
        self.mappings.append(Row(name='OLD', erpnext_item='DORMANT', needs_review=0,
            tax_basis='Notified Retail Price', notified_retail_price=0))
        self.assertTrue(self.inspect()['ready'])
        self.assertTrue(self.inspect()['third_schedule']['not_required'])

    def test_zero_rate_native_path_is_ready(self):
        self.native_map()
        result = self.inspect()
        self.assertTrue(result['ready'], result['blockers'])
        self.assertTrue(result['zero_rate_configuration_used'])

    def test_na_native_path_needs_no_financial_mapping(self):
        self.native_map(na=True)
        self.sales = []
        self.components = []
        result = self.inspect()
        self.assertTrue(result['ready'], result['blockers'])
        self.assertTrue(result['na_configuration_used'])

    def test_unrelated_template_cannot_green_company(self):
        self.default_sales = False
        self.assert_blocked('missing/unresolved')

    def test_native_item_group_inheritance(self):
        self.native_map()
        self.group.taxes, self.item.taxes = self.item.taxes, []
        result = self.inspect()
        self.assertTrue(result['ready'])
        self.assertEqual(result['native_items'][0]['paths'][0]['native_source'], 'Item Group Group')

    def test_native_effective_date_selection(self):
        self.native_map(na=True)
        self.sales = []
        self.item.taxes[0].valid_from = '2999-01-01'
        self.assert_blocked('missing/unresolved')

    def test_conditional_rate_not_fabricated(self):
        self.native_map(na=True)
        self.item.taxes[0].maximum_net_rate = 100
        self.sales = []
        result = self.assert_blocked('missing/unresolved')
        self.assertIn('net-rate-dependent', ' '.join(result['warnings']))

    def test_native_auto_item_rows_enabled_zero_rate(self):
        self.native_map()
        self.sales = []
        self.auto_item_rows = True
        self.assertTrue(self.inspect()['ready'])

    def test_native_auto_item_rows_disabled_blocks_missing_row(self):
        self.native_map(rate=18)
        self.sales = []
        self.assert_blocked('no reachable financial tax row')

    def test_native_default_tax_rule_provides_sales_path(self):
        self.default_sales = False
        self.default_rule.return_value = 'SALES'
        result = self.inspect()
        self.assertTrue(result['ready'], result['blockers'])
        self.assertEqual(result['native_items'][0]['paths'][0]['sales_source'], 'ERPNext default Tax Rule')

    def test_pos_configured_template_and_category_path(self):
        context = dict(source='POS Profile Counter', doctype='POS Invoice', tax_category='Retail', taxes_and_charges='SALES')
        self.native_map(na=True)
        self.item.taxes[0].tax_category = 'Retail'
        with patch.object(native_tax_paths, 'native_contexts', return_value=([context], [])):
            self.assertTrue(self.inspect()['na_configuration_used'])

    def test_customer_specific_and_dated_rules_cannot_false_green(self):
        for field, value in (("customer", "Buyer"), ("customer_group", "Group"), ("tax_category", "Alternate"), ("from_date", "2026-01-01")):
            self.rules = [Row(name="CONTEXT", **{field: value})]
            result = self.assert_blocked("contextual transaction path")
            self.assertFalse(result["complete_transaction_surface_ready"])

    def test_net_rate_condition_blocks_even_with_valid_default_path(self):
        self.native_map()
        self.item.taxes[0].maximum_net_rate = 100
        self.assert_blocked("net-rate-dependent")

    def test_alternate_category_blocks_even_with_valid_default_path(self):
        self.native_map()
        self.item.taxes[0].tax_category = "Other"
        self.assert_blocked("another Tax Category")

    def test_default_only_configuration_has_complete_surface(self):
        result = self.inspect()
        self.assertTrue(result["ready"])
        self.assertTrue(result["complete_transaction_surface_ready"])


class TestClientTaxIntegration(NoNetworkTest):
    def inspect(self, tax_ready):
        from fbr_v1.api import client_readiness as api
        profile = Row(name='PROFILE', mode='Sandbox', enabled=1, protocol_version='Federal POS/IMS V1',
            production_post_armed=0, sandbox_token='DO-NOT-EXPOSE')
        device = Row(name='DEVICE', environment='Sandbox')
        self.db.exists.return_value = True
        with ExitStack() as stack:
            stack.enter_context(patch.object(api, 'get_profile', return_value=profile))
            stack.enter_context(patch.object(api, 'profile_active', return_value=True))
            stack.enter_context(patch.object(api, 'resolve_company_seller_identity', return_value={'ready': True, 'errors': [], 'seller': {}}))
            stack.enter_context(patch.object(api, 'configuration_blockers', return_value=['Transport is disabled.']))
            stack.enter_context(patch.object(api, 'get_payment_readiness', return_value={'ready': True, 'blockers': []}))
            stack.enter_context(patch('fbr_v1.services.v1_configuration.setup_configuration_blockers', return_value=[]))
            stack.enter_context(patch.object(frappe, 'get_doc', side_effect=lambda dt, name: Row(name=name) if dt=='Company' else device))
            stack.enter_context(patch.object(frappe, 'get_list', return_value=['DEVICE']))
            stack.enter_context(patch.object(api.erpnext_tax_readiness, 'get_company_tax_readiness', return_value={
                'ready': tax_ready, 'blockers': [] if tax_ready else ['SKU2 mapping missing.']}))
            stack.enter_context(patch.object(api.transport, 'network_cutover_active', return_value=False))
            stack.enter_context(patch.object(api.transport, 'production_cutover_active', return_value=False))
            return api.get_client_readiness('Shop')

    def test_setup_readiness_does_not_require_network_or_production_arming(self):
        result = self.inspect(True)
        self.assertTrue(result['setup_ready'])
        self.assertTrue(result['source_accounting_ready'])
        self.assertTrue(result['tax_configuration_ready'])
        self.assertFalse(result['network_cutover_active'])
        self.assertFalse(result['production_configuration_ready'])
        self.assertFalse(result['production_ready'])
        self.assertNotIn('sandbox_token', result['profile_state'])
        self.assertNotIn('DO-NOT-EXPOSE', str(result))
        self.db.set_value.assert_not_called()

    def test_tax_blockers_prevent_setup_and_configuration_readiness(self):
        result = self.inspect(False)
        self.assertTrue(result['source_accounting_ready'])
        self.assertFalse(result['tax_configuration_ready'])
        self.assertFalse(result['setup_ready'])
        self.assertIn('SKU2 mapping missing.', result['setup_blockers'])
        self.assertFalse(result['sandbox_configuration_ready'])
        self.assertFalse(result['production_ready'])


class TestItemMappingController(NoNetworkTest):
    def setUp(self):
        super().setUp()
        self.db.exists.return_value = True
        self.db.get_value.return_value = 0
        self.others = []
        self.stack.enter_context(patch.object(frappe, 'get_all', side_effect=lambda *a, **k: self.others))
        self.stack.enter_context(patch.object(frappe, 'get_roles', return_value=['Ledgix Admin']))
        self.old = Row(company='Shop', erpnext_item='SKU', hs_code='12345678', tax_basis='Transaction Value',
            notified_retail_price=0, effective_from=None, effective_to=None, needs_review=1)
        self.doc = Row(**self.old, active=1, name='MAP', get_doc_before_save=lambda: self.old)

    def validate(self):
        controller.LedgixFBRItemMapping.validate(self.doc)

    def test_active_template_mapping_rejected_inactive_preserved(self):
        self.db.get_value.return_value = 1
        with self.assertRaisesRegex(frappe.ValidationError, 'variant templates'):
            self.validate()
        self.doc.active = 0
        self.validate()

    def test_non_overlapping_and_open_periods_allowed(self):
        self.doc.effective_from = '2027-01-01'
        self.others = [Row(name='OLD', effective_from=None, effective_to='2026-12-31')]
        self.validate()

    def test_inclusive_overlap_and_open_bounds_rejected(self):
        for other in (Row(effective_to='2026-12-31'), Row(effective_from=None, effective_to=None)):
            self.doc.effective_from = '2026-12-31'
            self.others = [other]
            with self.assertRaisesRegex(frappe.ValidationError, 'overlap'):
                self.validate()

    def test_invalid_date_range_rejected(self):
        self.doc.effective_from, self.doc.effective_to = '2027-01-01', '2026-12-31'
        with self.assertRaisesRegex(frappe.ValidationError, 'on or before'):
            self.validate()

    def test_overlap_search_excludes_current_document(self):
        with patch.object(frappe, 'get_all', return_value=[]) as query:
            self.validate()
        self.assertEqual(query.call_args.kwargs['filters']['name'], ['!=', 'MAP'])

    def test_new_mapping_requires_review_even_if_client_clears_it(self):
        self.doc.get_doc_before_save = lambda: None
        self.doc.needs_review = 0
        self.validate()
        self.assertEqual(self.doc.needs_review, 1)
        self.assertIsNone(self.doc.reviewed_by)

    def test_approval_stamps_session_reviewer_and_time(self):
        self.doc.needs_review = 0
        fixed = datetime(2026, 10, 4, 10, 0, 0)
        with patch.object(controller, 'now_datetime', return_value=fixed):
            self.validate()
        self.assertEqual(self.doc.reviewed_by, 'test@example.invalid')
        self.assertEqual(self.doc.last_reviewed_at, fixed)

    def test_unprivileged_roles_cannot_approve(self):
        self.doc.needs_review = 0
        for role in ('Accounts User', 'Ledgix Manager'):
            with patch.object(frappe, 'get_roles', return_value=[role]):
                with self.assertRaises(frappe.PermissionError):
                    self.validate()

    def test_material_changes_reset_approval(self):
        self.old.update(needs_review=0, reviewed_by='reviewer', last_reviewed_at='yesterday')
        for field, value in dict(company='Other', erpnext_item='OTHER', hs_code='87654321',
                tax_basis='Notified Retail Price', notified_retail_price=50,
                effective_from='2027-01-01', effective_to='2027-12-31').items():
            with self.subTest(field=field):
                self.doc.update(self.old)
                self.doc[field] = value
                if field == 'tax_basis':
                    self.doc.notified_retail_price = 50
                self.validate()
                self.assertEqual(self.doc.needs_review, 1)
                self.assertIsNone(self.doc.reviewed_by)
                self.assertIsNone(self.doc.last_reviewed_at)

    def test_non_material_edit_preserves_server_approval(self):
        self.old.update(needs_review=0, reviewed_by='reviewer', last_reviewed_at='yesterday')
        self.doc.update(self.old)
        self.doc.source_notes = 'Explanation'
        self.doc.reviewed_by = 'forged'
        self.validate()
        self.assertEqual(self.doc.reviewed_by, 'reviewer')

    def test_reviewed_mapping_identity_still_validated(self):
        self.doc.needs_review = 0
        for field, value in (('hs_code', ''), ('hs_code', '123456789'), ('tax_basis', 'Invalid')):
            self.doc.update(self.old)
            self.doc.needs_review = 0
            self.doc[field] = value
            with self.assertRaises(frappe.ValidationError):
                self.validate()

    def test_exactly_one_effective_mapping_selected(self):
        from fbr_v1.services.erpnext_fbr_snapshot import _matching_item_mapping
        rows = [Row(name='2026', effective_from='2026-01-01', effective_to='2026-12-31'),
                Row(name='2027', effective_from='2027-01-01', effective_to=None)]
        with patch.object(frappe, 'get_all', return_value=rows):
            self.assertEqual(_matching_item_mapping('Shop', 'SKU', '2026-12-31')['name'], '2026')
            self.assertEqual(_matching_item_mapping('Shop', 'SKU', '2027-01-01')['name'], '2027')
            rows[1].effective_from = '2026-12-31'
            with self.assertRaisesRegex(frappe.ValidationError, 'overlap'):
                _matching_item_mapping('Shop', 'SKU', '2026-12-31')


class TestPaymentReadiness(NoNetworkTest):
    def setUp(self):
        super().setUp()
        self.profile = Row(name='COUNTER', company='Shop', disabled=0,
            payments=[Row(mode_of_payment='Cash'), Row(mode_of_payment='Card')])
        self.modes = {'Cash': Row(enabled=1, custom_ledgix_fbr_v1_payment_mode='1 - Cash'),
                      'Card': Row(enabled=1, custom_ledgix_fbr_v1_payment_mode='2 - Card')}
        self.stack.enter_context(patch.object(frappe, 'get_all', return_value=['COUNTER']))
        self.stack.enter_context(patch.object(frappe, 'get_doc', return_value=self.profile))
        self.db.get_value.side_effect = lambda dt, name, *a, **k: self.modes.get(name)

    def inspect(self):
        return payment_readiness.get_payment_readiness('Shop', [])

    def test_all_pos_and_b2b_selectable_modes_must_be_mapped(self):
        self.modes['Card'].custom_ledgix_fbr_v1_payment_mode = ''
        result = self.inspect()
        self.assertFalse(result['ready'])
        self.assertEqual(result['missing_modes'], ['Card'])
        self.assertEqual(result['required_modes'], ['Card', 'Cash'])
        self.assertIn('Ledgix B2B tender', result['sources'][0]['paths'])

    def test_all_required_modes_mapped(self):
        self.assertTrue(self.inspect()['ready'])
        self.assertEqual(self.inspect()['mapped_count'], 2)
        self.db.set_value.assert_not_called()

    def test_disabled_or_invalid_payment_mapping_blocks(self):
        for update in ({'enabled': 0}, {'custom_ledgix_fbr_v1_payment_mode': '5 - Unknown'}):
            with self.subTest(update=update):
                self.modes['Card'] = Row(enabled=1, custom_ledgix_fbr_v1_payment_mode='2 - Card')
                self.modes['Card'].update(update)
                self.assertFalse(self.inspect()['ready'])

    def test_no_profiles_and_empty_payment_lists_block(self):
        self.profile.payments = []
        self.assertFalse(self.inspect()['ready'])
        with patch.object(frappe, 'get_all', return_value=[]):
            self.assertFalse(self.inspect()['ready'])

    def test_device_bound_foreign_disabled_profile_blocks(self):
        for update in ({'company': 'Other'}, {'disabled': 1}):
            with self.subTest(update=update):
                self.profile.update(company='Shop', disabled=0)
                self.profile.update(update)
                result = payment_readiness.get_payment_readiness('Shop', [Row(pos_profile='COUNTER')])
                self.assertFalse(result['ready'])


class TestConfigurationPermissions(NoNetworkTest):
    def test_four_configuration_doctypes_follow_role_policy(self):
        root = Path(__file__).resolve().parents[1] / 'fbr_v1/doctype'
        for suffix in ('item_mapping', 'tax_component_mapping', 'pos_device', 'integration_profile'):
            name = 'ledgix_fbr_' + suffix
            schema = json.loads((root / name / (name + '.json')).read_text())
            perms = {p['role']: p for p in schema['permissions']}
            for role in ('Accounts User', 'Ledgix Manager'):
                for key in ('create', 'write', 'delete'):
                    self.assertFalse(perms[role].get(key), (name, role, key))
            for role in ('System Manager', 'Ledgix Admin', 'Accounts Manager'):
                self.assertTrue(perms[role]['write'])
                self.assertTrue(perms[role]['create'])
            self.assertFalse(perms['Accounts Manager'].get('delete'))
            if suffix == 'item_mapping':
                fields = {f['fieldname']: f for f in schema['fields']}
                self.assertEqual(fields['reviewed_by']['options'], 'User')
                self.assertTrue(fields['reviewed_by']['read_only'])

    def test_ledgix_admin_is_operator_but_cannot_manage_cutover(self):
        from fbr_v1.api.fiscalization import require_operator
        from fbr_v1.api.center import _require_cutover_manager
        with patch.object(frappe, 'get_roles', return_value=['Ledgix Admin']):
            require_operator()
            with self.assertRaises(frappe.PermissionError):
                _require_cutover_manager()


class TestNativeTaxRuleContext(NoNetworkTest):
    def test_native_default_rule_reuses_resolver_with_complete_context(self):
        with patch('erpnext.accounts.doctype.tax_rule.tax_rule.get_tax_template', return_value='SALES') as resolver:
            self.assertEqual(native_tax_paths.default_sales_tax_rule('Shop', '2026-10-04'), 'SALES')
        date, args = resolver.call_args.args
        self.assertEqual(date, '2026-10-04')
        self.assertEqual(args['company'], 'Shop')
        for key in ('customer', 'customer_group', 'tax_category', 'billing_country', 'shipping_country'):
            self.assertEqual(args[key], '')
        self.assertNotIn('base_net_rate', args)
