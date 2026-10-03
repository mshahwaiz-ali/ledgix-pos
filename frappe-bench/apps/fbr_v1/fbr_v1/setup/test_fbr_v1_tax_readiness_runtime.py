from contextlib import ExitStack
from unittest.mock import Mock, patch

import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row
from fbr_v1.services import erpnext_tax_readiness as readiness
from fbr_v1.fbr_v1.doctype.ledgix_fbr_item_mapping.ledgix_fbr_item_mapping import LedgixFBRItemMapping


class TestTaxReadiness(NoNetworkTest):
    def setUp(self):
        super().setUp()
        self.db.exists.return_value = True
        self.db.count.return_value = 1
        self.db.get_value.return_value = Row(company='Shop', is_group=0, disabled=0)
        self.items = [Row(name='SKU')]
        self.mappings = [Row(name='MAP', erpnext_item='SKU', needs_review=0,
            hs_code='12345678', tax_basis='Transaction Value', notified_retail_price=0)]
        self.components = [Row(name='TAX-MAP', account_head='GST', component=readiness.SALES_TAX)]
        self.sales = [Row(name='SALES')]
        self.item_templates = []
        self.docs = {'SALES': Row(name='SALES', is_default=1,
            taxes=[Row(account_head='GST', rate=12.5, charge_type='On Net Total')])}
        self.scope = []
        self.stack.enter_context(patch.object(frappe, 'get_all', side_effect=self.query))
        self.stack.enter_context(patch.object(frappe, 'get_doc', side_effect=lambda dt, name: self.docs[name]))
        self.meta = Mock(get_field=Mock(return_value=Row(options='On Net Total\nOn Notified Retail Price')))
        self.stack.enter_context(patch.object(frappe, 'get_meta', return_value=self.meta))
        self.hooks = {readiness.CHARGE_TYPE: [readiness.RESOLVER]}
        self.stack.enter_context(patch.object(frappe, 'get_hooks', side_effect=lambda *a: self.hooks))

    def query(self, doctype, **kwargs):
        return {'Item': self.items, 'Ledgix FBR Item Mapping': self.mappings,
            'Ledgix FBR Tax Component Mapping': self.components,
            'Sales Taxes and Charges Template': self.sales, 'Item Tax Template': self.item_templates,
            'Item Default': self.scope, 'Sales Invoice': [], 'POS Invoice': []}[doctype]

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
                self.db.get_value.return_value = Row(company='Shop', is_group=0, disabled=0)
                self.db.get_value.return_value.update(attributes)
                self.assert_blocked('enabled leaf Account')

    def test_missing_account(self):
        self.db.get_value.return_value = None
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

    def test_multi_company_shared_items_warn_without_false_blockers(self):
        self.db.count.return_value = 2
        self.items.append(Row(name='SHARED'))
        self.scope = [Row(parent='SKU')]
        result = self.inspect()
        self.assertTrue(result['ready'], result['blockers'])
        self.assertEqual(result['item_coverage']['required_items'], ['SKU'])
        self.assertIn('SHARED', ' '.join(result['warnings']))

    def test_zero_rate_visibility_does_not_invent_exemption(self):
        self.item_templates = [Row(name='ZERO')]
        self.docs['ZERO'] = Row(name='ZERO', taxes=[Row(tax_type='GST', tax_rate=0)])
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

    def test_reviewed_mapping_controller_validates_v1_identity(self):
        for values in ({'hs_code': ''}, {'hs_code': '123456789'}, {'tax_basis': 'Invalid'}):
            doc = Row(dict(doctype='Ledgix FBR Item Mapping', company='Shop',
                erpnext_item='SKU', active=1, needs_review=0, hs_code='12345678',
                tax_basis='Transaction Value', **{}))
            doc.update(values)
            self.db.exists.side_effect = lambda dt, filters: dt != 'Ledgix FBR Item Mapping'
            with self.assertRaises(frappe.ValidationError):
                LedgixFBRItemMapping.validate(doc)


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
            stack.enter_context(patch.object(api, 'configuration_blockers', return_value=['Transport remains disarmed.']))
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
