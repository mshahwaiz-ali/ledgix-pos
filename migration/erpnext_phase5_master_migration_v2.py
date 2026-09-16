from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from ledgix_saas.migration import erpnext_phase5_master_migration as base
from ledgix_saas.setup import erpnext_extensions, erpnext_phase5_extensions


class MasterMigration(base.MasterMigration):
    """Canonical Phase 5 migration with exact legacy field normalization."""

    def _inventory_enabled(self) -> bool:
        features = erpnext_extensions.get_effective_business_features()
        return bool(cint(features.get("enable_inventory")))

    def _assert_prerequisites(self) -> None:
        super()._assert_prerequisites()
        if self.ctx.migrate_opening_stock and not self._inventory_enabled():
            frappe.throw(
                "Opening-stock migration is not allowed while the Ledgix Business Profile has inventory disabled. "
                "Invoice + FBR Only clients must use non-stock ERPNext Items."
            )

    def _source_rows(self, doctype: str, key_field: str) -> list:
        # Ledgix Item Price names are generated as IP-##### and therefore cannot
        # be prefix-filtered directly. Scope them through their linked legacy Item.
        if doctype == "Ledgix Item Price" and self.ctx.source_prefix:
            item_names = frappe.get_all(
                "Ledgix Item",
                filters={"item_code": ["like", f"{self.ctx.source_prefix}%"]},
                pluck="name",
                limit_page_length=0,
            )
            if not item_names:
                return []
            return frappe.get_all(
                doctype,
                filters={"item": ["in", item_names]},
                fields=["*"],
                order_by="name asc",
                limit_page_length=0,
            )
        return super()._source_rows(doctype, key_field)

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
            target.custom_ledgix_category_active = cint(source.is_active)
            target.custom_ledgix_category_description = source.description or ""
            target.custom_ledgix_category_icon = source.category_icon or ""
            target.custom_ledgix_accent_color = source.accent_color or ""
            target.custom_ledgix_tax_defaults_enabled = cint(source.tax_defaults_enabled)
            target.custom_ledgix_default_tax_category = source.default_tax_category or ""
            target.custom_ledgix_default_taxable = cint(source.default_taxable)
            target.custom_ledgix_default_sales_type = source.default_sales_type or ""
            target.custom_ledgix_default_uom_for_fbr = source.default_uom_for_fbr or ""
            target.custom_ledgix_default_scenario_id = source.default_scenario_id or ""
            if source.custom_icon_image and not target.image:
                target.image = source.custom_icon_image
            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)
            self.category_map[source.name] = target.name
            self._record(stage, action, source.name, target.name)

    def _item_expected(self, source) -> dict:
        inventory_enabled = self._inventory_enabled()
        tracking = str(source.tracking_type or "Normal")
        return {
            "item_group": self.category_map.get(source.category) or source.category or "Products",
            "stock_uom": base.UNIT_MAP.get(source.unit, source.unit or "Nos"),
            "is_stock_item": 1 if inventory_enabled else 0,
            "has_batch_no": 1 if inventory_enabled and tracking == "Lot Based" else 0,
            "has_serial_no": 1 if inventory_enabled and tracking == "Serial Based" else 0,
        }

    def migrate_items(self) -> None:
        stage = "items"
        inventory_enabled = self._inventory_enabled()
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

                mismatches = {}
                for field, value in expected.items():
                    actual = target.get(field)
                    if field in {"is_stock_item", "has_batch_no", "has_serial_no"}:
                        differs = cint(actual) != cint(value)
                    else:
                        differs = str(actual or "") != str(value or "")
                    if differs:
                        mismatches[field] = {"erpnext": actual, "ledgix_target": value}
                if mismatches:
                    self._conflict(stage, source.name, target.name, f"structural mismatch: {mismatches}")
                    continue
                action = "updated" if marker == source.name else "matched"
            else:
                values = {
                    "doctype": "Item",
                    "item_code": source.item_code,
                    "item_name": source.item_name or source.item_code,
                    "description": source.get("description") or source.item_name or source.item_code,
                    "item_group": expected["item_group"],
                    "stock_uom": expected["stock_uom"],
                    "is_stock_item": expected["is_stock_item"],
                    "include_item_in_manufacturing": 0,
                    "has_batch_no": expected["has_batch_no"],
                    "create_new_batch": 0,
                    "has_serial_no": expected["has_serial_no"],
                    "standard_rate": max(flt(source.selling_price), 0),
                }
                if inventory_enabled:
                    values["valuation_method"] = "Moving Average"
                    values["valuation_rate"] = max(flt(source.cost_price), 0)
                target = frappe.get_doc(values)
                action = "created"

            target.item_name = source.item_name or source.item_code
            if source.get("description"):
                target.description = source.description
            target.disabled = 0 if cint(source.active) else 1
            target.custom_ledgix_legacy_item = source.name
            target.custom_ledgix_legacy_sku = source.sku or ""
            target.custom_ledgix_legacy_tracking_type = source.tracking_type or "Normal"
            target.custom_ledgix_minimum_stock = max(flt(source.minimum_stock), 0)

            if source.barcode:
                existing_barcodes = {str(row.barcode or "") for row in target.get("barcodes") or []}
                if source.barcode not in existing_barcodes:
                    target.append("barcodes", {"barcode": source.barcode, "uom": expected["stock_uom"]})

            if target.is_new():
                target.insert(ignore_permissions=True)
            else:
                target.save(ignore_permissions=True)

            if not inventory_enabled and (
                abs(flt(source.current_stock)) > 0.005 or (source.tracking_type or "Normal") != "Normal"
            ):
                self._defer(
                    stage,
                    source.name,
                    "business profile has inventory disabled; legacy stock/tracking state is retained for audit and is not posted to ERPNext",
                    {
                        "current_stock": flt(source.current_stock),
                        "tracking_type": source.tracking_type or "Normal",
                    },
                )

            self.item_map[source.name] = target.name
            self._record(stage, action, source.name, target.name)

    def _party_contact(self, target_doctype: str, target_name: str, source_doctype: str, source) -> str:
        mobile = source.get("mobile_number") or source.get("mobile") or ""
        email = source.get("email_address") or source.get("email") or ""
        if not mobile and not email:
            return ""

        source_key = f"{source_doctype}:{source.name}"
        existing = frappe.db.get_value(
            "Contact", {"custom_ledgix_legacy_contact_source": source_key}, "name"
        )
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

        # email_id/mobile_no are derived read-only fields in pinned Frappe v15.
        # Store authoritative values in their child tables and let Contact
        # validation populate the derived fields.
        contact.set("email_ids", [])
        contact.set("phone_nos", [])
        if email:
            contact.append("email_ids", {"email_id": email, "is_primary": 1})
        if mobile:
            contact.append(
                "phone_nos",
                {
                    "phone": mobile,
                    "is_primary_mobile_no": 1,
                    "is_primary_phone": 0,
                },
            )
        contact.is_primary_contact = 1
        if contact.is_new():
            contact.insert(ignore_permissions=True)
        else:
            contact.save(ignore_permissions=True)
        return contact.name

    def _party_address(self, target_doctype: str, target_name: str, source_doctype: str, source) -> str:
        # Ledgix Customer uses address_line_1/area while Ledgix Supplier uses
        # address. Normalize both without inventing missing city/address data.
        address_line = source.get("address_line_1") or source.get("address") or ""
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
        existing = frappe.db.get_value(
            "Address", {"custom_ledgix_legacy_address_source": source_key}, "name"
        )
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
        super().migrate_customers()
        for source in self._source_rows("Ledgix Customer", "customer_name"):
            balances = {
                "outstanding_amount": flt(source.outstanding_amount),
                "overdue_amount": flt(source.overdue_amount),
                "unallocated_credit": flt(source.unallocated_credit),
                "credit_balance": flt(source.credit_balance),
                "current_balance": flt(source.current_balance),
            }
            if any(abs(value) > 0.005 for value in balances.values()):
                self._defer(
                    "customers",
                    source.name,
                    "customer receivable/credit balances are transactional accounting state and move in Phase 6",
                    balances,
                )


def run(
    dry_run: int | bool = 1,
    source_prefix: str | None = None,
    company: str | None = None,
    warehouse: str | None = None,
    migrate_opening_stock: int | bool = 0,
) -> dict:
    """Canonical Phase 5 migration entry point.

    Defaults remain production-safe: dry-run enabled and opening stock disabled.
    """

    frappe.set_user("Administrator")
    erpnext_phase5_extensions.sync_all()
    company = company or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw("Explicit company is required for Phase 5 master migration.")

    context = base.MigrationContext(
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
        result["inventory_enabled"] = MasterMigration(context)._inventory_enabled()
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
