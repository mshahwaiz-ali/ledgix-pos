from __future__ import annotations

"""Explicit, idempotent migration from legacy Ledgix masters to ERPNext v15.

The service is intentionally *not* an after_migrate data hook.  Schema extensions
are installed automatically, but moving business data is an explicit operator
action with a dry-run, conflict report and reconciliation result.
"""

from dataclasses import dataclass
from typing import Any

import frappe
from frappe.utils import cint, flt, nowdate

from ledgix_saas.setup import erpnext_phase5_extensions


UNIT_MAP = {
    "Piece": "Nos",
    "Kg": "Kg",
    "Gram": "Gram",
    "Liter": "Litre",
    "Pack": "Pack",
}

CUSTOMER_TYPE_MAP = {
    "Retail": "Individual",
    "Wholesale": "Company",
    "B2B": "Company",
}

PAYMENT_TYPE_MAP = {
    "Cash": "Cash",
    "Card": "Bank",
    "Bank Transfer": "Bank",
    "Wallet": "Phone",
    "Other": "General",
}

IN_STOCK_SERIAL_STATUSES = {"Available", "Returned"}


@dataclass
class MigrationContext:
    company: str
    warehouse: str | None = None
    source_prefix: str | None = None
    dry_run: bool = True
    migrate_opening_stock: bool = False


class MasterMigration:
    def __init__(self, context: MigrationContext):
        self.ctx = context
        self.report: dict[str, Any] = {
            "company": context.company,
            "warehouse": context.warehouse or "",
            "source_prefix": context.source_prefix or "",
            "dry_run": bool(context.dry_run),
            "migrate_opening_stock": bool(context.migrate_opening_stock),
            "stages": {},
            "conflicts": [],
            "errors": [],
            "deferred": [],
        }
        self.item_map: dict[str, str] = {}
        self.category_map: dict[str, str] = {}
        self.price_list_map: dict[str, str] = {}
        self.customer_map: dict[str, str] = {}
        self.supplier_map: dict[str, str] = {}
        self.payment_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # reporting / safety
    # ------------------------------------------------------------------
    def _stage(self, name: str) -> dict:
        return self.report["stages"].setdefault(
            name,
            {"created": 0, "updated": 0, "matched": 0, "skipped": 0, "rows": []},
        )

    def _record(self, stage: str, action: str, source: str, target: str = "", detail: str = "") -> None:
        bucket = self._stage(stage)
        if action in bucket:
            bucket[action] += 1
        bucket["rows"].append(
            {"action": action, "source": source, "target": target, "detail": detail}
        )

    def _conflict(self, stage: str, source: str, target: str, reason: str) -> None:
        self.report["conflicts"].append(
            {"stage": stage, "source": source, "target": target, "reason": reason}
        )
        self._record(stage, "skipped", source, target, reason)

    def _defer(self, stage: str, source: str, reason: str, values: dict | None = None) -> None:
        self.report["deferred"].append(
            {"stage": stage, "source": source, "reason": reason, "values": values or {}}
        )

    def _source_rows(self, doctype: str, key_field: str) -> list:
        filters: dict[str, Any] = {}
        if self.ctx.source_prefix:
            filters[key_field] = ["like", f"{self.ctx.source_prefix}%"]
        return frappe.get_all(
            doctype,
            filters=filters,
            fields=["*"],
            order_by=f"{key_field} asc",
            limit_page_length=0,
        )

    def _assert_prerequisites(self) -> None:
        if not frappe.db.exists("Company", self.ctx.company):
            frappe.throw(f"ERPNext Company {self.ctx.company!r} does not exist.")
        required = (
            "Ledgix Category",
            "Ledgix Item",
            "Ledgix Price List",
            "Ledgix Item Price",
            "Ledgix Customer",
            "Ledgix Supplier",
            "Ledgix Payment Method",
            "Ledgix Item Tax Profile",
            "Item Group",
            "Item",
            "Price List",
            "Item Price",
            "Customer",
            "Supplier",
            "Mode of Payment",
        )
        missing = [name for name in required if not frappe.db.exists("DocType", name)]
        if missing:
            frappe.throw("Phase 5 migration prerequisites missing: " + ", ".join(missing))

        if self.ctx.migrate_opening_stock:
            if not self.ctx.warehouse:
                frappe.throw("An explicit ERPNext target warehouse is required for opening-stock migration.")
            row = frappe.db.get_value(
                "Warehouse",
                self.ctx.warehouse,
                ["company", "is_group", "disabled"],
                as_dict=True,
            )
            if not row or row.company != self.ctx.company or cint(row.is_group) or cint(row.disabled):
                frappe.throw(
                    f"Opening-stock target {self.ctx.warehouse!r} must be an enabled leaf Warehouse for {self.ctx.company!r}."
                )

    @staticmethod
    def _tree_root(doctype: str, parent_field: str, preferred: str) -> str:
        if frappe.db.exists(doctype, preferred):
            return preferred
        rows = frappe.get_all(
            doctype,
            filters={"is_group": 1},
            fields=["name", parent_field],
            order_by="lft asc",
            limit_page_length=0,
        )
        for row in rows:
            if not row.get(parent_field):
                return row.name
        frappe.throw(f"Could not resolve root {doctype}.")

    # ------------------------------------------------------------------
    # UOM / classification masters
    # ------------------------------------------------------------------
    def migrate_uoms(self) -> None:
        stage = "uoms"
        units = sorted({str(row.unit or "").strip() for row in self._source_rows("Ledgix Item", "item_code") if row.unit})
        for legacy in units:
            target = UNIT_MAP.get(legacy, legacy)
            if frappe.db.exists("UOM", target):
                self._record(stage, "matched", legacy, target)
                continue
            doc = frappe.get_doc({"doctype": "UOM", "uom_name": target})
            doc.insert(ignore_permissions=True)
            self._record(stage, "created", legacy, doc.name)

    def migrate_categories(self) -> None:
        stage = "categories"
        root = self._tree_root("Item Group", "parent_item_group", "All Item Groups")
        for source in self._source_rows("Ledgix Category", "category_name"):
            target_name = source.category_name
            existing = frappe.db.exists("Item Group", target_name)
            if existing:
                target = frappe.get_doc("Item Group", existing)
                marker = target.get("custom_ledgix_legacy_category")
                if cint(target.is_group):
                    self._conflict(stage, source.name, target.name, "existing Item Group is a group node")
                    continue
                if marker and marker != source.name:
                    self._conflict(stage, source.name, target.name, f"already owned by {marker}")
                    continue
                action = "updated" if marker == source.name else "matched"
            else:
                target = frappe.get_doc(
                    {
                        "doctype": "Item Group",
                        "item_group_name": target_name,
                        "parent_item_group": root,
                        "is_group": 0,
                    }
                )
                action = "created"

            target.custom_ledgix_legacy_category = source.name
            target.custom_ledgix_category_description = source.description or ""
            target.custom_ledgix_accent_color = source.accent_color or ""
            target.custom_ledgix_default_tax_category = source.default_tax_category or ""
            target.custom_ledgix_default_taxable = cint(source.default_taxable)
            target.custom_ledgix_default_sales_type = source.default_sales_type or ""
            target.custom_ledgix_default_uom_for_fbr = source.default_uom_for_fbr or ""
            target.custom_ledgix_default_scenario_id = source.default_scenario_id or ""
            if source.image and not target.image:
                target.image = source.image
            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)
            self.category_map[source.name] = target.name
            self._record(stage, action, source.name, target.name)

    def migrate_price_lists(self) -> None:
        stage = "price_lists"
        for source in self._source_rows("Ledgix Price List", "price_list_name"):
            target_name = source.price_list_name
            existing = frappe.db.exists("Price List", target_name)
            if existing:
                target = frappe.get_doc("Price List", existing)
                marker = target.get("custom_ledgix_legacy_price_list")
                if marker and marker != source.name:
                    self._conflict(stage, source.name, target.name, f"already owned by {marker}")
                    continue
                if target.currency and source.currency and target.currency != source.currency:
                    self._conflict(
                        stage,
                        source.name,
                        target.name,
                        f"currency mismatch ERPNext={target.currency} Ledgix={source.currency}",
                    )
                    continue
                action = "updated" if marker == source.name else "matched"
            else:
                target = frappe.get_doc(
                    {
                        "doctype": "Price List",
                        "price_list_name": target_name,
                        "currency": source.currency,
                        "selling": 1,
                        "buying": 0,
                    }
                )
                action = "created"

            target.enabled = cint(source.enabled)
            target.selling = 1
            target.custom_ledgix_legacy_price_list = source.name
            target.custom_ledgix_is_default_retail = cint(source.is_default_retail)
            target.custom_ledgix_priority = cint(source.priority)
            target.custom_ledgix_price_list_notes = source.notes or ""
            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)
            self.price_list_map[source.name] = target.name
            self._record(stage, action, source.name, target.name)

    # ------------------------------------------------------------------
    # Items / prices
    # ------------------------------------------------------------------
    def _item_expected(self, source) -> dict:
        tracking = str(source.tracking_type or "Normal")
        return {
            "item_group": self.category_map.get(source.category) or source.category or "Products",
            "stock_uom": UNIT_MAP.get(source.unit, source.unit or "Nos"),
            "has_batch_no": 1 if tracking == "Lot Based" else 0,
            "has_serial_no": 1 if tracking == "Serial Based" else 0,
        }

    def migrate_items(self) -> None:
        stage = "items"
        for source in self._source_rows("Ledgix Item", "item_code"):
            expected = self._item_expected(source)
            if source.category and not frappe.db.exists("Item Group", expected["item_group"]):
                self._conflict(stage, source.name, source.item_code, "target Item Group missing")
                continue
            if not frappe.db.exists("UOM", expected["stock_uom"]):
                self._conflict(stage, source.name, source.item_code, "target UOM missing")
                continue

            existing = frappe.db.exists("Item", source.item_code)
            if existing:
                target = frappe.get_doc("Item", existing)
                marker = target.get("custom_ledgix_legacy_item")
                if marker and marker != source.name:
                    self._conflict(stage, source.name, target.name, f"already owned by {marker}")
                    continue
                mismatches = {
                    field: {"erpnext": target.get(field), "ledgix": value}
                    for field, value in expected.items()
                    if str(target.get(field) or "") != str(value or "")
                }
                if not cint(target.is_stock_item):
                    mismatches["is_stock_item"] = {"erpnext": target.is_stock_item, "ledgix": 1}
                if mismatches:
                    self._conflict(stage, source.name, target.name, f"structural mismatch: {mismatches}")
                    continue
                action = "updated" if marker == source.name else "matched"
            else:
                target = frappe.get_doc(
                    {
                        "doctype": "Item",
                        "item_code": source.item_code,
                        "item_name": source.item_name or source.item_code,
                        "description": source.description or source.item_name or source.item_code,
                        "item_group": expected["item_group"],
                        "stock_uom": expected["stock_uom"],
                        "is_stock_item": 1,
                        "include_item_in_manufacturing": 0,
                        "valuation_method": "Moving Average",
                        "has_batch_no": expected["has_batch_no"],
                        "create_new_batch": 0,
                        "has_serial_no": expected["has_serial_no"],
                        "valuation_rate": max(flt(source.cost_price), 0),
                        "standard_rate": max(flt(source.selling_price), 0),
                    }
                )
                action = "created"

            target.item_name = source.item_name or source.item_code
            if source.description:
                target.description = source.description
            target.disabled = 0 if cint(source.active) else 1
            target.custom_ledgix_legacy_item = source.name
            target.custom_ledgix_legacy_sku = source.sku or ""
            target.custom_ledgix_minimum_stock = max(flt(source.minimum_stock), 0)

            if source.barcode:
                existing_barcodes = {str(row.barcode or "") for row in target.get("barcodes") or []}
                if source.barcode not in existing_barcodes:
                    target.append("barcodes", {"barcode": source.barcode, "uom": expected["stock_uom"]})

            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)
            self.item_map[source.name] = target.name
            self._record(stage, action, source.name, target.name)

    def migrate_item_prices(self) -> None:
        stage = "item_prices"
        for source in self._source_rows("Ledgix Item Price", "name"):
            legacy_item = source.item
            target_item = self.item_map.get(legacy_item)
            target_price_list = self.price_list_map.get(source.price_list)
            if not target_item or not target_price_list:
                self._conflict(stage, source.name, "", "item or price-list mapping missing")
                continue
            if not cint(source.enabled):
                self._record(stage, "skipped", source.name, "", "disabled legacy Item Price is intentionally not active in ERPNext")
                continue

            uom = UNIT_MAP.get(source.uom, source.uom or frappe.db.get_value("Item", target_item, "stock_uom"))
            reference = f"Ledgix Item Price:{source.name}"
            name = frappe.db.get_value("Item Price", {"reference": reference}, "name")
            if name:
                target = frappe.get_doc("Item Price", name)
                action = "updated"
            else:
                semantic_filters = {
                    "item_code": target_item,
                    "price_list": target_price_list,
                    "uom": uom,
                    "valid_from": source.effective_from,
                    "valid_upto": source.effective_to,
                }
                semantic = frappe.db.get_value("Item Price", semantic_filters, ["name", "price_list_rate", "reference"], as_dict=True)
                if semantic:
                    if semantic.reference and semantic.reference != reference:
                        self._conflict(stage, source.name, semantic.name, f"semantic price already has reference {semantic.reference}")
                        continue
                    if abs(flt(semantic.price_list_rate) - flt(source.rate)) > 0.005:
                        self._conflict(stage, source.name, semantic.name, "same price key exists with a different rate")
                        continue
                    target = frappe.get_doc("Item Price", semantic.name)
                    action = "matched"
                else:
                    target = frappe.get_doc(
                        {
                            "doctype": "Item Price",
                            "item_code": target_item,
                            "price_list": target_price_list,
                            "uom": uom,
                            "price_list_rate": flt(source.rate),
                            "valid_from": source.effective_from,
                            "valid_upto": source.effective_to,
                        }
                    )
                    action = "created"

            target.price_list_rate = flt(source.rate)
            target.reference = reference
            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)
            self._record(stage, action, source.name, target.name)

    # ------------------------------------------------------------------
    # party masters
    # ------------------------------------------------------------------
    def _ensure_customer_group(self, name: str) -> str:
        if frappe.db.exists("Customer Group", name):
            if cint(frappe.db.get_value("Customer Group", name, "is_group")):
                frappe.throw(f"Customer Group {name!r} exists as a group node.")
            return name
        root = self._tree_root("Customer Group", "parent_customer_group", "All Customer Groups")
        doc = frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": name,
                "parent_customer_group": root,
                "is_group": 0,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _ensure_supplier_group(self, name: str) -> str:
        if frappe.db.exists("Supplier Group", name):
            if cint(frappe.db.get_value("Supplier Group", name, "is_group")):
                frappe.throw(f"Supplier Group {name!r} exists as a group node.")
            return name
        root = self._tree_root("Supplier Group", "parent_supplier_group", "All Supplier Groups")
        doc = frappe.get_doc(
            {
                "doctype": "Supplier Group",
                "supplier_group_name": name,
                "parent_supplier_group": root,
                "is_group": 0,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _ensure_payment_terms(self, days: int) -> str:
        if days <= 0:
            return ""
        name = f"Ledgix Net {days}"
        if not frappe.db.exists("Payment Term", name):
            frappe.get_doc(
                {
                    "doctype": "Payment Term",
                    "payment_term_name": name,
                    "invoice_portion": 100,
                    "due_date_based_on": "Day(s) after invoice date",
                    "credit_days": days,
                    "description": f"Migrated Ledgix {days}-day payment term",
                }
            ).insert(ignore_permissions=True)
        if not frappe.db.exists("Payment Terms Template", name):
            frappe.get_doc(
                {
                    "doctype": "Payment Terms Template",
                    "template_name": name,
                    "terms": [
                        {
                            "payment_term": name,
                            "invoice_portion": 100,
                            "due_date_based_on": "Day(s) after invoice date",
                            "credit_days": days,
                        }
                    ],
                }
            ).insert(ignore_permissions=True)
        return name

    def _party_contact(self, target_doctype: str, target_name: str, source_doctype: str, source) -> str:
        mobile = source.get("mobile_number") or source.get("mobile") or ""
        email = source.get("email_address") or source.get("email") or ""
        if not mobile and not email:
            return ""
        source_key = f"{source_doctype}:{source.name}"
        existing = frappe.db.get_value("Contact", {"custom_ledgix_legacy_contact_source": source_key}, "name")
        if existing:
            contact = frappe.get_doc("Contact", existing)
        else:
            contact = frappe.get_doc(
                {
                    "doctype": "Contact",
                    "first_name": source.get("customer_name") or source.get("supplier_name") or source.name,
                    "custom_ledgix_legacy_contact_source": source_key,
                    "links": [{"link_doctype": target_doctype, "link_name": target_name}],
                }
            )
        contact.mobile_no = mobile
        contact.email_id = email
        if contact.is_new():
            contact.insert(ignore_permissions=True)
        else:
            contact.save(ignore_permissions=True)
        return contact.name

    def _party_address(self, target_doctype: str, target_name: str, source_doctype: str, source) -> str:
        address_line = source.get("address_line_1") or ""
        city = source.get("city") or ""
        area = source.get("area") or ""
        if not address_line and not city and not area:
            return ""
        if not address_line or not city:
            self._defer(
                "addresses",
                source.name,
                "ERPNext Address requires both a usable address line and city; raw legacy values retained on legacy master",
                {"address_line_1": address_line, "area": area, "city": city},
            )
            return ""

        source_key = f"{source_doctype}:{source.name}"
        existing = frappe.db.get_value("Address", {"custom_ledgix_legacy_address_source": source_key}, "name")
        if existing:
            address = frappe.get_doc("Address", existing)
        else:
            title = source.get("customer_name") or source.get("supplier_name") or source.name
            address = frappe.get_doc(
                {
                    "doctype": "Address",
                    "address_title": title,
                    "address_type": "Billing",
                    "custom_ledgix_legacy_address_source": source_key,
                    "links": [{"link_doctype": target_doctype, "link_name": target_name}],
                }
            )
        address.address_line1 = address_line
        address.address_line2 = area
        address.city = city
        address.country = "Pakistan"
        if address.is_new():
            address.insert(ignore_permissions=True)
        else:
            address.save(ignore_permissions=True)
        return address.name

    def migrate_customers(self) -> None:
        stage = "customers"
        for source in self._source_rows("Ledgix Customer", "customer_name"):
            group = self._ensure_customer_group(source.customer_type or "Retail")
            marker_name = frappe.db.get_value(
                "Customer", {"custom_ledgix_legacy_customer": source.name}, "name"
            )
            if marker_name:
                target = frappe.get_doc("Customer", marker_name)
                action = "updated"
            else:
                unmarked = frappe.db.get_value("Customer", {"customer_name": source.customer_name}, "name")
                if unmarked:
                    self._conflict(
                        stage,
                        source.name,
                        unmarked,
                        "same customer_name exists without Ledgix provenance; manual merge decision required",
                    )
                    continue
                target = frappe.get_doc(
                    {
                        "doctype": "Customer",
                        "customer_name": source.customer_name,
                        "customer_type": CUSTOMER_TYPE_MAP.get(source.customer_type, "Company"),
                        "customer_group": group,
                        "territory": "Pakistan",
                    }
                )
                action = "created"

            target.customer_name = source.customer_name
            target.customer_type = CUSTOMER_TYPE_MAP.get(source.customer_type, "Company")
            target.customer_group = group
            target.territory = "Pakistan"
            target.disabled = 0 if cint(source.is_active) else 1
            target.custom_ledgix_legacy_customer = source.name
            target.default_price_list = self.price_list_map.get(source.default_price_list) or ""
            target.customer_details = source.notes or ""
            target.custom_ledgix_buyer_registration_type = source.buyer_registration_type or "Unregistered"
            target.custom_ledgix_buyer_ntn_cnic = source.buyer_ntn_cnic or ""
            target.custom_ledgix_buyer_strn = source.buyer_strn or ""
            target.custom_ledgix_buyer_province = source.buyer_province or ""
            target.custom_ledgix_buyer_fbr_address = source.buyer_fbr_address or ""
            target.custom_ledgix_fbr_verification_status = source.fbr_verification_status or "Not Checked"
            target.custom_ledgix_last_fbr_verification_date = source.last_fbr_verification_date
            target.payment_terms = self._ensure_payment_terms(cint(source.payment_terms_days))

            credit_limit = max(flt(source.credit_limit), 0)
            if credit_limit:
                row = next((row for row in target.get("credit_limits") or [] if row.company == self.ctx.company), None)
                if not row:
                    row = target.append("credit_limits", {"company": self.ctx.company})
                row.credit_limit = credit_limit

            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)

            contact = self._party_contact("Customer", target.name, "Ledgix Customer", source)
            address = self._party_address("Customer", target.name, "Ledgix Customer", source)
            updates = {}
            if contact:
                updates["customer_primary_contact"] = contact
            if address:
                updates["customer_primary_address"] = address
            if updates:
                frappe.db.set_value("Customer", target.name, updates, update_modified=False)
            self.customer_map[source.name] = target.name
            self._record(stage, action, source.name, target.name)

    def migrate_suppliers(self) -> None:
        stage = "suppliers"
        for source in self._source_rows("Ledgix Supplier", "supplier_name"):
            group = self._ensure_supplier_group(source.supplier_type or "Local")
            marker_name = frappe.db.get_value(
                "Supplier", {"custom_ledgix_legacy_supplier": source.name}, "name"
            )
            if marker_name:
                target = frappe.get_doc("Supplier", marker_name)
                action = "updated"
            else:
                unmarked = frappe.db.get_value("Supplier", {"supplier_name": source.supplier_name}, "name")
                if unmarked:
                    self._conflict(
                        stage,
                        source.name,
                        unmarked,
                        "same supplier_name exists without Ledgix provenance; manual merge decision required",
                    )
                    continue
                target = frappe.get_doc(
                    {
                        "doctype": "Supplier",
                        "supplier_name": source.supplier_name,
                        "supplier_group": group,
                        "supplier_type": "Company",
                        "country": "Pakistan",
                    }
                )
                action = "created"

            target.supplier_name = source.supplier_name
            target.supplier_group = group
            target.supplier_type = "Company"
            target.country = "Pakistan"
            target.disabled = 0 if cint(source.is_active) else 1
            target.custom_ledgix_legacy_supplier = source.name
            details = [value for value in (source.company_name, source.notes) if value]
            target.supplier_details = "\n".join(details)
            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)

            contact = self._party_contact("Supplier", target.name, "Ledgix Supplier", source)
            address = self._party_address("Supplier", target.name, "Ledgix Supplier", source)
            updates = {}
            if contact:
                updates["supplier_primary_contact"] = contact
            if address:
                updates["supplier_primary_address"] = address
            if updates:
                frappe.db.set_value("Supplier", target.name, updates, update_modified=False)

            balances = {
                "opening_balance": flt(source.opening_balance),
                "current_balance": flt(source.current_balance),
            }
            if any(abs(value) > 0.005 for value in balances.values()):
                self._defer(
                    stage,
                    source.name,
                    "supplier AP/opening balances are transactional accounting state and move in Phase 6, not master migration",
                    balances,
                )
            self.supplier_map[source.name] = target.name
            self._record(stage, action, source.name, target.name)

    # ------------------------------------------------------------------
    # payment / FBR references
    # ------------------------------------------------------------------
    def migrate_payment_methods(self) -> None:
        stage = "payment_methods"
        for source in self._source_rows("Ledgix Payment Method", "payment_method_name"):
            target_name = source.payment_method_name
            expected_type = PAYMENT_TYPE_MAP.get(source.method_type, "General")
            if frappe.db.exists("Mode of Payment", target_name):
                target = frappe.get_doc("Mode of Payment", target_name)
                marker = target.get("custom_ledgix_legacy_payment_method")
                if marker and marker != source.name:
                    self._conflict(stage, source.name, target.name, f"already owned by {marker}")
                    continue
                # Exact-name native modes (e.g. Cash) are safe to adopt; never
                # overwrite their account child table here.
                action = "updated" if marker == source.name else "matched"
            else:
                target = frappe.get_doc(
                    {
                        "doctype": "Mode of Payment",
                        "mode_of_payment": target_name,
                        "type": expected_type,
                    }
                )
                action = "created"
            target.type = expected_type
            target.enabled = cint(source.enabled)
            target.custom_ledgix_legacy_payment_method = source.name
            target.custom_ledgix_legacy_method_type = source.method_type or ""
            target.custom_ledgix_sort_order = cint(source.sort_order)
            target.custom_ledgix_requires_reference = cint(source.requires_reference)
            target.custom_ledgix_allow_change = cint(source.allow_change)
            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)
            self.payment_map[source.name] = target.name
            self._record(stage, action, source.name, target.name)

    def relink_item_tax_profiles(self) -> None:
        stage = "item_tax_profiles"
        rows = frappe.get_all(
            "Ledgix Item Tax Profile",
            fields=["name", "item", "erpnext_item"],
            limit_page_length=0,
        )
        for row in rows:
            if not row.item:
                continue
            if self.ctx.source_prefix:
                legacy_code = frappe.db.get_value("Ledgix Item", row.item, "item_code")
                if not legacy_code or not str(legacy_code).startswith(self.ctx.source_prefix):
                    continue
            target_item = self.item_map.get(row.item) or frappe.db.get_value(
                "Item", {"custom_ledgix_legacy_item": row.item}, "name"
            )
            if not target_item:
                self._conflict(stage, row.name, "", "target ERPNext Item mapping missing")
                continue
            if row.erpnext_item and row.erpnext_item != target_item:
                self._conflict(stage, row.name, row.erpnext_item, f"profile already points to different Item; expected {target_item}")
                continue
            if row.erpnext_item == target_item:
                self._record(stage, "matched", row.name, target_item)
                continue
            frappe.db.set_value(
                "Ledgix Item Tax Profile", row.name, "erpnext_item", target_item, update_modified=False
            )
            self._record(stage, "updated", row.name, target_item)

    # ------------------------------------------------------------------
    # opening stock / batch / serial state
    # ------------------------------------------------------------------
    @staticmethod
    def _bin_qty(item_code: str, warehouse: str) -> float:
        return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))

    @staticmethod
    def _sle_count(item_code: str, warehouse: str) -> int:
        return frappe.db.count(
            "Stock Ledger Entry",
            {"item_code": item_code, "warehouse": warehouse, "is_cancelled": 0},
        )

    def _stock_entry(self, *, item_code: str, qty: float, rate: float, marker: str, batch_no: str = "", serial_no: str = ""):
        existing = frappe.db.get_value(
            "Stock Entry",
            {"company": self.ctx.company, "remarks": marker, "docstatus": 1},
            "name",
        )
        if existing:
            return frappe.get_doc("Stock Entry", existing), False

        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

        kwargs = {
            "item_code": item_code,
            "qty": qty,
            "company": self.ctx.company,
            "rate": rate,
            "to_warehouse": self.ctx.warehouse,
            "purpose": "Material Receipt",
            "do_not_save": True,
            "use_serial_batch_fields": 1 if (batch_no or serial_no) else 0,
        }
        if batch_no:
            kwargs["batch_no"] = batch_no
        if serial_no:
            kwargs["serial_no"] = serial_no
        doc = make_stock_entry(**kwargs)
        doc.remarks = marker
        doc.insert(ignore_permissions=True)
        doc.submit()
        doc.reload()
        return doc, True

    def _ensure_batch(self, batch_id: str, item_code: str, source) -> str:
        if frappe.db.exists("Batch", batch_id):
            owner = frappe.db.get_value("Batch", batch_id, "item")
            if owner != item_code:
                frappe.throw(f"ERPNext Batch {batch_id!r} belongs to {owner!r}, expected {item_code!r}.")
            return batch_id
        values = {
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": item_code,
        }
        if source.get("purchase_date"):
            values["manufacturing_date"] = source.purchase_date
        return frappe.get_doc(values).insert(ignore_permissions=True).name

    def _opening_normal(self, source, target_item: str, expected_qty: float) -> None:
        stage = "opening_stock"
        marker = f"LEDGIX-P5-OPENING:{source.name}"
        existing = frappe.db.get_value(
            "Stock Entry", {"company": self.ctx.company, "remarks": marker, "docstatus": 1}, "name"
        )
        if existing:
            actual = self._bin_qty(target_item, self.ctx.warehouse)
            if abs(actual - expected_qty) > 0.005:
                self._conflict(stage, source.name, existing, f"rerun quantity mismatch target={actual} legacy={expected_qty}")
            else:
                self._record(stage, "matched", source.name, existing)
            return
        if self._sle_count(target_item, self.ctx.warehouse):
            self._conflict(stage, source.name, target_item, "target already has unrelated stock ledger activity")
            return
        doc, created = self._stock_entry(
            item_code=target_item,
            qty=expected_qty,
            rate=max(flt(source.cost_price), 0),
            marker=marker,
        )
        self._record(stage, "created" if created else "matched", source.name, doc.name)

    def _opening_batch(self, source, target_item: str, expected_qty: float) -> None:
        stage = "opening_stock"
        lots = frappe.get_all(
            "Ledgix Stock Lot",
            filters={"item": source.name, "status": ["!=", "Cancelled"]},
            fields=["name", "remaining_qty", "cost_rate", "purchase_date", "status"],
            order_by="creation asc, name asc",
            limit_page_length=0,
        )
        lots = [row for row in lots if flt(row.remaining_qty) > 0]
        lot_qty = sum(flt(row.remaining_qty) for row in lots)
        if abs(lot_qty - expected_qty) > 0.005:
            self._conflict(stage, source.name, target_item, f"lot remaining qty {lot_qty} != item current_stock {expected_qty}")
            return
        markers = [f"LEDGIX-P5-OPENING:{source.name}:LOT:{row.name}" for row in lots]
        existing_markers = [
            frappe.db.get_value("Stock Entry", {"company": self.ctx.company, "remarks": marker, "docstatus": 1}, "name")
            for marker in markers
        ]
        if lots and all(existing_markers):
            actual = self._bin_qty(target_item, self.ctx.warehouse)
            if abs(actual - expected_qty) > 0.005:
                self._conflict(stage, source.name, target_item, f"rerun batch qty mismatch target={actual} legacy={expected_qty}")
            else:
                self._record(stage, "matched", source.name, target_item, f"{len(lots)} batch receipt(s) already migrated")
            return
        if any(existing_markers) or self._sle_count(target_item, self.ctx.warehouse):
            self._conflict(stage, source.name, target_item, "partial/unrelated target batch stock activity detected")
            return
        for row, marker in zip(lots, markers):
            batch = self._ensure_batch(row.name, target_item, row)
            doc, _ = self._stock_entry(
                item_code=target_item,
                qty=flt(row.remaining_qty),
                rate=max(flt(row.cost_rate) or flt(source.cost_price), 0),
                marker=marker,
                batch_no=batch,
            )
            self._record(stage, "created", f"{source.name}:{row.name}", doc.name)

    def _opening_serial(self, source, target_item: str, expected_qty: float) -> None:
        stage = "opening_stock"
        rows = frappe.get_all(
            "Ledgix Stock Serial",
            filters={"item": source.name, "status": ["in", sorted(IN_STOCK_SERIAL_STATUSES)]},
            fields=["name", "serial_no", "cost_rate", "status"],
            order_by="creation asc, name asc",
            limit_page_length=0,
        )
        if abs(expected_qty - round(expected_qty)) > 0.0001 or len(rows) != int(round(expected_qty)):
            self._conflict(stage, source.name, target_item, f"in-stock serial count {len(rows)} != current_stock {expected_qty}")
            return
        marker = f"LEDGIX-P5-OPENING:{source.name}:SERIAL"
        existing = frappe.db.get_value(
            "Stock Entry", {"company": self.ctx.company, "remarks": marker, "docstatus": 1}, "name"
        )
        if existing:
            actual = self._bin_qty(target_item, self.ctx.warehouse)
            if abs(actual - expected_qty) > 0.005:
                self._conflict(stage, source.name, target_item, f"rerun serial qty mismatch target={actual} legacy={expected_qty}")
            else:
                self._record(stage, "matched", source.name, existing)
            return
        if self._sle_count(target_item, self.ctx.warehouse):
            self._conflict(stage, source.name, target_item, "target already has unrelated serial stock activity")
            return
        serials = []
        for row in rows:
            if not row.serial_no:
                self._conflict(stage, source.name, target_item, f"legacy serial row {row.name} has no serial_no")
                return
            if frappe.db.exists("Serial No", row.serial_no):
                owner = frappe.db.get_value("Serial No", row.serial_no, "item_code")
                if owner != target_item:
                    self._conflict(stage, source.name, row.serial_no, f"ERPNext Serial No belongs to {owner}")
                    return
            serials.append(row.serial_no)
        rate_values = [flt(row.cost_rate) for row in rows if flt(row.cost_rate) > 0]
        rate = sum(rate_values) / len(rate_values) if rate_values else flt(source.cost_price)
        doc, _ = self._stock_entry(
            item_code=target_item,
            qty=len(serials),
            rate=max(rate, 0),
            marker=marker,
            serial_no="\n".join(serials),
        )
        self._record(stage, "created", source.name, doc.name)

    def migrate_opening_stock_state(self) -> None:
        if not self.ctx.migrate_opening_stock:
            return
        for source in self._source_rows("Ledgix Item", "item_code"):
            target_item = self.item_map.get(source.name) or frappe.db.get_value(
                "Item", {"custom_ledgix_legacy_item": source.name}, "name"
            )
            if not target_item:
                self._conflict("opening_stock", source.name, "", "target Item mapping missing")
                continue
            expected_qty = max(flt(source.current_stock), 0)
            if expected_qty <= 0.000001:
                self._record("opening_stock", "skipped", source.name, target_item, "zero current stock")
                continue
            tracking = source.tracking_type or "Normal"
            if tracking == "Lot Based":
                self._opening_batch(source, target_item, expected_qty)
            elif tracking == "Serial Based":
                self._opening_serial(source, target_item, expected_qty)
            else:
                self._opening_normal(source, target_item, expected_qty)

    # ------------------------------------------------------------------
    # reconciliation / execution
    # ------------------------------------------------------------------
    def reconcile(self) -> dict:
        checks: dict[str, bool] = {}
        source_items = self._source_rows("Ledgix Item", "item_code")
        checks["all_items_mapped"] = all(
            bool(frappe.db.get_value("Item", {"custom_ledgix_legacy_item": row.name}, "name"))
            for row in source_items
        )
        checks["item_identifiers_match"] = all(
            frappe.db.get_value("Item", {"custom_ledgix_legacy_item": row.name}, "item_code") == row.item_code
            for row in source_items
        )

        source_categories = self._source_rows("Ledgix Category", "category_name")
        checks["all_categories_mapped"] = all(
            bool(frappe.db.get_value("Item Group", {"custom_ledgix_legacy_category": row.name}, "name"))
            for row in source_categories
        )

        source_lists = self._source_rows("Ledgix Price List", "price_list_name")
        checks["all_price_lists_mapped"] = all(
            bool(frappe.db.get_value("Price List", {"custom_ledgix_legacy_price_list": row.name}, "name"))
            for row in source_lists
        )

        active_prices = [row for row in self._source_rows("Ledgix Item Price", "name") if cint(row.enabled)]
        checks["all_active_item_prices_mapped"] = all(
            bool(frappe.db.get_value("Item Price", {"reference": f"Ledgix Item Price:{row.name}"}, "name"))
            for row in active_prices
        )

        customers = self._source_rows("Ledgix Customer", "customer_name")
        checks["all_customers_mapped"] = all(
            bool(frappe.db.get_value("Customer", {"custom_ledgix_legacy_customer": row.name}, "name"))
            for row in customers
        )
        suppliers = self._source_rows("Ledgix Supplier", "supplier_name")
        checks["all_suppliers_mapped"] = all(
            bool(frappe.db.get_value("Supplier", {"custom_ledgix_legacy_supplier": row.name}, "name"))
            for row in suppliers
        )
        methods = self._source_rows("Ledgix Payment Method", "payment_method_name")
        checks["all_payment_methods_mapped"] = all(
            bool(frappe.db.get_value("Mode of Payment", {"custom_ledgix_legacy_payment_method": row.name}, "name"))
            for row in methods
        )

        profiles = frappe.get_all("Ledgix Item Tax Profile", fields=["name", "item", "erpnext_item"], limit_page_length=0)
        relevant_profiles = []
        for row in profiles:
            if not row.item:
                continue
            code = frappe.db.get_value("Ledgix Item", row.item, "item_code")
            if self.ctx.source_prefix and (not code or not str(code).startswith(self.ctx.source_prefix)):
                continue
            relevant_profiles.append(row)
        checks["all_legacy_item_tax_profiles_relinked"] = all(bool(row.erpnext_item) for row in relevant_profiles)

        stock_rows = []
        if self.ctx.migrate_opening_stock:
            for source in source_items:
                target = frappe.db.get_value("Item", {"custom_ledgix_legacy_item": source.name}, "name")
                if not target:
                    stock_rows.append({"source": source.name, "target": "", "legacy_qty": flt(source.current_stock), "erpnext_qty": None, "matches": False})
                    continue
                actual = self._bin_qty(target, self.ctx.warehouse)
                stock_rows.append(
                    {
                        "source": source.name,
                        "target": target,
                        "legacy_qty": flt(source.current_stock),
                        "erpnext_qty": actual,
                        "matches": abs(actual - flt(source.current_stock)) < 0.005,
                    }
                )
            checks["opening_stock_quantities_match"] = all(row["matches"] for row in stock_rows)

        result = {
            "checks": checks,
            "stock": stock_rows,
            "counts": {
                "categories": len(source_categories),
                "items": len(source_items),
                "price_lists": len(source_lists),
                "active_item_prices": len(active_prices),
                "customers": len(customers),
                "suppliers": len(suppliers),
                "payment_methods": len(methods),
                "item_tax_profiles": len(relevant_profiles),
            },
        }
        result["passed"] = all(checks.values())
        return result

    def execute(self) -> dict:
        self._assert_prerequisites()
        self.migrate_uoms()
        self.migrate_categories()
        self.migrate_price_lists()
        self.migrate_items()
        self.migrate_item_prices()
        self.migrate_customers()
        self.migrate_suppliers()
        self.migrate_payment_methods()
        self.relink_item_tax_profiles()
        self.migrate_opening_stock_state()
        self.report["reconciliation"] = self.reconcile()
        self.report["passed"] = bool(
            not self.report["conflicts"]
            and not self.report["errors"]
            and self.report["reconciliation"].get("passed")
        )
        self.report["legacy_master_freeze_performed"] = False
        self.report["transaction_authority_cutover_performed"] = False
        self.report["phase6_deferred_accounting_rows"] = len(self.report["deferred"])
        return self.report


def run(
    dry_run: int | bool = 1,
    source_prefix: str | None = None,
    company: str | None = None,
    warehouse: str | None = None,
    migrate_opening_stock: int | bool = 0,
) -> dict:
    """Run or dry-run Phase 5 migration on the current site.

    Production-safe defaults deliberately perform a dry-run and do not create
    opening stock.  Operators must explicitly name a warehouse and enable stock
    migration after reviewing the reconciliation report.
    """

    frappe.set_user("Administrator")
    erpnext_phase5_extensions.sync_all()
    company = company or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw("Explicit company is required for Phase 5 master migration.")

    context = MigrationContext(
        company=company,
        warehouse=warehouse or None,
        source_prefix=source_prefix or None,
        dry_run=bool(cint(dry_run)),
        migrate_opening_stock=bool(cint(migrate_opening_stock)),
    )
    savepoint = "ledgix_phase5_master_migration"
    frappe.db.savepoint(savepoint)
    try:
        result = MasterMigration(context).execute()
        if context.dry_run:
            frappe.db.rollback(save_point=savepoint)
            result["rolled_back"] = True
        else:
            frappe.db.commit()
            result["rolled_back"] = False
        return result
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        raise
