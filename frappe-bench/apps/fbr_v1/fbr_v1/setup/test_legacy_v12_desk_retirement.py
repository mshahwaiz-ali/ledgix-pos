"""Current V1 owns narrow historical Desk retirement, without fiscal mutation."""
from unittest.mock import Mock, patch
import json
from pathlib import Path
import frappe
from fbr_v1.setup import install, legacy_v12_retirement as retirement, print_formats
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row


class TestDeskRetirement(NoNetworkTest):
    def test_exact_historical_targets_retire_once_preserving_current_and_fiscal_records(self):
        records={('Page','fbr-v12-center'):Row(module='FBR V12',title='FBR V1.2 Center'),
                 ('Workspace','FBR V1.2'):Row(module='FBR V12'),
                 ('Page','fbr-v1-center'):Row(module='FBR V1'),
                 ('Workspace','FBR V1'):Row(module='FBR V1'),
                 ('Ledgix FBR Submission Log','OLD'):Row(module='FBR V12')}
        self.db.exists.side_effect=lambda d,n:(d,n) in records
        def delete_linked_metadata(doctype, name, **kwargs):
            if doctype == 'Page':
                self.assertNotIn(('Workspace', 'FBR V1.2'), records,
                                 'Retire the linking workspace before its Page')
            self.assertNotIn('ignore_links', kwargs)
            return records.pop((doctype, name))
        with patch.object(frappe,'get_doc',side_effect=lambda d,n:records[(d,n)]),patch.object(frappe,'delete_doc',side_effect=delete_linked_metadata) as delete:
            self.assertEqual(retirement.retire_legacy_desk_metadata()['retired'],2)
            self.assertEqual(retirement.retire_legacy_desk_metadata()['retired'],0)
            self.assertEqual(delete.call_count,2)
            self.assertTrue(all(c.args[0] in ('Page','Workspace') for c in delete.call_args_list))
        self.assertIn(('Page','fbr-v1-center'),records)
        self.assertIn(('Workspace','FBR V1'),records)
        self.assertIn(('Ledgix FBR Submission Log','OLD'),records)
        self.db.set_value.assert_not_called();self.db.sql.assert_not_called()

    def test_unexpected_custom_owner_blocks_all_deletions(self):
        self.db.exists.return_value=True
        with patch.object(frappe,'get_doc',return_value=Row(module='Custom',title='Custom')),patch.object(frappe,'delete_doc') as delete:
            with self.assertRaises(frappe.ValidationError):retirement.retire_legacy_desk_metadata()
            delete.assert_not_called()

    def test_current_migrate_syncs_shared_prints_before_desk_retirement(self):
        events=[]
        with patch.object(install,'sync_all',side_effect=lambda:events.append('sync')),patch.object(retirement,'retire_legacy_desk_metadata',side_effect=lambda:events.append('retire')):
            install.after_migrate()
        self.assertEqual(events,['sync','retire'])

    def test_shared_prints_adopt_current_module_doctype_html_and_enabled_state(self):
        root=Path(print_formats.__file__).resolve().parents[1]/'fbr_v1/print_format'
        rows={name:Row(json.loads((root/docname/(docname+'.json')).read_text())) for name,docname,dt in print_formats.PRINT_FORMATS}
        self.db.get_value.side_effect=lambda d,n,*args,**kwargs:rows[n]
        with patch.object(frappe,'reload_doc') as reload,patch.object(frappe,'delete_doc') as delete:
            print_formats.sync_native_print_formats()
            self.assertEqual(reload.call_count,2);delete.assert_not_called()
        for name,row in rows.items():
            self.assertEqual(row.module,'FBR V1')
            self.assertFalse(row.disabled)
            self.assertIn('get_native_invoice_print_context',row.html)
            self.assertIn("p['items']",row.html)

    def test_tombstone_remains_without_cleanup_or_runtime_hooks(self):
        from fbr_v12 import hooks
        self.assertEqual(hooks.before_install,'fbr_v12.retired.reject')
        self.assertEqual(hooks.doc_events,{})
        self.assertEqual(hooks.scheduler_events,{})
        for name in ('after_migrate','after_install','jinja','erpnext_taxable_base_resolvers'):
            self.assertFalse(hasattr(hooks,name))
