"""Current V1 print and correction contracts; historical DI cannot execute."""
import json
from pathlib import Path
import unittest

APP_ROOT = Path(__file__).resolve().parents[1]
V1 = APP_ROOT.parent / 'fbr_v1/fbr_v1'

class TestFBRPhase8PrintCorrectionContract(unittest.TestCase):
    def text(self, path):
        return (V1 / path).read_text()

    def test_active_printing_uses_neutral_return_label(self):
        self.assertIn('"RETURN / ADJUSTMENT" if is_return', self.text('api/printing.py'))
        for name in ('ledgix_erpnext_tax_invoice','ledgix_erpnext_pos_receipt'):
            html = self.text(f'fbr_v1/print_format/{name}/{name}.json')
            self.assertNotIn('POS RETURN / CREDIT NOTE', html)
            self.assertIn('{{ p.title }}', html)

    def test_old_return_network_payload_remains_retired(self):
        source = (APP_ROOT / 'services/fbr_v2_payload_builder.py').read_text()
        self.assertIn('reject_legacy_v2_action', source)
        self.assertNotIn('requests', source)

    def test_offline_pending_print_requires_durable_authority(self):
        source = self.text('api/printing.py')
        for expected in ('Offline Deferred','Offline Invoice Issued','read_persisted_v1_snapshot','source_snapshot_hash'):
            self.assertIn(expected, source)
        self.assertIn('get_fbr_qr_data_uri(fbr_invoice_number)', source)

    def test_pos_print_includes_software_registration_number(self):
        self.assertIn('software_registration_number', self.text('fbr_v1/print_format/ledgix_erpnext_pos_receipt/ledgix_erpnext_pos_receipt.json'))

    def test_official_generation_time_has_separate_persisted_evidence(self):
        self.assertIn('custom_ledgix_fbr_generated_at', self.text('setup/erpnext_phase9_extensions.py'))
        self.assertIn('custom_ledgix_fbr_generated_at', self.text('fbr_v1/doctype/ledgix_fbr_correction_request/ledgix_fbr_correction_request.py'))

    def test_correction_completion_requires_external_evidence(self):
        folder = 'fbr_v1/doctype/ledgix_fbr_correction_request/'
        schema = json.loads(self.text(folder+'ledgix_fbr_correction_request.json'))
        self.assertEqual(next(f for f in schema['fields'] if f['fieldname']=='external_evidence')['fieldtype'], 'Attach')
        source = self.text(folder+'ledgix_fbr_correction_request.py')
        for expected in ('hours=72','Commissioner','_require_controlled_write','external_evidence'):
            self.assertIn(expected, source)
        self.assertNotIn('requests', source)

    def test_historical_print_never_fetches_current_artwork(self):
        source = (APP_ROOT / 'api/printing.py').read_text()
        self.assertIn('digital_invoicing_logo=""', source)
        self.assertNotIn('get_brand_settings', source)
        self.assertNotIn('_v2_profile_public', source)
