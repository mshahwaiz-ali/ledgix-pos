"""Current retirement contract; obsolete execution expectations remain in Git history."""
from ledgix_saas.setup.fbr_retirement_test_support import RetirementCase

class TestFBRV2TransportContract(RetirementCase):
    def test_api_fbr_v2_transport_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.api.fbr_v2_transport")

    def test_current_v1_gates_are_closed_by_default(self):
        from unittest.mock import patch
        import frappe
        from fbr_v1.protocol import transport
        with patch.object(frappe, "conf", frappe._dict(), create=True):
            self.assertFalse(transport.network_cutover_active())
            self.assertFalse(transport.production_cutover_active())
