"""Current client setup uses the optional Federal V1 authority boundary."""
from unittest.mock import Mock, patch
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest
from ledgix_saas.services import fbr_v1_bridge


class TestFBRV2ClientSetupReadinessContract(NoNetworkTest):
    def test_installed_v1_readiness_is_forwarded_without_v2_fallback(self):
        state = {'sandbox_certification_complete': True, 'setup_ready': True,
                 'database_write': False, 'fbr_network_call': False, 'production_ready': False}
        target = Mock(return_value=state)
        with patch.object(frappe, 'get_installed_apps', return_value=['fbr_v1']), \
             patch.object(frappe, 'get_attr', return_value=target) as lookup:
            self.assertIs(fbr_v1_bridge.get_company_readiness('Shop'), state)
            lookup.assert_called_once_with('fbr_v1.api.client_readiness.get_client_readiness')
            target.assert_called_once_with('Shop')
        self.db.set_value.assert_not_called()

    def test_missing_v1_extension_fails_closed(self):
        with patch.object(frappe, 'get_installed_apps', return_value=['ledgix_saas']), \
             patch.object(frappe, 'get_attr') as lookup:
            self.assertFalse(fbr_v1_bridge.get_company_readiness('Shop')['setup_ready'])
            lookup.assert_not_called()
