from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api import stock_ops
from ledgix_saas.migration import erpnext_phase5_master_migration_gate as base
from ledgix_saas.setup import erpnext_extensions


NAMES = {
    "CATEGORY": "P5-Retail-Category",
    "PRICE_LIST": "P5-Retail",
    "CUSTOMER": "P5-Customer",
    "SUPPLIER": "P5-Supplier",
    "PAYMENT_METHOD": "P5-Wallet",
    "TAX_CATEGORY": "P5-Standard-18",
}

NONSTOCK_PREFIX = "P5N-"
NONSTOCK_CATEGORY = "P5N-Category"
NONSTOCK_ITEM = "P5N-SERIAL-META"


def _apply_names() -> dict[str, str]:
    previous = {}
    for key, value in NAMES.items():
        previous[key] = getattr(base, key)
        setattr(base, key, value)
    return previous


def _restore_names(previous: dict[str, str]) -> None:
    for key, value in previous.items():
        setattr(base, key, value)


def _ensure_exact_serial_opening(serial_item) -> list[str]:
    expected = list(base.SERIALS)
    rows = frappe.get_all(
        "Ledgix Stock Serial",
        filters={"item": serial_item.name, "status": ["!=", "Cancelled"]},
        fields=["name", "serial_no", "status"],
        order_by="creation asc, name asc",
        limit_page_length=0,
    )
    current_qty = flt(serial_item.current_stock)

    if current_qty <= 0.000001 and not rows:
        stock_ops.record_opening_stock(
            serial_item.name,
            len(expected),
            serial_numbers="\n".join(expected),
        )
        serial_item.reload()
        rows = frappe.get_all(
            "Ledgix Stock Serial",
            filters={"item": serial_item.name, "status": ["!=", "Cancelled"]},
            fields=["name", "serial_no", "status"],
            order_by="creation asc, name asc",
            limit_page_length=0,
        )
        current_qty = flt(serial_item.current_stock)

    actual = [row.serial_no for row in rows if row.status in {"Available", "Returned"}]
    if current_qty != len(expected) or sorted(actual) != sorted(expected):
        frappe.throw(
            "Phase 5 serial fixture is inconsistent: "
            f"current_stock={current_qty}, available={actual}, expected={expected}."
        )
    return [row.name for row in rows if row.serial_no in expected]


def _ensure_legacy_fixtures() -> dict:
    base._ensure_tax_category()
    base._ensure_category()
    base._ensure_price_list()

    normal = base._ensure_legacy_item(
        base.NORMAL_ITEM, "Normal", 5, 100, 150, "P5BAR001", "P5SKU001"
    )
    batch = base._ensure_legacy_item(
        base.BATCH_ITEM, "Lot Based", 3, 110, 165, "P5BAR002", "P5SKU002"
    )
    # Serial Based legacy opening_stock auto-generates identities. Seed zero and
    # then post the exact serial numbers so identity parity is deterministic.
    serial = base._ensure_legacy_item(
        base.SERIAL_ITEM, "Serial Based", 0, 120, 180, "P5BAR003", "P5SKU003"
    )

    lot = base._ensure_lot(batch.name, 3, 110)
    serial_rows = _ensure_exact_serial_opening(serial)
    prices = {
        normal.name: base._ensure_item_price(normal.name, 155),
        batch.name: base._ensure_item_price(batch.name, 170),
        serial.name: base._ensure_item_price(serial.name, 185),
    }
    customer = base._ensure_customer()
    supplier = base._ensure_supplier()
    method = base._ensure_payment_method()
    profiles = {
        item.name: base._ensure_item_profile(item.name)
        for item in (normal, batch, serial)
    }
    frappe.db.commit()
    return {
        "category": base.CATEGORY,
        "price_list": base.PRICE_LIST,
        "items": [normal.name, batch.name, serial.name],
        "lot": lot,
        "serial_rows": serial_rows,
        "prices": prices,
        "customer": customer,
        "supplier": supplier,
        "payment_method": method,
        "profiles": profiles,
    }


def _ensure_nonstock_fixture() -> None:
    if frappe.db.exists("Ledgix Category", NONSTOCK_CATEGORY):
        category = frappe.get_doc("Ledgix Category", NONSTOCK_CATEGORY)
    else:
        category = frappe.get_doc(
            {"doctype": "Ledgix Category", "category_name": NONSTOCK_CATEGORY}
        )
    category.is_active = 1
    category.description = "Phase 5 invoice-only migration proof"
    if category.is_new():
        category.insert(ignore_permissions=True)
    else:
        category.save(ignore_permissions=True)

    if frappe.db.exists("Ledgix Item", NONSTOCK_ITEM):
        item = frappe.get_doc("Ledgix Item", NONSTOCK_ITEM)
        if item.category != NONSTOCK_CATEGORY or item.tracking_type != "Serial Based":
            frappe.throw("P5N invoice-only fixture structure changed unexpectedly.")
    else:
        item = frappe.get_doc(
            {
                "doctype": "Ledgix Item",
                "item_code": NONSTOCK_ITEM,
                "item_name": "Phase 5 Invoice Only Item",
                "category": NONSTOCK_CATEGORY,
                "sku": "P5NSKU001",
                "unit": "Piece",
                "tracking_type": "Serial Based",
                "active": 1,
                "opening_stock": 0,
                "minimum_stock": 0,
                "cost_price": 0,
                "selling_price": 500,
            }
        )
        item.insert(ignore_permissions=True)
    frappe.db.commit()


def _prove_invoice_only_nonstock() -> dict:
    _ensure_nonstock_fixture()
    profile = frappe.get_single("Ledgix Business Profile")
    feature_fields = tuple(erpnext_extensions.FEATURE_FIELDS)
    original = {
        "business_profile": profile.business_profile,
        "use_profile_defaults": cint(profile.use_profile_defaults),
        **{field: cint(profile.get(field)) for field in feature_fields},
    }

    try:
        profile.business_profile = "Invoice + FBR Only"
        profile.use_profile_defaults = 1
        erpnext_extensions.apply_business_profile_defaults(profile)
        profile.save(ignore_permissions=True)
        frappe.db.commit()

        report = base.migration.run(
            dry_run=0,
            source_prefix=NONSTOCK_PREFIX,
            company=base.TEST_COMPANY,
            warehouse=None,
            migrate_opening_stock=0,
        )
        item = frappe.get_doc("Item", NONSTOCK_ITEM)
        sle_count = frappe.db.count(
            "Stock Ledger Entry", {"item_code": NONSTOCK_ITEM, "is_cancelled": 0}
        )
        checks = {
            "migration_passed": bool(report.get("passed")),
            "profile_inventory_disabled": not bool(
                cint(erpnext_extensions.get_effective_business_features().get("enable_inventory"))
            ),
            "item_is_nonstock": cint(item.is_stock_item) == 0,
            "no_batch_flag": cint(item.has_batch_no) == 0,
            "no_serial_flag": cint(item.has_serial_no) == 0,
            "legacy_tracking_preserved": item.custom_ledgix_legacy_tracking_type == "Serial Based",
            "no_stock_ledger": sle_count == 0,
        }
        return {
            "item": item.name,
            "legacy_item": item.custom_ledgix_legacy_item,
            "legacy_tracking": item.custom_ledgix_legacy_tracking_type,
            "is_stock_item": cint(item.is_stock_item),
            "has_batch_no": cint(item.has_batch_no),
            "has_serial_no": cint(item.has_serial_no),
            "stock_ledger_entries": sle_count,
            "migration_conflicts": report.get("conflicts") or [],
            "migration_deferred": report.get("deferred") or [],
            "checks": checks,
            "passed": all(checks.values()),
        }
    finally:
        restored = frappe.get_single("Ledgix Business Profile")
        for field, value in original.items():
            restored.set(field, value)
        restored.save(ignore_permissions=True)
        frappe.db.commit()


def run() -> dict:
    previous_names = _apply_names()
    original_fixtures = base._ensure_legacy_fixtures
    base._ensure_legacy_fixtures = _ensure_legacy_fixtures
    try:
        result = base.run()
        nonstock = _prove_invoice_only_nonstock()
        result["invoice_only_nonstock_proof"] = nonstock
        result.setdefault("checks", {})["invoice_only_profile_creates_nonstock_items"] = bool(
            nonstock.get("passed")
        )
        complete = all((result.get("checks") or {}).values())
        result["phase5_complete"] = complete
        result["phase6_ready"] = complete
        result["passed"] = complete
        result["fixture_namespace"] = dict(NAMES)
        return result
    finally:
        base._ensure_legacy_fixtures = original_fixtures
        _restore_names(previous_names)