from __future__ import annotations

"""ERPNext-native reporting and inventory intelligence for Ledgix.

Phase 10 keeps Ledgix report/analytics UX but removes active reads from legacy
Ledgix Sale/Purchase/Payment/Stock/Lot/Serial ledgers. ERPNext standard masters,
transaction documents, GL Entry, Bin and Stock Ledger Entry are authoritative.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate, today


TOLERANCE = 0.005


def company_name(company: str | None = None) -> str:
    company = (
        company
        or frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if not company or not frappe.db.exists("Company", company):
        frappe.throw(_("A valid ERPNext Company is required."))
    return company


def _date_conditions(alias: str, field: str, filters: dict, params: dict) -> list[str]:
    conditions: list[str] = []
    if filters.get("from_date"):
        params["from_date"] = str(getdate(filters.get("from_date")))
        conditions.append(f"{alias}.{field} >= %(from_date)s")
    if filters.get("to_date"):
        params["to_date"] = str(getdate(filters.get("to_date")))
        conditions.append(f"{alias}.{field} <= %(to_date)s")
    return conditions


def _docstatus_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    return {"Draft": 0, "Submitted": 1, "Cancelled": 2}.get(str(value))


def _status_label(docstatus: int) -> str:
    return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(int(docstatus or 0), "Unknown")


def _selling_price_subquery(item_alias: str = "i") -> str:
    return f"""
        COALESCE((
            SELECT ip.price_list_rate
            FROM `tabItem Price` ip
            WHERE ip.item_code = {item_alias}.name
              AND IFNULL(ip.selling, 0) = 1
            ORDER BY IFNULL(ip.valid_from, '1900-01-01') DESC, ip.modified DESC
            LIMIT 1
        ), 0)
    """


def current_stock_rows(filters: dict | None = None) -> list[dict]:
    filters = dict(filters or {})
    company = company_name(filters.get("company"))
    params = {"company": company}
    conditions = ["IFNULL(i.disabled, 0) = 0"]
    if filters.get("item"):
        params["item"] = filters["item"]
        conditions.append("i.name = %(item)s")
    if filters.get("category") or filters.get("item_group"):
        params["item_group"] = filters.get("category") or filters.get("item_group")
        conditions.append("i.item_group = %(item_group)s")
    if filters.get("only_active"):
        conditions.append("IFNULL(i.disabled, 0) = 0")

    rows = frappe.db.sql(
        f"""
        SELECT
            i.name AS item,
            i.item_name,
            i.item_group AS category,
            i.stock_uom AS unit,
            IFNULL(SUM(b.actual_qty), 0) AS current_stock,
            IFNULL(MAX(ir.warehouse_reorder_level), 0) AS minimum_stock,
            CASE
                WHEN ABS(IFNULL(SUM(b.actual_qty), 0)) > {TOLERANCE}
                THEN IFNULL(SUM(b.stock_value), 0) / SUM(b.actual_qty)
                ELSE IFNULL(i.valuation_rate, 0)
            END AS cost_price,
            {_selling_price_subquery('i')} AS selling_price,
            IFNULL(SUM(b.stock_value), 0) AS stock_value,
            i.has_batch_no,
            i.has_serial_no,
            i.is_stock_item
        FROM `tabItem` i
        LEFT JOIN `tabBin` b
          ON b.item_code = i.name
         AND EXISTS (
            SELECT 1 FROM `tabWarehouse` w
            WHERE w.name = b.warehouse AND w.company = %(company)s
         )
        LEFT JOIN `tabItem Reorder` ir
          ON ir.parent = i.name
         AND ir.parenttype = 'Item'
         AND (ir.warehouse IS NULL OR ir.warehouse = '' OR EXISTS (
            SELECT 1 FROM `tabWarehouse` rw
            WHERE rw.name = ir.warehouse AND rw.company = %(company)s
         ))
        WHERE {' AND '.join(conditions)}
        GROUP BY i.name, i.item_name, i.item_group, i.stock_uom,
                 i.valuation_rate, i.has_batch_no, i.has_serial_no, i.is_stock_item
        ORDER BY i.item_name ASC
        """,
        params,
        as_dict=True,
    )
    stock_status_filter = str(filters.get("stock_status") or "").strip()
    for row in rows:
        current = flt(row.current_stock)
        minimum = flt(row.minimum_stock)
        row.opening_stock = 0.0
        row.expected_profit_per_unit = flt(row.selling_price) - flt(row.cost_price)
        row.potential_profit = max(current, 0) * row.expected_profit_per_unit
        row.shortage_qty = max(minimum - current, 0)
        row.potential_sales_gap = row.shortage_qty * flt(row.selling_price)
        if current <= TOLERANCE:
            status = "Out of Stock"
        elif minimum > TOLERANCE and current < minimum - TOLERANCE:
            status = "Low Stock"
        elif minimum > TOLERANCE and abs(current - minimum) <= TOLERANCE:
            status = "At Minimum"
        else:
            status = "In Stock"
        row.stock_status = status
        row.risk_status = status if status != "In Stock" else "Healthy"
        row.view_action = row.item
        row.print_action = row.item
        row.authority = "ERPNext Item + Bin + Item Reorder + Item Price"
    if stock_status_filter:
        rows = [row for row in rows if row.stock_status == stock_status_filter or row.risk_status == stock_status_filter]
    return rows


def low_stock_rows(filters: dict | None = None) -> list[dict]:
    rows = current_stock_rows(filters)
    return [
        row
        for row in rows
        if flt(row.minimum_stock) > TOLERANCE and flt(row.current_stock) <= flt(row.minimum_stock) + TOLERANCE
    ]


def stock_movement_rows(filters: dict | None = None) -> list[dict]:
    filters = dict(filters or {})
    company = company_name(filters.get("company"))
    params = {"company": company}
    conditions = ["sle.company = %(company)s", "IFNULL(sle.is_cancelled, 0) = 0"]
    conditions += _date_conditions("sle", "posting_date", filters, params)
    if filters.get("item"):
        params["item"] = filters["item"]
        conditions.append("sle.item_code = %(item)s")
    if filters.get("warehouse"):
        params["warehouse"] = filters["warehouse"]
        conditions.append("sle.warehouse = %(warehouse)s")
    if filters.get("reference_doctype"):
        params["reference_doctype"] = filters["reference_doctype"]
        conditions.append("sle.voucher_type = %(reference_doctype)s")
    if filters.get("reference_name"):
        params["reference_name"] = filters["reference_name"]
        conditions.append("sle.voucher_no = %(reference_name)s")

    rows = frappe.db.sql(
        f"""
        SELECT
            sle.name AS movement,
            CONCAT(sle.posting_date, ' ', sle.posting_time) AS movement_date,
            sle.item_code AS item,
            sle.warehouse,
            CASE
                WHEN sle.actual_qty > 0 THEN 'IN'
                WHEN sle.actual_qty < 0 THEN 'OUT'
                ELSE 'ADJUSTMENT'
            END AS movement_type,
            ABS(sle.actual_qty) AS quantity,
            sle.actual_qty AS signed_quantity,
            sle.qty_after_transaction,
            sle.valuation_rate,
            sle.stock_value_difference,
            sle.voucher_type AS reference_doctype,
            sle.voucher_no AS reference_name,
            sle.voucher_detail_no AS reference_note,
            sle.owner,
            sle.batch_no,
            sle.serial_no
        FROM `tabStock Ledger Entry` sle
        WHERE {' AND '.join(conditions)}
        ORDER BY sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC
        LIMIT 5000
        """,
        params,
        as_dict=True,
    )
    for row in rows:
        row.status = "Submitted"
        row.view_action = row.reference_name
        row.print_action = row.reference_name
        row.authority = "ERPNext Stock Ledger Entry"
    movement_type = str(filters.get("movement_type") or "").strip()
    if movement_type:
        rows = [row for row in rows if row.movement_type == movement_type]
    return rows


def _sales_conditions(alias: str, filters: dict, params: dict, *, returns: bool) -> list[str]:
    conditions = [f"IFNULL({alias}.is_return, 0) = {1 if returns else 0}"]
    conditions += _date_conditions(alias, "posting_date", filters, params)
    docstatus = _docstatus_value(filters.get("docstatus"))
    if docstatus is not None:
        params["docstatus"] = docstatus
        conditions.append(f"{alias}.docstatus = %(docstatus)s")
    if filters.get("customer"):
        params["customer"] = filters["customer"]
        conditions.append(f"{alias}.customer = %(customer)s")
    return conditions


def _sales_invoice_rows(filters: dict, *, returns: bool) -> list[dict]:
    params: dict = {}
    conditions = _sales_conditions("si", filters, params, returns=returns)
    conditions.extend(
        [
            "NOT EXISTS (SELECT 1 FROM `tabPOS Invoice` pi0 WHERE pi0.consolidated_invoice = si.name AND pi0.docstatus = 1)",
            "NOT (IFNULL(si.is_pos, 0) = 1 AND IFNULL(si.custom_ledgix_sale_channel, '') = '')",
        ]
    )
    return frappe.db.sql(
        f"""
        SELECT
            'Sales Invoice' AS reference_doctype,
            si.name AS sale,
            si.name AS invoice_number,
            si.posting_date AS sale_date,
            si.posting_date AS return_date,
            si.customer,
            si.docstatus,
            si.is_return,
            si.return_against AS original_sale,
            COUNT(sii.name) AS items_count,
            ABS(IFNULL(SUM(sii.qty), 0)) AS total_qty,
            ABS(IFNULL(si.grand_total, 0)) AS total_amount,
            ABS(IFNULL(si.grand_total, 0)) AS return_amount,
            IFNULL(SUM(
                CASE WHEN IFNULL(item.is_stock_item, 0) = 1
                     THEN ABS(IFNULL(sii.base_net_amount, 0)) - ABS(IFNULL(sii.incoming_rate, 0) * IFNULL(sii.stock_qty, 0))
                     ELSE 0 END
            ), 0) AS total_profit,
            si.creation
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        LEFT JOIN `tabItem` item ON item.name = sii.item_code
        WHERE {' AND '.join(conditions)}
        GROUP BY si.name
        """,
        params,
        as_dict=True,
    )


def _pos_invoice_rows(filters: dict, *, returns: bool) -> list[dict]:
    params: dict = {}
    conditions = _sales_conditions("pi", filters, params, returns=returns)
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
                     THEN ABS(IFNULL(pii.base_net_amount, 0)) - ABS(IFNULL(pii.incoming_rate, 0) * IFNULL(pii.stock_qty, 0))
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


def sales_rows(filters: dict | None = None) -> list[dict]:
    filters = dict(filters or {})
    rows = _sales_invoice_rows(filters, returns=False) + _pos_invoice_rows(filters, returns=False)
    for row in rows:
        row.status = _status_label(row.docstatus)
        row.avg_sale_value = flt(row.total_amount) / flt(row.total_qty) if flt(row.total_qty) else 0
        row.view_action = row.sale
        row.print_action = row.sale
        row.authority = row.reference_doctype
    rows.sort(key=lambda row: (str(row.sale_date or ""), str(row.creation or "")), reverse=True)
    return rows


def sales_return_rows(filters: dict | None = None) -> list[dict]:
    filters = dict(filters or {})
    rows = _sales_invoice_rows(filters, returns=True) + _pos_invoice_rows(filters, returns=True)
    for row in rows:
        row.sales_return = row.sale
        row.status = _status_label(row.docstatus)
        row.total_profit_reversal = abs(flt(row.total_profit))
        row.avg_return_value = flt(row.return_amount) / flt(row.total_qty) if flt(row.total_qty) else 0
        row.view_action = row.sale
        row.print_action = row.sale
        row.authority = row.reference_doctype
    rows.sort(key=lambda row: (str(row.return_date or ""), str(row.creation or "")), reverse=True)
    return rows


def purchase_rows(filters: dict | None = None) -> list[dict]:
    filters = dict(filters or {})
    company = company_name(filters.get("company"))
    params = {"company": company}
    conditions = ["pi.company = %(company)s", "IFNULL(pi.is_return, 0) = 0"]
    conditions += _date_conditions("pi", "posting_date", filters, params)
    docstatus = _docstatus_value(filters.get("docstatus"))
    if docstatus is not None:
        params["docstatus"] = docstatus
        conditions.append("pi.docstatus = %(docstatus)s")
    if filters.get("supplier"):
        params["supplier"] = filters["supplier"]
        conditions.append("pi.supplier = %(supplier)s")
    rows = frappe.db.sql(
        f"""
        SELECT
            pi.name AS purchase,
            pi.bill_no AS invoice_number,
            pi.posting_date AS purchase_date,
            pi.supplier,
            pi.docstatus,
            COUNT(pii.name) AS items_count,
            IFNULL(SUM(pii.qty), 0) AS total_qty,
            ABS(IFNULL(pi.grand_total, 0)) AS total_cost,
            pi.creation
        FROM `tabPurchase Invoice` pi
        LEFT JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
        WHERE {' AND '.join(conditions)}
        GROUP BY pi.name
        ORDER BY pi.posting_date DESC, pi.creation DESC
        """,
        params,
        as_dict=True,
    )
    for row in rows:
        row.reference_doctype = "Purchase Invoice"
        row.status = _status_label(row.docstatus)
        row.avg_cost = flt(row.total_cost) / flt(row.total_qty) if flt(row.total_qty) else 0
        row.view_action = row.purchase
        row.print_action = row.purchase
        row.authority = "ERPNext Purchase Invoice"
    return rows


def customer_statement_rows(filters: dict | None = None) -> list[dict]:
    filters = dict(filters or {})
    customer = str(filters.get("customer") or "").strip()
    if not customer:
        return []
    company = company_name(filters.get("company"))
    params = {"company": company, "customer": customer}
    conditions = [
        "gle.company = %(company)s",
        "gle.party_type = 'Customer'",
        "gle.party = %(customer)s",
        "IFNULL(gle.is_cancelled, 0) = 0",
    ]
    conditions += _date_conditions("gle", "posting_date", filters, params)
    opening = 0.0
    if filters.get("from_date"):
        opening = flt(
            frappe.db.sql(
                """
                SELECT IFNULL(SUM(gle.debit - gle.credit), 0)
                FROM `tabGL Entry` gle
                WHERE gle.company=%(company)s
                  AND gle.party_type='Customer'
                  AND gle.party=%(customer)s
                  AND IFNULL(gle.is_cancelled,0)=0
                  AND gle.posting_date < %(from_date)s
                """,
                params,
            )[0][0]
        )
    entries = frappe.db.sql(
        f"""
        SELECT gle.posting_date, gle.voucher_type AS reference_doctype,
               gle.voucher_no AS reference_name, gle.remarks AS details,
               gle.debit, gle.credit, gle.creation
        FROM `tabGL Entry` gle
        WHERE {' AND '.join(conditions)}
        ORDER BY gle.posting_date ASC, gle.creation ASC, gle.name ASC
        """,
        params,
        as_dict=True,
    )
    rows: list[dict] = []
    balance = opening
    if abs(opening) > TOLERANCE:
        rows.append(
            frappe._dict(
                posting_date=filters.get("from_date"),
                reference_doctype="Opening Balance",
                reference_name="",
                invoice_number="",
                details="Balance before selected period",
                debit=opening if opening > 0 else 0,
                credit=abs(opening) if opening < 0 else 0,
                balance=opening,
                is_opening=1,
            )
        )
    for entry in entries:
        balance += flt(entry.debit) - flt(entry.credit)
        entry.balance = balance
        entry.invoice_number = entry.reference_name if entry.reference_doctype in {"Sales Invoice", "POS Invoice"} else ""
        rows.append(entry)
    return rows


def report_summary(kind: str, rows: list[dict]) -> list[dict]:
    if kind == "stock":
        return [
            {"value": len(rows), "label": "Items", "datatype": "Int"},
            {"value": sum(flt(r.current_stock) for r in rows), "label": "Stock Qty", "datatype": "Float"},
            {"value": sum(flt(r.stock_value) for r in rows), "label": "Stock Value", "datatype": "Currency"},
            {"value": sum(flt(r.potential_profit) for r in rows), "label": "Potential Profit", "datatype": "Currency"},
            {"value": sum(1 for r in rows if r.stock_status == "Low Stock"), "label": "Low Stock", "datatype": "Int"},
            {"value": sum(1 for r in rows if r.stock_status == "Out of Stock"), "label": "Out of Stock", "datatype": "Int"},
        ]
    if kind == "low_stock":
        return [
            {"value": len(rows), "label": "Risk Items", "datatype": "Int"},
            {"value": sum(1 for r in rows if r.risk_status == "Out of Stock"), "label": "Out of Stock", "datatype": "Int"},
            {"value": sum(flt(r.shortage_qty) for r in rows), "label": "Shortage Qty", "datatype": "Float"},
            {"value": sum(flt(r.potential_sales_gap) for r in rows), "label": "Sales Gap", "datatype": "Currency"},
        ]
    if kind == "sales":
        total = sum(flt(r.total_amount) for r in rows)
        return [
            {"value": len(rows), "label": "Sales", "datatype": "Int"},
            {"value": sum(int(r.items_count or 0) for r in rows), "label": "Line Items", "datatype": "Int"},
            {"value": sum(flt(r.total_qty) for r in rows), "label": "Total Qty", "datatype": "Float"},
            {"value": total, "label": "Total Amount", "datatype": "Currency"},
            {"value": sum(flt(r.total_profit) for r in rows), "label": "Gross Profit", "datatype": "Currency"},
            {"value": total / len(rows) if rows else 0, "label": "Avg Sale Value", "datatype": "Currency"},
        ]
    if kind == "returns":
        return [
            {"value": len(rows), "label": "Returns", "datatype": "Int"},
            {"value": sum(flt(r.total_qty) for r in rows), "label": "Return Qty", "datatype": "Float"},
            {"value": sum(flt(r.return_amount) for r in rows), "label": "Return Amount", "datatype": "Currency"},
            {"value": sum(flt(r.total_profit_reversal) for r in rows), "label": "Margin Reversal", "datatype": "Currency"},
        ]
    if kind == "purchases":
        cost = sum(flt(r.total_cost) for r in rows)
        qty = sum(flt(r.total_qty) for r in rows)
        return [
            {"value": len(rows), "label": "Purchases", "datatype": "Int"},
            {"value": qty, "label": "Total Qty", "datatype": "Float"},
            {"value": cost, "label": "Total Cost", "datatype": "Currency"},
            {"value": cost / qty if qty else 0, "label": "Avg Cost", "datatype": "Currency"},
        ]
    if kind == "movements":
        return [
            {"value": len(rows), "label": "Movements", "datatype": "Int"},
            {"value": sum(flt(r.quantity) for r in rows if r.movement_type == "IN"), "label": "Total IN", "datatype": "Float"},
            {"value": sum(flt(r.quantity) for r in rows if r.movement_type == "OUT"), "label": "Total OUT", "datatype": "Float"},
        ]
    if kind == "statement":
        tx = [r for r in rows if not r.get("is_opening")]
        return [
            {"value": len(tx), "label": "Transactions", "datatype": "Int"},
            {"value": sum(flt(r.debit) for r in tx), "label": "Debit", "datatype": "Currency"},
            {"value": sum(flt(r.credit) for r in tx), "label": "Credit", "datatype": "Currency"},
            {"value": rows[-1].balance if rows else 0, "label": "Closing Balance", "datatype": "Currency"},
        ]
    return []


def _tracking_filter_clause(tracking_type: str) -> str:
    if tracking_type == "Serial Based":
        return "AND IFNULL(i.has_serial_no, 0) = 1"
    if tracking_type == "Lot Based":
        return "AND IFNULL(i.has_batch_no, 0) = 1"
    if tracking_type == "Normal Stock":
        return "AND IFNULL(i.has_batch_no, 0) = 0 AND IFNULL(i.has_serial_no, 0) = 0"
    return ""


def _intelligence_item_codes(filters: dict, company: str) -> list[str]:
    params = {"company": company}
    conditions = ["IFNULL(i.disabled,0)=0", "IFNULL(i.is_stock_item,0)=1"]
    if filters.get("item"):
        params["item"] = filters["item"]
        conditions.append("i.name=%(item)s")
    tracking = str(filters.get("tracking_type") or "All")
    tracking_clause = _tracking_filter_clause(tracking)
    return frappe.db.sql_list(
        f"SELECT i.name FROM `tabItem` i WHERE {' AND '.join(conditions)} {tracking_clause} ORDER BY i.name",
        params,
    )


def _return_vouchers(item_codes: list[str], filters: dict) -> set[tuple[str, str]]:
    if not item_codes:
        return set()
    result: set[tuple[str, str]] = set()
    values = {"items": tuple(item_codes)}
    date_si = []
    if filters.get("from_date"):
        values["from_date"] = str(getdate(filters["from_date"]))
        date_si.append("AND si.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        values["to_date"] = str(getdate(filters["to_date"]))
        date_si.append("AND si.posting_date <= %(to_date)s")
    for row in frappe.db.sql(
        f"""
        SELECT DISTINCT 'Sales Invoice' doctype, si.name
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent=si.name
        WHERE si.docstatus=1 AND si.is_return=1 AND sii.item_code IN %(items)s {' '.join(date_si)}
        UNION ALL
        SELECT DISTINCT 'POS Invoice' doctype, pi.name
        FROM `tabPOS Invoice` pi
        INNER JOIN `tabPOS Invoice Item` pii ON pii.parent=pi.name
        WHERE pi.docstatus=1 AND pi.is_return=1 AND pii.item_code IN %(items)s {' '.join(s.replace('si.', 'pi.') for s in date_si)}
        """,
        values,
        as_dict=True,
    ):
        result.add((row.doctype, row.name))
    return result


def _sales_financials(item_codes: list[str], filters: dict) -> dict:
    if not item_codes:
        return {"gross_revenue": 0.0, "return_amount": 0.0, "gross_profit": 0.0, "return_profit": 0.0}
    params = {"items": tuple(item_codes)}
    date_clause = []
    if filters.get("from_date"):
        params["from_date"] = str(getdate(filters["from_date"]))
        date_clause.append("AND parent.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        params["to_date"] = str(getdate(filters["to_date"]))
        date_clause.append("AND parent.posting_date <= %(to_date)s")
    result = {"gross_revenue": 0.0, "return_amount": 0.0, "gross_profit": 0.0, "return_profit": 0.0}
    for parent_table, child_table in (("Sales Invoice", "Sales Invoice Item"), ("POS Invoice", "POS Invoice Item")):
        extra = ""
        if parent_table == "Sales Invoice":
            extra = "AND NOT EXISTS (SELECT 1 FROM `tabPOS Invoice` px WHERE px.consolidated_invoice=parent.name AND px.docstatus=1) AND NOT (IFNULL(parent.is_pos,0)=1 AND IFNULL(parent.custom_ledgix_sale_channel,'')='')"
        row = frappe.db.sql(
            f"""
            SELECT
                IFNULL(SUM(CASE WHEN parent.is_return=0 THEN ABS(child.base_net_amount) ELSE 0 END),0) gross_revenue,
                IFNULL(SUM(CASE WHEN parent.is_return=1 THEN ABS(child.base_net_amount) ELSE 0 END),0) return_amount,
                IFNULL(SUM(CASE WHEN parent.is_return=0 AND item.is_stock_item=1 THEN ABS(child.base_net_amount)-ABS(child.incoming_rate*child.stock_qty) ELSE 0 END),0) gross_profit,
                IFNULL(SUM(CASE WHEN parent.is_return=1 AND item.is_stock_item=1 THEN ABS(child.base_net_amount)-ABS(child.incoming_rate*child.stock_qty) ELSE 0 END),0) return_profit
            FROM `tab{parent_table}` parent
            INNER JOIN `tab{child_table}` child ON child.parent=parent.name
            LEFT JOIN `tabItem` item ON item.name=child.item_code
            WHERE parent.docstatus=1 AND child.item_code IN %(items)s {' '.join(date_clause)} {extra}
            """,
            params,
            as_dict=True,
        )[0]
        for key in result:
            result[key] += flt(row.get(key))
    return result


def inventory_intelligence(filters: dict | None = None) -> dict:
    filters = dict(filters or {})
    company = company_name(filters.get("company"))
    item_codes = _intelligence_item_codes(filters, company)
    if not item_codes:
        return _empty_intelligence(filters, company)

    params = {"company": company, "items": tuple(item_codes)}
    conditions = ["sle.company=%(company)s", "sle.item_code IN %(items)s", "IFNULL(sle.is_cancelled,0)=0"]
    conditions += _date_conditions("sle", "posting_date", filters, params)
    sle_rows = frappe.db.sql(
        f"""
        SELECT sle.posting_date, sle.posting_time, sle.item_code AS item,
               i.item_name, sle.warehouse, sle.actual_qty, sle.qty_after_transaction,
               sle.valuation_rate, sle.stock_value_difference,
               sle.voucher_type AS reference_doctype, sle.voucher_no AS reference_name,
               sle.batch_no, sle.serial_no, sle.creation
        FROM `tabStock Ledger Entry` sle
        LEFT JOIN `tabItem` i ON i.name=sle.item_code
        WHERE {' AND '.join(conditions)}
        ORDER BY sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC
        LIMIT 500
        """,
        params,
        as_dict=True,
    )
    search = str(filters.get("search") or "").strip().lower()
    if search:
        fields = ("item", "item_name", "warehouse", "reference_doctype", "reference_name", "batch_no", "serial_no")
        sle_rows = [r for r in sle_rows if search in " ".join(str(r.get(f) or "") for f in fields).lower()]

    return_vouchers = _return_vouchers(item_codes, filters)
    purchased_qty = 0.0
    sold_qty = 0.0
    returned_qty = 0.0
    timeline = []
    batch_stats: dict[str, dict] = {}
    for row in sle_rows:
        qty = flt(row.actual_qty)
        voucher_key = (row.reference_doctype, row.reference_name)
        is_return = voucher_key in return_vouchers
        if is_return and qty > 0:
            event = "Return"
            returned_qty += qty
        elif row.reference_doctype in {"Purchase Receipt", "Purchase Invoice"} and qty > 0:
            event = "Purchase"
            purchased_qty += qty
        elif row.reference_doctype in {"Sales Invoice", "POS Invoice"} and qty < 0:
            event = "Sale"
            sold_qty += abs(qty)
        elif qty > 0:
            event = "Stock In"
        elif qty < 0:
            event = "Stock Out"
        else:
            event = "Adjustment"
        rate = flt(row.valuation_rate)
        timeline.append(
            {
                "date": f"{row.posting_date} {row.posting_time}",
                "cycle_status": event,
                "event_type": event,
                "reference": row.reference_name,
                "reference_doctype": row.reference_doctype,
                "reference_name": row.reference_name,
                "item": row.item,
                "item_name": row.item_name,
                "warehouse": row.warehouse,
                "qty": qty,
                "purchased_qty": qty if event == "Purchase" else 0,
                "sale_qty": abs(qty) if event == "Sale" else 0,
                "return_qty": qty if event == "Return" else 0,
                "running_qty": flt(row.qty_after_transaction),
                "cost_rate": rate,
                "sale_rate": 0,
                "profit": 0,
                "loss": 0,
                "batch_no": row.batch_no or "",
                "lot_number": row.batch_no or "",
                "serial_no": row.serial_no or "",
                "authority": "ERPNext Stock Ledger Entry",
            }
        )
        if row.batch_no:
            stat = batch_stats.setdefault(
                row.batch_no,
                {
                    "lot_number": row.batch_no,
                    "item": row.item,
                    "item_name": row.item_name,
                    "supplier": "",
                    "purchase_date": row.posting_date if event == "Purchase" else None,
                    "purchased_qty": 0.0,
                    "remaining_qty": 0.0,
                    "sold_qty": 0.0,
                    "returned_qty": 0.0,
                    "profit": 0.0,
                    "lot_status": "Open",
                },
            )
            stat["remaining_qty"] += qty
            if event == "Purchase":
                stat["purchased_qty"] += qty
                stat["purchase_date"] = stat["purchase_date"] or row.posting_date
            elif event == "Sale":
                stat["sold_qty"] += abs(qty)
            elif event == "Return":
                stat["returned_qty"] += qty

    stock_rows = current_stock_rows({"company": company})
    stock_map = {r.item: r for r in stock_rows if r.item in item_codes}
    current_qty = sum(flt(r.current_stock) for r in stock_map.values())
    financials = _sales_financials(item_codes, filters)
    gross_revenue = flt(financials["gross_revenue"], 2)
    return_amount = flt(financials["return_amount"], 2)
    net_revenue = flt(gross_revenue - return_amount, 2)
    gross_profit = flt(financials["gross_profit"], 2)
    return_profit = flt(financials["return_profit"], 2)
    net_profit = flt(gross_profit - return_profit, 2)
    net_sold = max(sold_qty - returned_qty, 0)
    lots = list(batch_stats.values())
    for lot in lots:
        lot["remaining_qty"] = flt(lot["remaining_qty"], 3)
        lot["sell_through_percent"] = flt((lot["sold_qty"] - lot["returned_qty"]) / lot["purchased_qty"] * 100, 1) if lot["purchased_qty"] else 0
        lot["return_rate_percent"] = flt(lot["returned_qty"] / lot["sold_qty"] * 100, 1) if lot["sold_qty"] else 0
        lot["lot_status"] = "Closed" if lot["remaining_qty"] <= TOLERANCE else "Open"

    low_count = sum(1 for r in stock_map.values() if r.stock_status in {"Low Stock", "Out of Stock"})
    risk_level = "High" if low_count and low_count >= max(len(stock_map) // 2, 1) else ("Medium" if low_count else "Low")
    summary = {
        "current_qty": flt(current_qty, 3),
        "purchased_qty": flt(purchased_qty, 3),
        "remaining_qty": flt(current_qty, 3),
        "sold_qty": flt(sold_qty, 3),
        "returned_qty": flt(returned_qty, 3),
        "net_sold_qty": flt(net_sold, 3),
        "gross_revenue": gross_revenue,
        "return_amount": return_amount,
        "net_revenue": net_revenue,
        "gross_profit": gross_profit,
        "return_profit_impact": return_profit,
        "net_profit": net_profit,
        "total_cost_sold": flt(net_revenue - net_profit, 2),
        "margin_percent": flt(net_profit / net_revenue * 100, 1) if net_revenue else 0,
        "sell_through_percent": flt(net_sold / purchased_qty * 100, 1) if purchased_qty else 0,
        "return_rate_percent": flt(returned_qty / sold_qty * 100, 1) if sold_qty else 0,
        "risk_level": risk_level,
        "lot_count": len(lots),
    }
    signals = []
    if low_count:
        signals.append(f"{low_count} item(s) at or below reorder level")
    if summary["return_rate_percent"] >= 20:
        signals.append(f"Return rate {summary['return_rate_percent']}%")
    if not signals:
        signals.append("No material inventory risk signal in the selected scope")
    risks = [
        {
            "severity": "High" if r.stock_status == "Out of Stock" else "Medium",
            "title": r.stock_status,
            "message": f"{r.item_name}: {flt(r.current_stock, 2)} {r.unit} available; reorder level {flt(r.minimum_stock, 2)}.",
            "reference": r.item,
        }
        for r in stock_map.values()
        if r.stock_status in {"Low Stock", "Out of Stock"}
    ]
    return {
        "filters": filters,
        "summary": summary,
        "story": {
            "title": "ERPNext inventory position",
            "text": f"{len(item_codes)} native ERPNext item(s), {len(timeline)} stock-ledger event(s), and {len(lots)} batch identity record(s) are in scope.",
            "tone": "warning" if risks else "good",
            "signals": signals,
        },
        "lots": lots,
        "timeline": timeline,
        "cycle_rows": timeline,
        "risks": risks,
        "meta": {
            "generated_at": str(today()),
            "row_count": len(item_codes),
            "cycle_row_count": len(timeline),
            "timeline_loaded_count": len(timeline),
            "timeline_result_cap": 500,
            "timeline_cap_reached": len(timeline) >= 500,
            "lot_loaded_count": len(lots),
            "lot_result_cap": 500,
            "lot_cap_reached": len(lots) >= 500,
            "authority": "ERPNext Item / Bin / Stock Ledger Entry / Sales Invoice / POS Invoice / Purchase Invoice / Batch / Serial No",
        },
    }


def _empty_intelligence(filters: dict, company: str) -> dict:
    return {
        "filters": filters,
        "summary": {
            "current_qty": 0,
            "purchased_qty": 0,
            "remaining_qty": 0,
            "sold_qty": 0,
            "returned_qty": 0,
            "net_sold_qty": 0,
            "gross_revenue": 0,
            "return_amount": 0,
            "net_revenue": 0,
            "gross_profit": 0,
            "return_profit_impact": 0,
            "net_profit": 0,
            "total_cost_sold": 0,
            "margin_percent": 0,
            "sell_through_percent": 0,
            "return_rate_percent": 0,
            "risk_level": "Low",
            "lot_count": 0,
        },
        "story": {
            "title": "No native inventory activity found",
            "text": "No ERPNext Item/Stock Ledger activity matched the selected filters.",
            "tone": "neutral",
            "signals": [],
        },
        "lots": [],
        "timeline": [],
        "cycle_rows": [],
        "risks": [],
        "meta": {
            "generated_at": str(today()),
            "row_count": 0,
            "cycle_row_count": 0,
            "authority": "ERPNext",
            "company": company,
        },
    }
