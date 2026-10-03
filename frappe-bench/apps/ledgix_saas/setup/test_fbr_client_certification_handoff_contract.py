"""Current retirement contract; obsolete execution expectations remain in Git history."""
from ledgix_saas.setup.fbr_retirement_test_support import RetirementCase

class TestFBRClientCertificationHandoffContract(RetirementCase):
    def test_api_fbr_offline_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.api.fbr_offline")

    def test_api_fbr_reference_v2_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.api.fbr_reference_v2")

    def test_api_fbr_v2_center_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.api.fbr_v2_center")
