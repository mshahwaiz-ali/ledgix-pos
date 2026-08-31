from __future__ import annotations

import math
import random
from datetime import datetime, time

import frappe
from frappe.utils import add_days, flt, get_datetime, getdate, today

from ledgix_saas.services.payments import post_payment
from ledgix_saas.services.pricing import resolve_item_price
from ledgix_saas.services.receivables import refresh_customer_credit_summary
from ledgix_saas.services.tax import apply_sale_tax_snapshot

SEED = "CBM-DEMO-V1"
COMPANY = "Crescent Mart & Bakehouse"
OUTLET = "Gulberg Main Branch"
ADDRESS = "Main Boulevard, Gulberg III, Lahore"
RETAIL = "Retail"
WHOLESALE = "Wholesale Trade"
TAX_STD = "Standard Sales Tax"
TAX_RED = "Reduced Sales Tax"
TAX_ZERO = "Zero Rated Essentials"

CATEGORIES = (
    ("Fresh Breads & Buns", "Daily breads, buns and baked staples.", "bread", "#A05A2C", TAX_RED),
    ("Cakes & Desserts", "Cake slices, celebration cakes and chilled desserts.", "star", "#A43C68", TAX_STD),
    ("Savouries & Ready-to-Eat", "Fresh savouries and grab-and-go food.", "food", "#B06C2E", TAX_STD),
    ("Beverages", "Cold drinks, water, juice, coffee and tea.", "coffee", "#356C8A", TAX_STD),
    ("Pantry & Grocery", "Everyday pantry essentials and packaged grocery.", "package", "#4F7A4B", TAX_STD),
    ("Gifting & Essentials", "Celebration accessories, gift packs and retail essentials.", "gift", "#7A4B84", TAX_STD),
)

# code|name|category|unit|tracking|cost|retail|wholesale|min|hs|tax
ITEM_TEXT = """
CBM-BRD-001|Classic Milk Bread 400g|Fresh Breads & Buns|Piece|Normal|118|175|158|12|1905.90|Reduced Sales Tax
CBM-BRD-002|Whole Wheat Bread 400g|Fresh Breads & Buns|Piece|Normal|132|195|176|12|1905.90|Reduced Sales Tax
CBM-BRD-003|Seeded Multigrain Loaf|Fresh Breads & Buns|Piece|Normal|192|285|255|8|1905.90|Reduced Sales Tax
CBM-BRD-004|Soft Burger Buns - Pack of 6|Fresh Breads & Buns|Pack|Normal|148|225|198|10|1905.90|Reduced Sales Tax
CBM-BRD-005|Dinner Rolls - Pack of 6|Fresh Breads & Buns|Pack|Normal|128|195|174|10|1905.90|Reduced Sales Tax
CBM-CAK-001|Chocolate Fudge Cake Slice|Cakes & Desserts|Piece|Normal|152|290|255|8|1905.90|Standard Sales Tax
CBM-CAK-002|Red Velvet Cake Slice|Cakes & Desserts|Piece|Normal|165|315|278|8|1905.90|Standard Sales Tax
CBM-CAK-003|Lotus Cheesecake Slice|Cakes & Desserts|Piece|Normal|228|425|385|6|1905.90|Standard Sales Tax
CBM-CAK-004|Chocolate Fudge Cake 2lb|Cakes & Desserts|Piece|Lot Based|1450|2290|2090|3|1905.90|Standard Sales Tax
CBM-CAK-005|Vanilla Celebration Cake 2lb|Cakes & Desserts|Piece|Lot Based|1280|2050|1890|3|1905.90|Standard Sales Tax
CBM-SAV-001|Chicken Patties|Savouries & Ready-to-Eat|Piece|Normal|92|165|145|15|1905.90|Standard Sales Tax
CBM-SAV-002|Vegetable Samosa|Savouries & Ready-to-Eat|Piece|Normal|38|70|58|20|1905.90|Standard Sales Tax
CBM-SAV-003|Smoked Chicken Sandwich|Savouries & Ready-to-Eat|Piece|Normal|205|365|325|8|1602.32|Standard Sales Tax
CBM-SAV-004|Cheese Croissant|Savouries & Ready-to-Eat|Piece|Normal|135|245|215|10|1905.90|Standard Sales Tax
CBM-SAV-005|Chicken Pizza Slice|Savouries & Ready-to-Eat|Piece|Normal|178|320|285|10|1905.90|Standard Sales Tax
CBM-BEV-001|Mineral Water 500ml|Beverages|Piece|Normal|42|70|58|24|2201.10|Zero Rated Essentials
CBM-BEV-002|Classic Cola 500ml|Beverages|Piece|Normal|82|120|105|18|2202.10|Standard Sales Tax
CBM-BEV-003|Orange Juice 250ml|Beverages|Piece|Normal|96|155|135|12|2009.12|Standard Sales Tax
CBM-BEV-004|Cold Brew Iced Coffee 250ml|Beverages|Piece|Lot Based|145|245|220|8|2202.99|Standard Sales Tax
CBM-BEV-005|Green Tea - 20 Bags|Beverages|Pack|Normal|235|345|305|6|0902.10|Standard Sales Tax
CBM-PAN-001|Premium Black Tea 250g|Pantry & Grocery|Pack|Normal|420|595|535|6|0902.30|Standard Sales Tax
CBM-PAN-002|Fine Sugar 1kg|Pantry & Grocery|Pack|Normal|142|175|158|12|1701.99|Zero Rated Essentials
CBM-PAN-003|Iodized Salt 800g|Pantry & Grocery|Pack|Normal|64|95|84|10|2501.00|Zero Rated Essentials
CBM-PAN-004|Salted Butter 200g|Pantry & Grocery|Pack|Lot Based|485|625|575|6|0405.10|Standard Sales Tax
CBM-PAN-005|Strawberry Preserve 450g|Pantry & Grocery|Piece|Normal|365|525|475|6|2007.99|Standard Sales Tax
CBM-GFT-001|Birthday Candle Set|Gifting & Essentials|Pack|Normal|72|145|118|8|3406.00|Standard Sales Tax
CBM-GFT-002|Celebration Gift Box - Medium|Gifting & Essentials|Piece|Normal|285|495|430|5|4819.50|Standard Sales Tax
CBM-GFT-003|Digital Kitchen Scale|Gifting & Essentials|Piece|Serial Based|2850|4490|4090|2|8423.81|Standard Sales Tax
""".strip()


def _items():
    result = []
    for line in ITEM_TEXT.splitlines():
        code, name, category, unit, tracking, cost, retail, wholesale, minimum, hs, tax = line.split("|")
        result.append({"code": code, "name": name, "category": category, "unit": unit, "tracking": tracking,
                       "cost": flt(cost), "retail": flt(retail), "wholesale": flt(wholesale),
                       "minimum": flt(minimum), "hs": hs, "tax": tax})
    return result

ITEMS = _items()
ITEM = {row["code"]: row for row in ITEMS}
GENERAL_POOL = [row["code"] for row in ITEMS if row["code"] != "CBM-GFT-003"]

SUPPLIERS = (
    ("Heritage Bakery Supply Co.", "Manufacturer", "Gulberg Industrial Area"),
    ("BlueRiver Food & Beverage Distribution", "Distributor", "Kot Lakhpat"),
    ("FreshFields Dairy & Grocery", "Distributor", "Model Town"),
    ("PackPro Retail Supplies", "Local", "Shah Alam Market"),
)
CUSTOMERS = (
    ("Walk-in Customer", "Retail", RETAIL, 0, 0, "Gulberg III"),
    ("Ayesha Khan", "Retail", RETAIL, 0, 0, "DHA Phase 5"),
    ("Hamza Malik", "Retail", RETAIL, 0, 0, "Johar Town"),
    ("Sara Ahmed", "Retail", RETAIL, 0, 0, "Model Town"),
    ("Usman Tariq", "Retail", RETAIL, 0, 0, "Garden Town"),
    ("Noor Fatima", "Retail", RETAIL, 0, 0, "Gulberg II"),
    ("Greenline Offices", "B2B", WHOLESALE, 15, 120000, "Gulberg III"),
    ("The Morning Table Cafe", "B2B", WHOLESALE, 14, 150000, "DHA Phase 6"),
    ("Northgate Hostel Mess", "Wholesale", WHOLESALE, 21, 250000, "Canal Road"),
    ("Urban Crust Cafe", "B2B", WHOLESALE, 7, 120000, "MM Alam Road"),
)
PAYMENTS = (
    ("Cash", "Cash", 0, 1, 10), ("Card", "Card", 1, 0, 20),
    ("EasyPaisa", "Wallet", 1, 0, 30), ("JazzCash", "Wallet", 1, 0, 40),
    ("Bank Transfer", "Bank Transfer", 1, 0, 50), ("Other", "Other", 1, 0, 90),
)

# offset|supplier|invoice|cost-multiplier|item:qty,item:qty...
PURCHASE_TEXT = """
-46|Heritage Bakery Supply Co.|HBS-2607-1842|1.00|CBM-BRD-001:120,CBM-BRD-002:110,CBM-BRD-003:70,CBM-BRD-004:80,CBM-BRD-005:80,CBM-CAK-001:70,CBM-CAK-002:60,CBM-CAK-003:55,CBM-CAK-004:18,CBM-CAK-005:18,CBM-SAV-001:110,CBM-SAV-002:150,CBM-SAV-003:65,CBM-SAV-004:75,CBM-SAV-005:75
-44|BlueRiver Food & Beverage Distribution|BRB-2607-7719|1.00|CBM-BEV-001:180,CBM-BEV-002:130,CBM-BEV-003:100,CBM-BEV-004:70,CBM-BEV-005:45
-42|FreshFields Dairy & Grocery|FDG-2607-5526|1.00|CBM-PAN-001:50,CBM-PAN-002:100,CBM-PAN-003:90,CBM-PAN-004:55,CBM-PAN-005:45
-40|PackPro Retail Supplies|PPR-2607-2904|1.00|CBM-GFT-001:60,CBM-GFT-002:30,CBM-GFT-003:8
-19|Heritage Bakery Supply Co.|HBS-2608-2261|1.025|CBM-BRD-001:70,CBM-BRD-002:60,CBM-BRD-004:45,CBM-BRD-005:45,CBM-CAK-001:35,CBM-CAK-002:30,CBM-CAK-004:10,CBM-SAV-001:60,CBM-SAV-002:80,CBM-SAV-004:40,CBM-SAV-005:40
-11|BlueRiver Food & Beverage Distribution|BRB-2608-8143|1.015|CBM-BEV-001:90,CBM-BEV-002:70,CBM-BEV-003:55,CBM-BEV-004:35,CBM-PAN-001:24,CBM-PAN-002:45,CBM-PAN-004:24
""".strip()


def _purchases():
    rows = []
    for line in PURCHASE_TEXT.splitlines():
        offset, supplier, invoice, multiplier, items = line.split("|")
        rows.append((int(offset), supplier, invoice, flt(multiplier),
                     {code: flt(qty) for code, qty in (part.split(":") for part in items.split(","))}))
    return rows


def _seeded():
    return bool(frappe.get_all("Ledgix Sale", filters={"client_sale_id": ["like", f"{SEED}-%"]}, pluck="name", limit=1))


def _dt(value, hour=10, minute=0):
    return get_datetime(datetime.combine(getdate(value), time(hour=hour, minute=minute)))


def _ean13(index):
    base = f"6291101{index:05d}"
    digits = [int(x) for x in base]
    check = (10 - ((sum(digits[::2]) + 3 * sum(digits[1::2])) % 10)) % 10
    return f"{base}{check}"


def _single(doctype, values):
    doc = frappe.get_single(doctype)
    for key, value in values.items():
        if doc.meta.has_field(key):
            setattr(doc, key, value)
    doc.save(ignore_permissions=True)
    return doc


def _settings():
    _single("Ledgix Brand Settings", {"brand_name": "Ledgix", "legal_business_name": COMPANY,
            "business_address": ADDRESS, "business_phone": "+92 42 0000 2846",
            "business_email": "accounts@crescentmart.example"})
    _single("Ledgix FBR Settings", {"enabled": 0, "mode": "Disabled", "submit_trigger": "Manual",
            "production_post_armed": 0, "block_sale_if_fbr_fails": 0, "sandbox_post_on_submit": 0,
            "retry_enabled": 0, "seller_business_name": COMPANY, "seller_province": "Punjab",
            "seller_address": ADDRESS})


def _taxes():
    for name, rate, zero in ((TAX_STD, 18, 0), (TAX_RED, 10, 0), (TAX_ZERO, 0, 1)):
        values = {"tax_type": "Sales Tax", "default_rate": rate, "active": 1, "is_exempt": 0, "is_zero_rated": zero}
        if frappe.db.exists("Ledgix Tax Category", name):
            frappe.db.set_value("Ledgix Tax Category", name, values, update_modified=False)
        else:
            doc = frappe.new_doc("Ledgix Tax Category"); doc.category_name = name
            for k, v in values.items(): setattr(doc, k, v)
            doc.insert(ignore_permissions=True)
        if not frappe.db.exists("Ledgix Tax Rate", {"tax_category": name, "province": "Punjab",
                "effective_from": "2026-01-01", "applies_to": "Both", "active": 1}):
            doc = frappe.new_doc("Ledgix Tax Rate"); doc.tax_category = name; doc.rate = rate
            doc.applies_to = "Both"; doc.province = "Punjab"; doc.active = 1; doc.effective_from = "2026-01-01"
            doc.insert(ignore_permissions=True)
    _single("Ledgix Tax Profile", {"business_name": COMPANY, "business_type": "Retail & Wholesale",
            "province": "Punjab", "default_tax_category": TAX_STD, "default_sales_type": "Goods at standard rate",
            "default_buyer_type": "Unregistered", "tax_enabled": 1, "price_includes_tax": 1,
            "receipt_tax_display_enabled": 1, "branch__outlet_name": OUTLET,
            "pos_registration_number": "CBM-GUL-01", "outlet_address": ADDRESS})


def _masters():
    for name, method_type, ref, change, order in PAYMENTS:
        values = {"method_type": method_type, "enabled": 1, "requires_reference": ref, "allow_change": change, "sort_order": order}
        if frappe.db.exists("Ledgix Payment Method", name): frappe.db.set_value("Ledgix Payment Method", name, values, update_modified=False)
        else:
            doc = frappe.new_doc("Ledgix Payment Method"); doc.payment_method_name = name
            for k, v in values.items(): setattr(doc, k, v)
            doc.insert(ignore_permissions=True)
    for name, default, priority, notes in ((RETAIL, 1, 1, "Default counter and consumer pricing."),
            (WHOLESALE, 0, 10, "Trade pricing for approved wholesale and B2B accounts.")):
        values = {"enabled": 1, "is_default_retail": default, "currency": "PKR", "priority": priority, "notes": notes}
        if frappe.db.exists("Ledgix Price List", name): frappe.db.set_value("Ledgix Price List", name, values, update_modified=False)
        else:
            doc = frappe.new_doc("Ledgix Price List"); doc.price_list_name = name
            for k, v in values.items(): setattr(doc, k, v)
            doc.insert(ignore_permissions=True)
    for name, desc, icon, color, tax in CATEGORIES:
        values = {"description": desc, "is_active": 1, "category_icon": icon, "accent_color": color,
                  "tax_defaults_enabled": 1, "default_tax_category": tax, "default_taxable": 1,
                  "default_sales_type": "Goods at standard rate", "default_uom_for_fbr": "Numbers"}
        if frappe.db.exists("Ledgix Category", name): frappe.db.set_value("Ledgix Category", name, values, update_modified=False)
        else:
            doc = frappe.new_doc("Ledgix Category"); doc.category_name = name
            for k, v in values.items(): setattr(doc, k, v)
            doc.insert(ignore_permissions=True)


def _catalog():
    for index, row in enumerate(ITEMS, 1):
        code = row["code"]
        if not frappe.db.exists("Ledgix Item", code):
            doc = frappe.new_doc("Ledgix Item"); doc.item_code = code; doc.item_name = row["name"]; doc.category = row["category"]
            doc.barcode = _ean13(index); doc.sku = code; doc.unit = row["unit"]; doc.tracking_type = row["tracking"]
            doc.active = 1; doc.opening_stock = 0; doc.minimum_stock = row["minimum"]
            doc.cost_price = row["cost"]; doc.selling_price = row["retail"]; doc.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Ledgix Item", code, {"item_name": row["name"], "category": row["category"],
                "barcode": _ean13(index), "sku": code, "unit": row["unit"], "active": 1,
                "minimum_stock": row["minimum"], "selling_price": row["retail"]}, update_modified=False)
        for price_list, rate in ((RETAIL, row["retail"]), (WHOLESALE, row["wholesale"])):
            values = {"rate": rate, "currency": "PKR", "uom": row["unit"], "enabled": 1,
                      "effective_from": "2026-01-01", "notes": "Counter pricing" if price_list == RETAIL else "Approved trade pricing"}
            name = frappe.db.get_value("Ledgix Item Price", {"item": code, "price_list": price_list, "enabled": 1}, "name")
            if name: frappe.db.set_value("Ledgix Item Price", name, values, update_modified=False)
            else:
                doc = frappe.new_doc("Ledgix Item Price"); doc.item = code; doc.price_list = price_list
                for k, v in values.items(): setattr(doc, k, v)
                doc.insert(ignore_permissions=True)
        values = {"tax_category": row["tax"], "taxable": 1, "active": 1, "needs_review": 0,
                  "tax_basis": "Transaction Value", "hs_code": row["hs"], "uom_for_fbr": "Numbers",
                  "sales_type": "Goods at standard rate"}
        name = frappe.db.get_value("Ledgix Item Tax Profile", {"item": code, "active": 1}, "name")
        if name: frappe.db.set_value("Ledgix Item Tax Profile", name, values, update_modified=False)
        else:
            doc = frappe.new_doc("Ledgix Item Tax Profile"); doc.item = code
            for k, v in values.items(): setattr(doc, k, v)
            doc.insert(ignore_permissions=True)


def _parties():
    for name, kind, area in SUPPLIERS:
        values = {"company_name": name, "supplier_type": kind, "is_active": 1, "address": area, "city": "Lahore",
                  "notes": "Regular approved supplier for the Gulberg outlet."}
        if frappe.db.exists("Ledgix Supplier", name): frappe.db.set_value("Ledgix Supplier", name, values, update_modified=False)
        else:
            doc = frappe.new_doc("Ledgix Supplier"); doc.supplier_name = name
            for k, v in values.items(): setattr(doc, k, v)
            doc.insert(ignore_permissions=True)
    for index, (name, kind, price_list, terms, limit, area) in enumerate(CUSTOMERS, 1):
        values = {"customer_type": kind, "is_active": 1, "default_price_list": price_list,
                  "payment_terms_days": terms, "credit_limit": limit, "area": area, "city": "Lahore",
                  "address_line_1": area, "buyer_registration_type": "Unregistered", "buyer_province": "Punjab",
                  "buyer_fbr_address": f"{area}, Lahore", "notes": "Regular counter customer." if kind == "Retail" else "Approved trade account with agreed payment terms."}
        if name != "Walk-in Customer":
            values.update({"mobile_number": f"0300-000-{1000 + index:04d}", "email_address": f"account{index}@crescent-customer.example"})
        if frappe.db.exists("Ledgix Customer", name): frappe.db.set_value("Ledgix Customer", name, values, update_modified=False)
        else:
            doc = frappe.new_doc("Ledgix Customer"); doc.customer_name = name
            for k, v in values.items(): setattr(doc, k, v)
            doc.insert(ignore_permissions=True)


def _buy(base_date):
    for offset, supplier, invoice, multiplier, lines in _purchases():
        if frappe.db.exists("Ledgix Purchase", {"supplier": supplier, "invoice_number": invoice, "docstatus": 1}): continue
        doc = frappe.new_doc("Ledgix Purchase"); doc.supplier = supplier; doc.purchase_date = add_days(base_date, offset); doc.invoice_number = invoice
        for code, qty in lines.items():
            doc.append("items", {"item": code, "quantity": qty, "rate": flt(ITEM[code]["cost"] * multiplier, 2), "unit": ITEM[code]["unit"]})
        doc.insert(ignore_permissions=True); doc.submit()


def _shift(date_value, seq, opening_cash):
    marker = f"{SEED}:SHIFT:{getdate(date_value)}"
    name = frappe.db.get_value("Ledgix POS Shift", {"notes": ["like", f"%{marker}%"]}, "name")
    if name: return frappe.get_doc("Ledgix POS Shift", name)
    doc = frappe.new_doc("Ledgix POS Shift"); doc.opening_time = _dt(date_value, 8, 45 + seq % 10)
    doc.opened_by = "Administrator"; doc.opening_cash = opening_cash; doc.notes = f"Morning counter shift - {OUTLET}. {marker}"
    doc.insert(ignore_permissions=True); return doc


def _ref(method, serial, date_value):
    prefix = {"Card": "POS", "EasyPaisa": "EP", "JazzCash": "JC", "Bank Transfer": "IBFT", "Other": "REF"}.get(method, "")
    return f"{prefix}-{getdate(date_value).strftime('%m%d')}-{serial:06d}" if prefix else ""


def _backdate_payments(sale, date_value, serial):
    names = frappe.db.sql("""SELECT DISTINCT pa.parent FROM `tabLedgix Payment Allocation` pa
        INNER JOIN `tabLedgix Payment` p ON p.name=pa.parent WHERE pa.reference_doctype='Ledgix Sale'
        AND pa.reference_name=%s AND p.docstatus=1""", (sale,), pluck=True)
    for i, name in enumerate(names):
        frappe.db.set_value("Ledgix Payment", name, "payment_date", _dt(date_value, 10 + serial % 7, (serial * 7 + i * 11) % 60), update_modified=False)


def _tenders(sale, plan, payable, serial, date_value):
    if not plan: return
    if plan == "CashRound":
        sale.append("payments", {"payment_method": "Cash", "amount": math.ceil(payable / 100) * 100, "reference_no": ""}); return
    if isinstance(plan, str) and plan != "Mixed":
        sale.append("payments", {"payment_method": plan, "amount": payable, "reference_no": _ref(plan, serial, date_value)}); return
    if plan == "Mixed":
        cash = flt(payable * .4, 2); sale.append("payments", {"payment_method": "Cash", "amount": cash, "reference_no": ""})
        sale.append("payments", {"payment_method": "Card", "amount": flt(payable - cash, 2), "reference_no": _ref("Card", serial, date_value)}); return
    parts = list(plan); total_fraction = sum(flt(f) for _m, f in parts); allocated = 0
    for i, (method, fraction) in enumerate(parts):
        amount = flt(payable - allocated, 2) if total_fraction >= .999 and i == len(parts) - 1 else flt(payable * flt(fraction), 2)
        if amount > 0:
            sale.append("payments", {"payment_method": method, "amount": amount, "reference_no": _ref(method, serial + i, date_value)}); allocated += amount


def _sale(key, sale_date, customer, channel, price_list, lines, plan, serial, shift=None, discount=0):
    client_id = f"{SEED}-{key}"
    name = frappe.db.get_value("Ledgix Sale", {"client_sale_id": client_id, "docstatus": 1}, "name")
    if name: return frappe.get_doc("Ledgix Sale", name)
    prepared, subtotal = [], 0
    for code, qty in lines:
        price = resolve_item_price(code, customer=customer, price_list=price_list, sale_channel=channel, transaction_date=sale_date)
        subtotal += flt(qty) * flt(price["rate"]); prepared.append((code, qty, price, flt(frappe.db.get_value("Ledgix Item", code, "cost_price"))))
    discount = max(min(flt(discount), 100), 0); disc_amount = flt(subtotal * discount / 100, 2); ratio = disc_amount / subtotal if subtotal else 0
    doc = frappe.new_doc("Ledgix Sale"); doc.customer = customer; doc.sale_channel = channel; doc.price_list = price_list
    doc.sale_date = sale_date; doc.pos_shift = shift; doc.client_sale_id = client_id; doc.allow_partial_payment = 1 if channel == "B2B" else 0
    doc.subtotal_before_discount = flt(subtotal, 2); doc.discount_type = "Percent" if discount else ""; doc.discount_value = discount; doc.discount_amount = disc_amount
    for code, qty, price, cost in prepared:
        doc.append("items", {"item": code, "quantity": qty, "serial_numbers": "", "price_list_snapshot": price["price_list"],
            "item_price_reference": price["item_price_reference"], "list_rate": price["list_rate"],
            "rate": flt(price["rate"] * (1 - ratio), 2), "price_override": 0, "price_override_reason": "", "cost_price": cost})
    doc.calculate_totals(); apply_sale_tax_snapshot(doc); _tenders(doc, plan, flt(doc.grand_total or doc.total_amount, 2), serial, sale_date)
    doc.insert(ignore_permissions=True); doc.submit(); _backdate_payments(doc.name, sale_date, serial); return doc


def _close_shift(name, date_value, variance=0):
    doc = frappe.get_doc("Ledgix POS Shift", name)
    if doc.docstatus == 1: return doc
    doc.calculate_shift_summary(); doc.calculate_expected_cash(); doc.closing_time = _dt(date_value, 19, 10)
    doc.closed_by = "Administrator"; doc.status = "Closed"; doc.actual_cash = flt(doc.expected_cash + variance, 2)
    doc.save(ignore_permissions=True); doc.submit(); return doc


def _retail_sales(base_date):
    rng = random.Random(260831); retail = []; serial_sale = None; serial = 1
    customers = ["Walk-in Customer"] * 3 + ["Ayesha Khan", "Hamza Malik", "Sara Ahmed", "Usman Tariq", "Noor Fatima"]
    methods = ("Cash", "Card", "EasyPaisa", "JazzCash", "Bank Transfer", "Mixed")
    for seq, offset in enumerate((-34, -30, -26, -22, -18, -14, -9, -4), 1):
        date_value = add_days(base_date, offset); shift = _shift(date_value, seq, 12000 + seq * 500)
        if shift.docstatus != 0 or shift.status != "Open": continue
        for slot in range(5):
            selected = rng.sample(GENERAL_POOL, 2 + ((serial + slot) % 3)); lines = [(code, 1 + rng.randint(0, 2)) for code in selected]
            method = methods[(serial - 1) % len(methods)]; plan = "CashRound" if method == "Cash" and serial % 4 == 0 else method
            retail.append(_sale(f"R{serial:03d}", date_value, rng.choice(customers), "Retail", RETAIL, lines, plan, serial, shift.name,
                                5 if serial % 9 == 0 else (7.5 if serial % 17 == 0 else 0))); serial += 1
        if offset == -9:
            serial_sale = _sale("SERIAL-001", date_value, "Ayesha Khan", "Retail", RETAIL, [("CBM-GFT-003", 1)], "Card", 9001, shift.name)
            retail.append(serial_sale)
        _close_shift(shift.name, date_value, -35 if seq == 3 else (20 if seq == 6 else 0))
    shift = _shift(base_date, 99, 15000)
    if shift.docstatus == 0 and shift.status == "Open":
        patterns = ((("CBM-BRD-001", 1), ("CBM-SAV-001", 2), ("CBM-BEV-002", 1)),
                    (("CBM-CAK-001", 2), ("CBM-BEV-004", 2)),
                    (("CBM-PAN-001", 1), ("CBM-PAN-005", 1), ("CBM-GFT-001", 1)))
        for i, lines in enumerate(patterns, 1):
            retail.append(_sale(f"TODAY-{i:02d}", base_date, ("Walk-in Customer", "Sara Ahmed", "Hamza Malik")[i-1],
                                "Retail", RETAIL, list(lines), ("CashRound", "EasyPaisa", "Mixed")[i-1], 9500+i, shift.name))
    return retail, serial_sale, shift.name


def _b2b(base_date):
    specs = (
        ("B2B-001", -29, "Greenline Offices", [("CBM-BRD-001", 12), ("CBM-SAV-003", 8), ("CBM-BEV-003", 12)], "Bank Transfer", 2001, 5),
        ("B2B-002", -21, "The Morning Table Cafe", [("CBM-BRD-004", 14), ("CBM-SAV-001", 18), ("CBM-SAV-004", 10)], [("Bank Transfer", .5)], 2002, 0),
        ("B2B-003", -28, "Northgate Hostel Mess", [("CBM-BRD-002", 20), ("CBM-BEV-001", 24), ("CBM-PAN-001", 8)], None, 2003, 4),
        ("B2B-004", -13, "Urban Crust Cafe", [("CBM-SAV-004", 10), ("CBM-CAK-001", 8), ("CBM-BEV-004", 8)], None, 2004, 0),
    )
    sales = [_sale(key, add_days(base_date, offset), customer, "B2B", WHOLESALE, lines, plan, serial, discount=discount)
             for key, offset, customer, lines, plan, serial, discount in specs]
    urban = sales[-1]
    exists = frappe.db.sql("""SELECT p.name FROM `tabLedgix Payment` p INNER JOIN `tabLedgix Payment Allocation` pa ON pa.parent=p.name
        WHERE p.docstatus=1 AND pa.reference_doctype='Ledgix Sale' AND pa.reference_name=%s LIMIT 1""", (urban.name,), pluck=True)
    urban.reload()
    if not exists and flt(urban.remaining_amount) > 0:
        amount = flt(urban.remaining_amount, 2)
        payment = post_payment(customer=urban.customer, payment_method="Bank Transfer", amount=amount,
            reference_number="IBFT-CMB-482731", allocations=[{"reference_doctype": "Ledgix Sale", "reference_name": urban.name,
            "allocated_amount": amount, "remarks": "Settlement against weekly trade invoice"}])
        frappe.db.set_value("Ledgix Payment", payment.name, "payment_date", _dt(add_days(urban.sale_date, 5), 14, 20), update_modified=False)
    return sales


def _return(sale, row_index, qty, date_value, reason):
    sale = frappe.get_doc("Ledgix Sale", sale.name if hasattr(sale, "name") else sale); row = sale.items[row_index]
    name = frappe.db.sql("""SELECT r.name FROM `tabLedgix Sales Return` r INNER JOIN `tabLedgix Sales Return Item` ri ON ri.parent=r.name
        WHERE r.docstatus=1 AND r.original_sale=%s AND ri.original_sale_item_row=%s LIMIT 1""", (sale.name, row.name), pluck=True)
    if name: return frappe.get_doc("Ledgix Sales Return", name[0])
    doc = frappe.new_doc("Ledgix Sales Return"); doc.original_sale = sale.name; doc.return_date = date_value; doc.return_reason = reason; doc.fbr_reason_remarks = reason
    doc.append("items", {"item": row.item, "original_sale_item_row": row.name, "quantity": min(flt(qty), flt(row.quantity)), "serial_numbers": ""})
    doc.insert(ignore_permissions=True); doc.submit(); return doc


def _returns(retail, serial_sale):
    result = [_return(retail[4], 0, 1, add_days(retail[4].sale_date, 2), "Customer reported damaged outer packaging; item accepted back after counter inspection."),
              _return(retail[16], 0, 1, add_days(retail[16].sale_date, 1), "Incorrect item selected at checkout; unopened unit returned and restocked.")]
    if serial_sale:
        result.append(_return(serial_sale, 0, 1, add_days(serial_sale.sale_date, 2), "Digital scale returned unopened; serial verified and unit restored to saleable stock."))
    return result


def _stock_target(code, target, date_value, note):
    if frappe.db.get_value("Ledgix Item", code, "tracking_type") != "Normal": return
    current = flt(frappe.db.get_value("Ledgix Item", code, "current_stock")); qty = flt(current - target, 3)
    if qty <= 0 or frappe.db.exists("Ledgix Stock Movement", {"item": code, "movement_source": "Manual OUT",
            "reference_note": ["like", f"%{SEED}%"], "docstatus": 1}): return
    doc = frappe.new_doc("Ledgix Stock Movement"); doc.item = code; doc.movement_type = "OUT"; doc.movement_source = "Manual OUT"
    doc.quantity = qty; doc.movement_date = date_value; doc.reference_note = f"{note} [{SEED}]"; doc.insert(ignore_permissions=True); doc.submit()


def _low_stock(base_date):
    for code, target, minute, note in (
        ("CBM-CAK-003", 0, 10, "End-of-day chilled display write-off"),
        ("CBM-GFT-001", 4, 15, "Cycle count adjustment after weekend demand"),
        ("CBM-PAN-001", 3, 20, "Stock count correction before supplier replenishment"),
        ("CBM-BEV-003", 8, 25, "Damaged carton units written off during stock count"),
    ):
        _stock_target(code, target, _dt(add_days(base_date, -1), 18, minute), note)


def _refresh_credit():
    for customer in frappe.get_all("Ledgix Customer", pluck="name"): refresh_customer_credit_summary(customer)


def summary():
    low = frappe.get_all("Ledgix Item", filters={"stock_status": "Low Stock", "active": 1}, pluck="name")
    out = frappe.get_all("Ledgix Item", filters={"stock_status": "Out of Stock", "active": 1}, pluck="name")
    trade = frappe.get_all("Ledgix Customer", filters={"customer_type": ["in", ["B2B", "Wholesale"]]}, fields=["outstanding_amount", "overdue_amount"])
    result = {"business": COMPANY, "outlet": OUTLET, "seed_version": SEED,
        "categories": frappe.db.count("Ledgix Category"), "items": frappe.db.count("Ledgix Item"),
        "customers": frappe.db.count("Ledgix Customer"), "suppliers": frappe.db.count("Ledgix Supplier"),
        "price_lists": frappe.db.count("Ledgix Price List"), "purchases_submitted": frappe.db.count("Ledgix Purchase", {"docstatus": 1}),
        "sales_submitted": frappe.db.count("Ledgix Sale", {"docstatus": 1}), "retail_sales": frappe.db.count("Ledgix Sale", {"docstatus": 1, "sale_channel": "Retail"}),
        "b2b_sales": frappe.db.count("Ledgix Sale", {"docstatus": 1, "sale_channel": "B2B"}),
        "b2b_partial_sales": frappe.db.count("Ledgix Sale", {"docstatus": 1, "sale_channel": "B2B", "payment_status": "Partial"}),
        "b2b_unpaid_sales": frappe.db.count("Ledgix Sale", {"docstatus": 1, "sale_channel": "B2B", "payment_status": "Unpaid"}),
        "sales_returns": frappe.db.count("Ledgix Sales Return", {"docstatus": 1}), "payments_posted": frappe.db.count("Ledgix Payment", {"docstatus": 1}),
        "stock_movements": frappe.db.count("Ledgix Stock Movement", {"docstatus": 1}), "low_stock_items": low, "out_of_stock_items": out,
        "b2b_outstanding": flt(sum(flt(x.outstanding_amount) for x in trade), 2), "b2b_overdue": flt(sum(flt(x.overdue_amount) for x in trade), 2),
        "open_pos_shift": frappe.db.get_value("Ledgix POS Shift", {"status": "Open", "docstatus": 0}, "name", order_by="creation desc"),
        "tax_enabled": bool(frappe.db.get_single_value("Ledgix Tax Profile", "tax_enabled")),
        "fbr_mode": frappe.db.get_single_value("Ledgix FBR Settings", "mode") or "Disabled"}
    if frappe.db.exists("DocType", "Ledgix Stock Lot"): result["stock_lots"] = frappe.db.count("Ledgix Stock Lot")
    if frappe.db.exists("DocType", "Ledgix Stock Serial"): result["stock_serials"] = frappe.db.count("Ledgix Stock Serial")
    return result


def verify():
    result = summary(); negative = frappe.get_all("Ledgix Item", filters={"current_stock": ["<", 0]}, fields=["name", "current_stock"])
    result.update({"negative_stock": negative,
        "fbr_safe": not bool(frappe.db.get_single_value("Ledgix FBR Settings", "enabled")) and (frappe.db.get_single_value("Ledgix FBR Settings", "mode") or "Disabled") == "Disabled",
        "has_payment_mix": all(frappe.db.exists("Ledgix Payment", {"payment_method": method, "docstatus": 1}) for method in ("Cash", "Card", "EasyPaisa", "JazzCash", "Bank Transfer")),
        "has_low_stock": bool(result["low_stock_items"]), "has_out_of_stock": bool(result["out_of_stock_items"])})
    result["ok"] = bool(not negative and result["fbr_safe"] and result["has_payment_mix"] and result["sales_submitted"] >= 45
        and result["purchases_submitted"] >= 6 and result["sales_returns"] >= 3 and result["b2b_partial_sales"] >= 1
        and result["b2b_unpaid_sales"] >= 1 and result["b2b_outstanding"] > 0 and result["b2b_overdue"] > 0
        and result["has_low_stock"] and result["has_out_of_stock"])
    return result


def seed():
    """Create a realistic one-shot demo dataset. Never runs automatically on install/migrate."""
    if _seeded(): return {"created": False, "already_seeded": True, **verify()}
    old_user = frappe.session.user or "Administrator"; frappe.set_user("Administrator"); base_date = getdate(today())
    try:
        _settings(); _taxes(); _masters(); _catalog(); _parties(); _buy(base_date)
        retail, serial_sale, _open_shift = _retail_sales(base_date); _b2b(base_date); _returns(retail, serial_sale); _low_stock(base_date); _refresh_credit()
        result = verify()
        if not result["ok"]: frappe.throw(f"Demo data verification failed: {result}")
        frappe.db.commit(); return {"created": True, "already_seeded": False, **result}
    except Exception:
        frappe.db.rollback(); raise
    finally:
        frappe.set_user(old_user)
