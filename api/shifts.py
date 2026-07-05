# ============================================================
# LEDGIX POS SHIFT APIs
# ============================================================
# Shift opening/closing and active shift summary helpers.

import frappe
from frappe.utils import flt
from ledgix_saas.api.security import has_any_role, require_ledgix_cashier_or_above

# ============================================================
# POS SHIFT APIs
# ============================================================

def _has_field(doctype, fieldname):
    return frappe.get_meta(doctype).has_field(fieldname)


def _set_if_field(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        doc.set(fieldname, value)


def _get_sale_shift_field():
    meta = frappe.get_meta("Ledgix Sale")

    for field in meta.fields:
        if field.fieldtype == "Link" and field.options == "Ledgix POS Shift":
            return field.fieldname

    if meta.has_field("pos_shift"):
        return "pos_shift"

    if meta.has_field("shift"):
        return "shift"

    return None


def _get_shift_sales_summary(shift_name):
    shift_field = _get_sale_shift_field()

    if not shift_field:
        return {
            "total_sales": 0,
            "cash_sales": 0,
            "non_cash_sales": 0,
            "invoice_count": 0
        }

    sales = frappe.db.sql(f"""
        SELECT
            name,
            COALESCE(grand_total, total_amount, 0) AS sale_total
        FROM `tabLedgix Sale`
        WHERE
            docstatus = 1
            AND `{shift_field}` = %s
    """, (shift_name,), as_dict=True)

    total_sales = 0
    cash_sales = 0
    non_cash_sales = 0

    for sale in sales:
        sale_total = flt(sale.sale_total)
        total_sales += sale_total

        cash_amount = 0
        non_cash_amount = 0
        payment_rows_found = False

        sale_doc = frappe.get_doc("Ledgix Sale", sale.name)

        for field in sale_doc.meta.fields:
            if field.fieldtype != "Table":
                continue

            child_rows = sale_doc.get(field.fieldname) or []

            if not child_rows:
                continue

            for row in child_rows:
                row_dict = row.as_dict()

                method = (
                    row_dict.get("payment_method")
                    or row_dict.get("method")
                    or row_dict.get("mode_of_payment")
                    or ""
                )

                amount = (
                    row_dict.get("amount")
                    or row_dict.get("paid_amount")
                    or row_dict.get("payment_amount")
                    or 0
                )

                if method:
                    payment_rows_found = True

                    if str(method).strip().lower() == "cash":
                        cash_amount += flt(amount)
                    else:
                        non_cash_amount += flt(amount)

        if payment_rows_found:
            cash_required = max(sale_total - non_cash_amount, 0)
            cash_sales += min(cash_amount, cash_required)
            non_cash_sales += min(non_cash_amount, sale_total)
        else:
            cash_sales += sale_total

    return {
        "total_sales": flt(total_sales),
        "cash_sales": flt(cash_sales),
        "non_cash_sales": flt(non_cash_sales),
        "invoice_count": len(sales)
    }


def _get_open_shift_for_user(user=None):
    user = user or frappe.session.user
    filters = {"status": "Open", "docstatus": 0}

    if _has_field("Ledgix POS Shift", "opened_by"):
        filters["opened_by"] = user

    return frappe.db.get_value(
        "Ledgix POS Shift",
        filters,
        "name",
        order_by="creation desc"
    )


@frappe.whitelist()
def get_active_shift_info():
    require_ledgix_cashier_or_above()

    shift_name = _get_open_shift_for_user()

    if not shift_name:
        return {
            "has_active_shift": False
        }

    shift = frappe.db.get_value(
        "Ledgix POS Shift",
        shift_name,
        [
            "name",
            "opening_cash",
            "expected_cash",
            "cash_sales",
            "non_cash_sales",
            "total_sales",
            "invoice_count"
        ],
        as_dict=True
    )

    summary = _get_shift_sales_summary(shift.name)

    expected_cash = flt(shift.opening_cash) + flt(summary["cash_sales"])

    return {
        "has_active_shift": True,
        "shift_id": shift.name,
        "opening_cash": flt(shift.opening_cash),
        "expected_cash": flt(expected_cash),
        "cash_sales": flt(summary["cash_sales"]),
        "non_cash_sales": flt(summary["non_cash_sales"]),
        "total_sales": flt(summary["total_sales"]),
        "invoice_count": summary["invoice_count"]
    }


@frappe.whitelist()
def open_pos_shift(opening_cash=0, notes=None):
    require_ledgix_cashier_or_above()

    existing_shift = _get_open_shift_for_user()

    if existing_shift:
        frappe.throw(f"Shift already open: {existing_shift}")

    shift = frappe.new_doc("Ledgix POS Shift")

    _set_if_field(shift, "opening_time", frappe.utils.now_datetime())
    _set_if_field(shift, "opened_by", frappe.session.user)
    _set_if_field(shift, "status", "Open")

    _set_if_field(shift, "opening_cash", flt(opening_cash))
    _set_if_field(shift, "expected_cash", flt(opening_cash))
    _set_if_field(shift, "actual_cash", 0)
    _set_if_field(shift, "cash_variance", 0)

    _set_if_field(shift, "cash_sales", 0)
    _set_if_field(shift, "non_cash_sales", 0)
    _set_if_field(shift, "total_sales", 0)
    _set_if_field(shift, "invoice_count", 0)

    if notes:
        _set_if_field(shift, "notes", notes)
        _set_if_field(shift, "opening_notes", notes)

    shift.insert(ignore_permissions=True)

    return {
        "success": True,
        "shift_id": shift.name,
        "opening_cash": flt(opening_cash),
        "expected_cash": flt(opening_cash),
        "message": "POS shift opened successfully"
    }


@frappe.whitelist()
def close_pos_shift(actual_cash=0, closing_notes=None, shift_name=None, notes=None):
    require_ledgix_cashier_or_above()

    if not closing_notes and notes:
        closing_notes = notes

    explicit_shift_name = bool(shift_name)

    if shift_name:
        shift_status = frappe.db.get_value(
            "Ledgix POS Shift",
            shift_name,
            ["status", "docstatus"],
            as_dict=True
        )

        if not shift_status:
            frappe.throw("Selected POS shift was not found")

        if shift_status.status != "Open" or shift_status.docstatus != 0:
            frappe.throw("Only open draft POS shifts can be closed")
    else:
        shift_name = _get_open_shift_for_user()

    if not shift_name:
        frappe.throw("No open POS shift found")

    shift = frappe.get_doc("Ledgix POS Shift", shift_name)

    if shift.status != "Open" or shift.docstatus != 0:
        frappe.throw("Only open draft POS shifts can be closed")

    if explicit_shift_name and _has_field("Ledgix POS Shift", "opened_by"):
        opened_by = getattr(shift, "opened_by", None)
        if opened_by and opened_by != frappe.session.user and not has_any_role(("System Manager", "Ledgix Admin")):
            frappe.throw("You can only close POS shifts opened by your own user.", frappe.PermissionError)

    summary = _get_shift_sales_summary(shift.name)

    opening_cash = flt(shift.opening_cash)
    cash_sales = flt(summary["cash_sales"])
    expected_cash = opening_cash + cash_sales
    actual_cash = flt(actual_cash)
    cash_variance = actual_cash - expected_cash

    _set_if_field(shift, "closing_time", frappe.utils.now_datetime())
    _set_if_field(shift, "closed_by", frappe.session.user)
    _set_if_field(shift, "status", "Closed")

    _set_if_field(shift, "cash_sales", cash_sales)
    _set_if_field(shift, "non_cash_sales", flt(summary["non_cash_sales"]))
    _set_if_field(shift, "total_sales", flt(summary["total_sales"]))
    _set_if_field(shift, "invoice_count", summary["invoice_count"])

    _set_if_field(shift, "expected_cash", expected_cash)
    _set_if_field(shift, "actual_cash", actual_cash)
    _set_if_field(shift, "cash_variance", cash_variance)

    if closing_notes:
        _set_if_field(shift, "closing_notes", closing_notes)

    shift.save(ignore_permissions=True)

    return {
        "success": True,
        "shift_id": shift.name,
        "opening_cash": opening_cash,
        "expected_cash": expected_cash,
        "actual_cash": actual_cash,
        "cash_variance": cash_variance,
        "cash_sales": cash_sales,
        "non_cash_sales": flt(summary["non_cash_sales"]),
        "total_sales": flt(summary["total_sales"]),
        "invoice_count": summary["invoice_count"],
        "message": "POS shift closed successfully"
    }
