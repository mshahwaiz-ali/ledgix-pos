"""Native fiscal ownership after DI retirement; no legacy execution authority."""
from pathlib import Path
import json
from ledgix_saas.setup.fbr_retirement_test_support import RetirementCase

APP_ROOT = Path(__file__).resolve().parents[1]
V1 = APP_ROOT.parent / 'fbr_v1/fbr_v1'

class TestERPNextPhase9Contract(RetirementCase):
    def test_old_native_fiscal_adapter_rejects_every_direct_entry(self):
        self.assert_module_retired('ledgix_saas.api.fbr_native')

    def test_active_invoice_hooks_belong_only_to_v1(self):
        hooks = (V1 / 'hooks.py').read_text()
        for source in ('Sales Invoice', 'POS Invoice'):
            self.assertIn('"'+source+'"', hooks)
        self.assertIn('fbr_v1.api.fiscalization.on_native_invoice_submit', hooks)
        self.assertNotIn('fbr_v2', hooks)
        self.assertNotIn('on_native_invoice_submit', (APP_ROOT / 'hooks.py').read_text())

    def test_v1_uses_immutable_native_snapshot_and_no_second_pos_source(self):
        source = (V1 / 'api/fiscalization.py').read_text()
        self.assertIn('inspect_invoice', source)
        self.assertIn('read_persisted_v1_snapshot', (V1 / 'services/fbr_v1_readiness.py').read_text())
        self.assertIn('is_consolidated', source)
        self.assertNotIn('"Ledgix Sale"', source)
        self.assertNotIn('"GL Entry"', source)

    def test_strict_historical_snapshot_reader_remains_read_only(self):
        source = (APP_ROOT / 'services/historical_fbr_evidence.py').read_text()
        for expected in ('hash verification failed', 'line count does not match', 'hash manifest does not match'):
            self.assertIn(expected, source)
        for forbidden in ('get_seller_identity', 'get_brand_settings', '.save(', 'db.set_value'):
            self.assertNotIn(forbidden, source)

    def test_current_correction_schema_is_retained(self):
        folder = V1 / 'fbr_v1/doctype/ledgix_fbr_correction_request'
        schema = json.loads((folder / 'ledgix_fbr_correction_request.json').read_text())
        fields = {f['fieldname']: f for f in schema['fields']}
        self.assertIn('reference_doctype', fields)
        self.assertIn('external_evidence', fields)
        source = (folder / 'ledgix_fbr_correction_request.py').read_text()
        self.assertIn('hours=72', source)
        self.assertIn('Commissioner', source)

    def test_retired_payload_builder_cannot_generate_di_returns(self):
        self.assert_module_retired('ledgix_saas.services.fbr_v2_payload_builder')
