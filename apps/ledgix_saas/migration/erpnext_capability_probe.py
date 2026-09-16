from __future__ import annotations

from collections import OrderedDict

import frappe


# Read-only schema probe used during the ERPNext-core migration. Keep this list
# focused on fields that decide whether a Ledgix concept can move to a native
# ERPNext model without inventing another parallel source of truth.
CAPABILITIES = OrderedDict(
    {
        "masters": OrderedDict(
            {
                "Item": [
                    "item_code",
                    "item_name",
                    "item_group",
                    "stock_uom",
                    "is_stock_item",
                    "has_batch_no",
                    "has_serial_no",
                    "disabled",
                    "barcodes",
                    "valuation_method",
                ],
                "Item Group": ["item_group_name", "parent_item_group", "is_group"],
                "UOM": ["uom_name", "must_be_whole_number"],
                "Customer": [
                    "customer_name",
                    "customer_type",
                    "customer_group",
                    "territory",
                    "default_price_list",
                    "payment_terms",
                    "credit_limits",
                    "tax_id",
                ],
                "Supplier": [
                    "supplier_name",
                    "supplier_group",
                    "supplier_type",
                    "tax_id",
                ],
                "Address": ["address_title", "address_type", "address_line1", "city", "links"],
                "Contact": ["first_name", "last_name", "email_ids", "phone_nos", "links"],
            }
        ),
        "pricing": OrderedDict(
            {
                "Price List": ["price_list_name", "enabled", "buying", "selling", "currency"],
                "Item Price": [
                    "item_code",
                    "price_list",
                    "price_list_rate",
                    "currency",
                    "uom",
                    "batch_no",
                    "valid_from",
                    "valid_upto",
                ],
                "Pricing Rule": [
                    "title",
                    "apply_on",
                    "price_or_product_discount",
                    "rate_or_discount",
                    "discount_percentage",
                    "rate",
                    "for_price_list",
                    "selling",
                    "buying",
                    "valid_from",
                    "valid_upto",
                ],
            }
        ),
        "sales": OrderedDict(
            {
                "Sales Invoice": [
                    "customer",
                    "posting_date",
                    "due_date",
                    "items",
                    "taxes",
                    "is_pos",
                    "payments",
                    "update_stock",
                    "is_return",
                    "return_against",
                    "net_total",
                    "total_taxes_and_charges",
                    "grand_total",
                    "paid_amount",
                    "outstanding_amount",
                ],
                "POS Invoice": [
                    "customer",
                    "posting_date",
                    "pos_profile",
                    "items",
                    "taxes",
                    "payments",
                    "update_stock",
                    "is_return",
                    "return_against",
                    "net_total",
                    "total_taxes_and_charges",
                    "grand_total",
                    "paid_amount",
                    "outstanding_amount",
                ],
            }
        ),
        "payments": OrderedDict(
            {
                "Mode of Payment": ["mode_of_payment", "type", "enabled", "accounts"],
                "Payment Entry": [
                    "payment_type",
                    "party_type",
                    "party",
                    "mode_of_payment",
                    "paid_from",
                    "paid_to",
                    "paid_amount",
                    "received_amount",
                    "reference_no",
                    "reference_date",
                    "references",
                    "unallocated_amount",
                ],
            }
        ),
        "buying": OrderedDict(
            {
                "Purchase Order": [
                    "supplier",
                    "transaction_date",
                    "schedule_date",
                    "items",
                    "taxes",
                    "grand_total",
                    "status",
                ],
                "Purchase Receipt": [
                    "supplier",
                    "posting_date",
                    "items",
                    "taxes",
                    "is_return",
                    "return_against",
                    "grand_total",
                ],
                "Purchase Invoice": [
                    "supplier",
                    "posting_date",
                    "due_date",
                    "items",
                    "taxes",
                    "update_stock",
                    "is_return",
                    "return_against",
                    "grand_total",
                    "outstanding_amount",
                ],
            }
        ),
        "stock": OrderedDict(
            {
                "Warehouse": ["warehouse_name", "company", "parent_warehouse", "is_group", "disabled"],
                "Stock Entry": [
                    "stock_entry_type",
                    "purpose",
                    "posting_date",
                    "from_warehouse",
                    "to_warehouse",
                    "items",
                ],
                "Stock Ledger Entry": [
                    "item_code",
                    "warehouse",
                    "posting_date",
                    "actual_qty",
                    "qty_after_transaction",
                    "valuation_rate",
                    "stock_value",
                    "voucher_type",
                    "voucher_no",
                    "serial_and_batch_bundle",
                ],
                "Batch": ["batch_id", "item", "manufacturing_date", "expiry_date", "disabled"],
                "Serial No": ["serial_no", "item_code", "warehouse", "status", "batch_no"],
                "Serial and Batch Bundle": [
                    "item_code",
                    "warehouse",
                    "type_of_transaction",
                    "voucher_type",
                    "voucher_no",
                    "entries",
                ],
            }
        ),
        "pos_shift": OrderedDict(
            {
                "POS Profile": [
                    "company",
                    "warehouse",
                    "customer",
                    "selling_price_list",
                    "payments",
                    "print_format",
                ],
                "POS Opening Entry": [
                    "user",
                    "company",
                    "period_start_date",
                    "pos_profile",
                    "balance_details",
                    "status",
                ],
                "POS Closing Entry": [
                    "user",
                    "company",
                    "period_start_date",
                    "period_end_date",
                    "pos_opening_entry",
                    "payment_reconciliation",
                    "grand_total",
                    "status",
                ],
            }
        ),
    }
)


def _field_probe(meta, fieldname: str) -> dict:
    field = meta.get_field(fieldname)
    if not field:
        return {"exists": False}

    return {
        "exists": True,
        "fieldtype": field.fieldtype,
        "options": field.options or None,
        "reqd": bool(field.reqd),
        "read_only": bool(field.read_only),
    }


def _doctype_probe(doctype: str, fields: list[str]) -> dict:
    if not frappe.db.exists("DocType", doctype):
        return {
            "exists": False,
            "fields": {fieldname: {"exists": False} for fieldname in fields},
        }

    meta = frappe.get_meta(doctype)
    custom_fields = sorted(
        field.fieldname
        for field in meta.fields
        if getattr(field, "is_custom_field", False) or field.fieldname.startswith("custom_")
    )

    return {
        "exists": True,
        "module": meta.module,
        "is_submittable": bool(getattr(meta, "is_submittable", False)),
        "is_single": bool(getattr(meta, "issingle", False)),
        "custom_fields": custom_fields,
        "fields": {fieldname: _field_probe(meta, fieldname) for fieldname in fields},
    }


def run() -> dict:
    """Return a read-only ERPNext schema capability snapshot for the current site."""

    apps = frappe.get_installed_apps()
    result = OrderedDict(
        {
            "site": frappe.local.site,
            "installed_apps": apps,
            "erpnext_installed": "erpnext" in apps,
            "domains": OrderedDict(),
        }
    )

    for domain, doctypes in CAPABILITIES.items():
        result["domains"][domain] = OrderedDict(
            (doctype, _doctype_probe(doctype, fields)) for doctype, fields in doctypes.items()
        )

    return result


def run_summary() -> dict:
    """Return the compact gap view used for the first Phase 2 terminal probe."""

    full = run()
    summary = OrderedDict(
        {
            "site": full["site"],
            "installed_apps": full["installed_apps"],
            "erpnext_installed": full["erpnext_installed"],
            "domains": OrderedDict(),
        }
    )

    for domain, doctypes in full["domains"].items():
        domain_summary = OrderedDict()
        for doctype, probe in doctypes.items():
            missing_fields = [
                fieldname
                for fieldname, field_probe in probe.get("fields", {}).items()
                if not field_probe.get("exists")
            ]
            domain_summary[doctype] = {
                "exists": probe.get("exists", False),
                "is_submittable": probe.get("is_submittable", False),
                "missing_fields": missing_fields,
                "custom_fields": probe.get("custom_fields", []),
            }
        summary["domains"][domain] = domain_summary

    return summary
