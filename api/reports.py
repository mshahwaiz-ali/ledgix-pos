# ============================================================
# LEDGIX REPORTS APIs
# ============================================================
# Reports page APIs and shared report helpers.
# Mode-aware filters keep Strict Inventory and Billing Only data separated.

import frappe
from frappe.utils import flt, cint, today

from ledgix_saas.api.settings import (
    get_stock_control_mode,
    get_pos_theme_settings,
)
from ledgix_saas.api.security import require_ledgix_manager_or_above

# ============================================================
# LEDGIX REPORTS PAGE APIs
# Paste this near the bottom of: ledgix_saas/api/api.py
# ============================================================



LEDGIX_REPORT_PAGE_SIZE = 20
PURCHASE_DOCTYPE = "Ledgix Purchase"


def _lx_status_label(docstatus):
    return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(cint(docstatus), "Unknown")


def _lx_status_value(status):
    if status in (None, ""):
        return None
    return {"draft": 0, "submitted": 1, "cancelled": 2}.get(str(status).strip().lower())


def _lx_page_args(page=1, page_size=20):
    page = max(cint(page or 1), 1)
    page_size = cint(page_size or LEDGIX_REPORT_PAGE_SIZE)
    if page_size <= 0:
        page_size = LEDGIX_REPORT_PAGE_SIZE
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size
    return page, page_size, offset


def _lx_date_filters(alias, date_field, from_date=None, to_date=None, use_date_func=False):
    conditions = []
    values = {}
    field = f"DATE({alias}.{date_field})" if use_date_func else f"{alias}.{date_field}"
    if from_date:
        conditions.append(f"{field} >= %(from_date)s")
        values["from_date"] = from_date
    if to_date:
        conditions.append(f"{field} <= %(to_date)s")
        values["to_date"] = to_date
    return conditions, values


def _lx_amount_filters(expr, min_amount=None, max_amount=None):
    conditions = []
    values = {}
    if min_amount not in (None, ""):
        conditions.append(f"{expr} >= %(min_amount)s")
        values["min_amount"] = flt(min_amount)
    if max_amount not in (None, ""):
        conditions.append(f"{expr} <= %(max_amount)s")
        values["max_amount"] = flt(max_amount)
    return conditions, values


def _lx_where(conditions):
    return " AND ".join(conditions) if conditions else "1=1"






@frappe.whitelist()
def get_return_report_data(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    """
    Return report API for the Ledgix Reports page.

    Cleanup notes:
    - Kept the same public method path for JS compatibility.
    - Avoids loading every matching return row into Python for summary/count.
    - Uses SQL COUNT/SUM aggregates so tab switching stays lighter as data grows.
    """
    require_ledgix_manager_or_above()

    page, page_size, offset = _lx_page_args(page, page_size)
    conditions, values = _lx_date_filters("sr", "creation", from_date, to_date, use_date_func=True)

    ds = _lx_status_value(status)
    if ds is not None:
        conditions.append("sr.docstatus = %(docstatus)s")
        values["docstatus"] = ds

    if party:
        conditions.append("sr.customer LIKE %(party)s")
        values["party"] = f"%{party}%"

    if search:
        conditions.append("(sr.name LIKE %(search)s OR sr.original_sale LIKE %(search)s OR sr.customer LIKE %(search)s)")
        values["search"] = f"%{search}%"

    amount_conditions, amount_values = _lx_amount_filters("IFNULL(sr.total_amount, 0)", min_amount, max_amount)
    conditions.extend(amount_conditions)
    values.update(amount_values)

    where = _lx_where(conditions)
    values.update({"limit": page_size, "offset": offset})

    rows = frappe.db.sql(f"""
        SELECT
            sr.name AS name,
            sr.name AS `return`,
            sr.original_sale AS sale,
            sr.customer AS customer,
            CASE WHEN sr.docstatus = 0 THEN 'Draft' WHEN sr.docstatus = 1 THEN 'Submitted' WHEN sr.docstatus = 2 THEN 'Cancelled' ELSE 'Unknown' END AS status,
            IFNULL(sr.total_amount, 0) AS amount,
            COUNT(ri.name) AS items_count,
            IFNULL(SUM(ri.quantity), 0) AS total_qty,
            DATE(sr.creation) AS date
        FROM `tabLedgix Sales Return` sr
        LEFT JOIN `tabLedgix Sales Return Item` ri ON ri.parent = sr.name
        WHERE {where}
        GROUP BY sr.name
        ORDER BY sr.creation DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, values, as_dict=True)

    aggregate = frappe.db.sql(f"""
        SELECT
            COUNT(*) AS return_count,
            IFNULL(SUM(sr.total_amount), 0) AS return_amount
        FROM `tabLedgix Sales Return` sr
        WHERE {where}
    """, values, as_dict=True)[0]

    qty_row = frappe.db.sql(f"""
        SELECT IFNULL(SUM(ri.quantity), 0) AS items_returned
        FROM `tabLedgix Sales Return` sr
        INNER JOIN `tabLedgix Sales Return Item` ri ON ri.parent = sr.name
        WHERE {where}
    """, values, as_dict=True)[0]

    sales_count = frappe.db.sql("""
        SELECT COUNT(*) AS total
        FROM `tabLedgix Sale`
        WHERE docstatus = 1
    """, as_dict=True)[0].total or 0

    return_count = cint(aggregate.return_count)
    return_amount = flt(aggregate.return_amount)
    items_returned = flt(qty_row.items_returned)

    summary = {
        "return_amount": return_amount,
        "return_count": return_count,
        "items_returned": items_returned,
        "return_rate": (return_count / sales_count * 100) if sales_count else 0,
    }

    chart_data = frappe.db.sql(f"""
        SELECT DATE(sr.creation) AS label,
               IFNULL(SUM(sr.total_amount), 0) AS value,
               COUNT(sr.name) AS count
        FROM `tabLedgix Sales Return` sr
        WHERE {where}
        GROUP BY DATE(sr.creation)
        ORDER BY DATE(sr.creation) ASC
    """, values, as_dict=True)

    return {
        "rows": rows,
        "summary": summary,
        "total_count": return_count,
        "page": page,
        "page_size": page_size,
        "chart_data": chart_data,
        "stock_control_mode": get_stock_control_mode()
    }


@frappe.whitelist()
def get_customer_statement(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    require_ledgix_manager_or_above()

    page, page_size, offset = _lx_page_args(page, page_size)
    customer = party or search

    if not customer:
        return {
            "rows": [],
            "summary": {"receivable": 0, "customers": 0, "invoices": 0, "balance": 0},
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "chart_data": [],
            "requires_party": 1
        }

    values = {
        "customer": customer,
        "from_date": from_date or "1900-01-01",
        "to_date": to_date or today()
    }

    rows = frappe.db.sql("""
        SELECT * FROM (
            SELECT
                s.sale_date AS date,
                s.name AS reference,
                CONCAT('Sale invoice ', COALESCE(s.invoice_number, '')) AS description,
                IFNULL(s.total_amount, 0) AS debit,
                IFNULL(s.paid_amount, 0) AS credit,
                s.creation AS sort_time
            FROM `tabLedgix Sale` s
            WHERE
                s.docstatus = 1
                AND s.customer = %(customer)s
                AND s.sale_date BETWEEN %(from_date)s AND %(to_date)s

            UNION ALL

            SELECT
                DATE(sr.creation) AS date,
                sr.name AS reference,
                CONCAT('Sales return against ', COALESCE(sr.original_sale, '-')) AS description,
                0 AS debit,
                IFNULL(sr.total_amount, 0) AS credit,
                sr.creation AS sort_time
            FROM `tabLedgix Sales Return` sr
            LEFT JOIN `tabLedgix Sale` s ON s.name = sr.original_sale
            WHERE
                sr.docstatus = 1
                AND (sr.customer = %(customer)s OR s.customer = %(customer)s)
                AND DATE(sr.creation) BETWEEN %(from_date)s AND %(to_date)s
        ) x
        ORDER BY x.date ASC, x.sort_time ASC
    """, values, as_dict=True)

    balance = 0

    for row in rows:
        balance += flt(row.debit) - flt(row.credit)
        row["balance"] = balance

    paged = rows[offset:offset + page_size]

    summary = {
        "receivable": max(balance, 0),
        "customers": 1,
        "invoices": len([row for row in rows if flt(row.debit) > 0]),
        "balance": balance
    }

    chart_data = [
        {
            "label": str(row.date),
            "value": flt(row.balance),
            "count": 1
        }
        for row in rows
    ]

    return {
        "rows": paged,
        "summary": summary,
        "total_count": len(rows),
        "page": page,
        "page_size": page_size,
        "chart_data": chart_data
    }


@frappe.whitelist()
def get_supplier_statement(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    require_ledgix_manager_or_above()

    page, page_size, offset = _lx_page_args(page, page_size)
    supplier = party or search

    if not supplier:
        return {
            "rows": [],
            "summary": {"payable": 0, "suppliers": 0, "purchases": 0, "balance": 0},
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "chart_data": [],
            "requires_party": 1
        }

    purchase_table = f"tab{PURCHASE_DOCTYPE}"

    values = {
        "supplier": supplier,
        "from_date": from_date or "1900-01-01",
        "to_date": to_date or today()
    }

    rows = frappe.db.sql(f"""
        SELECT
            p.purchase_date AS date,
            p.name AS reference,
            CONCAT('Purchase invoice ', COALESCE(p.invoice_number, '')) AS description,
            0 AS debit,
            IFNULL(SUM(pi.amount), 0) AS credit,
            p.creation AS sort_time
        FROM `{purchase_table}` p
        LEFT JOIN `tabLedgix Purchase Item` pi ON pi.parent = p.name
        WHERE
            p.docstatus = 1
            AND p.supplier = %(supplier)s
            AND p.purchase_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY p.name
        ORDER BY p.purchase_date ASC, p.creation ASC
    """, values, as_dict=True)

    balance = 0

    for row in rows:
        balance += flt(row.credit) - flt(row.debit)
        row["balance"] = balance

    paged = rows[offset:offset + page_size]

    summary = {
        "payable": max(balance, 0),
        "suppliers": 1,
        "purchases": len(rows),
        "balance": balance
    }

    chart_data = [
        {
            "label": str(row.date),
            "value": flt(row.balance),
            "count": 1
        }
        for row in rows
    ]

    return {
        "rows": paged,
        "summary": summary,
        "total_count": len(rows),
        "page": page,
        "page_size": page_size,
        "chart_data": chart_data
    }



# ============================================================
# REPORT PARTY SEARCH
# ============================================================

@frappe.whitelist()
def search_report_parties(party_type=None, search=None):
	require_ledgix_manager_or_above()

	search = (search or "").strip()

	if party_type == "supplier":
		doctype = "Ledgix Supplier"
		field = "supplier_name"
	else:
		doctype = "Ledgix Customer"
		field = "customer_name"

	filters = {}

	if search:
		filters[field] = ["like", f"%{search}%"]

	rows = frappe.get_all(
		doctype,
		filters=filters,
		fields=[
			"name",
			f"{field} as label"
		],
		order_by=f"{field} asc",
		limit=20
	)

	return rows





# ============================================================
# LEDGIX REPORTS APIs
# ============================================================

@frappe.whitelist()
def get_reports_boot_data():
    """Boot payload for Ledgix Reports page."""
    require_ledgix_manager_or_above()

    return {
        "stock_control_mode": get_stock_control_mode(),
        "theme_settings": get_pos_theme_settings()
    }


def _lx_reports_is_billing_mode():
    return get_stock_control_mode() == "Billing Only"


def _lx_empty_report_response(page=1, page_size=20, summary=None):
    page, page_size, _offset = _lx_page_args(page, page_size)
    return {
        "rows": [],
        "summary": summary or {},
        "total_count": 0,
        "page": page,
        "page_size": page_size,
        "chart_data": [],
        "stock_control_mode": get_stock_control_mode()
    }


def _lx_sale_mode_condition(alias="s"):
    if get_stock_control_mode() == "Strict Inventory":
        return f"""
            EXISTS (
                SELECT 1
                FROM `tabLedgix Stock Movement` sm_mode
                WHERE
                    sm_mode.reference_doctype = 'Ledgix Sale'
                    AND sm_mode.reference_name = {alias}.name
                    AND sm_mode.docstatus = 1
            )
        """

    return f"""
        NOT EXISTS (
            SELECT 1
            FROM `tabLedgix Stock Movement` sm_mode
            WHERE
                sm_mode.reference_doctype = 'Ledgix Sale'
                AND sm_mode.reference_name = {alias}.name
                AND sm_mode.docstatus = 1
        )
    """


@frappe.whitelist()
def get_sales_report_data(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    require_ledgix_manager_or_above()

    page, page_size, offset = _lx_page_args(page, page_size)
    conditions, values = _lx_date_filters("s", "sale_date", from_date, to_date)
    conditions.append(_lx_sale_mode_condition("s"))

    ds = _lx_status_value(status)
    if ds is not None:
        conditions.append("s.docstatus = %(docstatus)s")
        values["docstatus"] = ds

    if party:
        conditions.append("s.customer LIKE %(party)s")
        values["party"] = f"%{party}%"

    if search:
        conditions.append("(s.name LIKE %(search)s OR s.invoice_number LIKE %(search)s OR s.customer LIKE %(search)s)")
        values["search"] = f"%{search}%"

    if type:
        conditions.append("""
            EXISTS (
                SELECT 1
                FROM `tabLedgix Sale Payment` sp
                WHERE sp.parent = s.name
                  AND sp.parenttype = 'Ledgix Sale'
                  AND sp.parentfield = 'payments'
                  AND sp.payment_method LIKE %(payment_type)s
            )
        """)
        values["payment_type"] = f"%{type}%"

    amount_conditions, amount_values = _lx_amount_filters("IFNULL(s.total_amount, 0)", min_amount, max_amount)
    conditions.extend(amount_conditions)
    values.update(amount_values)

    where = _lx_where(conditions)
    values.update({"limit": page_size, "offset": offset})

    rows = frappe.db.sql(f"""
        SELECT
            s.name AS name,
            COALESCE(NULLIF(s.invoice_number, ''), s.name) AS invoice,
            s.customer AS customer,
            CASE WHEN s.docstatus = 0 THEN 'Draft' WHEN s.docstatus = 1 THEN 'Submitted' WHEN s.docstatus = 2 THEN 'Cancelled' ELSE 'Unknown' END AS status,
            IFNULL(s.total_amount, 0) AS amount,
            IFNULL(s.total_profit, 0) AS profit,
            COALESCE(NULLIF(s.payment_status, ''), '-') AS payment_mode,
            s.sale_date AS date,
            COUNT(si.name) AS items_count,
            IFNULL(SUM(si.quantity), 0) AS total_qty
        FROM `tabLedgix Sale` s
        LEFT JOIN `tabLedgix Sale Item` si ON si.parent = s.name
        WHERE {where}
        GROUP BY s.name
        ORDER BY s.sale_date DESC, s.creation DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, values, as_dict=True)

    total_count = frappe.db.sql(f"SELECT COUNT(*) AS total FROM `tabLedgix Sale` s WHERE {where}", values, as_dict=True)[0].total or 0

    summary = frappe.db.sql(f"""
        SELECT
            IFNULL(SUM(CASE WHEN s.docstatus = 1 THEN s.total_amount ELSE 0 END), 0) AS total_sales,
            IFNULL(SUM(CASE WHEN s.docstatus = 1 THEN s.total_profit ELSE 0 END), 0) AS total_profit,
            SUM(CASE WHEN s.docstatus = 1 THEN 1 ELSE 0 END) AS invoice_count,
            CASE WHEN SUM(CASE WHEN s.docstatus = 1 THEN 1 ELSE 0 END) > 0
                THEN IFNULL(SUM(CASE WHEN s.docstatus = 1 THEN s.total_amount ELSE 0 END), 0) / SUM(CASE WHEN s.docstatus = 1 THEN 1 ELSE 0 END)
                ELSE 0
            END AS avg_order
        FROM `tabLedgix Sale` s
        WHERE {where}
    """, values, as_dict=True)[0]

    chart_data = frappe.db.sql(f"""
        SELECT s.sale_date AS label,
               IFNULL(SUM(CASE WHEN s.docstatus = 1 THEN s.total_amount ELSE 0 END), 0) AS value,
               SUM(CASE WHEN s.docstatus = 1 THEN 1 ELSE 0 END) AS count
        FROM `tabLedgix Sale` s
        WHERE {where}
        GROUP BY s.sale_date
        ORDER BY s.sale_date ASC
    """, values, as_dict=True)

    return {"rows": rows, "summary": summary, "total_count": total_count, "page": page, "page_size": page_size, "chart_data": chart_data, "stock_control_mode": get_stock_control_mode()}


@frappe.whitelist()
def get_purchase_report_data(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    require_ledgix_manager_or_above()

    if _lx_reports_is_billing_mode():
        return _lx_empty_report_response(page, page_size, {
            "total_purchases": 0,
            "suppliers": 0,
            "items_bought": 0,
            "avg_purchase": 0,
        })

    page, page_size, offset = _lx_page_args(page, page_size)
    purchase_table = f"tab{PURCHASE_DOCTYPE}"
    conditions, values = _lx_date_filters("p", "purchase_date", from_date, to_date)

    ds = _lx_status_value(status)
    if ds is not None:
        conditions.append("p.docstatus = %(docstatus)s")
        values["docstatus"] = ds
    if party:
        conditions.append("p.supplier LIKE %(party)s")
        values["party"] = f"%{party}%"
    if search:
        conditions.append("(p.name LIKE %(search)s OR p.invoice_number LIKE %(search)s OR p.supplier LIKE %(search)s)")
        values["search"] = f"%{search}%"

    where = _lx_where(conditions)
    values.update({"limit": page_size, "offset": offset})

    base = f"""
        FROM `{purchase_table}` p
        LEFT JOIN `tabLedgix Purchase Item` pi ON pi.parent = p.name
        WHERE {where}
        GROUP BY p.name
    """

    having, having_values = _lx_amount_filters("IFNULL(SUM(pi.amount), 0)", min_amount, max_amount)
    having_sql = " HAVING " + " AND ".join(having) if having else ""
    values.update(having_values)

    rows = frappe.db.sql(f"""
        SELECT
            p.name AS name,
            p.name AS purchase,
            p.supplier AS supplier,
            CASE WHEN p.docstatus = 0 THEN 'Draft' WHEN p.docstatus = 1 THEN 'Submitted' WHEN p.docstatus = 2 THEN 'Cancelled' ELSE 'Unknown' END AS status,
            IFNULL(SUM(pi.amount), 0) AS amount,
            COUNT(pi.name) AS items_count,
            IFNULL(SUM(pi.quantity), 0) AS total_qty,
            p.purchase_date AS date
        {base}
        {having_sql}
        ORDER BY p.purchase_date DESC, p.creation DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, values, as_dict=True)

    count_rows = frappe.db.sql(f"SELECT p.name, p.supplier, IFNULL(SUM(pi.amount), 0) AS amount, IFNULL(SUM(pi.quantity), 0) AS total_qty {base} {having_sql}", values, as_dict=True)
    total_count = len(count_rows)
    total_purchases = sum(flt(r.amount) for r in count_rows)
    suppliers = len(set([r.get("supplier") for r in count_rows if r.get("supplier")]))
    items_bought = sum(flt(r.get("total_qty")) for r in count_rows)

    chart_data = frappe.db.sql(f"""
        SELECT p.purchase_date AS label, IFNULL(SUM(pi.amount), 0) AS value, COUNT(DISTINCT p.name) AS count
        FROM `{purchase_table}` p
        LEFT JOIN `tabLedgix Purchase Item` pi ON pi.parent = p.name
        WHERE {where}
        GROUP BY p.purchase_date
        ORDER BY p.purchase_date ASC
    """, values, as_dict=True)

    return {"rows": rows, "summary": {"total_purchases": total_purchases, "suppliers": suppliers, "items_bought": items_bought, "avg_purchase": total_purchases / total_count if total_count else 0}, "total_count": total_count, "page": page, "page_size": page_size, "chart_data": chart_data, "stock_control_mode": get_stock_control_mode()}


@frappe.whitelist()
def get_stock_report_data(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    require_ledgix_manager_or_above()

    if _lx_reports_is_billing_mode():
        return _lx_empty_report_response(page, page_size, {
            "in_qty": 0,
            "out_qty": 0,
            "adjustments": 0,
            "stock_value": 0,
        })

    page, page_size, offset = _lx_page_args(page, page_size)
    conditions, values = _lx_date_filters("sm", "movement_date", from_date, to_date, use_date_func=True)

    ds = _lx_status_value(status)
    if ds is not None:
        conditions.append("sm.docstatus = %(docstatus)s")
        values["docstatus"] = ds
    if type:
        conditions.append("sm.movement_type = %(movement_type)s")
        values["movement_type"] = str(type).upper()
    if search:
        conditions.append("(sm.name LIKE %(search)s OR sm.item LIKE %(search)s OR sm.reference_name LIKE %(search)s OR sm.reference_doctype LIKE %(search)s)")
        values["search"] = f"%{search}%"

    where = _lx_where(conditions)
    values.update({"limit": page_size, "offset": offset})

    rows = frappe.db.sql(f"""
        SELECT
            sm.name AS name,
            sm.name AS movement,
            sm.item AS item,
            sm.movement_type AS type,
            CASE WHEN sm.docstatus = 0 THEN 'Draft' WHEN sm.docstatus = 1 THEN 'Submitted' WHEN sm.docstatus = 2 THEN 'Cancelled' ELSE 'Unknown' END AS status,
            IFNULL(sm.quantity, 0) AS quantity,
            sm.reference_doctype,
            sm.reference_name AS reference,
            sm.reference_note,
            DATE(sm.movement_date) AS date
        FROM `tabLedgix Stock Movement` sm
        WHERE {where}
        ORDER BY sm.movement_date DESC, sm.creation DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, values, as_dict=True)

    total_count = frappe.db.sql(f"SELECT COUNT(*) AS total FROM `tabLedgix Stock Movement` sm WHERE {where}", values, as_dict=True)[0].total or 0
    summary_row = frappe.db.sql(f"""
        SELECT
            IFNULL(SUM(CASE WHEN sm.movement_type = 'IN' THEN sm.quantity ELSE 0 END), 0) AS in_qty,
            IFNULL(SUM(CASE WHEN sm.movement_type = 'OUT' THEN sm.quantity ELSE 0 END), 0) AS out_qty,
            IFNULL(SUM(CASE WHEN sm.movement_type = 'ADJUSTMENT' THEN sm.quantity ELSE 0 END), 0) AS adjustments
        FROM `tabLedgix Stock Movement` sm
        WHERE {where}
    """, values, as_dict=True)[0]
    stock_value = frappe.db.sql("""
        SELECT IFNULL(SUM(IFNULL(current_stock, 0) * IFNULL(cost_price, 0)), 0) AS value
        FROM `tabLedgix Item`
    """, as_dict=True)[0].value or 0

    chart_data = frappe.db.sql(f"""
        SELECT DATE(sm.movement_date) AS label,
               IFNULL(SUM(ABS(sm.quantity)), 0) AS value,
               COUNT(sm.name) AS count
        FROM `tabLedgix Stock Movement` sm
        WHERE {where}
        GROUP BY DATE(sm.movement_date)
        ORDER BY DATE(sm.movement_date) ASC
    """, values, as_dict=True)

    return {"rows": rows, "summary": {"in_qty": summary_row.in_qty, "out_qty": summary_row.out_qty, "adjustments": summary_row.adjustments, "stock_value": stock_value}, "total_count": total_count, "page": page, "page_size": page_size, "chart_data": chart_data, "stock_control_mode": get_stock_control_mode()}


@frappe.whitelist()
def get_profit_report_data(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    require_ledgix_manager_or_above()

    page, page_size, offset = _lx_page_args(page, page_size)
    conditions, values = _lx_date_filters("s", "sale_date", from_date, to_date)
    conditions.append("s.docstatus = 1")
    conditions.append(_lx_sale_mode_condition("s"))

    if party:
        conditions.append("s.customer LIKE %(party)s")
        values["party"] = f"%{party}%"
    if search:
        conditions.append("(s.name LIKE %(search)s OR s.invoice_number LIKE %(search)s OR si.item LIKE %(search)s OR s.customer LIKE %(search)s)")
        values["search"] = f"%{search}%"

    where = _lx_where(conditions)
    values.update({"limit": page_size, "offset": offset})

    having, having_values = _lx_amount_filters("IFNULL(SUM(si.item_total_profit), 0)", min_amount, max_amount)
    having_sql = " HAVING " + " AND ".join(having) if having else ""
    values.update(having_values)

    rows = frappe.db.sql(f"""
        SELECT
            CONCAT(s.name, '-', si.item) AS name,
            s.name AS reference,
            s.customer AS customer,
            si.item AS item,
            IFNULL(SUM(si.amount), 0) AS revenue,
            IFNULL(SUM(si.cost_price * si.quantity), 0) AS cost,
            IFNULL(SUM(si.item_total_profit), 0) AS profit,
            CASE WHEN IFNULL(SUM(si.amount), 0) > 0 THEN IFNULL(SUM(si.item_total_profit), 0) / IFNULL(SUM(si.amount), 0) * 100 ELSE 0 END AS margin,
            s.sale_date AS date
        FROM `tabLedgix Sale` s
        LEFT JOIN `tabLedgix Sale Item` si ON si.parent = s.name
        WHERE {where}
        GROUP BY s.name, si.item
        {having_sql}
        ORDER BY s.sale_date DESC, s.creation DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, values, as_dict=True)

    all_rows = frappe.db.sql(f"""
        SELECT
            s.name AS reference,
            si.item AS item,
            IFNULL(SUM(si.amount), 0) AS revenue,
            IFNULL(SUM(si.cost_price * si.quantity), 0) AS cost,
            IFNULL(SUM(si.item_total_profit), 0) AS profit
        FROM `tabLedgix Sale` s
        LEFT JOIN `tabLedgix Sale Item` si ON si.parent = s.name
        WHERE {where}
        GROUP BY s.name, si.item
        {having_sql}
    """, values, as_dict=True)

    total_revenue = sum(flt(r.revenue) for r in all_rows)
    gross_profit = sum(flt(r.profit) for r in all_rows)
    best = max(all_rows, key=lambda r: flt(r.profit), default={})

    chart_data = frappe.db.sql(f"""
        SELECT s.sale_date AS label, IFNULL(SUM(s.total_profit), 0) AS value, COUNT(s.name) AS count
        FROM `tabLedgix Sale` s
        WHERE {where}
        GROUP BY s.sale_date
        ORDER BY s.sale_date ASC
    """, values, as_dict=True)

    return {"rows": rows, "summary": {"gross_profit": gross_profit, "profit_margin": (gross_profit / total_revenue * 100) if total_revenue else 0, "best_item": best.get("item") or "-", "avg_profit": gross_profit / len(all_rows) if all_rows else 0}, "total_count": len(all_rows), "page": page, "page_size": page_size, "chart_data": chart_data, "stock_control_mode": get_stock_control_mode()}

# ============================================================
# INVENTORY + ITEM INTELLIGENCE REPORT APIs
# Add below existing Ledgix Reports APIs in ledgix_saas/api/api.py
# ============================================================

@frappe.whitelist()
def get_inventory_report_data(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    """
    Inventory snapshot report.

    Notes:
    - `status` = Stock Status filter: In Stock / Low Stock / Out of Stock
    - `type` = Active / Inactive filter
    - `party` = Category filter, kept for compatibility with the common reports filter payload
    - Date filters are intentionally ignored because this is a current stock snapshot.
    """
    require_ledgix_manager_or_above()

    if _lx_reports_is_billing_mode():
        return _lx_empty_report_response(page, page_size, {
            "inventory_value": 0,
            "total_items": 0,
            "low_stock": 0,
            "out_of_stock": 0,
        })

    page, page_size, offset = _lx_page_args(page, page_size)
    conditions = []
    values = {}

    if status:
        conditions.append("i.stock_status = %(stock_status)s")
        values["stock_status"] = status

    if type:
        clean_type = str(type).strip().lower()
        if clean_type == "active":
            conditions.append("IFNULL(i.active, 0) = 1")
        elif clean_type == "inactive":
            conditions.append("IFNULL(i.active, 0) = 0")

    if party:
        conditions.append("i.category LIKE %(category)s")
        values["category"] = f"%{party}%"

    if search:
        conditions.append("""
            (
                i.name LIKE %(search)s
                OR i.item_name LIKE %(search)s
                OR i.item_code LIKE %(search)s
                OR i.sku LIKE %(search)s
                OR i.barcode LIKE %(search)s
                OR i.category LIKE %(search)s
            )
        """)
        values["search"] = f"%{search}%"

    amount_conditions, amount_values = _lx_amount_filters("IFNULL(i.current_stock, 0) * IFNULL(i.cost_price, 0)", min_amount, max_amount)
    conditions.extend(amount_conditions)
    values.update(amount_values)

    where = _lx_where(conditions)

    sort_map = {
        "item": "i.item_name",
        "category": "i.category",
        "current_stock": "i.current_stock",
        "minimum_stock": "i.minimum_stock",
        "stock_status": "i.stock_status",
        "cost_price": "i.cost_price",
        "selling_price": "i.selling_price",
        "inventory_value": "inventory_value",
        "profit_margin": "i.profit_margin",
    }
    order_field = sort_map.get(str(sort_by or "").strip(), "i.item_name")
    order_dir = "DESC" if str(sort_order or "").lower() == "desc" else "ASC"

    values.update({"limit": page_size, "offset": offset})

    rows = frappe.db.sql(f"""
        SELECT
            i.name AS name,
            COALESCE(NULLIF(i.item_name, ''), i.name) AS item,
            i.item_code AS item_code,
            i.sku AS sku,
            i.barcode AS barcode,
            i.category AS category,
            IFNULL(i.current_stock, 0) AS current_stock,
            IFNULL(i.minimum_stock, 0) AS minimum_stock,
            COALESCE(NULLIF(i.stock_status, ''), 'In Stock') AS stock_status,
            IFNULL(i.cost_price, 0) AS cost_price,
            IFNULL(i.selling_price, 0) AS selling_price,
            IFNULL(i.current_stock, 0) * IFNULL(i.cost_price, 0) AS inventory_value,
            IFNULL(i.profit_margin, 0) AS profit_margin,
            IFNULL(i.active, 0) AS active
        FROM `tabLedgix Item` i
        WHERE {where}
        ORDER BY {order_field} {order_dir}, i.modified DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, values, as_dict=True)

    total_count = frappe.db.sql(f"""
        SELECT COUNT(*) AS total
        FROM `tabLedgix Item` i
        WHERE {where}
    """, values, as_dict=True)[0].total or 0

    summary = frappe.db.sql(f"""
        SELECT
            IFNULL(SUM(IFNULL(i.current_stock, 0) * IFNULL(i.cost_price, 0)), 0) AS inventory_value,
            COUNT(*) AS total_items,
            SUM(CASE WHEN i.stock_status = 'Low Stock' THEN 1 ELSE 0 END) AS low_stock,
            SUM(CASE WHEN i.stock_status = 'Out of Stock' THEN 1 ELSE 0 END) AS out_of_stock
        FROM `tabLedgix Item` i
        WHERE {where}
    """, values, as_dict=True)[0]

    chart_data = frappe.db.sql(f"""
        SELECT
            COALESCE(NULLIF(i.stock_status, ''), 'In Stock') AS label,
            IFNULL(SUM(IFNULL(i.current_stock, 0) * IFNULL(i.cost_price, 0)), 0) AS value,
            COUNT(*) AS count
        FROM `tabLedgix Item` i
        WHERE {where}
        GROUP BY COALESCE(NULLIF(i.stock_status, ''), 'In Stock')
        ORDER BY count DESC
    """, values, as_dict=True)

    return {
        "rows": rows,
        "summary": summary,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "chart_data": chart_data,
        "stock_control_mode": get_stock_control_mode()
    }


@frappe.whitelist()
def get_item_full_cycle_report_data(from_date=None, to_date=None, search=None, status=None, type=None, party=None, min_amount=None, max_amount=None, page=1, page_size=20, sort_by=None, sort_order="asc"):
    """
    Legacy Item Intelligence report API across purchases, sales, returns, and manual stock adjustments.

    Filter mapping:
    - `search` = item/reference text
    - `party` = item/category text from common dialog field
    - `type` = Purchase / Sale / Return / Stock Movement
    - min/max amount = profit impact range
    """
    require_ledgix_manager_or_above()

    if _lx_reports_is_billing_mode():
        return _lx_empty_report_response(page, page_size, {
            "purchased_qty": 0,
            "sold_qty": 0,
            "returned_qty": 0,
            "net_profit": 0,
        })

    page, page_size, offset = _lx_page_args(page, page_size)
    purchase_table = f"tab{PURCHASE_DOCTYPE}"
    values = {
        "from_date": from_date or "1900-01-01",
        "to_date": to_date or today(),
    }

    common_filters = []

    if search:
        common_filters.append("(x.item LIKE %(search)s OR x.reference LIKE %(search)s OR x.event_type LIKE %(search)s)")
        values["search"] = f"%{search}%"

    if party:
        common_filters.append("(x.item LIKE %(party)s OR x.category LIKE %(party)s)")
        values["party"] = f"%{party}%"

    if type:
        type_map = {
            "purchase": "Purchase",
            "sale": "Sale",
            "return": "Return",
            "stock movement": "Stock Movement",
            "stock": "Stock Movement",
        }
        clean_type = type_map.get(str(type).strip().lower(), type)
        common_filters.append("x.event_type = %(event_type)s")
        values["event_type"] = clean_type

    amount_conditions, amount_values = _lx_amount_filters("IFNULL(x.profit_impact, 0)", min_amount, max_amount)
    common_filters.extend(amount_conditions)
    values.update(amount_values)

    where = _lx_where(common_filters)

    union_sql = f"""
        SELECT
            p.purchase_date AS date,
            p.creation AS sort_time,
            'Purchase' AS event_type,
            pi.item AS item,
            i.category AS category,
            p.name AS reference,
            IFNULL(pi.quantity, 0) AS qty_in,
            0 AS qty_out,
            IFNULL(pi.amount, 0) AS cost,
            0 AS revenue,
            0 AS profit_impact
        FROM `{purchase_table}` p
        INNER JOIN `tabLedgix Purchase Item` pi ON pi.parent = p.name
        LEFT JOIN `tabLedgix Item` i ON i.name = pi.item
        WHERE p.docstatus = 1 AND p.purchase_date BETWEEN %(from_date)s AND %(to_date)s

        UNION ALL

        SELECT
            s.sale_date AS date,
            s.creation AS sort_time,
            'Sale' AS event_type,
            si.item AS item,
            i.category AS category,
            COALESCE(NULLIF(s.invoice_number, ''), s.name) AS reference,
            0 AS qty_in,
            IFNULL(si.quantity, 0) AS qty_out,
            IFNULL(si.cost_price, 0) * IFNULL(si.quantity, 0) AS cost,
            IFNULL(si.amount, 0) AS revenue,
            IFNULL(si.item_total_profit, 0) AS profit_impact
        FROM `tabLedgix Sale` s
        INNER JOIN `tabLedgix Sale Item` si ON si.parent = s.name
        LEFT JOIN `tabLedgix Item` i ON i.name = si.item
        WHERE s.docstatus = 1 AND s.sale_date BETWEEN %(from_date)s AND %(to_date)s

        UNION ALL

        SELECT
            DATE(sr.creation) AS date,
            sr.creation AS sort_time,
            'Return' AS event_type,
            sri.item AS item,
            i.category AS category,
            sr.name AS reference,
            IFNULL(sri.quantity, 0) AS qty_in,
            0 AS qty_out,
            0 AS cost,
            IFNULL(sri.amount, 0) * -1 AS revenue,
            IFNULL(sri.item_total_profit, 0) * -1 AS profit_impact
        FROM `tabLedgix Sales Return` sr
        INNER JOIN `tabLedgix Sales Return Item` sri ON sri.parent = sr.name
        LEFT JOIN `tabLedgix Item` i ON i.name = sri.item
        WHERE sr.docstatus = 1 AND DATE(sr.creation) BETWEEN %(from_date)s AND %(to_date)s

        UNION ALL

        SELECT
            DATE(sm.movement_date) AS date,
            sm.creation AS sort_time,
            'Stock Movement' AS event_type,
            sm.item AS item,
            i.category AS category,
            sm.name AS reference,
            CASE WHEN sm.movement_type IN ('IN', 'ADJUSTMENT') AND IFNULL(sm.quantity, 0) > 0 THEN IFNULL(sm.quantity, 0) ELSE 0 END AS qty_in,
            CASE WHEN sm.movement_type = 'OUT' OR (sm.movement_type = 'ADJUSTMENT' AND IFNULL(sm.quantity, 0) < 0) THEN ABS(IFNULL(sm.quantity, 0)) ELSE 0 END AS qty_out,
            0 AS cost,
            0 AS revenue,
            0 AS profit_impact
        FROM `tabLedgix Stock Movement` sm
        LEFT JOIN `tabLedgix Item` i ON i.name = sm.item
        WHERE
            sm.docstatus = 1
            AND DATE(sm.movement_date) BETWEEN %(from_date)s AND %(to_date)s
            AND (
                sm.movement_type = 'ADJUSTMENT'
                OR IFNULL(sm.reference_doctype, '') NOT IN ('Ledgix Sale', 'Ledgix Sales Return', 'Ledgix Purchase', 'Ledgix Purchase')
            )
    """

    all_rows = frappe.db.sql(f"""
        SELECT * FROM ({union_sql}) x
        WHERE {where}
        ORDER BY x.item ASC, x.date ASC, x.sort_time ASC
    """, values, as_dict=True)

    running = {}
    for idx, row in enumerate(all_rows):
        item_key = row.get("item") or "-"
        running[item_key] = running.get(item_key, 0) + flt(row.get("qty_in")) - flt(row.get("qty_out"))
        row["running_stock"] = running[item_key]
        row["name"] = f"{row.get('event_type')}-{row.get('reference')}-{item_key}-{idx}"

    display_rows = sorted(
        all_rows,
        key=lambda row: (str(row.get("date") or ""), str(row.get("sort_time") or "")),
        reverse=(str(sort_order or "desc").lower() != "asc")
    )

    paged = display_rows[offset:offset + page_size]
    purchased_qty = sum(flt(row.qty_in) for row in all_rows if row.event_type == "Purchase")
    sold_qty = sum(flt(row.qty_out) for row in all_rows if row.event_type == "Sale")
    returned_qty = sum(flt(row.qty_in) for row in all_rows if row.event_type == "Return")
    net_profit = sum(flt(row.profit_impact) for row in all_rows)

    chart_bucket = {}
    for row in all_rows:
        label = str(row.get("date") or "-")
        if label not in chart_bucket:
            chart_bucket[label] = {"label": label, "value": 0, "count": 0}
        chart_bucket[label]["value"] += flt(row.get("profit_impact"))
        chart_bucket[label]["count"] += 1

    chart_data = [chart_bucket[key] for key in sorted(chart_bucket.keys())]

    return {
        "rows": paged,
        "summary": {
            "purchased_qty": purchased_qty,
            "sold_qty": sold_qty,
            "returned_qty": returned_qty,
            "net_profit": net_profit,
        },
        "total_count": len(all_rows),
        "page": page,
        "page_size": page_size,
        "chart_data": chart_data,
        "stock_control_mode": get_stock_control_mode()
    }
