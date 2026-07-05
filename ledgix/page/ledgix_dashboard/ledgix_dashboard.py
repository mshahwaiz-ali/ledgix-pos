import frappe
from frappe.utils import today, add_days, getdate, now_datetime
from frappe.utils.data import flt, cint
from ledgix_saas.api.settings import normalize_theme_settings
from ledgix_saas.api.security import require_ledgix_manager_or_above


# ============================================================
# LEDGIX DECISION DASHBOARD V2 APIs
# ============================================================

def _date_range(days=7, from_date=None, to_date=None):
    end_date = getdate(to_date) if to_date else getdate(today())

    if from_date:
        return getdate(from_date), end_date

    if to_date:
        return _get_earliest_dashboard_date(end_date), end_date

    start_date = add_days(end_date, -cint(days or 7) + 1)
    return start_date, end_date


def _get_earliest_dashboard_date(fallback_end_date):
    candidates = []

    date_sources = [
        ("Ledgix Sale", "sale_date"),
        ("Ledgix Purchase", "purchase_date"),
        ("Ledgix Sales Return", "creation"),
        ("Ledgix Stock Movement", "movement_date"),
    ]

    for doctype, fieldname in date_sources:
        if not _doctype_exists(doctype):
            continue

        try:
            row = frappe.db.sql(
                f"""
                SELECT MIN(DATE(`{fieldname}`)) AS min_date
                FROM `tab{doctype}`
                WHERE docstatus < 2
                """,
                as_dict=True,
            )[0]
            if row.min_date:
                candidates.append(getdate(row.min_date))
        except Exception:
            continue

    return min(candidates) if candidates else add_days(fallback_end_date, -364)


def _get_stock_mode():
    return frappe.db.get_single_value("Ledgix Mode Settings", "stock_control_mode") or "Strict Inventory"


def _is_inventory_mode():
    return _get_stock_mode() == "Strict Inventory"


def _get_theme_settings():
    try:
        settings = frappe.get_single("Ledgix POS Theme Settings")
        return normalize_theme_settings({
            "enable_custom_accent": settings.enable_custom_accent,
            "primary_accent_color": settings.primary_accent_color,
            "accent_hover": settings.accent_hover,
            "accent_soft": settings.accent_soft,
            "accent_soft_2": settings.accent_soft_2,
            "accent_border": settings.accent_border,
        })
    except Exception:
        return normalize_theme_settings({})


@frappe.whitelist()
def get_decision_dashboard_data(days=7, from_date=None, to_date=None):
    require_ledgix_manager_or_above()

    start_date, end_date = _date_range(days, from_date, to_date)
    today_start, today_end = _date_range(days=1)
    yesterday_start = add_days(today_start, -1)
    yesterday_end = add_days(today_end, -1)

    stock_mode = _get_stock_mode()
    inventory_mode = _is_inventory_mode()

    comparison_days = (end_date - start_date).days + 1
    comparison_start = add_days(start_date, -comparison_days)
    comparison_end = add_days(start_date, -1)

    sales = _get_sales_summary(start_date, end_date)
    today_sales = _get_sales_summary(today_start, today_end)
    yesterday_sales = _get_sales_summary(yesterday_start, yesterday_end)
    comparison_sales = _get_sales_summary(comparison_start, comparison_end)

    returns = _get_returns_summary(start_date, end_date)
    purchases = _get_purchase_summary(start_date, end_date)
    today_payments = _get_payment_distribution(today_start, today_end)
    today_cash_sales = _get_cash_amount(today_payments)
    today_non_cash_sales = max(0, flt(today_sales.get("revenue")) - today_cash_sales)

    net_sales = flt(sales["revenue"]) - flt(returns["amount"])
    net_profit = flt(sales["profit"]) - flt(returns["profit_reversal"])
    profit_margin = (net_profit / net_sales * 100) if net_sales else 0
    avg_bill = (flt(sales["revenue"]) / cint(sales["invoice_count"])) if cint(sales["invoice_count"]) else 0
    return_rate = (flt(returns["amount"]) / flt(sales["revenue"]) * 100) if flt(sales["revenue"]) else 0

    inventory = _get_inventory_summary() if inventory_mode else {}
    health_score = _get_health_score(
        profit_margin=profit_margin,
        return_rate=return_rate,
        inventory=inventory,
        inventory_mode=inventory_mode,
    )

    sales_change_percent = _percent_change(sales.get("revenue"), comparison_sales.get("revenue"))
    profit_change_percent = _percent_change(sales.get("profit"), comparison_sales.get("profit"))
    items_sold_change_percent = _percent_change(sales.get("items_sold"), comparison_sales.get("items_sold"))    

    profit_items = _get_profit_items(start_date, end_date)
    fast_moving_items = _get_fast_moving_items(start_date, end_date, limit=5)
    payment_distribution = _get_payment_distribution(start_date, end_date)
    shift = _get_shift_summary(today_start, today_cash_sales, today_non_cash_sales)
    inventory_command = _get_inventory_command_summary(inventory) if inventory_mode else _empty_inventory_command()
    alerts = _get_command_alerts(
        inventory=inventory_command,
        returns=returns,
        return_rate=return_rate,
        shift=shift,
        inventory_mode=inventory_mode,
    )

    payload = {
        "meta": {
            "from_date": str(start_date),
            "to_date": str(end_date),
            "business_date": str(today_start),
            "stock_control_mode": stock_mode,
            "is_inventory_mode": inventory_mode,
            "last_updated": str(now_datetime()),
            "comparison_days": comparison_days,
            "comparison_label": f"previous {comparison_days}D daily average",
            "theme": _get_theme_settings(),
        },
        "executive": {
            "today_sales": flt(today_sales["revenue"]),
            "today_profit": flt(today_sales["profit"]),
            "today_invoice_count": cint(today_sales["invoice_count"]),
            "today_items_sold": flt(today_sales["items_sold"]),
            "range_sales": flt(sales["revenue"]),
            "range_profit": flt(net_profit),
            "range_gross_profit": flt(sales["profit"]),
            "revenue": flt(sales["revenue"]),
            "profit": flt(net_profit),
            "gross_profit": flt(sales["profit"]),
            "profit_margin": flt(profit_margin, 2),
            "net_sales": flt(net_sales),
            "invoice_count": cint(sales["invoice_count"]),
            "items_sold": flt(sales["items_sold"]),
            "avg_bill": flt(avg_bill),
            "returns_amount": flt(returns["amount"]),
            "returns_count": cint(returns["count"]),
            "return_rate": flt(return_rate, 2),
            "purchase_amount": flt(purchases["amount"]),
            "sales_change_percent": sales_change_percent,
            "profit_change_percent": profit_change_percent,
            "items_sold_change_percent": items_sold_change_percent,
            "net_sales_change_percent": sales_change_percent,
        },
        "signals": _get_decision_signals(
            sales=sales,
            returns=returns,
            inventory=inventory,
            inventory_mode=inventory_mode,
            net_sales=net_sales,
            profit_margin=profit_margin,
            return_rate=return_rate,
        ),
        "charts": {
            "sales_profit_trend": _get_sales_profit_trend(start_date, end_date),
            "returns_trend": _get_returns_trend(start_date, end_date),
            "payment_distribution": payment_distribution,
            "category_performance": _get_category_performance(start_date, end_date),
            "sales_vs_purchases": _get_sales_vs_purchase_trend(start_date, end_date),
            "stock_movement": _get_stock_movement_trend(start_date, end_date) if inventory_mode else [],
        },
        "tables": {
            "profit_items": profit_items,
            "profit_intelligence": profit_items,
            "fast_moving_items": fast_moving_items,
            "low_margin_items": _get_low_margin_items(start_date, end_date),
            "recent_invoices": _get_recent_invoices(start_date, end_date),
            "low_stock_items": _get_low_stock_items() if inventory_mode else [],
        },
        "inventory": inventory,
        "health_score": health_score,
    }

    payload.update({
        "business_pulse": {
            "net_sales": flt(today_sales["revenue"]),
            "gross_profit": flt(today_sales["profit"]),
            "profit_margin": flt((flt(today_sales["profit"]) / flt(today_sales["revenue"]) * 100) if flt(today_sales["revenue"]) else 0, 2),
            "invoice_count": cint(today_sales["invoice_count"]),
            "expected_cash": flt(shift.get("expected_cash") or today_cash_sales),
            "cash_sales": flt(today_cash_sales),
            "non_cash_sales": flt(today_non_cash_sales),
            "sales_vs_yesterday_percent": _percent_change(today_sales.get("revenue"), yesterday_sales.get("revenue")),
            "profit_vs_yesterday_percent": _percent_change(today_sales.get("profit"), yesterday_sales.get("profit")),
        },
        "alerts": alerts,
        "trend": payload["charts"]["sales_profit_trend"],
        "payment_distribution": payment_distribution,
        "shift": shift,
        "inventory": inventory_command,
        "fast_moving_items": fast_moving_items,
        "recent_activity": _get_recent_risk_activity(start_date, end_date),
        "quick_actions": _get_quick_actions(),
    })

    return payload


def _percent_change(current, previous):
    current = flt(current)
    previous = flt(previous)

    if previous == 0:
        return 100 if current > 0 else 0

    return flt(((current - previous) / previous) * 100, 1)


def _daily_average_summary(summary, days):
    days = cint(days or 1) or 1

    return {
        "revenue": flt(summary.get("revenue")) / days,
        "profit": flt(summary.get("profit")) / days,
        "invoice_count": flt(summary.get("invoice_count")) / days,
        "items_sold": flt(summary.get("items_sold")) / days,
    }


# ============================================================
# SUMMARY CALCULATIONS
# ============================================================

def _get_sales_summary(start_date, end_date):
    sale_row = frappe.db.sql("""
        SELECT
            COALESCE(SUM(total_amount), 0) AS revenue,
            COALESCE(SUM(total_profit), 0) AS profit,
            COUNT(name) AS invoice_count
        FROM `tabLedgix Sale`
        WHERE docstatus = 1
        AND sale_date BETWEEN %s AND %s
    """, (start_date, end_date), as_dict=True)[0]

    item_row = frappe.db.sql("""
        SELECT
            COALESCE(SUM(i.quantity), 0) AS items_sold
        FROM `tabLedgix Sale Item` i
        INNER JOIN `tabLedgix Sale` s ON s.name = i.parent
        WHERE s.docstatus = 1
        AND s.sale_date BETWEEN %s AND %s
    """, (start_date, end_date), as_dict=True)[0]

    return {
        "revenue": flt(sale_row.revenue),
        "profit": flt(sale_row.profit),
        "invoice_count": cint(sale_row.invoice_count),
        "items_sold": flt(item_row.items_sold),
    }


def _get_returns_summary(start_date, end_date):
    row = frappe.db.sql("""
        SELECT
            COUNT(DISTINCT r.name) AS count,
            COALESCE(SUM(r.total_amount), 0) AS amount,
            COALESCE(SUM(r.total_profit_reversal), 0) AS profit_reversal
        FROM `tabLedgix Sales Return` r
        WHERE r.docstatus = 1
        AND DATE(r.creation) BETWEEN %s AND %s
    """, (start_date, end_date), as_dict=True)[0]

    return row


def _get_purchase_summary(start_date, end_date):
    row = frappe.db.sql("""
        SELECT
            COALESCE(SUM(i.amount), 0) AS amount
        FROM `tabLedgix Purchase Item` i
        INNER JOIN `tabLedgix Purchase` p ON p.name = i.parent
        WHERE p.docstatus = 1
        AND p.purchase_date BETWEEN %s AND %s
    """, (start_date, end_date), as_dict=True)[0]

    return row


def _get_inventory_summary():
    row = frappe.db.sql("""
        SELECT
            COALESCE(SUM(current_stock * cost_price), 0) AS value,
            COUNT(*) AS total_items,
            SUM(CASE WHEN current_stock <= minimum_stock AND current_stock > 0 THEN 1 ELSE 0 END) AS low_stock,
            SUM(CASE WHEN current_stock <= 0 THEN 1 ELSE 0 END) AS out_of_stock
        FROM `tabLedgix Item`
        WHERE active = 1
    """, as_dict=True)[0]

    return {
        "value": flt(row.value),
        "total_items": cint(row.total_items),
        "low_stock": cint(row.low_stock),
        "out_of_stock": cint(row.out_of_stock),
    }


def _empty_inventory_command():
    return {
        "inventory_value": 0,
        "low_stock": 0,
        "out_of_stock": 0,
        "total_items": 0,
        "tracked_items": 0,
        "tracked_lots": 0,
        "tracked_serials": 0,
    }


def _count_existing_records(doctype, where_clause="", values=None):
    if not _doctype_exists(doctype):
        return 0

    row = frappe.db.sql(
        f"""
        SELECT COUNT(*) AS count
        FROM `tab{doctype}`
        {where_clause}
        """,
        values or (),
        as_dict=True,
    )[0]
    return cint(row.count)


def _get_inventory_command_summary(inventory):
    tracked_items = frappe.db.sql("""
        SELECT COUNT(*) AS count
        FROM `tabLedgix Item`
        WHERE active = 1
        AND COALESCE(tracking_type, 'Normal') IN ('Lot Based', 'Serial Based')
    """, as_dict=True)[0]

    tracked_lots = _count_existing_records(
        "Ledgix Stock Lot",
        "WHERE docstatus < 2",
    )
    tracked_serials = _count_existing_records(
        "Ledgix Stock Serial",
        "WHERE docstatus < 2",
    )

    return {
        "inventory_value": flt(inventory.get("value")),
        "low_stock": cint(inventory.get("low_stock")),
        "out_of_stock": cint(inventory.get("out_of_stock")),
        "total_items": cint(inventory.get("total_items")),
        "tracked_items": cint(tracked_items.count),
        "tracked_lots": tracked_lots,
        "tracked_serials": tracked_serials,
    }


def _cash_method_label(label):
    return "cash" in str(label or "").strip().lower()


def _get_cash_amount(payment_rows):
    return flt(sum(flt(row.get("value")) for row in (payment_rows or []) if _cash_method_label(row.get("label"))))


def _doctype_exists(doctype):
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


# ============================================================
# DECISION SIGNALS
# ============================================================

def _get_decision_signals(sales, returns, inventory, inventory_mode, net_sales, profit_margin, return_rate):
    signals = []

    if flt(net_sales) > 0:
        signals.append({
            "type": "success",
            "title": "Sales active",
            "message": f"Net sales are PKR {flt(net_sales):,.2f} for this range."
        })
    else:
        signals.append({
            "type": "muted",
            "title": "No sales yet",
            "message": "No submitted sales found for this range."
        })

    if profit_margin < 10 and flt(net_sales) > 0:
        signals.append({
            "type": "warning",
            "title": "Low margin",
            "message": f"Profit margin is only {flt(profit_margin, 2)}%."
        })
    else:
        signals.append({
            "type": "success",
            "title": "Margin healthy",
            "message": f"Profit margin is {flt(profit_margin, 2)}%."
        })

    if return_rate >= 10:
        signals.append({
            "type": "danger",
            "title": "Return risk",
            "message": f"Returns are {flt(return_rate, 2)}% of sales."
        })
    elif cint(returns.get("count")) > 0:
        signals.append({
            "type": "warning",
            "title": "Returns present",
            "message": f"{cint(returns.get('count'))} return(s) recorded in this range."
        })

    if inventory_mode:
        low_stock = cint(inventory.get("low_stock"))
        out_stock = cint(inventory.get("out_of_stock"))

        if out_stock > 0:
            signals.append({
                "type": "danger",
                "title": "Out of stock",
                "message": f"{out_stock} item(s) are out of stock."
            })
        elif low_stock > 0:
            signals.append({
                "type": "warning",
                "title": "Low stock",
                "message": f"{low_stock} item(s) need reorder attention."
            })

    return signals


def _get_command_alerts(inventory, returns, return_rate, shift, inventory_mode):
    low_stock = cint(inventory.get("low_stock")) if inventory_mode else 0
    out_of_stock = cint(inventory.get("out_of_stock")) if inventory_mode else 0
    return_count = cint(returns.get("count"))

    shift_status = str(shift.get("status") or "").lower()
    shift_route = "/app/ledgix_operations?module=pos-shifts"
    shift_disabled = shift_status == "not_configured"
    shift_is_open = shift_status == "open"

    today_cash_variance = flt(shift.get("today_closed_variance")) or flt(shift.get("variance"))
    today_abs_variance = abs(today_cash_variance)
    closed_shift_count = cint(shift.get("closed_shift_count"))

    if closed_shift_count:
        variance_message = (
            f"Closed shift cash difference today is PKR {today_cash_variance:,.0f} "
            f"across {closed_shift_count} shift(s)."
        )
    elif shift_is_open:
        variance_message = "Cash variance will be final after the active shift is closed."
    else:
        variance_message = "No closed shift cash variance recorded today."

    if shift_disabled:
        shift_count = 0
        shift_message = "POS shift workflow is not configured yet."
        shift_action_label = "Shift Page Coming Next"
    elif shift_is_open:
        shift_count = "Open"
        shift_message = f"Active shift expected cash is PKR {flt(shift.get('expected_cash')):,.0f}."
        shift_action_label = "Review Active Shift"
    else:
        shift_count = "Closed" if shift.get("shift_id") else "None"
        shift_message = "No active shift right now. Open a shift before POS billing."
        shift_action_label = "Open Shift Control"

    alerts = [
        {
            "key": "low_stock",
            "title": "Low Stock Items",
            "count": low_stock,
            "message": "Items are near or below reorder level.",
            "severity": "warning" if low_stock else "success",
            "action_label": "Open Inventory",
            "route": "/app/ledgix-reports?report=inventory",
            "disabled": not inventory_mode,
        },
        {
            "key": "out_of_stock",
            "title": "Out of Stock Items",
            "count": out_of_stock,
            "message": "Items currently cannot be sold from stock.",
            "severity": "danger" if out_of_stock else "success",
            "action_label": "Open Inventory",
            "route": "/app/ledgix-reports?report=inventory",
            "disabled": not inventory_mode,
        },
        {
            "key": "returns",
            "title": "High Return Activity",
            "count": return_count,
            "message": f"Returns are {flt(return_rate, 2)}% of submitted sales in this range.",
            "severity": "danger" if return_rate >= 10 else ("warning" if return_count else "success"),
            "action_label": "View Returns",
            "route": "/app/ledgix_operations?module=sales-returns",
            "disabled": False,
        },
        {
            "key": "cash_variance",
            "title": "Today Cash Variance",
            "count": flt(today_cash_variance),
            "message": variance_message,
            "severity": "danger" if today_abs_variance else "info",
            "action_label": "Review Shifts",
            "route": shift_route,
            "disabled": shift_disabled,
        },
        {
            "key": "shift",
            "title": "Shift Status",
            "count": shift_count,
            "message": shift_message,
            "severity": "warning" if shift_is_open else ("success" if shift.get("shift_id") else "info"),
            "action_label": shift_action_label,
            "route": shift_route,
            "disabled": shift_disabled,
        },
        {
            "key": "lot_serial",
            "title": "Serial/Lot Alerts",
            "count": cint(inventory.get("tracked_lots")) + cint(inventory.get("tracked_serials")),
            "message": f"{cint(inventory.get('tracked_lots'))} lots and {cint(inventory.get('tracked_serials'))} serials are tracked.",
            "severity": "info",
            "action_label": "Open BI Center",
            "route": "/app/ledgix-reports?report=inventory",
            "disabled": not inventory_mode,
        },
    ]
    return alerts

def _get_health_score(profit_margin, return_rate, inventory, inventory_mode):
    score = 100

    if profit_margin < 20:
        score -= 15
    if profit_margin < 10:
        score -= 15

    if return_rate > 5:
        score -= 10
    if return_rate > 10:
        score -= 15

    if inventory_mode:
        if cint(inventory.get("out_of_stock")) > 0:
            score -= 20
        if cint(inventory.get("low_stock")) > 0:
            score -= 10

    score = max(0, min(100, cint(score)))

    if score >= 85:
        label = "Strong"
    elif score >= 70:
        label = "Stable"
    elif score >= 50:
        label = "Needs attention"
    else:
        label = "High risk"

    return {
        "score": score,
        "label": label,
    }


# ============================================================
# CHART DATA
# ============================================================

def _get_sales_profit_trend(start_date, end_date):
    rows = frappe.db.sql("""
        SELECT
            sale_date,
            COALESCE(SUM(total_amount), 0) AS sales,
            COALESCE(SUM(total_profit), 0) AS profit,
            COUNT(*) AS invoices
        FROM `tabLedgix Sale`
        WHERE docstatus = 1
        AND sale_date BETWEEN %s AND %s
        GROUP BY sale_date
        ORDER BY sale_date
    """, (start_date, end_date), as_dict=True)

    data_map = {
        str(r.sale_date): {
            "sales": flt(r.sales),
            "profit": flt(r.profit),
            "invoices": cint(r.invoices),
        }
        for r in rows
    }

    result = []
    current = start_date

    while current <= end_date:
        key = str(current)
        result.append({
            "date": key,
            "sales": data_map.get(key, {}).get("sales", 0),
            "profit": data_map.get(key, {}).get("profit", 0),
            "invoices": data_map.get(key, {}).get("invoices", 0),
        })
        current = add_days(current, 1)

    return result


def _get_returns_trend(start_date, end_date):
    rows = frappe.db.sql("""
        SELECT
            DATE(creation) AS return_date,
            COUNT(*) AS count,
            COALESCE(SUM(total_amount), 0) AS amount
        FROM `tabLedgix Sales Return`
        WHERE docstatus = 1
        AND DATE(creation) BETWEEN %s AND %s
        GROUP BY DATE(creation)
        ORDER BY DATE(creation)
    """, (start_date, end_date), as_dict=True)

    data_map = {
        str(r.return_date): {
            "count": cint(r.count),
            "amount": flt(r.amount),
        }
        for r in rows
    }

    result = []
    current = start_date

    while current <= end_date:
        key = str(current)
        result.append({
            "date": key,
            "count": data_map.get(key, {}).get("count", 0),
            "amount": data_map.get(key, {}).get("amount", 0),
        })
        current = add_days(current, 1)

    return result


def _get_payment_distribution(start_date, end_date):
    rows = _get_payment_child_distribution(start_date, end_date)

    if not rows:
        rows = _get_sale_level_payment_distribution(start_date, end_date)

    if not rows:
        rows = _get_default_cash_distribution(start_date, end_date)

    return _merge_payment_distribution(rows)


def _get_payment_child_distribution(start_date, end_date):
    if not _doctype_exists("Ledgix Sale Payment"):
        return []

    columns = _get_doctype_columns("Ledgix Sale Payment")
    method_field = _first_existing_column(columns, [
        "payment_method",
        "mode_of_payment",
        "payment_type",
        "payment_mode",
        "method",
    ])
    amount_field = _first_existing_column(columns, [
        "amount",
        "payment_amount",
        "paid_amount",
        "received_amount",
    ])

    if not method_field or not amount_field:
        return []

    try:
        return frappe.db.sql(f"""
            SELECT
                COALESCE(p.`{method_field}`, 'Unknown') AS label,
                COALESCE(SUM(p.`{amount_field}`), 0) AS value
            FROM `tabLedgix Sale Payment` p
            INNER JOIN `tabLedgix Sale` s ON s.name = p.parent
            WHERE s.docstatus = 1
            AND s.sale_date BETWEEN %s AND %s
            GROUP BY p.`{method_field}`
            HAVING value > 0
            ORDER BY value DESC
        """, (start_date, end_date), as_dict=True)
    except Exception:
        return []


def _get_sale_level_payment_distribution(start_date, end_date):
    columns = _get_doctype_columns("Ledgix Sale")
    method_field = _first_existing_column(columns, [
        "payment_method",
        "mode_of_payment",
        "payment_type",
        "payment_mode",
    ])
    amount_field = _first_existing_column(columns, [
        "paid_amount",
        "received_amount",
        "payment_amount",
        "amount_paid",
        "grand_total",
        "net_total",
        "total_amount",
    ])

    if not amount_field:
        return []

    label_sql = f"COALESCE(s.`{method_field}`, 'Cash')" if method_field else "'Cash'"
    group_sql = f"GROUP BY s.`{method_field}`" if method_field else ""

    try:
        return frappe.db.sql(f"""
            SELECT
                {label_sql} AS label,
                COALESCE(SUM(s.`{amount_field}`), 0) AS value
            FROM `tabLedgix Sale` s
            WHERE s.docstatus = 1
            AND s.sale_date BETWEEN %s AND %s
            {group_sql}
            HAVING value > 0
            ORDER BY value DESC
        """, (start_date, end_date), as_dict=True)
    except Exception:
        return []


def _get_default_cash_distribution(start_date, end_date):
    columns = _get_doctype_columns("Ledgix Sale")
    amount_field = _first_existing_column(columns, ["total_amount", "grand_total", "net_total"])

    if not amount_field:
        return []

    try:
        row = frappe.db.sql(f"""
            SELECT COALESCE(SUM(`{amount_field}`), 0) AS value
            FROM `tabLedgix Sale`
            WHERE docstatus = 1
            AND sale_date BETWEEN %s AND %s
        """, (start_date, end_date), as_dict=True)[0]
    except Exception:
        return []

    total = flt(row.get("value"))
    return [{"label": "Cash", "value": total}] if total > 0 else []


def _merge_payment_distribution(rows):
    totals = {}
    order = []

    for row in rows or []:
        label = _normalize_payment_label(row.get("label"))
        value = flt(row.get("value"))

        if value <= 0:
            continue

        if label not in totals:
            totals[label] = 0
            order.append(label)

        totals[label] += value

    return [
        {"label": label, "value": flt(totals[label])}
        for label in sorted(order, key=lambda item: totals[item], reverse=True)
    ]


def _normalize_payment_label(label):
    value = str(label or "").strip()
    lowered = value.lower().replace(" ", "")

    if "jazzcash" in lowered or "jazz" in lowered:
        return "JazzCash"
    if "easypaisa" in lowered or "easy" in lowered:
        return "EasyPaisa"
    if any(token in lowered for token in ["card", "visa", "master", "debit", "credit"]):
        return "Card"
    if "cash" in lowered:
        return "Cash"
    if any(token in lowered for token in ["digital", "online", "bank", "transfer", "wallet"]):
        return "Digital"

    return value or "Unknown"


def _get_doctype_columns(doctype):
    try:
        return set(frappe.db.get_table_columns(doctype) or [])
    except Exception:
        return set()


def _first_existing_column(columns, candidates):
    for fieldname in candidates:
        if fieldname in columns:
            return fieldname
    return None


def _get_category_performance(start_date, end_date):
    return frappe.db.sql("""
        SELECT
            COALESCE(item.category, 'Uncategorized') AS label,
            COALESCE(SUM(si.amount), 0) AS revenue,
            COALESCE(SUM(si.item_total_profit), 0) AS profit,
            COALESCE(SUM(si.quantity), 0) AS quantity
        FROM `tabLedgix Sale Item` si
        INNER JOIN `tabLedgix Sale` s ON s.name = si.parent
        LEFT JOIN `tabLedgix Item` item ON item.name = si.item
        WHERE s.docstatus = 1
        AND s.sale_date BETWEEN %s AND %s
        GROUP BY item.category
        ORDER BY revenue DESC
        LIMIT 8
    """, (start_date, end_date), as_dict=True)


def _get_sales_vs_purchase_trend(start_date, end_date):
    sales_rows = frappe.db.sql("""
        SELECT sale_date AS date, COALESCE(SUM(total_amount), 0) AS sales
        FROM `tabLedgix Sale`
        WHERE docstatus = 1
        AND sale_date BETWEEN %s AND %s
        GROUP BY sale_date
    """, (start_date, end_date), as_dict=True)

    purchase_rows = frappe.db.sql("""
        SELECT p.purchase_date AS date, COALESCE(SUM(i.amount), 0) AS purchases
        FROM `tabLedgix Purchase Item` i
        INNER JOIN `tabLedgix Purchase` p ON p.name = i.parent
        WHERE p.docstatus = 1
        AND p.purchase_date BETWEEN %s AND %s
        GROUP BY p.purchase_date
    """, (start_date, end_date), as_dict=True)

    sales_map = {str(r.date): flt(r.sales) for r in sales_rows}
    purchase_map = {str(r.date): flt(r.purchases) for r in purchase_rows}

    result = []
    current = start_date

    while current <= end_date:
        key = str(current)
        result.append({
            "date": key,
            "sales": sales_map.get(key, 0),
            "purchases": purchase_map.get(key, 0),
        })
        current = add_days(current, 1)

    return result


def _get_stock_movement_trend(start_date, end_date):
    rows = frappe.db.sql("""
        SELECT
            DATE(movement_date) AS date,
            movement_type,
            COALESCE(SUM(quantity), 0) AS quantity
        FROM `tabLedgix Stock Movement`
        WHERE docstatus = 1
        AND DATE(movement_date) BETWEEN %s AND %s
        GROUP BY DATE(movement_date), movement_type
        ORDER BY DATE(movement_date)
    """, (start_date, end_date), as_dict=True)

    data_map = {}

    for row in rows:
        key = str(row.date)
        movement_type = str(row.movement_type or "").strip().upper()
        data_map.setdefault(key, {"IN": 0, "OUT": 0, "ADJUSTMENT": 0})

        if movement_type in ("IN", "STOCK IN"):
            data_map[key]["IN"] += flt(row.quantity)
        elif movement_type in ("OUT", "STOCK OUT"):
            data_map[key]["OUT"] += flt(row.quantity)
        else:
            data_map[key]["ADJUSTMENT"] += flt(row.quantity)

    result = []
    current = start_date

    while current <= end_date:
        key = str(current)
        result.append({
            "date": key,
            "in_qty": data_map.get(key, {}).get("IN", 0),
            "out_qty": data_map.get(key, {}).get("OUT", 0),
            "adjustment_qty": data_map.get(key, {}).get("ADJUSTMENT", 0),
        })
        current = add_days(current, 1)

    return result


# ============================================================
# TABLE DATA
# ============================================================

def _get_profit_items(start_date, end_date):
    return frappe.db.sql("""
        SELECT
            si.item,
            COALESCE(SUM(si.quantity), 0) AS quantity,
            COALESCE(SUM(si.amount), 0) AS revenue,
            COALESCE(SUM(si.item_total_profit), 0) AS profit,
            CASE
                WHEN COALESCE(SUM(si.amount), 0) > 0
                THEN COALESCE(SUM(si.item_total_profit), 0) / COALESCE(SUM(si.amount), 0) * 100
                ELSE 0
            END AS margin
        FROM `tabLedgix Sale Item` si
        INNER JOIN `tabLedgix Sale` s ON s.name = si.parent
        WHERE s.docstatus = 1
        AND s.sale_date BETWEEN %s AND %s
        GROUP BY si.item
        ORDER BY profit DESC
        LIMIT 8
    """, (start_date, end_date), as_dict=True)


def _get_fast_moving_items(start_date, end_date, limit=8):
    return frappe.db.sql("""
        SELECT
            si.item,
            COALESCE(SUM(si.quantity), 0) AS quantity,
            COALESCE(SUM(si.amount), 0) AS revenue,
            COALESCE(SUM(si.item_total_profit), 0) AS profit
        FROM `tabLedgix Sale Item` si
        INNER JOIN `tabLedgix Sale` s ON s.name = si.parent
        WHERE s.docstatus = 1
        AND s.sale_date BETWEEN %s AND %s
        GROUP BY si.item
        ORDER BY quantity DESC
        LIMIT %s
    """, (start_date, end_date, cint(limit or 8)), as_dict=True)


def _get_low_margin_items(start_date, end_date):
    return frappe.db.sql("""
        SELECT
            si.item,
            COALESCE(SUM(si.quantity), 0) AS quantity,
            COALESCE(SUM(si.amount), 0) AS revenue,
            COALESCE(SUM(si.item_total_profit), 0) AS profit,
            CASE
                WHEN COALESCE(SUM(si.amount), 0) > 0
                THEN COALESCE(SUM(si.item_total_profit), 0) / COALESCE(SUM(si.amount), 0) * 100
                ELSE 0
            END AS margin
        FROM `tabLedgix Sale Item` si
        INNER JOIN `tabLedgix Sale` s ON s.name = si.parent
        WHERE s.docstatus = 1
        AND s.sale_date BETWEEN %s AND %s
        GROUP BY si.item
        HAVING revenue > 0
        ORDER BY margin ASC, revenue DESC
        LIMIT 8
    """, (start_date, end_date), as_dict=True)


def _get_recent_invoices(start_date, end_date):
    return frappe.db.sql("""
        SELECT
            s.name,
            s.invoice_number,
            s.customer,
            s.sale_date,
            s.total_amount,
            s.total_profit,
            s.payment_status,
            GROUP_CONCAT(DISTINCT p.payment_method SEPARATOR ' + ') AS payment_methods,
            GROUP_CONCAT(DISTINCT p.payment_method SEPARATOR ' + ') AS payment_method
        FROM `tabLedgix Sale` s
        LEFT JOIN `tabLedgix Sale Payment` p ON p.parent = s.name
        WHERE s.docstatus = 1
        AND s.sale_date BETWEEN %s AND %s
        GROUP BY s.name
        ORDER BY s.creation DESC
        LIMIT 50
    """, (start_date, end_date), as_dict=True)


def _get_low_stock_items():
    return frappe.db.sql("""
        SELECT
            name,
            item_name,
            category,
            current_stock,
            minimum_stock,
            cost_price,
            selling_price
        FROM `tabLedgix Item`
        WHERE active = 1
        AND current_stock <= minimum_stock
        ORDER BY current_stock ASC, minimum_stock DESC
        LIMIT 10
    """, as_dict=True)


def _get_shift_summary(business_date, cash_sales, non_cash_sales):
    if not _doctype_exists("Ledgix POS Shift"):
        return {
            "status": "not_configured",
            "shift_id": None,
            "opened_by": None,
            "opening_cash": 0,
            "cash_sales": flt(cash_sales),
            "non_cash_sales": flt(non_cash_sales),
            "expected_cash": flt(cash_sales),
            "variance": 0,
        }

    row = frappe.db.sql("""
        SELECT
            name,
            status,
            opened_by,
            opening_cash,
            expected_cash,
            cash_sales,
            non_cash_sales,
            cash_variance,
            opening_time,
            closing_time
        FROM `tabLedgix POS Shift`
        WHERE docstatus < 2
        ORDER BY
            CASE WHEN status = 'Open' THEN 0 ELSE 1 END,
            COALESCE(opening_time, creation) DESC
        LIMIT 1
    """, as_dict=True)

    if not row:
        return {
            "status": "closed",
            "shift_id": None,
            "opened_by": None,
            "opening_cash": 0,
            "cash_sales": flt(cash_sales),
            "non_cash_sales": flt(non_cash_sales),
            "expected_cash": flt(cash_sales),
            "variance": 0,
        }

    shift = row[0]
    opening_cash = flt(shift.opening_cash)
    shift_cash_sales = flt(shift.cash_sales) or flt(cash_sales)
    shift_non_cash_sales = flt(shift.non_cash_sales) or flt(non_cash_sales)
    expected_cash = flt(shift.expected_cash) or opening_cash + shift_cash_sales

    return {
        "status": str(shift.status or "").lower() or "closed",
        "shift_id": shift.name,
        "opened_by": shift.opened_by,
        "opening_cash": opening_cash,
        "cash_sales": shift_cash_sales,
        "non_cash_sales": shift_non_cash_sales,
        "expected_cash": expected_cash,
        "variance": flt(shift.cash_variance),
    }


def _get_recent_risk_activity(start_date, end_date):
    activity = []

    sales = frappe.db.sql("""
        SELECT name, invoice_number, sale_date AS date_value, total_amount AS amount, creation
        FROM `tabLedgix Sale`
        WHERE docstatus = 1
        AND sale_date BETWEEN %s AND %s
        ORDER BY creation DESC
        LIMIT 5
    """, (start_date, end_date), as_dict=True)
    for row in sales:
        activity.append({
            "document": row.invoice_number or row.name,
            "type": "Sale",
            "amount": flt(row.amount),
            "qty": None,
            "date": str(row.date_value),
            "risk": "normal",
            "creation": row.creation,
        })

    returns = frappe.db.sql("""
        SELECT name, total_amount AS amount, creation
        FROM `tabLedgix Sales Return`
        WHERE docstatus = 1
        AND DATE(creation) BETWEEN %s AND %s
        ORDER BY creation DESC
        LIMIT 5
    """, (start_date, end_date), as_dict=True)
    for row in returns:
        activity.append({
            "document": row.name,
            "type": "Return",
            "amount": flt(row.amount),
            "qty": None,
            "date": str(row.creation),
            "risk": "return",
            "creation": row.creation,
        })

    cancelled_sales = frappe.db.sql("""
        SELECT name, invoice_number, total_amount AS amount, modified AS creation
        FROM `tabLedgix Sale`
        WHERE docstatus = 2
        AND DATE(modified) BETWEEN %s AND %s
        ORDER BY modified DESC
        LIMIT 5
    """, (start_date, end_date), as_dict=True)
    for row in cancelled_sales:
        activity.append({
            "document": row.invoice_number or row.name,
            "type": "Cancelled",
            "amount": flt(row.amount),
            "qty": None,
            "date": str(row.creation),
            "risk": "cancel",
            "creation": row.creation,
        })

    if _doctype_exists("Ledgix Stock Movement"):
        adjustments = frappe.db.sql("""
            SELECT name, quantity, movement_date AS creation
            FROM `tabLedgix Stock Movement`
            WHERE docstatus = 1
            AND movement_type = 'ADJUSTMENT'
            AND DATE(movement_date) BETWEEN %s AND %s
            ORDER BY movement_date DESC
            LIMIT 5
        """, (start_date, end_date), as_dict=True)
        for row in adjustments:
            activity.append({
                "document": row.name,
                "type": "Adjustment",
                "amount": None,
                "qty": flt(row.quantity),
                "date": str(row.creation),
                "risk": "adjustment",
                "creation": row.creation,
            })

    purchases = frappe.db.sql("""
        SELECT name, invoice_number, purchase_date AS date_value, creation
        FROM `tabLedgix Purchase`
        WHERE docstatus = 1
        AND purchase_date BETWEEN %s AND %s
        ORDER BY creation DESC
        LIMIT 5
    """, (start_date, end_date), as_dict=True)
    for row in purchases:
        activity.append({
            "document": row.invoice_number or row.name,
            "type": "Purchase",
            "amount": None,
            "qty": None,
            "date": str(row.date_value),
            "risk": "normal",
            "creation": row.creation,
        })

    activity.sort(key=lambda row: row.get("creation") or "", reverse=True)
    for row in activity:
        row.pop("creation", None)
    return activity[:5]


def _get_quick_actions():
    return [
        {"label": "New Sale", "route": "/app/ledgix-pos", "icon": "sale", "disabled": False},
        {"label": "New Purchase", "route": "/app/ledgix_operations?module=purchases", "icon": "purchase", "disabled": False},
        {"label": "Add Item", "route": "/app/ledgix_operations?module=products", "icon": "item", "disabled": False},
        {"label": "Open/Close Shift", "route": None, "icon": "shift", "disabled": True, "disabled_label": "Coming Next"},
        {"label": "Reports", "route": "/app/ledgix-reports", "icon": "report", "disabled": False},
        {"label": "Inventory Alerts", "route": "/app/ledgix-reports?report=inventory", "icon": "stock", "disabled": False},
    ]


@frappe.whitelist()
def get_dashboard_boot_data(days=7, from_date=None, to_date=None):
    require_ledgix_manager_or_above()

    return get_decision_dashboard_data(days=days, from_date=from_date, to_date=to_date)


# ============================================================
# BACKWARD-COMPATIBILITY APIs
# ============================================================

@frappe.whitelist()
def get_dashboard_data():
    require_ledgix_manager_or_above()

    data = get_decision_dashboard_data(days=1)
    return {
        "sales": {
            "today_sales": data["executive"]["revenue"],
            "today_profit": data["executive"]["profit"],
            "invoice_count": data["executive"]["invoice_count"],
            "items_sold": data["executive"]["items_sold"],
            "net_sales": data["executive"]["net_sales"],
        },
        "returns": {
            "count": data["executive"]["returns_count"],
            "amount": data["executive"]["returns_amount"],
        },
        "inventory": {
            "value": data.get("inventory", {}).get("inventory_value", 0),
            "low_stock": data.get("inventory", {}).get("low_stock", 0),
            "out_of_stock": data.get("inventory", {}).get("out_of_stock", 0),
            "total_items": data.get("inventory", {}).get("total_items", 0),
        },
        "purchase": {
            "today_purchase": data["executive"]["purchase_amount"],
        },
        "fast_moving_items": data["tables"]["fast_moving_items"],
    }


@frappe.whitelist()
def get_sales_trend(days=7, from_date=None, to_date=None):
    require_ledgix_manager_or_above()

    start_date, end_date = _date_range(days, from_date, to_date)
    rows = _get_sales_profit_trend(start_date, end_date)

    return [
        {
            "sale_date": row["date"],
            "sales": row["sales"],
            "profit": row["profit"],
        }
        for row in rows
    ]
