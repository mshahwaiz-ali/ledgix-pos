"""Current retirement guard; obsolete V2 implementation contracts remain in Git history."""
from ledgix_saas.setup.fbr_retirement_test_support import RetirementCase


class TestRetiredV2Authority(RetirementCase):
    def test_all_retained_names_fail_closed_before_runtime_work(self):
        self.assert_module_retired('ledgix_saas.services.fbr_v2_payload_builder')
