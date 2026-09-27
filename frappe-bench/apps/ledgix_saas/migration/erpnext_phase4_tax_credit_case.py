from __future__ import annotations

from frappe.utils import flt

from ledgix_saas.migration import erpnext_phase4_tax_parity_gate as base


def _price_only_credit_case(accounts: dict) -> dict:
    """Prove a pure non-stock financial credit through ERPNext's native return rules.

    ERPNext requires at least one negative-quantity row on a linked Sales Invoice
    return. A zero-quantity linked return is therefore not a valid credit-note
    shape. The Phase 4 parity case uses a non-stock item with qty=-1 and a reduced
    adjustment rate of 100. Because update_stock remains disabled, this is a pure
    accounting/tax credit with no Stock Ledger Entry.
    """

    source = base._make_invoice(
        base._marker("price_credit_source"),
        [{"item_code": base.ITEMS["price_credit"], "qty": 1, "uom": "Nos", "rate": 1000}],
    )
    credit = base._make_return(
        source,
        base._marker("price_only_credit"),
        qty=-1,
        rate=100,
    )
    ev = base._invoice_evidence(credit, accounts)
    checks = {
        "submitted": credit.docstatus == 1,
        "linked_to_source": credit.return_against == source.name,
        "negative_adjustment_quantity": abs(flt(credit.items[0].qty) + 1) < 0.001,
        "credit_net_minus_100": abs(ev["net_total"] + 100) < 0.01,
        "credit_tax_minus_18": abs(ev["total_taxes_and_charges"] + 18) < 0.01,
        "credit_grand_total_minus_118": abs(ev["grand_total"] + 118) < 0.01,
        "tax_gl_reversed_18": abs(ev["tax_account_net_credit"]["sales_tax"] + 18) < 0.01,
        "no_stock_effect": ev["stock_ledger_entries"] == 0,
        "gl_balanced": ev["gl_balanced"],
    }
    return base._case("price_only_credit_note", ev, checks)


def run() -> dict:
    original = base._price_only_credit_case
    base._price_only_credit_case = _price_only_credit_case
    try:
        return base.run()
    finally:
        base._price_only_credit_case = original
