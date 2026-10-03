"""Current retirement contract; obsolete execution expectations remain in Git history."""
from ledgix_saas.setup.fbr_retirement_test_support import RetirementCase

class TestFBRNativeV2PreviewCutoverContract(RetirementCase):
    def test_api_fbr_native_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.api.fbr_native")

    def test_services_fbr_v2_payload_builder_rejects_before_credentials_queries_or_transport(self):
        self.assert_module_retired("ledgix_saas.services.fbr_v2_payload_builder")
