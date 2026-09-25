from __future__ import annotations

"""Realistic synthetic retail profile layered over the hardened ERPNext seeder.

This module keeps the tested transaction engine intact while replacing obvious
demo masters and user-facing references with a coherent operating supermarket
scenario. All people/business names and history are fictional local-test data.
"""

import frappe
from frappe.utils import getdate

from ledgix_saas.setup import erpnext_demo_data as native

SEED = "LEDGIX-RETAIL-OPERATING-V1"
SOURCE = "Crescent Mart Retail Operations"
RETAIL_PRICE_LIST = "Retail Selling"
WHOLESALE_PRICE_LIST = "Trade Selling"
BUYING_PRICE_LIST = "Standard Buying"
POS_PROFILE = "Main Counter POS"
ITEM_CODE_PREFIX = "CM-"
WAREHOUSE_POS_NAME = "Retail Floor"

CUSTOMER_GROUP_MAP = {
    "Demo Retail": "Retail Customers",
    "Demo Trade": "Trade Customers",
}
SUPPLIER_GROUP_MAP = {"Demo Suppliers": "Regular Suppliers"}
WAREHOUSE_MAP = {
    "Ledgix Demo Main Store": "Main Store",
    "Ledgix Demo POS Floor": WAREHOUSE_POS_NAME,
    "Ledgix Demo Back Store": "Back Store",
}
TAX_CATEGORY = "Standard Rated Goods"

ITEM_GROUPS = (
    "Bakery & Breakfast",
    "Beverages",
    "Dairy & Chilled",
    "Grocery & Pantry",
    "Snacks & Confectionery",
    "Household Care",
    "Personal Care",
    "Small Appliances",
    "Services",
)

# code | name | group | stock | tracking | cost | retail | wholesale | reorder | hs-style
ITEM_TEXT = """
CM-BRD-001|Fresh Milk Bread 400g|Bakery & Breakfast|1|normal|125|180|165|24|1905.90
CM-BRD-002|Whole Wheat Bread 400g|Bakery & Breakfast|1|normal|138|200|182|20|1905.90
CM-BRD-003|Burger Buns Pack of 6|Bakery & Breakfast|1|normal|155|230|210|18|1905.90
CM-BRD-004|Plain Rusk 300g|Bakery & Breakfast|1|normal|175|260|235|15|1905.40
CM-BRD-005|Chocolate Cake Slice|Bakery & Breakfast|1|normal|155|280|250|14|1905.90
CM-BRD-006|Vanilla Celebration Cake 2lb|Bakery & Breakfast|1|batch|1320|2100|1925|4|1905.90
CM-BEV-001|Mineral Water 500ml|Beverages|1|normal|43|70|60|42|2201.10
CM-BEV-002|Mineral Water 1.5L|Beverages|1|normal|78|120|105|30|2201.10
CM-BEV-003|Classic Cola 500ml|Beverages|1|normal|84|125|110|36|2202.10
CM-BEV-004|Lemon Lime Drink 500ml|Beverages|1|normal|84|125|110|30|2202.10
CM-BEV-005|Orange Juice 250ml|Beverages|1|normal|98|155|138|24|2009.12
CM-BEV-006|Mango Drink 250ml|Beverages|1|normal|92|145|128|24|2009.89
CM-BEV-007|Iced Coffee 250ml|Beverages|1|batch|150|245|220|12|2202.99
CM-DRY-001|Full Cream Milk 1L|Dairy & Chilled|1|batch|265|330|305|18|0401.20
CM-DRY-002|Plain Yogurt 500g|Dairy & Chilled|1|batch|205|280|255|14|0403.20
CM-DRY-003|Salted Butter 200g|Dairy & Chilled|1|normal|490|640|585|12|0405.10
CM-DRY-004|Cheese Slices Pack of 10|Dairy & Chilled|1|normal|460|625|575|10|0406.30
CM-DRY-005|Farm Eggs Pack of 12|Dairy & Chilled|1|normal|315|395|365|18|0407.21
CM-GRO-001|Premium Black Tea 250g|Grocery & Pantry|1|normal|425|600|545|12|0902.30
CM-GRO-002|Fine Sugar 1kg|Grocery & Pantry|1|normal|145|180|165|30|1701.99
CM-GRO-003|Iodized Salt 800g|Grocery & Pantry|1|normal|66|100|88|24|2501.00
CM-GRO-004|Basmati Rice 1kg|Grocery & Pantry|1|normal|310|390|355|24|1006.30
CM-GRO-005|Wheat Flour 5kg|Grocery & Pantry|1|normal|650|790|735|10|1101.00
CM-GRO-006|Cooking Oil 1L|Grocery & Pantry|1|normal|470|560|520|18|1512.19
CM-GRO-007|Red Lentils 1kg|Grocery & Pantry|1|normal|330|420|385|16|0713.40
CM-GRO-008|Chickpeas 1kg|Grocery & Pantry|1|normal|355|455|415|14|0713.20
CM-GRO-009|Strawberry Jam 450g|Grocery & Pantry|1|normal|370|530|485|10|2007.99
CM-GRO-010|Tomato Ketchup 800g|Grocery & Pantry|1|normal|395|560|510|12|2103.20
CM-SNK-001|Salted Potato Chips 70g|Snacks & Confectionery|1|normal|68|110|95|28|2005.20
CM-SNK-002|Masala Potato Chips 70g|Snacks & Confectionery|1|normal|68|110|95|28|2005.20
CM-SNK-003|Cream Biscuits 120g|Snacks & Confectionery|1|normal|72|120|105|24|1905.31
CM-SNK-004|Chocolate Wafer 60g|Snacks & Confectionery|1|normal|78|130|112|22|1905.32
CM-SNK-005|Milk Chocolate Bar 45g|Snacks & Confectionery|1|normal|115|180|158|18|1806.32
CM-SNK-006|Salted Peanuts 150g|Snacks & Confectionery|1|normal|155|235|210|16|2008.11
CM-SNK-007|Premium Dates 400g|Snacks & Confectionery|1|normal|430|620|565|10|0804.10
CM-HOM-001|Dishwashing Liquid 500ml|Household Care|1|normal|250|370|335|14|3402.20
CM-HOM-002|Laundry Detergent 1kg|Household Care|1|normal|420|565|520|12|3402.50
CM-HOM-003|Facial Tissue Box 150 Sheets|Household Care|1|normal|195|300|270|16|4818.20
CM-HOM-004|Kitchen Towels 2 Roll|Household Care|1|normal|215|330|298|12|4818.20
CM-HOM-005|Garbage Bags Medium 30 Pack|Household Care|1|normal|185|290|260|12|3923.21
CM-HOM-006|Aluminium Foil 20m|Household Care|1|normal|300|440|405|10|7607.19
CM-PER-001|Liquid Hand Wash 250ml|Personal Care|1|normal|190|300|270|14|3401.30
CM-PER-002|Daily Care Shampoo 360ml|Personal Care|1|normal|470|650|595|10|3305.10
CM-PER-003|Fresh Mint Toothpaste 140g|Personal Care|1|normal|225|340|305|14|3306.10
CM-PER-004|Bath Soap 120g|Personal Care|1|normal|115|175|155|20|3401.11
CM-PER-005|Body Spray 200ml|Personal Care|1|normal|390|560|510|10|3307.20
CM-ELC-001|Rechargeable Emergency Light|Small Appliances|1|serial|1750|2650|2425|3|9405.42
CM-ELC-002|Digital Kitchen Scale|Small Appliances|1|serial|2900|4550|4150|3|8423.81
CM-ELC-003|USB Rechargeable Desk Fan|Small Appliances|1|serial|2150|3290|2990|3|8414.59
CM-SVC-001|Home Delivery Service|Services|0|normal|0|300|250|0|9999.01
CM-SVC-002|Gift Wrapping Service|Services|0|normal|0|250|200|0|9999.02
CM-SVC-003|Custom Cake Message|Services|0|normal|0|100|80|0|9999.03
""".strip()

# Internal group tokens remain compatible with the transaction engine; configure()
# translates them to clean user-facing ERPNext groups when masters are created.
CUSTOMERS = (
    ("Walk-in Customer", "Individual", "Demo Retail", 0),
    ("Ayesha Khan", "Individual", "Demo Retail", 0),
    ("Hamza Malik", "Individual", "Demo Retail", 0),
    ("Sara Ahmed", "Individual", "Demo Retail", 0),
    ("Usman Tariq", "Individual", "Demo Retail", 0),
    ("Noor Fatima", "Individual", "Demo Retail", 0),
    ("Ali Raza", "Individual", "Demo Retail", 0),
    ("Hira Siddiqui", "Individual", "Demo Retail", 0),
    ("Bilal Ahmed", "Individual", "Demo Retail", 0),
    ("Maham Khan", "Individual", "Demo Retail", 0),
    ("Maple Office Services", "Company", "Demo Trade", 120000),
    ("Cornerstone Cafe", "Company", "Demo Trade", 150000),
    ("Sunrise Hostel Mess", "Company", "Demo Trade", 250000),
    ("Little Scholars Academy", "Company", "Demo Trade", 200000),
    ("Oak Event House", "Company", "Demo Trade", 180000),
    ("Bluebay Guest House", "Company", "Demo Trade", 220000),
)

SUPPLIERS = (
    "Harbor Foods Distribution",
    "Prime Beverage Suppliers",
    "Freshway Dairy & Chilled",
    "Pak Pantry Wholesalers",
    "Everyday Homecare Supply",
    "Brightline Small Appliances",
    "City Cash & Carry Wholesale",
    "Bakehouse Distribution",
)

_ORIGINAL_ENSURE_CUSTOMER_GROUP = native._ensure_customer_group
_ORIGINAL_ENSURE_SUPPLIER_GROUP = native._ensure_supplier_group
_ORIGINAL_ENSURE_WAREHOUSE = native._ensure_warehouse
_ORIGINAL_ENSURE_CUSTOMER = native._ensure_customer
_ORIGINAL_ENSURE_TAX_MAPPING = native._ensure_tax_mapping
_ORIGINAL_PURCHASE_CYCLE = native._purchase_cycle
_ORIGINAL_POS_INVOICE = native._pos_invoice
_ORIGINAL_CLOSE_OPENING = native._close_opening
_ORIGINAL_CUSTOMER_PAYMENT = native._customer_payment
_ORIGINAL_POS_RETURN = native._pos_return
_ORIGINAL_B2B_RETURN = native._b2b_return


def _items() -> list[dict]:
    rows = []
    for raw in ITEM_TEXT.splitlines():
        code, name, group, stock, tracking, cost, retail, wholesale, reorder, hs = raw.split("|")
        rows.append(
            {
                "code": code,
                "name": name,
                "group": group,
                "stock": int(stock),
                "tracking": tracking,
                "cost": float(cost),
                "retail": float(retail),
                "wholesale": float(wholesale),
                "reorder": float(reorder),
                "hs": hs,
            }
        )
    return rows


ITEMS = _items()
ITEM_BY_CODE = {row["code"]: row for row in ITEMS}
NORMAL_STOCK_ITEMS = [row["code"] for row in ITEMS if row["stock"] and row["tracking"] == "normal"]
SERVICE_ITEMS = [row["code"] for row in ITEMS if not row["stock"]]


def _ean13(index: int) -> str:
    base = f"6291199{index:05d}"
    digits = [int(value) for value in base]
    check = (10 - ((sum(digits[::2]) + 3 * sum(digits[1::2])) % 10)) % 10
    return f"{base}{check}"


def _ensure_customer_group(name: str) -> str:
    return _ORIGINAL_ENSURE_CUSTOMER_GROUP(CUSTOMER_GROUP_MAP.get(name, name))


def _ensure_supplier_group(name: str) -> str:
    return _ORIGINAL_ENSURE_SUPPLIER_GROUP(SUPPLIER_GROUP_MAP.get(name, name))


def _ensure_warehouse(company: str, warehouse_name: str) -> str:
    return _ORIGINAL_ENSURE_WAREHOUSE(company, WAREHOUSE_MAP.get(warehouse_name, warehouse_name))


def _ensure_customer(company: str, name: str, customer_type: str, group: str, credit_limit: float) -> str:
    return _ORIGINAL_ENSURE_CUSTOMER(
        company,
        name,
        customer_type,
        CUSTOMER_GROUP_MAP.get(group, group),
        credit_limit,
    )


def _ensure_tax_mapping(company: str, item_code: str, hs_code: str) -> None:
    _ORIGINAL_ENSURE_TAX_MAPPING(company, item_code, hs_code)


def _purchase_cycle(*args, **kwargs):
    order = _ORIGINAL_PURCHASE_CYCLE(*args, **kwargs)
    sequence = args[4] if len(args) > 4 else kwargs["sequence"]
    date_value = args[3] if len(args) > 3 else kwargs["date_value"]
    marker = f"{SEED}-BUY-{sequence:02d}-INV"
    invoice = frappe.db.get_value(
        "Purchase Invoice", {"custom_ledgix_client_purchase_invoice_id": marker}, "name"
    )
    if invoice:
        frappe.db.set_value(
            "Purchase Invoice",
            invoice,
            "bill_no",
            f"SUP-{sequence:04d}-{getdate(date_value).strftime('%m%y')}",
            update_modified=False,
        )
    return order


def _pos_invoice(*args, **kwargs):
    invoice = _ORIGINAL_POS_INVOICE(*args, **kwargs)
    for row in invoice.get("payments") or []:
        if row.reference_no and row.reference_no.startswith("DEMO-"):
            frappe.db.set_value(
                "POS Invoice Payment",
                row.name,
                "reference_no",
                row.reference_no.replace("DEMO-", "POS-", 1),
                update_modified=False,
            )
    return invoice


def _close_opening(opening, sequence: int):
    closing = _ORIGINAL_CLOSE_OPENING(opening, sequence)
    frappe.db.set_value(
        "POS Closing Entry",
        closing.name,
        "custom_ledgix_closing_notes",
        f"{SOURCE}; cashier variance {(-20, 0, 15)[sequence % 3]:+d}",
        update_modified=False,
    )
    return closing


def _customer_payment(invoice, amount: float, date_value, sequence: int):
    payment = _ORIGINAL_CUSTOMER_PAYMENT(invoice, amount, date_value, sequence)
    if payment:
        frappe.db.set_value(
            "Payment Entry",
            payment.name,
            "reference_no",
            f"IBFT-{getdate(date_value).strftime('%y%m')}-{sequence:05d}",
            update_modified=False,
        )
    return payment


def _pos_return(source, sequence: int, date_value):
    doc = _ORIGINAL_POS_RETURN(source, sequence, date_value)
    reason = "Customer return - unopened item accepted after counter inspection."
    frappe.db.set_value(
        "POS Invoice",
        doc.name,
        {"custom_ledgix_return_reason": reason, "remarks": reason},
        update_modified=False,
    )
    return doc


def _b2b_return(source, sequence: int, date_value):
    doc = _ORIGINAL_B2B_RETURN(source, sequence, date_value)
    frappe.db.set_value(
        "Sales Invoice",
        doc.name,
        "remarks",
        "Partial trade return - one unopened unit accepted and credited.",
        update_modified=False,
    )
    return doc


def configure() -> None:
    """Apply the retail profile to the native seeding engine for this process."""
    native.SEED = SEED
    native.SOURCE = SOURCE
    native.RETAIL_PRICE_LIST = RETAIL_PRICE_LIST
    native.WHOLESALE_PRICE_LIST = WHOLESALE_PRICE_LIST
    native.BUYING_PRICE_LIST = BUYING_PRICE_LIST
    native.POS_PROFILE = POS_PROFILE
    native.ITEM_GROUPS = ITEM_GROUPS
    native.ITEM_TEXT = ITEM_TEXT
    native.CUSTOMERS = CUSTOMERS
    native.SUPPLIERS = SUPPLIERS
    native.ITEMS = ITEMS
    native.ITEM_BY_CODE = ITEM_BY_CODE
    native.NORMAL_STOCK_ITEMS = NORMAL_STOCK_ITEMS
    native.SERVICE_ITEMS = SERVICE_ITEMS
    native._ean13 = _ean13
    native._ensure_customer_group = _ensure_customer_group
    native._ensure_supplier_group = _ensure_supplier_group
    native._ensure_warehouse = _ensure_warehouse
    native._ensure_customer = _ensure_customer
    native._ensure_tax_mapping = _ensure_tax_mapping
    native._purchase_cycle = _purchase_cycle
    native._pos_invoice = _pos_invoice
    native._close_opening = _close_opening
    native._customer_payment = _customer_payment
    native._pos_return = _pos_return
    native._b2b_return = _b2b_return


__all__ = [
    "SEED",
    "SOURCE",
    "POS_PROFILE",
    "ITEM_CODE_PREFIX",
    "WAREHOUSE_POS_NAME",
    "CUSTOMERS",
    "SUPPLIERS",
    "configure",
]
