from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from ledgix_saas.migration import erpnext_phase5_master_migration as base
from ledgix_saas.setup import erpnext_phase5_extensions


class MasterMigration(base.MasterMigration):
    """Canonical Phase 5 migration with exact legacy field normalization."""

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
