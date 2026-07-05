# ============================================================
# LEDGIX DASHBOARD APIs
# ============================================================
# Lightweight dashboard/insight APIs kept separate from POS/Reports.

import frappe
from frappe.utils import today, add_days, flt, cint
from datetime import datetime, timedelta
from ledgix_saas.api.security import require_ledgix_manager_or_above

def normalize_date_range(data, start_date, end_date):
    result = []

    data_map = {}
    for d in data:
        key = str(d["date"])
        data_map[key] = flt(d["value"])

    start = datetime.strptime(str(start_date), "%Y-%m-%d")
    end = datetime.strptime(str(end_date), "%Y-%m-%d")

    while start <= end:
        day = start.strftime("%Y-%m-%d")

        result.append({
            "date": day,
            "value": data_map.get(day, 0)
        })

        start += timedelta(days=1)

    return result


@frappe.whitelist()
def get_sales_last_7_days():
    require_ledgix_manager_or_above()

    end_date = today()
    start_date = add_days(end_date, -6)

    data = frappe.db.sql("""
        SELECT
            sale_date AS date,
            COALESCE(SUM(total_amount), 0) AS value
        FROM `tabLedgix Sale`
        WHERE
            docstatus = 1
            AND sale_date BETWEEN %s AND %s
        GROUP BY sale_date
        ORDER BY sale_date ASC
    """, (start_date, end_date), as_dict=True)

    return normalize_date_range(data, start_date, end_date)


@frappe.whitelist()
def get_profit_last_7_days():
    require_ledgix_manager_or_above()

    end_date = today()
    start_date = add_days(end_date, -6)

    data = frappe.db.sql("""
        SELECT
            sale_date AS date,
            COALESCE(SUM(total_profit), 0) AS value
        FROM `tabLedgix Sale`
        WHERE
            docstatus = 1
            AND sale_date BETWEEN %s AND %s
        GROUP BY sale_date
        ORDER BY sale_date ASC
    """, (start_date, end_date), as_dict=True)

    return normalize_date_range(data, start_date, end_date)


@frappe.whitelist()
def get_sales_insight():
    require_ledgix_manager_or_above()

    today_date = today()
    yesterday_date = add_days(today_date, -1)

    today_sales = frappe.db.sql("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM `tabLedgix Sale`
        WHERE
            docstatus = 1
            AND sale_date = %s
    """, (today_date,))[0][0]

    yesterday_sales = frappe.db.sql("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM `tabLedgix Sale`
        WHERE
            docstatus = 1
            AND sale_date = %s
    """, (yesterday_date,))[0][0]

    change_percent = 0

    if flt(yesterday_sales) > 0:
        change_percent = ((flt(today_sales) - flt(yesterday_sales)) / flt(yesterday_sales)) * 100

    return {
        "today_sales": flt(today_sales),
        "yesterday_sales": flt(yesterday_sales),
        "change_percent": round(change_percent, 2)
    }


@frappe.whitelist()
def get_profit_margin_insight():
    require_ledgix_manager_or_above()

    today_date = today()
    yesterday_date = add_days(today_date, -1)

    today_data = frappe.db.sql("""
        SELECT 
            COALESCE(SUM(total_amount), 0) AS sales,
            COALESCE(SUM(total_profit), 0) AS profit
        FROM `tabLedgix Sale`
        WHERE
            docstatus = 1
            AND sale_date = %s
    """, (today_date,), as_dict=True)[0]

    yesterday_data = frappe.db.sql("""
        SELECT 
            COALESCE(SUM(total_amount), 0) AS sales,
            COALESCE(SUM(total_profit), 0) AS profit
        FROM `tabLedgix Sale`
        WHERE
            docstatus = 1
            AND sale_date = %s
    """, (yesterday_date,), as_dict=True)[0]

    def calc_margin(sales, profit):
        sales = flt(sales)
        profit = flt(profit)

        if sales <= 0:
            return 0

        return (profit / sales) * 100

    today_margin = calc_margin(today_data.sales, today_data.profit)
    yesterday_margin = calc_margin(yesterday_data.sales, yesterday_data.profit)

    change = today_margin - yesterday_margin

    return {
        "today_margin": round(today_margin, 2),
        "yesterday_margin": round(yesterday_margin, 2),
        "change": round(change, 2)
    }
