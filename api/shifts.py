# ============================================================
# LEDGIX POS SHIFT APIs
# ============================================================
# Shift lifecycle endpoints. Summary calculations deliberately delegate to the
# Ledgix POS Shift controller, whose source of truth is the submitted Payment
# ledger and Payment Method.method_type metadata.

import frappe
from frappe.utils import flt

from ledgix_saas.api.security import has_any_role, require_ledgix_cashier_or_above


def _has_field(doctype, fieldname):
    return frappe.get_meta(doctype).has_field(fieldname)


def _set_if_field(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        doc.set(fieldname, value)


def _get_open_shift_for_user(user=None):
    user = user or frappe.session.user
    filters = {"status": "Open", "docstatus": 0}
    if _has_field("Ledgix POS Shift", "opened_by"):
        filters["opened_by"] = user
    return frappe.db.get_value(
        "Ledgix POS Shift",
        filters,
        "name",
        order_by="creation desc",
    )


def _shift_summary(shift_name):
    shift = frappe.get_doc("Ledgix POS Shift", shift_name)
    shift.calculate_shift_summary()
    shift.calculate_expected_cash()
    shift.calculate_variance()
    return {
        "total_sales": flt(shift.total_sales, 2),
        "cash_sales": flt(shift.cash_sales, 2),
        "non_cash_sales": flt(shift.non_cash_sales, 2),
        "invoice_count": int(shift.invoice_count or 0),
        "expected_cash": flt(shift.expected_cash, 2),
        "actual_cash": flt(shift.actual_cash, 2),
        "cash_variance": flt(shift.cash_variance, 2),
    }


@frappe.whitelist()
def get_active_shift_info():
    require_ledgix_cashier_or_above()
    shift_name = _get_open_shift_for_user()
    if not shift_name:
        return {"has_active_shift": False}

    shift = frappe.get_doc("Ledgix POS Shift", shift_name)
    summary = _shift_summary(shift.name)
    return {
        "has_active_shift": True,
        "shift_id": shift.name,
        "opening_cash": flt(shift.opening_cash, 2),
        **summary,
    }


@frappe.whitelist()
def open_pos_shift(opening_cash=0, notes=None):
    require_ledgix_cashier_or_above()
    existing_shift = _get_open_shift_for_user()
    if existing_shift:
        frappe.throw(f"Shift already open: {existing_shift}")

    shift = frappe.new_doc("Ledgix POS Shift")
    _set_if_field(shift, "opening_cash", max(flt(opening_cash), 0))
    if notes:
        _set_if_field(shift, "opening_notes", notes)
    shift.insert(ignore_permissions=True)

    return {
        "success": True,
        "shift_id": shift.name,
        "opening_cash": flt(shift.opening_cash, 2),
        "expected_cash": flt(shift.expected_cash, 2),
        "message": "POS shift opened successfully",
    }


@frappe.whitelist()
def close_pos_shift(actual_cash=0, closing_notes=None, shift_name=None, notes=None):
    require_ledgix_cashier_or_above()
    if not closing_notes and notes:
        closing_notes = notes

    explicit_shift = bool(shift_name)
    shift_name = shift_name or _get_open_shift_for_user()
    if not shift_name:
        frappe.throw("No open POS shift found")

    shift = frappe.get_doc("Ledgix POS Shift", shift_name)
    if shift.status != "Open" or shift.docstatus != 0:
        frappe.throw("Only open draft POS shifts can be closed")

    if explicit_shift and shift.opened_by and shift.opened_by != frappe.session.user:
        if not has_any_role(("System Manager", "Ledgix Admin")):
            frappe.throw(
                "You can only close POS shifts opened by your own user.",
                frappe.PermissionError,
            )

    shift.actual_cash = max(flt(actual_cash), 0)
    shift.closing_notes = closing_notes or ""
    shift.close_shift()

    # Closing a till is a final accounting event, not an editable draft. The API
    # is already role-gated, so submit with server authority even though Cashier
    # has no general-purpose submit permission on the DocType form.
    shift.flags.ignore_permissions = True
    shift.submit()
    shift.reload()

    return {
        "success": True,
        "shift_id": shift.name,
        "opening_cash": flt(shift.opening_cash, 2),
        "expected_cash": flt(shift.expected_cash, 2),
        "actual_cash": flt(shift.actual_cash, 2),
        "cash_variance": flt(shift.cash_variance, 2),
        "cash_sales": flt(shift.cash_sales, 2),
        "non_cash_sales": flt(shift.non_cash_sales, 2),
        "total_sales": flt(shift.total_sales, 2),
        "invoice_count": int(shift.invoice_count or 0),
        "message": "POS shift closed successfully",
    }
