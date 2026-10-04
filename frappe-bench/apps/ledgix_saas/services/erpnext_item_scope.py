"""ERPNext Items selectable by current Ledgix transactions."""


def sellable_item_filters():
    # A fresh dictionary lets catalog callers add search/category filters safely.
    return {"disabled": 0, "is_sales_item": 1, "has_variants": 0}


def assert_sellable_item(item_code):
    import frappe
    from frappe.utils import cint
    item = frappe.db.get_value("Item", item_code, ["disabled", "is_sales_item", "has_variants"], as_dict=True)
    if not item or cint(item.get("disabled")) or not cint(item.get("is_sales_item")) or cint(item.get("has_variants")):
        frappe.throw("New sales require an enabled sales Item or concrete variant; variant templates are unsupported.")
    return item_code
