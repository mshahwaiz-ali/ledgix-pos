import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
    configure_v2_test_environment,
    ensure_cash_payment_method,
    make_customer,
    make_item,
    make_sale,
    make_sales_return,
)
from ledgix_saas.ledgix.report.ledgix_customer_statement.ledgix_customer_statement import execute as customer_statement
from ledgix_saas.services.receivables import get_customer_receivables


class TestV2ReturnCreditBalance(FrappeTestCase):
    def setUp(self):
        super().setUp()
        configure_v2_test_environment()

    def test_paid_invoice_return_becomes_customer_credit_and_matches_statement(self):
        cash = ensure_cash_payment_method()
        item = make_item(selling_price=100, cost_price=40, opening_stock=5)
        customer = make_customer(customer_type="B2B", credit_limit=1000)
        sale = make_sale(
            customer.name,
            item.name,
            quantity=1,
            rate=100,
            sale_channel="B2B",
            payments=[{"payment_method": cash, "amount": 100}],
            submit=True,
        )
        make_sales_return(sale, quantity=0.5, submit=True)

        credit = get_customer_receivables(customer.name)
        self.assertAlmostEqual(credit["outstanding"], 0, places=2)
        self.assertAlmostEqual(credit["net_balance"], -50, places=2)
        self.assertAlmostEqual(credit["available_credit"], 1050, places=2)

        _columns, rows, _message, _chart, _summary = customer_statement({"customer": customer.name})
        self.assertTrue(rows)
        self.assertAlmostEqual(rows[-1]["balance"], -50, places=2)
