from __future__ import annotations

"""Deterministic local demo data for the ERPNext-authoritative Ledgix product.

This module is intentionally opt-in and local-site only. It never runs from
install/migrate and never writes the frozen legacy Ledgix business DocTypes.
All operational masters, stock, buying, selling and payments are standard
ERPNext documents; Ledgix contributes only product metadata/tax mappings.
"""

import random
from datetime import datetime, time

import frappe
from frappe.utils import add_days, cint, flt, get_datetime, getdate, nowdate, today

from ledgix_saas.services import erpnext_buying_inventory, erpnext_pos, erpnext_selling
from ledgix_saas.setup import erpnext_tax_foundation

SEED = "LEDGIX-ERP-DEMO-V2"
SOURCE = "Ledgix Local Demo V2"
RETAIL_PRICE_LIST = "Ledgix Demo Retail"
WHOLESALE_PRICE_LIST = "Ledgix Demo Wholesale"
BUYING_PRICE_LIST = "Ledgix Demo Buying"
POS_PROFILE = "Ledgix Demo POS"

ITEM_GROUPS = (
    "Demo Bakery",
    "Demo Beverages",
    "Demo Grocery",
    "Demo Home & Personal",
    "Demo Electronics",
    "Demo Services",
)

# code | name | group | stock | tracking | cost | retail | wholesale | reorder | hs-style
ITEM_TEXT = """
LXD-BRD-001|Classic Milk Bread 400g|Demo Bakery|1|normal|118|175|158|24|1905.90
LXD-BRD-002|Whole Wheat Bread 400g|Demo Bakery|1|normal|132|195|176|20|1905.90
LXD-BRD-003|Seeded Multigrain Loaf|Demo Bakery|1|normal|192|285|255|14|1905.90
LXD-BRD-004|Burger Buns Pack of 6|Demo Bakery|1|normal|148|225|198|18|1905.90
LXD-CAK-001|Chocolate Fudge Cake Slice|Demo Bakery|1|normal|152|290|255|14|1905.90
LXD-CAK-002|Vanilla Celebration Cake 2lb|Demo Bakery|1|batch|1280|2050|1890|4|1905.90
LXD-BEV-001|Mineral Water 500ml|Demo Beverages|1|normal|42|70|58|40|2201.10
LXD-BEV-002|Classic Cola 500ml|Demo Beverages|1|normal|82|120|105|30|2202.10
LXD-BEV-003|Orange Juice 250ml|Demo Beverages|1|normal|96|155|135|24|2009.12
LXD-BEV-004|Cold Brew Iced Coffee 250ml|Demo Beverages|1|batch|145|245|220|12|2202.99
LXD-BEV-005|Green Tea 20 Bags|Demo Beverages|1|normal|235|345|305|10|0902.10
LXD-GRO-001|Premium Black Tea 250g|Demo Grocery|1|normal|420|595|535|10|0902.30
LXD-GRO-002|Fine Sugar 1kg|Demo Grocery|1|normal|142|175|158|25|1701.99
LXD-GRO-003|Iodized Salt 800g|Demo Grocery|1|normal|64|95|84|20|2501.00
LXD-GRO-004|Salted Butter 200g|Demo Grocery|1|normal|485|625|575|12|0405.10
LXD-GRO-005|Strawberry Preserve 450g|Demo Grocery|1|normal|365|525|475|10|2007.99
LXD-HOM-001|Dishwashing Liquid 500ml|Demo Home & Personal|1|normal|245|365|330|12|3402.20
LXD-HOM-002|Kitchen Towels 2 Roll|Demo Home & Personal|1|normal|210|325|290|12|4818.20
LXD-HOM-003|Hand Wash 250ml|Demo Home & Personal|1|normal|185|295|265|12|3401.30
LXD-HOM-004|Birthday Candle Set|Demo Home & Personal|1|normal|72|145|118|10|3406.00
LXD-HOM-005|Gift Box Medium|Demo Home & Personal|1|normal|285|495|430|8|4819.50
LXD-ELC-001|Digital Kitchen Scale|Demo Electronics|1|serial|2850|4490|4090|3|8423.81
LXD-ELC-002|USB Rechargeable Lamp|Demo Electronics|1|serial|1650|2490|2290|3|9405.42
LXD-SVC-001|Gift Wrapping Service|Demo Services|0|normal|0|250|200|0|SERV-DEMO
LXD-SVC-002|Local Delivery Service|Demo Services|0|normal|0|350|300|0|SERV-DEMO
LXD-SVC-003|Cake Message Service|Demo Services|0|normal|0|100|80|0|SERV-DEMO
""".strip()

CUSTOMERS = (
    ("Walk-in Customer", "Individual", "Demo Retail", 0),
    ("Ayesha Khan", "Individual", "Demo Retail", 0),
    ("Hamza Malik", "Individual", "Demo Retail", 0),
    ("Sara Ahmed", "Individual", "Demo Retail", 0),
    ("Usman Tariq", "Individual", "Demo Retail", 0),
    ("Noor Fatima", "Individual", "Demo Retail", 0),
    ("Greenline Offices", "Company", "Demo Trade", 120000),
    ("Morning Table Cafe", "Company", "Demo Trade", 150000),
    ("Northgate Hostel Mess", "Company", "Demo Trade", 250000),
    ("Urban Crust Cafe", "Company", "Demo Trade", 120000),
    ("Sapphire Event Studio", "Company", "Demo Trade", 180000),
    ("Central Learning Academy", "Company", "Demo Trade", 200000),
)

SUPPLIERS = (
    "Heritage Food Supply Co.",
    "BlueRiver Beverage Distribution",
    "FreshFields Grocery Supply",
    "PackPro Retail Supplies",
    "Nova Small Appliances",
    "City Wholesale Traders",
)

PAYMENT_MODES = (
    ("Cash", "Cash", False, True),
    ("Card", "Bank", True, False),
    ("Bank Transfer", "Bank", True, False),
    ("EasyPaisa", "Bank", True, False),
    ("JazzCash", "Bank", True, False),
)


def _items() -> list[dict]:
    rows = []
    for raw in ITEM_TEXT.splitlines():
        code, name, group, stock, tracking, cost, retail, wholesale, reorder, hs = raw.split("|")
        rows.append(
            {
                "code": code,
                "name": name,
                "group": group,
                "stock": cint(stock),
                "tracking": tracking,
                "cost": flt(cost),
                "retail": flt(retail),
                "wholesale": flt(wholesale),
                "reorder": flt(reorder),
                "hs": hs,
            }
        )
    return rows


ITEMS = _items()
ITEM_BY_CODE = {row["code"]: row for row in ITEMS}
NORMAL_STOCK_ITEMS = [row["code"] for row in ITEMS if row["stock"] and row["tracking"] == "normal"]
SERVICE_ITEMS = [row["code"] for row in ITEMS if not row["stock"]]


def _local_only() -> None:
    site = str(getattr(frappe.local, "site", "") or "").strip().lower()
    if not site.endswith(".local"):
        frappe.throw(
            f"{SEED} is local-demo tooling only. Refusing to run on site {site or '<unknown>'}."
        )


def _company() -> str:
    company = (
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if not company or not frappe.db.exists("Company", company):
        frappe.throw("Configure an ERPNext default Company before seeding Ledgix demo data.")
    return company


def _abbr(company: str) -> str:
    return frappe.db.get_value("Company", company, "abbr")


def _dt(date_value, hour: int, minute: int = 0):
    return get_datetime(datetime.combine(getdate(date_value), time(hour=hour, minute=minute)))


def _ean13(index: int) -> str:
    base = f"6291102{index:05d}"
    digits = [int(value) for value in base]
    check = (10 - ((sum(digits[::2]) + 3 * sum(digits[1::2])) % 10)) % 10
    return f"{base}{check}"


def _find_leaf_account(company: str, account_type: str, fallback_field: str | None = None) -> str:
    if fallback_field:
        account = frappe.db.get_value("Company", company, fallback_field)
        if account and frappe.db.exists("Account", {"name": account, "company": company, "is_group": 0, "disabled": 0}):
            return account
    account = frappe.db.get_value(
        "Account",
        {"company": company, "account_type": account_type, "is_group": 0, "disabled": 0},
        "name",
        order_by="name asc",
    )
    if not account:
        frappe.throw(f"A leaf {account_type} Account is required for {company} before demo seeding.")
    return account


def _ensure_uom(name: str) -> None:
    if not frappe.db.exists("UOM", name):
        frappe.get_doc({"doctype": "UOM", "uom_name": name, "enabled": 1}).insert(ignore_permissions=True)


def _ensure_tree_leaf(doctype: str, name: str, parent_field: str, parent: str, **values) -> str:
    if frappe.db.exists(doctype, name):
        return name
    payload = {"doctype": doctype, parent_field: parent, "is_group": 0, **values}
    if doctype == "Item Group":
        payload["item_group_name"] = name
    elif doctype == "Customer Group":
        payload["customer_group_name"] = name
    elif doctype == "Supplier Group":
        payload["supplier_group_name"] = name
    doc = frappe.get_doc(payload)
    doc.insert(ignore_permissions=True)
    return doc.name


def _group_root(doctype: str, parent_field: str, company: str | None = None) -> str:
    filters = {"is_group": 1}
    if company and frappe.get_meta(doctype).has_field("company"):
        filters["company"] = company
    rows = frappe.get_all(doctype, filters=filters, pluck="name", order_by="lft asc", limit=1)
    if not rows:
        frappe.throw(f"No root {doctype} exists.")
    return rows[0]


def _ensure_warehouse(company: str, warehouse_name: str) -> str:
    existing = frappe.db.get_value(
        "Warehouse", {"company": company, "warehouse_name": warehouse_name}, "name"
    )
    if existing:
        return existing
    parent = _group_root("Warehouse", "parent_warehouse", company)
    doc = frappe.get_doc(
        {
            "doctype": "Warehouse",
            "warehouse_name": warehouse_name,
            "company": company,
            "parent_warehouse": parent,
            "is_group": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_price_list(name: str, *, selling: int = 0, buying: int = 0) -> str:
    if frappe.db.exists("Price List", name):
        return name
    doc = frappe.get_doc(
        {
            "doctype": "Price List",
            "price_list_name": name,
            "currency": "PKR",
            "enabled": 1,
            "selling": selling,
            "buying": buying,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item_price(item_code: str, price_list: str, rate: float, *, selling: int = 0, buying: int = 0) -> str:
    existing = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list, "selling": selling, "buying": buying},
        "name",
    )
    if existing:
        return existing
    doc = frappe.get_doc(
        {
            "doctype": "Item Price",
            "item_code": item_code,
            "price_list": price_list,
            "price_list_rate": rate,
            "currency": "PKR",
            "selling": selling,
            "buying": buying,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item(row: dict, index: int) -> str:
    if frappe.db.exists("Item", row["code"]):
        return row["code"]
    payload = {
        "doctype": "Item",
        "item_code": row["code"],
        "item_name": row["name"],
        "item_group": row["group"],
        "stock_uom": "Nos",
        "is_stock_item": row["stock"],
        "is_sales_item": 1,
        "is_purchase_item": 1 if row["stock"] else 0,
        "disabled": 0,
        "barcodes": [{"barcode": _ean13(index)}],
    }
    if row["tracking"] == "batch":
        payload.update({"has_batch_no": 1, "create_new_batch": 0})
    elif row["tracking"] == "serial":
        payload.update({"has_serial_no": 1, "serial_no_series": f"{row['code']}-.#####"})
    doc = frappe.get_doc(payload)
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_reorder(item_code: str, warehouse: str, level: float) -> None:
    if level <= 0:
        return
    item = frappe.get_doc("Item", item_code)
    if any(row.warehouse == warehouse for row in item.get("reorder_levels") or []):
        return
    item.append(
        "reorder_levels",
        {
            "warehouse": warehouse,
            "warehouse_reorder_level": level,
            "warehouse_reorder_qty": max(level * 2, 1),
        },
    )
    item.save(ignore_permissions=True)


def _ensure_customer_group(name: str) -> str:
    root = _group_root("Customer Group", "parent_customer_group")
    return _ensure_tree_leaf("Customer Group", name, "parent_customer_group", root)


def _ensure_supplier_group(name: str) -> str:
    root = _group_root("Supplier Group", "parent_supplier_group")
    return _ensure_tree_leaf("Supplier Group", name, "parent_supplier_group", root)


def _ensure_customer(company: str, name: str, customer_type: str, group: str, credit_limit: float) -> str:
    if frappe.db.exists("Customer", name):
        return name
    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": customer_type,
            "customer_group": group,
            "territory": "All Territories",
        }
    )
    if credit_limit:
        doc.append("credit_limits", {"company": company, "credit_limit": credit_limit})
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_supplier(name: str, supplier_group: str) -> str:
    if frappe.db.exists("Supplier", name):
        return name
    doc = frappe.get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": name,
            "supplier_group": supplier_group,
            "supplier_type": "Company",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_mode(company: str, name: str, mode_type: str, account: str, requires_reference: bool, allow_change: bool) -> str:
    if frappe.db.exists("Mode of Payment", name):
        doc = frappe.get_doc("Mode of Payment", name)
    else:
        doc = frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": name, "type": mode_type})
    if doc.meta.has_field("custom_ledgix_requires_reference"):
        doc.custom_ledgix_requires_reference = 1 if requires_reference else 0
    if doc.meta.has_field("custom_ledgix_allow_change"):
        doc.custom_ledgix_allow_change = 1 if allow_change else 0
    existing = next((row for row in doc.get("accounts") or [] if row.company == company), None)
    if existing:
        existing.default_account = account
    else:
        doc.append("accounts", {"company": company, "default_account": account})
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_tax_mapping(item_code: str, hs_code: str) -> None:
    category = "Ledgix Demo Standard Tax"
    if not frappe.db.exists("Ledgix Tax Category", category):
        doc = frappe.new_doc("Ledgix Tax Category")
        doc.category_name = category
        doc.tax_type = "Sales Tax"
        doc.default_rate = 18
        doc.active = 1
        doc.insert(ignore_permissions=True)
    existing = frappe.db.get_value(
        "Ledgix Item Tax Profile", {"erpnext_item": item_code, "active": 1}, "name"
    )
    if existing:
        return
    doc = frappe.new_doc("Ledgix Item Tax Profile")
    doc.erpnext_item = item_code
    doc.tax_category = category
    doc.taxable = 1
    doc.active = 1
    doc.needs_review = 0
    doc.tax_basis = "Transaction Value"
    doc.hs_code = hs_code
    doc.uom_for_fbr = "Numbers"
    doc.sales_type = "Goods at standard rate"
    doc.insert(ignore_permissions=True)


FBR_PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"


def _fbr_profile_state(company: str) -> dict:
    """Return non-secret V2 transport state for local demo safety checks."""

    if not frappe.db.exists("DocType", FBR_PROFILE_DOCTYPE):
        return {
            "exists": False,
            "name": "",
            "enabled": False,
            "mode": "Disabled",
            "submit_trigger": "Manual",
            "production_post_armed": False,
        }

    name = frappe.db.get_value(
        FBR_PROFILE_DOCTYPE,
        {"company": company},
        "name",
    )
    if not name:
        return {
            "exists": False,
            "name": "",
            "enabled": False,
            "mode": "Disabled",
            "submit_trigger": "Manual",
            "production_post_armed": False,
        }

    row = frappe.db.get_value(
        FBR_PROFILE_DOCTYPE,
        name,
        [
            "name",
            "enabled",
            "mode",
            "submit_trigger",
            "production_post_armed",
        ],
        as_dict=True,
    ) or {}
    return {
        "exists": True,
        "name": row.get("name") or name,
        "enabled": bool(cint(row.get("enabled"))),
        "mode": row.get("mode") or "Disabled",
        "submit_trigger": row.get("submit_trigger") or "Manual",
        "production_post_armed": bool(cint(row.get("production_post_armed"))),
    }


def _disable_fbr_transport() -> None:
    """Fail-close the company-scoped V2 profile for local demo generation."""

    company = _company()
    state = _fbr_profile_state(company)
    if not state["exists"]:
        return

    profile = frappe.get_doc(FBR_PROFILE_DOCTYPE, state["name"])
    profile.enabled = 0
    profile.mode = "Disabled"
    profile.submit_trigger = "Manual"
    profile.production_post_armed = 0
    profile.save(ignore_permissions=True)


def _ensure_pos_profile(company: str, warehouse: str, customer: str, bank_account: str, cash_account: str) -> str:
    if frappe.db.exists("POS Profile", POS_PROFILE):
        doc = frappe.get_doc("POS Profile", POS_PROFILE)
        return doc.name
    doc = frappe.get_doc(
        {
            "doctype": "POS Profile",
            "name": POS_PROFILE,
            "company": company,
            "warehouse": warehouse,
            "customer": customer,
            "selling_price_list": RETAIL_PRICE_LIST,
            "currency": "PKR",
            "disabled": 0,
            "payments": [
                {"mode_of_payment": "Cash", "default": 1},
                {"mode_of_payment": "Card", "default": 0},
                {"mode_of_payment": "Bank Transfer", "default": 0},
                {"mode_of_payment": "EasyPaisa", "default": 0},
                {"mode_of_payment": "JazzCash", "default": 0},
            ],
            "applicable_for_users": [{"user": "Administrator", "default": 1}],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _masters() -> dict:
    company = _company()
    _ensure_uom("Nos")
    item_root = _group_root("Item Group", "parent_item_group")
    for group in ITEM_GROUPS:
        _ensure_tree_leaf("Item Group", group, "parent_item_group", item_root)
    _ensure_customer_group("Demo Retail")
    _ensure_customer_group("Demo Trade")
    supplier_group = _ensure_supplier_group("Demo Suppliers")

    main = _ensure_warehouse(company, "Ledgix Demo Main Store")
    pos = _ensure_warehouse(company, "Ledgix Demo POS Floor")
    back = _ensure_warehouse(company, "Ledgix Demo Back Store")
    _ensure_price_list(RETAIL_PRICE_LIST, selling=1)
    _ensure_price_list(WHOLESALE_PRICE_LIST, selling=1)
    _ensure_price_list(BUYING_PRICE_LIST, buying=1)

    for index, row in enumerate(ITEMS, 1):
        _ensure_item(row, index)
        _ensure_item_price(row["code"], RETAIL_PRICE_LIST, row["retail"], selling=1)
        _ensure_item_price(row["code"], WHOLESALE_PRICE_LIST, row["wholesale"], selling=1)
        if row["stock"]:
            _ensure_item_price(row["code"], BUYING_PRICE_LIST, row["cost"], buying=1)
            _ensure_reorder(row["code"], pos, row["reorder"])
        _ensure_tax_mapping(row["code"], row["hs"])

    for name, customer_type, group, credit_limit in CUSTOMERS:
        _ensure_customer(company, name, customer_type, group, credit_limit)
    for supplier in SUPPLIERS:
        _ensure_supplier(supplier, supplier_group)

    cash_account = _find_leaf_account(company, "Cash", "default_cash_account")
    bank_account = _find_leaf_account(company, "Bank", "default_bank_account")
    for name, mode_type, requires_reference, allow_change in PAYMENT_MODES:
        account = cash_account if mode_type == "Cash" else bank_account
        _ensure_mode(company, name, mode_type, account, requires_reference, allow_change)

    _ensure_pos_profile(company, pos, "Walk-in Customer", bank_account, cash_account)
    _disable_fbr_transport()
    return {"company": company, "main": main, "pos": pos, "back": back}


def _purchase_cycle(company: str, warehouse: str, supplier: str, date_value, sequence: int, item_codes: list[str]):
    marker = f"{SEED}-BUY-{sequence:02d}"
    existing = frappe.db.get_value("Purchase Order", {"custom_ledgix_client_purchase_id": marker}, "name")
    if existing:
        return frappe.get_doc("Purchase Order", existing)
    lines = []
    for code in item_codes:
        row = ITEM_BY_CODE[code]
        qty = 180 if row["cost"] < 500 else 55
        lines.append(
            {
                "item_code": code,
                "qty": qty,
                "uom": "Nos",
                "rate": row["cost"] * (1 + ((sequence % 3) * 0.0125)),
                "warehouse": warehouse,
                "schedule_date": date_value,
            }
        )
    order = frappe.get_doc(
        {
            "doctype": "Purchase Order",
            "company": company,
            "supplier": supplier,
            "transaction_date": date_value,
            "schedule_date": date_value,
            "set_warehouse": warehouse,
            "custom_ledgix_client_purchase_id": marker,
            "custom_ledgix_buying_source": SOURCE,
            "items": lines,
        }
    )
    order.insert(ignore_permissions=True)
    order.submit()

    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
    receipt = make_purchase_receipt(order.name)
    receipt.posting_date = date_value
    receipt.posting_time = time(10, 30)
    receipt.set_posting_time = 1
    receipt.custom_ledgix_client_purchase_id = marker
    receipt.custom_ledgix_client_receipt_id = f"{marker}-REC"
    receipt.custom_ledgix_buying_source = SOURCE
    receipt.insert(ignore_permissions=True)
    receipt.submit()

    from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
    invoice = make_purchase_invoice(receipt.name)
    invoice.posting_date = add_days(date_value, 1)
    invoice.bill_date = date_value
    invoice.bill_no = f"DEMO-{sequence:04d}"
    invoice.custom_ledgix_client_purchase_id = marker
    invoice.custom_ledgix_client_purchase_invoice_id = f"{marker}-INV"
    invoice.custom_ledgix_buying_source = SOURCE
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return order


def _stock_entry(company: str, *, item_code: str, qty: float, date_value, purpose: str, source_warehouse=None,
                 target_warehouse=None, valuation_rate=None, batch_no=None, serial_numbers=None, marker: str):
    existing = frappe.db.get_value("Stock Entry", {"custom_ledgix_client_stock_id": marker}, "name")
    if existing:
        return frappe.get_doc("Stock Entry", existing)
    from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
    serial_no = ""
    if serial_numbers:
        serial_no = "\n".join(serial_numbers)
    kwargs = {
        "item_code": item_code,
        "qty": qty,
        "company": company,
        "do_not_save": True,
        "purpose": purpose,
        "use_serial_batch_fields": 1 if (batch_no or serial_no) else 0,
    }
    if source_warehouse:
        kwargs["from_warehouse"] = source_warehouse
    if target_warehouse:
        kwargs["to_warehouse"] = target_warehouse
    if valuation_rate is not None:
        kwargs["rate"] = valuation_rate
    if batch_no:
        kwargs["batch_no"] = batch_no
    if serial_no:
        kwargs["serial_no"] = serial_no
    doc = make_stock_entry(**kwargs)
    doc.posting_date = date_value
    doc.posting_time = time(11, 0)
    doc.set_posting_time = 1
    doc.custom_ledgix_client_stock_id = marker
    doc.custom_ledgix_stock_source = SOURCE
    doc.remarks = SOURCE
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


def _inventory(company: str, main: str, pos: str, back: str, base_date) -> None:
    normal = list(NORMAL_STOCK_ITEMS)
    for index, offset in enumerate((-86, -72, -56, -40, -23, -8), 1):
        subset = normal[(index - 1) % 3 :: 3] + normal[(index + 1) % 4 :: 4]
        subset = list(dict.fromkeys(subset))[:10]
        _purchase_cycle(
            company,
            main,
            SUPPLIERS[(index - 1) % len(SUPPLIERS)],
            add_days(base_date, offset),
            index,
            subset,
        )

    # Ensure every normal item has demonstrable stock even if not selected in the purchase rotation.
    for index, code in enumerate(normal, 1):
        if flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": main}, "actual_qty") or 0) <= 0:
            _stock_entry(
                company,
                item_code=code,
                qty=220,
                date_value=add_days(base_date, -84),
                purpose="Material Receipt",
                target_warehouse=main,
                valuation_rate=ITEM_BY_CODE[code]["cost"],
                marker=f"{SEED}-OPEN-{index:03d}",
            )
        transfer_qty = 120 if ITEM_BY_CODE[code]["cost"] < 500 else 35
        _stock_entry(
            company,
            item_code=code,
            qty=transfer_qty,
            date_value=add_days(base_date, -82),
            purpose="Material Transfer",
            source_warehouse=main,
            target_warehouse=pos,
            marker=f"{SEED}-POS-{index:03d}",
        )

    # Batch-tracked examples.
    for index, code in enumerate([row["code"] for row in ITEMS if row["tracking"] == "batch"], 1):
        batch = erpnext_buying_inventory.ensure_batch(code, f"LXD-BATCH-{index:03d}", manufacturing_date=add_days(base_date, -80))
        _stock_entry(
            company,
            item_code=code,
            qty=24,
            date_value=add_days(base_date, -79),
            purpose="Material Receipt",
            target_warehouse=pos,
            valuation_rate=ITEM_BY_CODE[code]["cost"],
            batch_no=batch,
            marker=f"{SEED}-BATCH-{index:03d}",
        )

    # Serial-tracked examples.
    for index, code in enumerate([row["code"] for row in ITEMS if row["tracking"] == "serial"], 1):
        serials = [f"{code}-DEMO-{n:03d}" for n in range(1, 9)]
        _stock_entry(
            company,
            item_code=code,
            qty=len(serials),
            date_value=add_days(base_date, -78),
            purpose="Material Receipt",
            target_warehouse=pos,
            valuation_rate=ITEM_BY_CODE[code]["cost"],
            serial_numbers=serials,
            marker=f"{SEED}-SERIAL-{index:03d}",
        )

    # A real warehouse movement into Back Store.
    for index, code in enumerate(normal[:4], 1):
        _stock_entry(
            company,
            item_code=code,
            qty=8,
            date_value=add_days(base_date, -35),
            purpose="Material Transfer",
            source_warehouse=main,
            target_warehouse=back,
            marker=f"{SEED}-BACK-{index:03d}",
        )


def _opening(company: str, date_value, sequence: int):
    marker = f"{SEED}:SHIFT:{sequence:02d}"
    existing = frappe.db.get_value(
        "POS Opening Entry", {"custom_ledgix_opening_notes": ["like", f"%{marker}%"], "docstatus": 1}, "name"
    )
    if existing:
        return frappe.get_doc("POS Opening Entry", existing)
    profile = frappe.get_doc("POS Profile", POS_PROFILE)
    balance_details = []
    for payment in erpnext_pos.payment_methods(profile):
        amount = 12000 + sequence * 250 if payment["type"] == "Cash" else 0
        balance_details.append({"mode_of_payment": payment["name"], "opening_amount": amount})
    doc = frappe.get_doc(
        {
            "doctype": "POS Opening Entry",
            "period_start_date": _dt(date_value, 8, 45),
            "posting_date": date_value,
            "company": company,
            "pos_profile": POS_PROFILE,
            "user": "Administrator",
            "custom_ledgix_opening_notes": f"{SOURCE} {marker}",
            "balance_details": balance_details,
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


def _pos_invoice(company: str, warehouse: str, date_value, serial: int, customer: str, item_lines: list[tuple[str, float]],
                 payment_plan: list[tuple[str, float]], discount_percent: float = 0):
    client_id = f"{SEED}-POSSALE-{serial:04d}"
    existing = frappe.db.get_value("POS Invoice", {"custom_ledgix_client_sale_id": client_id, "docstatus": 1}, "name")
    if existing:
        return frappe.get_doc("POS Invoice", existing)
    cart = [{"item": code, "qty": qty, "warehouse": warehouse} for code, qty in item_lines]
    invoice = erpnext_pos.build_pos_invoice(
        cart_items=cart,
        customer=customer,
        price_list=RETAIL_PRICE_LIST,
        discount_type="Percent",
        discount_value=discount_percent,
        client_sale_id=client_id,
        allow_rate_override=False,
        source=SOURCE,
        company=company,
        pos_profile=POS_PROFILE,
    )
    invoice.posting_date = date_value
    invoice.posting_time = time(9 + (serial % 10), (serial * 7) % 60)
    invoice.set_posting_time = 1
    invoice.set("payments", [])
    total = flt(invoice.rounded_total or invoice.grand_total, 2)
    allocated = 0.0
    methods = {row["name"]: row for row in erpnext_pos.payment_methods(frappe.get_doc("POS Profile", POS_PROFILE))}
    for index, (mode, fraction) in enumerate(payment_plan):
        amount = flt(total - allocated, 2) if index == len(payment_plan) - 1 else flt(total * fraction, 2)
        allocated += amount
        policy = methods[mode]
        invoice.append(
            "payments",
            {
                "mode_of_payment": mode,
                "amount": amount,
                "account": policy["account"],
                "type": policy["type"],
                "default": 1 if policy["default"] else 0,
                "reference_no": f"DEMO-{mode[:3].upper()}-{serial:06d}" if policy["requires_reference"] else "",
            },
        )
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def _close_opening(opening, sequence: int):
    existing = frappe.db.get_value("POS Closing Entry", {"pos_opening_entry": opening.name, "docstatus": 1}, "name")
    if existing:
        return frappe.get_doc("POS Closing Entry", existing)
    from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening
    closing = make_closing_entry_from_opening(opening)
    closing.custom_ledgix_closing_notes = f"{SOURCE}; demo variance {(-20, 0, 15)[sequence % 3]:+d}"
    for row in closing.payment_reconciliation:
        row.closing_amount = flt(row.expected_amount)
    closing.insert(ignore_permissions=True)
    closing.submit()
    return closing


def _retail_sales(company: str, warehouse: str, base_date) -> list:
    rng = random.Random(260917)
    customer_pool = ["Walk-in Customer"] * 4 + ["Ayesha Khan", "Hamza Malik", "Sara Ahmed", "Usman Tariq", "Noor Fatima"]
    plans = (
        [("Cash", 1.0)],
        [("Card", 1.0)],
        [("EasyPaisa", 1.0)],
        [("JazzCash", 1.0)],
        [("Bank Transfer", 1.0)],
        [("Cash", 0.4), ("Card", 0.6)],
        [("Cash", 0.25), ("EasyPaisa", 0.75)],
    )
    invoices = []
    serial = 1
    for shift_no, offset in enumerate(range(-84, 0, 7), 1):
        date_value = add_days(base_date, offset)
        opening = _opening(company, date_value, shift_no)
        for slot in range(9):
            chosen = rng.sample(NORMAL_STOCK_ITEMS, 2 + ((serial + slot) % 3))
            lines = [(code, 1 + rng.randint(0, 2)) for code in chosen]
            if serial % 13 == 0:
                lines.append((SERVICE_ITEMS[serial % len(SERVICE_ITEMS)], 1))
            invoices.append(
                _pos_invoice(
                    company,
                    warehouse,
                    date_value,
                    serial,
                    rng.choice(customer_pool),
                    lines,
                    plans[(serial - 1) % len(plans)],
                    5 if serial % 11 == 0 else (7.5 if serial % 29 == 0 else 0),
                )
            )
            serial += 1
        _close_opening(opening, shift_no)
    return invoices


def _b2b_invoice(company: str, warehouse: str, date_value, sequence: int, customer: str, lines: list[tuple[str, float]]):
    client_id = f"{SEED}-B2B-{sequence:03d}"
    existing = frappe.db.get_value("Sales Invoice", {"custom_ledgix_client_sale_id": client_id, "docstatus": 1}, "name")
    if existing:
        return frappe.get_doc("Sales Invoice", existing)
    invoice = erpnext_selling.build_sales_invoice(
        customer=customer,
        items=[{"item": code, "qty": qty, "warehouse": warehouse} for code, qty in lines],
        company=company,
        selling_price_list=WHOLESALE_PRICE_LIST,
        sale_channel="B2B",
        client_sale_id=client_id,
        posting_date=date_value,
        due_date=add_days(date_value, 21),
        discount_type="Percent",
        discount_value=5 if sequence % 5 == 0 else 0,
        update_stock=True,
        checkout_source=SOURCE,
    )
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def _customer_payment(invoice, amount: float, date_value, sequence: int):
    if amount <= 0:
        return None
    client_id = f"{SEED}-CUSTPAY-{sequence:03d}"
    existing = frappe.db.get_value("Payment Entry", {"custom_ledgix_client_payment_id": client_id, "docstatus": 1}, "name")
    if existing:
        return frappe.get_doc("Payment Entry", existing)
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    payment = get_payment_entry("Sales Invoice", invoice.name)
    payment.posting_date = date_value
    payment.mode_of_payment = "Bank Transfer"
    payment.custom_remarks = 1
    payment.remarks = SOURCE
    payment.custom_ledgix_client_payment_id = client_id
    payment.custom_ledgix_payment_source = SOURCE
    payment.reference_no = f"DEMO-IBFT-{sequence:05d}"
    payment.reference_date = date_value
    account = erpnext_selling._mode_account("Bank Transfer", invoice.company)
    payment.paid_to = account
    payment.paid_to_account_currency = erpnext_selling._account_currency(account)
    payment.paid_amount = amount
    payment.received_amount = amount
    payment.base_paid_amount = amount
    payment.base_received_amount = amount
    if payment.references:
        payment.references[0].allocated_amount = amount
    payment.insert(ignore_permissions=True)
    payment.submit()
    return payment


def _b2b_sales(company: str, warehouse: str, base_date) -> list:
    customers = [row[0] for row in CUSTOMERS if row[2] == "Demo Trade"]
    invoices = []
    for sequence in range(1, 13):
        date_value = add_days(base_date, -80 + sequence * 6)
        codes = NORMAL_STOCK_ITEMS[(sequence - 1) % 5 :: 5][:3]
        lines = [(code, 6 + ((sequence + index) % 8)) for index, code in enumerate(codes)]
        invoice = _b2b_invoice(company, warehouse, date_value, sequence, customers[(sequence - 1) % len(customers)], lines)
        invoices.append(invoice)
        invoice.reload()
        if sequence % 4 == 0:
            continue  # deliberately unpaid AR
        fraction = 0.5 if sequence % 3 == 0 else 1.0
        amount = flt(max(invoice.outstanding_amount, 0) * fraction, 2)
        _customer_payment(invoice, amount, add_days(date_value, 4), sequence)
    return invoices


def _pos_return(source, sequence: int, date_value):
    client_id = f"{SEED}-POSRET-{sequence:03d}"
    existing = frappe.db.get_value("POS Invoice", {"custom_ledgix_client_return_id": client_id, "docstatus": 1}, "name")
    if existing:
        return frappe.get_doc("POS Invoice", existing)
    from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return
    doc = make_sales_return(source.name)
    doc.set("items", [doc.items[0]])
    doc.items[0].qty = -1
    doc.posting_date = date_value
    doc.posting_time = time(15, sequence % 60)
    doc.set_posting_time = 1
    doc.custom_ledgix_sale_channel = "Retail"
    doc.custom_ledgix_checkout_source = SOURCE
    doc.custom_ledgix_client_return_id = client_id
    doc.custom_ledgix_return_reason = "Demo customer return - item unused and accepted after inspection."
    doc.remarks = doc.custom_ledgix_return_reason
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


def _b2b_return(source, sequence: int, date_value):
    client_id = f"{SEED}-B2BRET-{sequence:03d}"
    existing = frappe.db.get_value("Sales Invoice", {"custom_ledgix_client_return_id": client_id, "docstatus": 1}, "name")
    if existing:
        return frappe.get_doc("Sales Invoice", existing)
    from erpnext.controllers.sales_and_purchase_return import make_return_doc
    doc = make_return_doc("Sales Invoice", source.name)
    doc.payment_schedule = []
    doc.set("items", [doc.items[0]])
    doc.items[0].qty = -1
    doc.posting_date = date_value
    doc.custom_ledgix_sale_channel = "B2B"
    doc.custom_ledgix_client_return_id = client_id
    doc.custom_ledgix_checkout_source = SOURCE
    doc.remarks = "Demo B2B partial credit note - one unit returned."
    erpnext_tax_foundation.apply_tax_plan(doc, replace_managed_rows=True)
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


def _returns(retail: list, b2b: list, base_date) -> None:
    for sequence, source in enumerate(retail[8::23][:4], 1):
        _pos_return(source, sequence, min(add_days(source.posting_date, 4), getdate(base_date)))
    for sequence, source in enumerate(b2b[2::4][:3], 1):
        _b2b_return(source, sequence, min(add_days(source.posting_date, 5), getdate(base_date)))


def _shape_stock(company: str, warehouse: str, base_date) -> None:
    targets = ((NORMAL_STOCK_ITEMS[2], 0), (NORMAL_STOCK_ITEMS[5], 2), (NORMAL_STOCK_ITEMS[8], 5))
    for index, (code, target) in enumerate(targets, 1):
        current = flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": warehouse}, "actual_qty") or 0)
        if current <= target:
            continue
        _stock_entry(
            company,
            item_code=code,
            qty=current - target,
            date_value=add_days(base_date, -1),
            purpose="Material Issue",
            source_warehouse=warehouse,
            marker=f"{SEED}-SHAPE-{index:03d}",
        )


def inspect_site() -> dict:
    """Non-destructive pre-seed snapshot used before backup/cleanup."""
    _local_only()
    company = _company()
    doctypes = (
        "Item", "Customer", "Supplier", "Purchase Order", "Purchase Receipt", "Purchase Invoice",
        "Sales Invoice", "POS Invoice", "Payment Entry", "Stock Entry", "Stock Reconciliation",
        "POS Opening Entry", "POS Closing Entry", "Ledgix FBR Submission Log",
    )
    counts = {doctype: frappe.db.count(doctype) for doctype in doctypes if frappe.db.exists("DocType", doctype)}
    return {
        "site": frappe.local.site,
        "company": company,
        "counts": counts,
        "legacy_retirement_status": frappe.db.get_single_value("Ledgix Legacy Retirement State", "status")
        if frappe.db.exists("DocType", "Ledgix Legacy Retirement State") else "Not Installed",
        "fbr_mode": _fbr_profile_state(company)["mode"],
        "demo_seed": SEED,
        "demo_present": bool(
            frappe.db.exists("POS Invoice", {"custom_ledgix_client_sale_id": ["like", f"{SEED}-%"]})
            or frappe.db.exists("Sales Invoice", {"custom_ledgix_client_sale_id": ["like", f"{SEED}-%"]})
        ),
    }


def verify() -> dict:
    _local_only()
    company = _company()
    pos_profile = frappe.db.exists("POS Profile", POS_PROFILE)
    pos_sales = frappe.db.count("POS Invoice", {"custom_ledgix_client_sale_id": ["like", f"{SEED}-%"], "docstatus": 1, "is_return": 0})
    pos_returns = frappe.db.count("POS Invoice", {"custom_ledgix_client_return_id": ["like", f"{SEED}-%"], "docstatus": 1, "is_return": 1})
    b2b_sales = frappe.db.count("Sales Invoice", {"custom_ledgix_client_sale_id": ["like", f"{SEED}-%"], "docstatus": 1, "is_return": 0})
    b2b_returns = frappe.db.count("Sales Invoice", {"custom_ledgix_client_return_id": ["like", f"{SEED}-%"], "docstatus": 1, "is_return": 1})
    payments = frappe.db.count("Payment Entry", {"custom_ledgix_client_payment_id": ["like", f"{SEED}-%"], "docstatus": 1})
    purchases = frappe.db.count("Purchase Invoice", {"custom_ledgix_client_purchase_invoice_id": ["like", f"{SEED}-%"], "docstatus": 1})
    stock_entries = frappe.db.count("Stock Entry", {"custom_ledgix_client_stock_id": ["like", f"{SEED}-%"], "docstatus": 1})
    trade_customers = [row[0] for row in CUSTOMERS if row[2] == "Demo Trade"]
    outstanding = flt(sum(flt(frappe.db.get_value("Customer", customer, "outstanding_amount") or 0) for customer in trade_customers), 2)
    negative = frappe.db.sql(
        """select item_code, warehouse, actual_qty from `tabBin`
           where warehouse like %s and actual_qty < -0.001 order by item_code, warehouse""",
        ("Ledgix Demo%",),
        as_dict=True,
    )
    fbr_state = _fbr_profile_state(company)
    fbr_safe = (
        not fbr_state["enabled"]
        and fbr_state["mode"] == "Disabled"
        and not fbr_state["production_post_armed"]
    )
    result = {
        "seed": SEED,
        "company": company,
        "items": frappe.db.count("Item", {"item_code": ["like", "LXD-%"]}),
        "customers": sum(1 for row in CUSTOMERS if frappe.db.exists("Customer", row[0])),
        "suppliers": sum(1 for name in SUPPLIERS if frappe.db.exists("Supplier", name)),
        "pos_profile": POS_PROFILE if pos_profile else None,
        "pos_sales": pos_sales,
        "b2b_sales": b2b_sales,
        "total_sales": pos_sales + b2b_sales,
        "pos_returns": pos_returns,
        "b2b_returns": b2b_returns,
        "payments": payments,
        "purchase_invoices": purchases,
        "stock_entries": stock_entries,
        "trade_outstanding": outstanding,
        "negative_demo_bins": negative,
        "fbr_transport_disabled": fbr_safe,
    }
    result["ok"] = bool(
        result["items"] >= 20
        and result["customers"] >= 8
        and result["suppliers"] >= 5
        and result["total_sales"] >= 100
        and result["pos_returns"] >= 3
        and result["b2b_returns"] >= 2
        and result["purchase_invoices"] >= 6
        and result["payments"] >= 6
        and not negative
        and fbr_safe
    )
    return result


def seed() -> dict:
    """Seed deterministic ERPNext-native demo data on a .local site only."""
    _local_only()
    old_user = frappe.session.user or "Administrator"
    frappe.set_user("Administrator")
    base_date = getdate(today())
    try:
        _disable_fbr_transport()
        context = _masters()
        _inventory(context["company"], context["main"], context["pos"], context["back"], base_date)
        retail = _retail_sales(context["company"], context["pos"], base_date)
        b2b = _b2b_sales(context["company"], context["pos"], base_date)
        _returns(retail, b2b, base_date)
        _shape_stock(context["company"], context["pos"], base_date)
        result = verify()
        if not result["ok"]:
            frappe.throw(f"ERPNext demo verification failed: {result}")
        frappe.db.commit()
        return {"created": True, **result}
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.set_user(old_user)


def cleanup_seed_transactions() -> dict:
    """Remove only V2 demo transactions, never arbitrary user/test data or frozen legacy ledgers."""
    _local_only()
    old_user = frappe.session.user or "Administrator"
    frappe.set_user("Administrator")
    removed = []
    try:
        # Child/dependent accounting and returns first.
        selectors = (
            ("Payment Entry", "custom_ledgix_client_payment_id"),
            ("POS Invoice", "custom_ledgix_client_return_id"),
            ("Sales Invoice", "custom_ledgix_client_return_id"),
            ("POS Closing Entry", None),
            ("POS Invoice", "custom_ledgix_client_sale_id"),
            ("Sales Invoice", "custom_ledgix_client_sale_id"),
            ("Purchase Invoice", "custom_ledgix_client_purchase_invoice_id"),
            ("Purchase Receipt", "custom_ledgix_client_receipt_id"),
            ("Purchase Order", "custom_ledgix_client_purchase_id"),
            ("Stock Reconciliation", "custom_ledgix_client_stock_reconciliation_id"),
            ("Stock Entry", "custom_ledgix_client_stock_id"),
        )
        demo_openings = frappe.get_all(
            "POS Opening Entry",
            filters={"custom_ledgix_opening_notes": ["like", f"%{SEED}%"]},
            pluck="name",
            limit_page_length=0,
        )
        for doctype, fieldname in selectors:
            if doctype == "POS Closing Entry":
                names = frappe.get_all(
                    doctype,
                    filters={"pos_opening_entry": ["in", demo_openings]} if demo_openings else {"name": "__none__"},
                    pluck="name",
                    limit_page_length=0,
                )
            else:
                names = frappe.get_all(
                    doctype,
                    filters={fieldname: ["like", f"{SEED}-%"]},
                    pluck="name",
                    order_by="creation desc",
                    limit_page_length=0,
                )
            for name in names:
                doc = frappe.get_doc(doctype, name)
                if doc.docstatus == 1:
                    doc.cancel()
                doc.delete(ignore_permissions=True)
                removed.append(f"{doctype}:{name}")
        for name in demo_openings:
            if not frappe.db.exists("POS Opening Entry", name):
                continue
            doc = frappe.get_doc("POS Opening Entry", name)
            if doc.docstatus == 1:
                doc.cancel()
            doc.delete(ignore_permissions=True)
            removed.append(f"POS Opening Entry:{name}")
        frappe.db.commit()
        return {"removed": len(removed), "documents": removed, "seed": SEED}
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.set_user(old_user)
