from __future__ import annotations

"""Pinned ERPNext v15 reporting compatibility for Ledgix Phase 10.

ERPNext v15 exposes ``incoming_rate`` on Sales Invoice Item, but not on POS
Invoice Item. Retail cost/profit therefore comes from the authoritative Stock
Ledger Entry ``stock_value_difference`` for the exact POS invoice row.

Importing this module patches only the two internal cost helpers in
``erpnext_reporting``. Public report/BI functions continue to live in the
canonical service and keep the same API.
"""

import frappe

from ledgix_saas.services import erpnext_reporting as base


def _pos_line_cost_sql(parent_alias: str = "pi", child_alias: str = "pii") -> str:
    return f"""
        ABS(IFNULL((
            SELECT SUM(sle.stock_value_difference)
            FROM `tabStock Ledger Entry` sle
            WHERE sle.voucher_type = 'POS Invoice'
              AND sle.voucher_no = {parent_alias}.name
              AND sle.voucher_detail_no = {child_alias}.name
              AND IFNULL(sle.is_cancelled, 0) = 0
        ), 0))
    """


def _pos_invoice_rows(filters: dict, *, returns: bool) -> list[dict]:
    params: dict = {}
    conditions = base._sales_conditions("pi", filters, params, returns=returns)
    cost = _pos_line_cost_sql("pi", "pii")
    return frappe.db.sql(
        f"""
        SELECT
            'POS Invoice' AS reference_doctype,
            pi.name AS sale,
            pi.name AS invoice_number,
            pi.posting_date AS sale_date,
            pi.posting_date AS return_date,
            pi.customer,
            pi.docstatus,
            pi.is_return,
            pi.return_against AS original_sale,
            COUNT(pii.name) AS items_count,
            ABS(IFNULL(SUM(pii.qty), 0)) AS total_qty,
            ABS(IFNULL(pi.grand_total, 0)) AS total_amount,
            ABS(IFNULL(pi.grand_total, 0)) AS return_amount,
            IFNULL(SUM(
                CASE WHEN IFNULL(item.is_stock_item, 0) = 1
                     THEN ABS(IFNULL(pii.base_net_amount, 0)) - {cost}
                     ELSE 0 END
            ), 0) AS total_profit,
            pi.creation
        FROM `tabPOS Invoice` pi
        LEFT JOIN `tabPOS Invoice Item` pii ON pii.parent = pi.name
        LEFT JOIN `tabItem` item ON item.name = pii.item_code
        WHERE {' AND '.join(conditions)}
        GROUP BY pi.name
        """,
        params,
        as_dict=True,
    )


def _sales_financials(item_codes: list[str], filters: dict) -> dict:
    if not item_codes:
        return {"gross_revenue": 0.0, "return_amount": 0.0, "gross_profit": 0.0, "return_profit": 0.0}

    params = {"items": tuple(item_codes)}
    date_clause = []
    if filters.get("from_date"):
        params["from_date"] = str(base.getdate(filters["from_date"]))
        date_clause.append("AND parent.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        params["to_date"] = str(base.getdate(filters["to_date"]))
        date_clause.append("AND parent.posting_date <= %(to_date)s")

    result = {"gross_revenue": 0.0, "return_amount": 0.0, "gross_profit": 0.0, "return_profit": 0.0}
    for parent_table, child_table in (("Sales Invoice", "Sales Invoice Item"), ("POS Invoice", "POS Invoice Item")):
        extra = ""
        if parent_table == "Sales Invoice":
            extra = (
                "AND NOT EXISTS (SELECT 1 FROM `tabPOS Invoice` px "
                "WHERE px.consolidated_invoice=parent.name AND px.docstatus=1) "
                "AND NOT (IFNULL(parent.is_pos,0)=1 "
                "AND IFNULL(parent.custom_ledgix_sale_channel,'')='')"
            )
            cost = "ABS(IFNULL(child.incoming_rate, 0) * IFNULL(child.stock_qty, 0))"
        else:
            cost = _pos_line_cost_sql("parent", "child")

        row = frappe.db.sql(
            f"""
            SELECT
                IFNULL(SUM(CASE WHEN parent.is_return=0 THEN ABS(child.base_net_amount) ELSE 0 END),0) gross_revenue,
                IFNULL(SUM(CASE WHEN parent.is_return=1 THEN ABS(child.base_net_amount) ELSE 0 END),0) return_amount,
                IFNULL(SUM(CASE WHEN parent.is_return=0 AND item.is_stock_item=1 THEN ABS(child.base_net_amount)-{cost} ELSE 0 END),0) gross_profit,
                IFNULL(SUM(CASE WHEN parent.is_return=1 AND item.is_stock_item=1 THEN ABS(child.base_net_amount)-{cost} ELSE 0 END),0) return_profit
            FROM `tab{parent_table}` parent
            INNER JOIN `tab{child_table}` child ON child.parent=parent.name
            LEFT JOIN `tabItem` item ON item.name=child.item_code
            WHERE parent.docstatus=1
              AND child.item_code IN %(items)s
              {' '.join(date_clause)}
              {extra}
            """,
            params,
            as_dict=True,
        )[0]
        for key in result:
            result[key] += base.flt(row.get(key))
    return result


# Install once per Python process. Public methods keep using the canonical module,
# but their global helper lookup now follows the pinned ERPNext-v15 schema.
base._pos_invoice_rows = _pos_invoice_rows
base._sales_financials = _sales_financials

sales_rows = base.sales_rows
sales_return_rows = base.sales_return_rows
report_summary = base.report_summary
inventory_intelligence = base.inventory_intelligence
