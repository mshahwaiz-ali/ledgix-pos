from datetime import datetime, date
from fbr_v1.setup.v1_test_support import NoNetworkTest
from fbr_v1.api.fbr_offline import restoration_due_at
from fbr_v1.services.fiscal_closing import period_bounds

class TestV1Offline(NoNetworkTest):
    def test_deadline_is_restoration_plus_24h_across_month_end(self):
        self.assertEqual(restoration_due_at(datetime(2026,9,30,15,30)),datetime(2026,10,1,15,30))

    def test_calendar_closing_periods(self):
        self.assertEqual(period_bounds('Daily','2026-09-27'),(date(2026,9,27),date(2026,9,27)))
        self.assertEqual(period_bounds('Weekly','2026-09-27'),(date(2026,9,21),date(2026,9,27)))
        self.assertEqual(period_bounds('Monthly','2024-02-20'),(date(2024,2,1),date(2024,2,29)))
        with self.assertRaises(ValueError):period_bounds('Yearly','2026-09-27')
