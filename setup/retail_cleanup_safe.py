from __future__ import annotations

"""Safe local cleanup for historical Ledgix demo/spike artifacts.

Submitted accounting/POS history is audit data and is never force-cancelled or
force-deleted here. User-facing masters are deleted when unlinked; otherwise
we disable/archive them when the DocType supports that state.
"""

import frappe
from frappe.model.delete_doc import check_if_doc_is_dynamically_linked, check_if_doc_is_linked

from ledgix_saas.setup import erpnext_demo_data as native
from ledgix_saas.setup import retail_local_hygiene as legacy

OLD_POS_PROFILES = tuple(
    dict.fromkeys((*legacy.OLD_POS_PROFILES, "Ledgix ERPNextPOS Spike"))
)


def _is_linked(doc) -> bool:
    try:
        check_if_doc_is_linked(doc)
        check_if_doc_is_dynamically_linked(doc)
        return False
    except frappe.LinkExistsError:
        return True


def _archive(doctype: str, name: str, archived: list[str], retained: list[str]) -> bool:
    meta = frappe.get_meta(doctype)
    if meta.has_field("disabled"):
        frappe.db.set_value(doctype, name, "disabled", 1, update_modified=False)
        archived.append(f"{doctype}:{name}")
        return True
    if meta.has_field("enabled"):
        frappe.db.set_value(doctype, name, "enabled", 0, update_modified=False)
        archived.append(f"{doctype}:{name}")
        return True
    retained.append(f"linked:{doctype}:{name}")
    return False


def _retire_master(
    doctype: str,
    name: str,
    removed: list[str],
    archived: list[str],
    retained: list[str],
) -> None:
    if not frappe.db.exists(doctype, name):
        return

    doc = frappe.get_doc(doctype, name)
    if _is_linked(doc):
        _archive(doctype, name, archived, retained)
        return

    # Masters used here are normally draft-style documents. Never cancel a
    # submitted document just to make local cleanup prettier.
    if getattr(doc, "docstatus", 0) == 1:
        retained.append(f"historical:{doctype}:{name}")
        return

    try:
        doc.delete(ignore_permissions=True)
        removed.append(f"{doctype}:{name}")
    except frappe.LinkExistsError:
        _archive(doctype, name, archived, retained)
    except Exception:
        # If ERPNext has another business rule preventing deletion, prefer an
        # inactive master over mutating linked history. Re-raise only when the
        # DocType has no safe inactive state.
        if not _archive(doctype, name, archived, retained):
            raise


def _retire_old_marker_transactions(
    seed: str,
    removed: list[str],
    retained: list[str],
) -> None:
    selectors = (
        ("Payment Entry", "custom_ledgix_client_payment_id"),
        ("POS Invoice", "custom_ledgix_client_return_id"),
        ("Sales Invoice", "custom_ledgix_client_return_id"),
        ("POS Invoice", "custom_ledgix_client_sale_id"),
        ("Sales Invoice", "custom_ledgix_client_sale_id"),
        ("Purchase Invoice", "custom_ledgix_client_purchase_invoice_id"),
        ("Purchase Receipt", "custom_ledgix_client_receipt_id"),
        ("Purchase Order", "custom_ledgix_client_purchase_id"),
        ("Stock Reconciliation", "custom_ledgix_client_stock_reconciliation_id"),
        ("Stock Entry", "custom_ledgix_client_stock_id"),
    )
    for doctype, fieldname in selectors:
        if not frappe.get_meta(doctype).has_field(fieldname):
            continue
        names = frappe.get_all(
            doctype,
            filters={fieldname: ["like", f"{seed}-%"]},
            pluck="name",
            order_by="creation desc",
            limit_page_length=0,
        )
        for name in names:
            doc = frappe.get_doc(doctype, name)
            if getattr(doc, "docstatus", 0) == 1:
                retained.append(f"historical:{doctype}:{name}")
                continue
            if _is_linked(doc):
                retained.append(f"linked:{doctype}:{name}")
                continue
            doc.delete(ignore_permissions=True)
            removed.append(f"{doctype}:{name}")


def _retire_old_pos_profiles(
    removed: list[str], archived: list[str], retained: list[str]
) -> None:
    # Historical POS Invoices/Openings/Closings can be tied to merge logs and
    # GL/stock history. Preserve that audit history and only retire the profile.
    for profile in OLD_POS_PROFILES:
        _retire_master("POS Profile", profile, removed, archived, retained)


def cleanup_old_local_artifacts() -> dict:
    native._local_only()
    old_user = frappe.session.user or "Administrator"
    frappe.set_user("Administrator")
    removed: list[str] = []
    archived: list[str] = []
    retained: list[str] = []
    try:
        _retire_old_marker_transactions(legacy.OLD_SEED, removed, retained)
        _retire_old_pos_profiles(removed, archived, retained)

        # Extension rows and prices are local demo metadata, not accounting
        # history; clear them before retiring the old LXD masters.
        old_tax_profiles = frappe.get_all(
            "Ledgix Item Tax Profile",
            filters={"erpnext_item": ["like", f"{legacy.OLD_ITEM_PREFIX}%"]},
            pluck="name",
            limit_page_length=0,
        )
        for name in old_tax_profiles:
            frappe.db.delete("Ledgix Item Tax Profile", {"name": name})
            removed.append(f"Ledgix Item Tax Profile:{name}")
        frappe.db.delete("Item Price", {"item_code": ["like", f"{legacy.OLD_ITEM_PREFIX}%"]})

        for name in frappe.get_all(
            "Item",
            filters={"item_code": ["like", f"{legacy.OLD_ITEM_PREFIX}%"]},
            pluck="name",
            limit_page_length=0,
        ):
            _retire_master("Item", name, removed, archived, retained)

        for doctype, names in (
            ("Customer", legacy.OLD_ONLY_CUSTOMERS),
            ("Supplier", legacy.OLD_ONLY_SUPPLIERS),
            ("Warehouse", legacy.OLD_WAREHOUSES),
            ("Price List", legacy.OLD_PRICE_LISTS),
            ("Item Group", legacy.OLD_ITEM_GROUPS),
            ("Customer Group", legacy.OLD_CUSTOMER_GROUPS),
            ("Supplier Group", legacy.OLD_SUPPLIER_GROUPS),
            ("Ledgix Tax Category", legacy.OLD_TAX_CATEGORIES),
        ):
            for name in names:
                _retire_master(doctype, name, removed, archived, retained)

        frappe.db.commit()
        return {
            "removed": sorted(set(removed)),
            "archived": sorted(set(archived)),
            "historical_retained": sorted(set(retained)),
        }
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.set_user(old_user)


__all__ = ["cleanup_old_local_artifacts"]
