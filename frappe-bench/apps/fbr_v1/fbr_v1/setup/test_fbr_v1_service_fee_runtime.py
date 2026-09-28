from unittest.mock import patch

from fbr_v1.setup.v1_test_support import NoNetworkTest, Row
from fbr_v1.services import pos_service_fee as fee


class FakeInvoice(Row):
    def append(self, fieldname, values):
        row = Row(values)
        self.setdefault(fieldname, []).append(row)
        return row

    def remove(self, row):
        self.setdefault("taxes", []).remove(row)


class TestV1POSServiceFee(NoNetworkTest):
    def profile(self):
        return Row(
            company="Test Company",
            protocol_version="Federal POS/IMS V1",
            enabled=1,
            mode="Production",
            pos_service_fee_account="FBR POS Service Fee Payable - TEST",
        )

    def test_sale_gets_exactly_one_native_actual_fee(self):
        doc = FakeInvoice(
            doctype="POS Invoice",
            company="Test Company",
            docstatus=0,
            is_return=0,
            taxes=[],
        )
        with patch.object(fee, "get_profile", return_value=self.profile()), \
             patch.object(fee, "is_consolidated", return_value=False), \
             patch.object(fee, "service_fee_configuration_blockers", return_value=[]):
            fee.ensure_pos_service_fee(doc)
            fee.ensure_pos_service_fee(doc)
        self.assertEqual(len(doc.taxes), 1)
        row = doc.taxes[0]
        self.assertEqual(row.charge_type, "Actual")
        self.assertEqual(row.tax_amount, 1.0)
        self.assertEqual(row.included_in_print_rate, 0)

    def test_credit_removes_copied_fee_and_consolidation_adds_nothing(self):
        copied_fee = Row(
            charge_type="Actual",
            account_head="FBR POS Service Fee Payable - TEST",
            description="FBR POS Service Fee",
            rate=0,
            tax_amount=1.0,
            included_in_print_rate=0,
        )

        credit = FakeInvoice(
            doctype="Sales Invoice",
            company="Test Company",
            docstatus=0,
            is_return=1,
            taxes=[copied_fee],
        )
        with patch.object(fee, "get_profile", return_value=self.profile()), \
             patch.object(fee, "is_consolidated", return_value=False):
            fee.ensure_pos_service_fee(credit)

        self.assertEqual(credit.taxes, [])

        consolidated = FakeInvoice(
            doctype="Sales Invoice",
            company="Test Company",
            docstatus=0,
            is_return=0,
            taxes=[],
        )
        with patch.object(fee, "get_profile", return_value=self.profile()), \
             patch.object(fee, "is_consolidated", return_value=True):
            fee.ensure_pos_service_fee(consolidated)

        self.assertEqual(consolidated.taxes, [])
