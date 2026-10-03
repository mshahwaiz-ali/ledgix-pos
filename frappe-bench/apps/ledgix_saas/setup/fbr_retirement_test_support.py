"""Behavior guards for retained V2 names; no site, credentials, or network."""
import ast
import importlib
from pathlib import Path
from unittest.mock import patch

import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest
from ledgix_saas.api.fbr_legacy_guard import LEGACY_V2_RETIRED_MESSAGE


class RetirementCase(NoNetworkTest):
    def assert_module_retired(self, module_name):
        module = importlib.import_module(module_name)
        tree = ast.parse(Path(module.__file__).read_text())
        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.assertTrue(functions)
        with patch('frappe.utils.password.get_decrypted_password', side_effect=AssertionError('Credential access forbidden')) as decrypt, \
             patch.object(frappe, 'get_doc', side_effect=AssertionError('Document work forbidden')) as docs, \
             patch.object(frappe, 'get_all', side_effect=AssertionError('Query forbidden')) as query, \
             patch.object(frappe, 'get_list', side_effect=AssertionError('Query forbidden')) as listed, \
             patch('ledgix_saas.api.fbr_transport.get_json', side_effect=AssertionError('GET forbidden')) as get, \
             patch('ledgix_saas.api.fbr_transport.post_json', side_effect=AssertionError('POST forbidden')) as post:
            for name in functions:
                with self.subTest(module=module_name, function=name):
                    with self.assertRaises(frappe.ValidationError) as error:
                        getattr(module, name)('arbitrary', injected='argument')
                    self.assertEqual(str(error.exception), LEGACY_V2_RETIRED_MESSAGE)
            for spy in (decrypt, docs, query, listed, get, post):
                spy.assert_not_called()
        for method in ('get_value', 'exists', 'set_value', 'sql', 'insert', 'commit', 'rollback'):
            getattr(self.db, method).assert_not_called()
        return len(functions)
