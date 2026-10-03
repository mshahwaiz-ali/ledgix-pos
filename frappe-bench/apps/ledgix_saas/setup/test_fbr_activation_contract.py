"""Current retirement contract; obsolete execution expectations remain in Git history."""
from ledgix_saas.setup.fbr_retirement_test_support import RetirementCase

class TestFBRActivationContract(RetirementCase):
    def test_api_fbr_activation_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.api.fbr_activation")
