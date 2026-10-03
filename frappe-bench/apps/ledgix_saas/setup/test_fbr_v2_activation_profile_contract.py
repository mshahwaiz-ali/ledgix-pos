"""Current retirement contract; obsolete execution expectations remain in Git history."""
from ledgix_saas.setup.fbr_retirement_test_support import RetirementCase

class TestFBRV2ActivationProfileContract(RetirementCase):
    def test_services_fbr_v2_readiness_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.services.fbr_v2_readiness")

    def test_services_fbr_v2_status_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.services.fbr_v2_status")
