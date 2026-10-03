"""ERPNext Items selectable by current Ledgix transactions."""


def sellable_item_filters():
    # A fresh dictionary lets catalog callers add search/category filters safely.
    return {"disabled": 0, "is_sales_item": 1, "has_variants": 0}
