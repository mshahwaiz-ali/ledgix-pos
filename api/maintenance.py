# ============================================================
# LEDGIX MAINTENANCE / RESET APIs
# ============================================================

import re

import frappe
from frappe import _
from frappe.utils.password import check_password


ALLOWED_RESET_ROLES = ("System Manager", "Ledgix Super Admin")
CONFIRMATION_PHRASE = "RESET LEDGIX"

LEDGIX_SERIES_PREFIXES = [
    "PUR-",
    "SAL-",
    "INV-",
    "RET-",
    "STK-",
    "LOT-",
    "SER-",
    "SHIFT-",
    "HOLD-",
    "ALLOC-",
]

LEDGIX_NUMBERED_DOCTYPES = {
    "PUR-": "Ledgix Purchase",
    "SAL-": "Ledgix Sale",
    "RET-": "Ledgix Sales Return",
    "STK-": "Ledgix Stock Movement",
    "LOT-": "Ledgix Stock Lot",
    "SER-": "Ledgix Stock Serial",
    "SHIFT-": "Ledgix POS Shift",
    "HOLD-": "Ledgix POS Hold",
    "ALLOC-": "Ledgix Stock Lot Allocation",
}

TRANSACTION_DOCTYPES_TO_CLEAR = [
    # Child / detail tables first
    "Ledgix Purchase Item",
    "Ledgix Sale Item",
    "Ledgix Sales Return Item",
    "Ledgix Sale Payment",
    "Ledgix POS Hold Item",
    "Ledgix POS Hold Payment",

    # Identity / allocation layer
    "Ledgix Stock Lot Allocation",
    "Ledgix Stock Serial",
    "Ledgix Stock Lot",

    # Main transaction docs
    "Ledgix Stock Movement",
    "Ledgix Sales Return",
    "Ledgix Sale",
    "Ledgix Purchase",
    "Ledgix POS Shift",
    "Ledgix POS Hold",
]

FRESH_TENANT_MASTER_DOCTYPES_TO_CLEAR = [
    # Business masters only. Actual Frappe Users/Roles/Settings are intentionally preserved.
    "Ledgix Item",
    "Ledgix Category",
    "Ledgix Customer",
    "Ledgix Supplier",
    "Ledgix User Profile",
]


def _user_has_allowed_role():
    user_roles = set(frappe.get_roles(frappe.session.user))
    return any(role in user_roles for role in ALLOWED_RESET_ROLES)


def _verify_reset_permission():
    if frappe.session.user == "Guest":
        frappe.throw(_("You must be logged in to run maintenance actions."))

    if not _user_has_allowed_role():
        frappe.throw(_("Only System Manager or Ledgix Super Admin can run this action."))


def _to_bool(value):
    return value in (1, True, "1", "true", "True", "yes", "Yes", "on")


def _verify_safety_inputs(backup_confirmed, confirmation_text, admin_password):
    if not _to_bool(backup_confirmed):
        frappe.throw(_("Please confirm that a backup has been taken."))

    if (confirmation_text or "").strip() != CONFIRMATION_PHRASE:
        frappe.throw(_("Type RESET LEDGIX exactly before running this action."))

    if not admin_password:
        frappe.throw(_("Admin password is required."))

    try:
        check_password(frappe.session.user, admin_password)
    except Exception:
        frappe.throw(_("Invalid admin password."))


def _doctype_exists(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def _get_count(doctype):
    if not _doctype_exists(doctype):
        return None
    return frappe.db.count(doctype)


def _delete_all_rows(doctype):
    if not _doctype_exists(doctype):
        return {"doctype": doctype, "status": "skipped", "reason": "DocType not found", "count": None}

    count = frappe.db.count(doctype)
    frappe.db.sql(f"DELETE FROM `tab{doctype}`")

    return {"doctype": doctype, "status": "cleared", "count": count}


def _get_max_existing_number(prefix, doctype):
    if not _doctype_exists(doctype):
        return 0

    rows = frappe.db.sql(
        f"""
        SELECT name
        FROM `tab{doctype}`
        WHERE name LIKE %s
        """,
        (prefix + "%",),
        as_dict=True,
    )

    max_number = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")

    for row in rows:
        match = pattern.match(row.name or "")
        if match:
            max_number = max(max_number, int(match.group(1)))

    return max_number


def _get_max_existing_invoice_number():
    if not _doctype_exists("Ledgix Sale"):
        return 0

    rows = frappe.db.sql(
        """
        SELECT invoice_number
        FROM `tabLedgix Sale`
        WHERE invoice_number LIKE 'INV-%'
        """,
        as_dict=True,
    )

    max_invoice = 0
    pattern = re.compile(r"^INV-(\d+)$")

    for row in rows:
        match = pattern.match(row.invoice_number or "")
        if match:
            max_invoice = max(max_invoice, int(match.group(1)))

    return max_invoice


def _reset_numbering_series_safely():
    deleted_series = frappe.db.sql(
        """
        SELECT name, current
        FROM `tabSeries`
        WHERE name LIKE 'PUR-%'
           OR name LIKE 'SAL-%'
           OR name LIKE 'INV-%'
           OR name LIKE 'RET-%'
           OR name LIKE 'STK-%'
           OR name LIKE 'LOT-%'
           OR name LIKE 'SER-%'
           OR name LIKE 'SHIFT-%'
           OR name LIKE 'HOLD-%'
           OR name LIKE 'ALLOC-%'
        ORDER BY name
        """,
        as_dict=True,
    )

    for prefix in LEDGIX_SERIES_PREFIXES:
        frappe.db.sql("DELETE FROM `tabSeries` WHERE `name` LIKE %s", (prefix + "%",))

    restored_series = []

    # Prevent duplicate names if old records still exist.
    for prefix, doctype in LEDGIX_NUMBERED_DOCTYPES.items():
        max_existing = _get_max_existing_number(prefix, doctype)

        if max_existing > 0:
            frappe.db.sql(
                """
                INSERT INTO `tabSeries` (`name`, `current`)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE `current` = VALUES(`current`)
                """,
                (prefix, max_existing),
            )
            restored_series.append({
                "name": prefix,
                "current": max_existing,
                "reason": f"Existing {doctype} records found",
            })

    max_invoice = _get_max_existing_invoice_number()
    if max_invoice > 0:
        frappe.db.sql(
            """
            INSERT INTO `tabSeries` (`name`, `current`)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE `current` = VALUES(`current`)
            """,
            ("INV-", max_invoice),
        )
        restored_series.append({
            "name": "INV-",
            "current": max_invoice,
            "reason": "Existing Ledgix Sale invoice numbers found",
        })

    return deleted_series, restored_series


def _reset_items_to_opening_stock():
    if not _doctype_exists("Ledgix Item"):
        return {"status": "skipped", "reason": "Ledgix Item DocType not found"}

    frappe.db.sql(
        """
        UPDATE `tabLedgix Item`
        SET
            current_stock = IFNULL(opening_stock, 0),
            stock_status = CASE
                WHEN IFNULL(opening_stock, 0) <= 0 THEN 'Out of Stock'
                WHEN IFNULL(opening_stock, 0) <= IFNULL(minimum_stock, 0) THEN 'Low Stock'
                ELSE 'In Stock'
            END
        """
    )

    return {"status": "reset", "message": "Item stock reset back to opening stock"}


def _reset_master_balances_after_transaction_wipe():
    result = []

    if _doctype_exists("Ledgix Customer"):
        frappe.db.sql("UPDATE `tabLedgix Customer` SET current_balance = 0")
        result.append({"doctype": "Ledgix Customer", "field": "current_balance", "value": 0})

    if _doctype_exists("Ledgix Supplier"):
        frappe.db.sql(
            """
            UPDATE `tabLedgix Supplier`
            SET current_balance = IFNULL(opening_balance, 0)
            """
        )
        result.append({"doctype": "Ledgix Supplier", "field": "current_balance", "value": "opening_balance"})

    return result


def _clear_doctypes(doctypes):
    results = []

    for doctype in doctypes:
        results.append(_delete_all_rows(doctype))

    return results


def _run_transaction_reset_core():
    cleared = _clear_doctypes(TRANSACTION_DOCTYPES_TO_CLEAR)
    item_stock_reset = _reset_items_to_opening_stock()
    balance_reset = _reset_master_balances_after_transaction_wipe()
    deleted_series, restored_series = _reset_numbering_series_safely()

    return {
        "cleared": cleared,
        "item_stock_reset": item_stock_reset,
        "balance_reset": balance_reset,
        "deleted_series_count": len(deleted_series),
        "restored_series": restored_series,
    }


def _run_fresh_tenant_core():
    transaction_result = _run_transaction_reset_core()
    masters_cleared = _clear_doctypes(FRESH_TENANT_MASTER_DOCTYPES_TO_CLEAR)
    deleted_series, restored_series = _reset_numbering_series_safely()

    return {
        "transaction_result": transaction_result,
        "masters_cleared": masters_cleared,
        "deleted_series_count": len(deleted_series),
        "restored_series": restored_series,
    }


def _log_maintenance_action(action, payload):
    frappe.logger("ledgix").info({
        "action": action,
        "user": frappe.session.user,
        "payload": payload,
    })


@frappe.whitelist()
def run_numbering_reset(backup_confirmed=0, confirmation_text=None, admin_password=None):
    _verify_reset_permission()
    _verify_safety_inputs(backup_confirmed, confirmation_text, admin_password)

    deleted_series, restored_series = _reset_numbering_series_safely()

    frappe.db.commit()
    frappe.clear_cache()

    result = {
        "status": "success",
        "message": "Numbering Reset completed successfully.",
        "deleted_series_count": len(deleted_series),
        "restored_series": restored_series,
    }
    _log_maintenance_action("Numbering Reset", result)

    return result


@frappe.whitelist()
def run_transaction_reset(backup_confirmed=0, confirmation_text=None, admin_password=None):
    _verify_reset_permission()
    _verify_safety_inputs(backup_confirmed, confirmation_text, admin_password)

    result = _run_transaction_reset_core()

    frappe.db.commit()
    frappe.clear_cache()

    result.update({
        "status": "success",
        "message": "Transaction Reset completed successfully.",
    })
    _log_maintenance_action("Transaction Reset", result)

    return result


@frappe.whitelist()
def run_prepare_fresh_tenant(backup_confirmed=0, confirmation_text=None, admin_password=None):
    _verify_reset_permission()
    _verify_safety_inputs(backup_confirmed, confirmation_text, admin_password)

    result = _run_fresh_tenant_core()

    frappe.db.commit()
    frappe.clear_cache()

    result.update({
        "status": "success",
        "message": "Prepare Fresh Tenant completed successfully.",
    })
    _log_maintenance_action("Prepare Fresh Tenant", result)

    return result
