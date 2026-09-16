from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from ledgix_saas.migration import erpnext_phase5_master_migration as base
from ledgix_saas.setup import erpnext_phase5_extensions


class MasterMigration(base.MasterMigration):
    """Phase 5 migration with exact legacy party field normalization."""

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
