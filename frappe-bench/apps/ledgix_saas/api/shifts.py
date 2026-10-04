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
    """Delegate direct Python calls to the current native POS authority."""
    from ledgix_saas.api import pos_compat
    return pos_compat.get_active_shift_info()


@frappe.whitelist()
def open_pos_shift(opening_cash=0, notes=None):
    """Delegate direct Python calls to the current native POS authority."""
    from ledgix_saas.api import pos_compat
    return pos_compat.open_pos_shift(opening_cash=opening_cash, notes=notes)


@frappe.whitelist()
def close_pos_shift(actual_cash=0, closing_notes=None, shift_name=None, notes=None):
    """Delegate direct Python calls to the current native POS authority."""
    from ledgix_saas.api import pos_compat
    return pos_compat.close_pos_shift(actual_cash=actual_cash, closing_notes=closing_notes, shift_name=shift_name, notes=notes)
