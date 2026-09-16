from __future__ import annotations

import frappe
from frappe.utils import cint, flt, nowdate

from ledgix_saas.migration import erpnext_phase5_master_migration_runtime as migration
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.migration.erpnext_stock_purchase_behavioral_spike import _leaf_warehouse
from ledgix_saas.setup import erpnext_phase5_extensions

PREFIX = "P5-"
CATEGORY = "P5 Retail Category"
PRICE_LIST = "P5 Retail"
NORMAL_ITEM = "P5-NORMAL"
BATCH_ITEM = "P5-BATCH"
SERIAL_ITEM = "P5-SERIAL"
CUSTOMER = "P5 Customer"
SUPPLIER = "P5 Supplier"
PAYMENT_METHOD = "P5 Wallet"
TAX_CATEGORY = "P5 Standard 18"
SERIALS = ("P5-SERIAL-001", "P5-SERIAL-002")
ITEM_PRICE_PROVENANCE_FIELD = "custom_ledgix_legacy_item_price"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 5 master migration gate on {frappe.local.site!r}; "
            f"this gate is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing.")


def _ensure_tax_category() -> str:
    if frappe.db.exists("Ledgix Tax Category", TAX_CATEGORY):
        return TAX_CATEGORY
    doc = frappe.get_doc(
        {
            "doctype": "Ledgix Tax Category",
            "category_name": TAX_CATEGORY,
            "tax_type": "Sales Tax",
            "default_rate": 18,
            "active": 1,
            "is_exempt": 0,
            "is_zero_rated": 0,
            "description": "Phase 5 native master migration fixture",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_category() -> str:
    if frappe.db.exists("Ledgix Category", CATEGORY):
        doc = frappe.get_doc("Ledgix Category", CATEGORY)
    else:
        doc = frappe.get_doc({"doctype": "Ledgix Category", "category_name": CATEGORY})
    values = {
        "description": "Phase 5 retail category",
        "is_active": 1,
        "category_icon": "shopping-bag",
        "accent_color": "#A43A47",
        "tax_defaults_enabled": 1,
        "default_tax_category": TAX_CATEGORY,
        "default_taxable": 1,
        "default_sales_type": "Goods at standard rate",
        "default_uom_for_fbr": "Numbers, pieces, units",
        "default_scenario_id": "SN001",
    }
    for key, value in values.items():
        doc.set(key, value)
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_price_list() -> str:
    if frappe.db.exists("Ledgix Price List", PRICE_LIST):
        doc = frappe.get_doc("Ledgix Price List", PRICE_LIST)
    else:
        doc = frappe.get_doc({"doctype": "Ledgix Price List", "price_list_name": PRICE_LIST})
    doc.currency = "PKR"
    doc.enabled = 1
    doc.is_default_retail = 1
    doc.priority = 1
    doc.notes = "Phase 5 migration fixture retail price list"
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_legacy_item(item_code: str, tracking: str, opening_stock: float, cost: float, selling: float, barcode: str, sku: str):
    if frappe.db.exists("Ledgix Item", item_code):
        doc = frappe.get_doc("Ledgix Item", item_code)
        expected = {
            "tracking_type": tracking,
            "category": CATEGORY,
            "unit": "Piece",
        }
        for field, value in expected.items():
            if doc.get(field) != value:
                frappe.throw(f"Fixture {item_code} has {field}={doc.get(field)!r}, expected {value!r}.")
        return doc
    doc = frappe.get_doc(
        {
            "doctype": "Ledgix Item",
            "item_code": item_code,
            "item_name": item_code.replace("P5-", "Phase 5 ").title(),
            "category": CATEGORY,
            "barcode": barcode,
            "sku": sku,
            "unit": "Piece",
            "tracking_type": tracking,
            "active": 1,
            "opening_stock": opening_stock,
            "minimum_stock": 2,
            "cost_price": cost,
            "selling_price": selling,
        }
    )
    doc.insert(ignore_permissions=True)
    doc.reload()
    return doc


def _ensure_lot(item_name: str, qty: float, cost: float) -> str:
    existing = frappe.db.get_value(
        "Ledgix Stock Lot",
        {"item": item_name, "status": ["!=", "Cancelled"]},
        "name",
        order_by="creation asc",
    )
    if existing:
        return existing
    doc = frappe.get_doc(
        {
            "doctype": "Ledgix Stock Lot",
            "item": item_name,
            "purchase_date": nowdate(),
            "status": "Open",
            "purchased_qty": qty,
            "sold_qty": 0,
            "returned_qty": 0,
            "remaining_qty": qty,
            "cost_rate": cost,
            "total_cost": qty * cost,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_serial(item_name: str, serial_no: str, cost: float) -> str:
    existing = frappe.db.get_value("Ledgix Stock Serial", {"serial_no": serial_no}, "name")
    if existing:
        owner = frappe.db.get_value("Ledgix Stock Serial", existing, "item")
        if owner != item_name:
            frappe.throw(f"Legacy serial {serial_no!r} belongs to {owner!r}, expected {item_name!r}.")
        return existing
    doc = frappe.get_doc(
        {
            "doctype": "Ledgix Stock Serial",
            "serial_no": serial_no,
            "item": item_name,
            "status": "Available",
            "purchase_date": nowdate(),
            "cost_rate": cost,
            "notes": "Phase 5 migration fixture",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item_price(item_name: str, rate: float) -> str:
    existing = frappe.db.get_value(
        "Ledgix Item Price",
        {"item": item_name, "price_list": PRICE_LIST, "enabled": 1},
        "name",
        order_by="creation asc",
    )
    if existing:
        doc = frappe.get_doc("Ledgix Item Price", existing)
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Ledgix Item Price",
                "item": item_name,
                "price_list": PRICE_LIST,
            }
        )
    doc.rate = rate
    doc.uom = "Piece"
    doc.enabled = 1
    doc.effective_from = nowdate()
    doc.effective_to = None
    doc.notes = "Phase 5 explicit price fixture"
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_customer() -> str:
    if frappe.db.exists("Ledgix Customer", CUSTOMER):
        doc = frappe.get_doc("Ledgix Customer", CUSTOMER)
    else:
        doc = frappe.get_doc({"doctype": "Ledgix Customer", "customer_name": CUSTOMER})
    values = {
        "customer_type": "Retail",
        "is_active": 1,
        "mobile_number": "03001234567",
        "email_address": "p5.customer@example.com",
        "default_price_list": PRICE_LIST,
        "payment_terms_days": 30,
        "credit_limit": 5000,
        "address_line_1": "Phase 5 Customer Street",
        "area": "Integration Area",
        "city": "Karachi",
        "notes": "Phase 5 customer fixture",
        "buyer_registration_type": "Registered",
        "buyer_ntn_cnic": "1234567",
        "buyer_strn": "STRN-P5",
        "buyer_province": "Sindh",
        "buyer_fbr_address": "Phase 5 Customer Street, Karachi",
    }
    for key, value in values.items():
        doc.set(key, value)
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_supplier() -> str:
    if frappe.db.exists("Ledgix Supplier", SUPPLIER):
        doc = frappe.get_doc("Ledgix Supplier", SUPPLIER)
    else:
        doc = frappe.get_doc({"doctype": "Ledgix Supplier", "supplier_name": SUPPLIER})
    values = {
        "company_name": "P5 Supplier Company",
        "supplier_type": "Local",
        "mobile_number": "03007654321",
        "email_address": "p5.supplier@example.com",
        "is_active": 1,
        "opening_balance": 250,
        "address": "Phase 5 Supplier Street",
        "city": "Karachi",
        "notes": "Phase 5 supplier fixture",
    }
    for key, value in values.items():
        doc.set(key, value)
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_payment_method() -> str:
    if frappe.db.exists("Ledgix Payment Method", PAYMENT_METHOD):
        doc = frappe.get_doc("Ledgix Payment Method", PAYMENT_METHOD)
    else:
        doc = frappe.get_doc(
            {"doctype": "Ledgix Payment Method", "payment_method_name": PAYMENT_METHOD}
        )
    doc.method_type = "Wallet"
    doc.enabled = 1
    doc.sort_order = 7
    doc.requires_reference = 1
    doc.allow_change = 0
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_item_profile(item_name: str) -> str:
    existing = frappe.db.get_value(
        "Ledgix Item Tax Profile", {"item": item_name}, "name", order_by="creation asc"
    )
    if existing:
        doc = frappe.get_doc("Ledgix Item Tax Profile", existing)
    else:
        doc = frappe.get_doc({"doctype": "Ledgix Item Tax Profile", "item": item_name})
    doc.erpnext_item = None
    doc.tax_category = TAX_CATEGORY
    doc.taxable = 1
    doc.active = 1
    doc.needs_review = 0
    doc.tax_basis = "Transaction Value"
    doc.hs_code = "0101.21"
    doc.uom_for_fbr = "Numbers, pieces, units"
    doc.sales_type = "Goods at standard rate"
    doc.fbr_rate_description = "18%"
    doc.scenario_id = "SN001"
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_legacy_fixtures() -> dict:
    _ensure_tax_category()
    _ensure_category()
    _ensure_price_list()
    normal = _ensure_legacy_item(NORMAL_ITEM, "Normal", 5, 100, 150, "P5BAR001", "P5SKU001")
    batch = _ensure_legacy_item(BATCH_ITEM, "Lot Based", 3, 110, 165, "P5BAR002", "P5SKU002")
    serial = _ensure_legacy_item(SERIAL_ITEM, "Serial Based", 2, 120, 180, "P5BAR003", "P5SKU003")
    lot = _ensure_lot(batch.name, 3, 110)
    serial_rows = [_ensure_serial(serial.name, serial_no, 120) for serial_no in SERIALS]
    prices = {
        normal.name: _ensure_item_price(normal.name, 155),
        batch.name: _ensure_item_price(batch.name, 170),
        serial.name: _ensure_item_price(serial.name, 185),
    }
    customer = _ensure_customer()
    supplier = _ensure_supplier()
    method = _ensure_payment_method()
    profiles = {item.name: _ensure_item_profile(item.name) for item in (normal, batch, serial)}
    frappe.db.commit()
    return {
        "category": CATEGORY,
        "price_list": PRICE_LIST,
        "items": [normal.name, batch.name, serial.name],
        "lot": lot,
        "serial_rows": serial_rows,
        "prices": prices,
        "customer": customer,
        "supplier": supplier,
        "payment_method": method,
        "profiles": profiles,
    }


def _target_counts() -> dict:
    item_names = frappe.get_all("Item", filters={"item_code": ["like", f"{PREFIX}%"]}, pluck="name", limit_page_length=0)
    return {
        "item_groups": frappe.db.count("Item Group", {"custom_ledgix_legacy_category": ["like", f"{PREFIX}%"]}),
        "items": len(item_names),
        "price_lists": frappe.db.count("Price List", {"custom_ledgix_legacy_price_list": ["like", f"{PREFIX}%"]}),
        "item_prices": frappe.db.count("Item Price", {"item_code": ["in", item_names]}) if item_names else 0,
        "customers": frappe.db.count("Customer", {"custom_ledgix_legacy_customer": ["like", f"{PREFIX}%"]}),
        "suppliers": frappe.db.count("Supplier", {"custom_ledgix_legacy_supplier": ["like", f"{PREFIX}%"]}),
        "payment_methods": frappe.db.count("Mode of Payment", {"custom_ledgix_legacy_payment_method": ["like", f"{PREFIX}%"]}),
        "opening_entries": frappe.db.count("Stock Entry", {"remarks": ["like", "LEDGIX-P5-OPENING:P5-%"], "docstatus": 1}),
    }


def _legacy_counts() -> dict:
    return {
        "categories": frappe.db.count("Ledgix Category", {"category_name": ["like", f"{PREFIX}%"]}),
        "items": frappe.db.count("Ledgix Item", {"item_code": ["like", f"{PREFIX}%"]}),
        "price_lists": frappe.db.count("Ledgix Price List", {"price_list_name": ["like", f"{PREFIX}%"]}),
        "customers": frappe.db.count("Ledgix Customer", {"customer_name": ["like", f"{PREFIX}%"]}),
        "suppliers": frappe.db.count("Ledgix Supplier", {"supplier_name": ["like", f"{PREFIX}%"]}),
        "payment_methods": frappe.db.count("Ledgix Payment Method", {"payment_method_name": ["like", f"{PREFIX}%"]}),
    }


def _compact(report: dict) -> dict:
    stages = {}
    for name, values in (report.get("stages") or {}).items():
        stages[name] = {key: values.get(key, 0) for key in ("created", "updated", "matched", "skipped")}
    return {
        "passed": bool(report.get("passed")),
        "dry_run": bool(report.get("dry_run")),
        "rolled_back": bool(report.get("rolled_back")),
        "stages": stages,
        "conflicts": report.get("conflicts") or [],
        "errors": report.get("errors") or [],
        "deferred": report.get("deferred") or [],
        "reconciliation": report.get("reconciliation") or {},
        "legacy_master_freeze_performed": bool(report.get("legacy_master_freeze_performed")),
        "transaction_authority_cutover_performed": bool(report.get("transaction_authority_cutover_performed")),
    }


def _target_evidence(warehouse: str, fixtures: dict) -> dict:
    item_group = frappe.get_doc("Item Group", CATEGORY)
    items = {code: frappe.get_doc("Item", code) for code in (NORMAL_ITEM, BATCH_ITEM, SERIAL_ITEM)}
    customer_name = frappe.db.get_value("Customer", {"custom_ledgix_legacy_customer": fixtures["customer"]}, "name")
    supplier_name = frappe.db.get_value("Supplier", {"custom_ledgix_legacy_supplier": fixtures["supplier"]}, "name")
    customer = frappe.get_doc("Customer", customer_name) if customer_name else None
    supplier = frappe.get_doc("Supplier", supplier_name) if supplier_name else None
    method = frappe.get_doc("Mode of Payment", PAYMENT_METHOD)

    item_price_rows = {}
    for item_name, legacy_price in fixtures["prices"].items():
        row = frappe.db.get_value(
            "Item Price",
            {ITEM_PRICE_PROVENANCE_FIELD: legacy_price},
            [
                "name",
                "item_code",
                "price_list",
                "price_list_rate",
                "uom",
                "valid_from",
                ITEM_PRICE_PROVENANCE_FIELD,
            ],
            as_dict=True,
        )
        item_price_rows[item_name] = dict(row or {})

    credit_limit = 0.0
    if customer:
        row = next((row for row in customer.credit_limits if row.company == TEST_COMPANY), None)
        credit_limit = flt(row.credit_limit) if row else 0.0

    profiles = {
        item_name: frappe.db.get_value(
            "Ledgix Item Tax Profile", fixtures["profiles"][item_name], "erpnext_item"
        )
        for item_name in fixtures["items"]
    }

    batches = frappe.db.get_value("Batch", fixtures["lot"], ["name", "item"], as_dict=True)
    serial_docs = {
        serial_no: frappe.db.get_value("Serial No", serial_no, ["name", "item_code", "warehouse"], as_dict=True)
        for serial_no in SERIALS
    }
    return {
        "item_group": {
            "name": item_group.name,
            "legacy": item_group.custom_ledgix_legacy_category,
            "active": cint(item_group.custom_ledgix_category_active),
            "icon": item_group.custom_ledgix_category_icon,
            "accent_color": item_group.custom_ledgix_accent_color,
            "tax_defaults_enabled": cint(item_group.custom_ledgix_tax_defaults_enabled),
            "tax_category": item_group.custom_ledgix_default_tax_category,
            "sales_type": item_group.custom_ledgix_default_sales_type,
        },
        "items": {
            code: {
                "legacy": doc.custom_ledgix_legacy_item,
                "item_group": doc.item_group,
                "stock_uom": doc.stock_uom,
                "has_batch_no": cint(doc.has_batch_no),
                "has_serial_no": cint(doc.has_serial_no),
                "sku": doc.custom_ledgix_legacy_sku,
                "minimum_stock": flt(doc.custom_ledgix_minimum_stock),
                "barcodes": [row.barcode for row in doc.barcodes],
                "bin_qty": flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": warehouse}, "actual_qty")),
            }
            for code, doc in items.items()
        },
        "item_prices": item_price_rows,
        "customer": {
            "name": customer.name if customer else "",
            "group": customer.customer_group if customer else "",
            "type": customer.customer_type if customer else "",
            "default_price_list": customer.default_price_list if customer else "",
            "payment_terms": customer.payment_terms if customer else "",
            "credit_limit": credit_limit,
            "primary_contact": customer.customer_primary_contact if customer else "",
            "primary_address": customer.customer_primary_address if customer else "",
            "buyer_ntn": customer.custom_ledgix_buyer_ntn_cnic if customer else "",
            "buyer_province": customer.custom_ledgix_buyer_province if customer else "",
        },
        "supplier": {
            "name": supplier.name if supplier else "",
            "group": supplier.supplier_group if supplier else "",
            "primary_contact": supplier.supplier_primary_contact if supplier else "",
            "primary_address": supplier.supplier_primary_address if supplier else "",
        },
        "payment_method": {
            "name": method.name,
            "type": method.type,
            "enabled": cint(method.enabled),
            "legacy_type": method.custom_ledgix_legacy_method_type,
            "sort_order": cint(method.custom_ledgix_sort_order),
            "requires_reference": cint(method.custom_ledgix_requires_reference),
            "allow_change": cint(method.custom_ledgix_allow_change),
        },
        "profiles": profiles,
        "batch": dict(batches or {}),
        "serials": {key: dict(value or {}) for key, value in serial_docs.items()},
    }


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")
    erpnext_phase5_extensions.sync_all()
    warehouse = _leaf_warehouse()
    fixtures = _ensure_legacy_fixtures()

    legacy_before = _legacy_counts()
    targets_before_dry = _target_counts()
    dry = migration.run(
        dry_run=1,
        source_prefix=PREFIX,
        company=TEST_COMPANY,
        warehouse=warehouse,
        migrate_opening_stock=1,
    )
    targets_after_dry = _target_counts()

    first = migration.run(
        dry_run=0,
        source_prefix=PREFIX,
        company=TEST_COMPANY,
        warehouse=warehouse,
        migrate_opening_stock=1,
    )
    targets_after_first = _target_counts()

    second = migration.run(
        dry_run=0,
        source_prefix=PREFIX,
        company=TEST_COMPANY,
        warehouse=warehouse,
        migrate_opening_stock=1,
    )
    targets_after_second = _target_counts()
    legacy_after = _legacy_counts()
    evidence = _target_evidence(warehouse, fixtures)

    deferred_reasons = [row.get("reason", "") for row in first.get("deferred") or []]
    checks = {
        "dry_run_passed": bool(dry.get("passed")),
        "dry_run_rolled_back": bool(dry.get("rolled_back")),
        "dry_run_no_target_count_change": targets_before_dry == targets_after_dry,
        "first_migration_passed": bool(first.get("passed")),
        "second_migration_passed": bool(second.get("passed")),
        "rerun_target_counts_stable": targets_after_first == targets_after_second,
        "legacy_records_not_deleted": legacy_before == legacy_after,
        "first_no_conflicts": not first.get("conflicts"),
        "second_no_conflicts": not second.get("conflicts"),
        "category_identity_native": evidence["item_group"]["legacy"] == CATEGORY,
        "category_metadata_preserved": (
            evidence["item_group"]["active"] == 1
            and evidence["item_group"]["icon"] == "shopping-bag"
            and evidence["item_group"]["accent_color"] == "#A43A47"
            and evidence["item_group"]["tax_defaults_enabled"] == 1
            and evidence["item_group"]["tax_category"] == TAX_CATEGORY
            and evidence["item_group"]["sales_type"] == "Goods at standard rate"
        ),
        "normal_item_mapped": (
            evidence["items"][NORMAL_ITEM]["legacy"] == NORMAL_ITEM
            and evidence["items"][NORMAL_ITEM]["stock_uom"] == "Nos"
            and evidence["items"][NORMAL_ITEM]["sku"] == "P5SKU001"
            and "P5BAR001" in evidence["items"][NORMAL_ITEM]["barcodes"]
            and abs(evidence["items"][NORMAL_ITEM]["minimum_stock"] - 2) < 0.001
        ),
        "batch_tracking_mapped": evidence["items"][BATCH_ITEM]["has_batch_no"] == 1,
        "serial_tracking_mapped": evidence["items"][SERIAL_ITEM]["has_serial_no"] == 1,
        "explicit_item_prices_mapped": all(
            row.get("price_list") == PRICE_LIST and flt(row.get("price_list_rate")) > 0
            for row in evidence["item_prices"].values()
        ),
        "customer_pricing_credit_terms_mapped": (
            evidence["customer"]["group"] == "Retail"
            and evidence["customer"]["type"] == "Individual"
            and evidence["customer"]["default_price_list"] == PRICE_LIST
            and evidence["customer"]["payment_terms"] == "Ledgix Net 30"
            and abs(evidence["customer"]["credit_limit"] - 5000) < 0.01
        ),
        "customer_contact_address_mapped": bool(
            evidence["customer"]["primary_contact"] and evidence["customer"]["primary_address"]
        ),
        "customer_fbr_fields_mapped": (
            evidence["customer"]["buyer_ntn"] == "1234567"
            and evidence["customer"]["buyer_province"] == "Sindh"
        ),
        "supplier_group_contact_address_mapped": (
            evidence["supplier"]["group"] == "Local"
            and bool(evidence["supplier"]["primary_contact"])
            and bool(evidence["supplier"]["primary_address"])
        ),
        "supplier_opening_balance_deferred": any("supplier AP/opening balances" in reason for reason in deferred_reasons),
        "payment_method_policy_preserved": (
            evidence["payment_method"]["type"] == "Phone"
            and evidence["payment_method"]["legacy_type"] == "Wallet"
            and evidence["payment_method"]["sort_order"] == 7
            and evidence["payment_method"]["requires_reference"] == 1
            and evidence["payment_method"]["allow_change"] == 0
        ),
        "all_item_profiles_relinked": all(value == item_name for item_name, value in evidence["profiles"].items()),
        "normal_opening_stock_exact": abs(evidence["items"][NORMAL_ITEM]["bin_qty"] - 5) < 0.005,
        "batch_opening_stock_exact": abs(evidence["items"][BATCH_ITEM]["bin_qty"] - 3) < 0.005,
        "serial_opening_stock_exact": abs(evidence["items"][SERIAL_ITEM]["bin_qty"] - 2) < 0.005,
        "legacy_lot_became_erpnext_batch": evidence["batch"].get("item") == BATCH_ITEM,
        "legacy_serial_numbers_preserved": all(
            row.get("item_code") == SERIAL_ITEM for row in evidence["serials"].values()
        ),
        "master_freeze_not_performed": not first.get("legacy_master_freeze_performed"),
        "transaction_cutover_not_performed": not first.get("transaction_authority_cutover_performed"),
    }

    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": TEST_COMPANY,
        "warehouse": warehouse,
        "fixtures": fixtures,
        "legacy_counts_before": legacy_before,
        "legacy_counts_after": legacy_after,
        "target_counts_before_dry": targets_before_dry,
        "target_counts_after_dry": targets_after_dry,
        "target_counts_after_first": targets_after_first,
        "target_counts_after_second": targets_after_second,
        "dry_run": _compact(dry),
        "first_migration": _compact(first),
        "second_migration": _compact(second),
        "evidence": evidence,
        "checks": checks,
        "phase5_complete": all(checks.values()),
        "phase6_ready": all(checks.values()),
        "next_phase": "Phase 6 — Selling, Payments and Returns Cutover",
        "legacy_master_freeze_performed": False,
        "transaction_authority_cutover_performed": False,
    }
    result["passed"] = result["phase5_complete"]
    frappe.db.commit()
    return result