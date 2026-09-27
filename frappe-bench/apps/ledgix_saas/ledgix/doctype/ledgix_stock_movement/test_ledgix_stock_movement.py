import unittest


LEGACY_BUSINESS_TEST_RETIRED = True
LEGACY_HISTORICAL_SOURCE_COMMIT = "808f384311b0545e1d3e39791f085db5678832bb"
LEGACY_HISTORICAL_SOURCE_PATH = "ledgix/doctype/ledgix_stock_movement/test_ledgix_stock_movement.py"
LEGACY_BUSINESS_TEST_RETIREMENT_REASON = 'Retired after Phase 12 ERPNext cutover: this historical suite exercised the frozen pre-cutover Ledgix business engine. ERPNext-native gates are authoritative.'


@unittest.skip(LEGACY_BUSINESS_TEST_RETIREMENT_REASON)
class TestLegacyBusinessSuiteRetired(unittest.TestCase):
    def test_historical_suite_retired_after_phase12_cutover(self):
        self.fail("retired historical suite must remain skipped")
