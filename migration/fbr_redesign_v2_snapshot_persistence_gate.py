from __future__ import annotations

import frappe
from frappe.utils import cint

from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

from ledgix_saas.api import fbr_native
from ledgix_saas.migration import fbr_redesign_phase1_native_core_parity_gate as core
from ledgix_saas.services import (
    erpnext_pos,
    erpnext_selling,
    erpnext_tax_authority,
    fbr_v2_snapshot_persistence as snapshots,
)


def _snapshot_evidence(doc) -> dict:
    persisted = snapshots.read_persisted_v2_snapshot(doc.doctype, doc.name)
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "docstatus": cint(doc.docstatus),
        "is_return": cint(doc.get("is_return")),
        "return_against": doc.get("return_against") or "",
        "snapshot_version": cint(doc.get(snapshots.HEADER_VERSION_FIELD)),
        "snapshot_hash": doc.get(snapshots.HEADER_HASH_FIELD) or "",
        "snapshot_hash_verified": bool(persisted.get("hash_verified")),
        "line_count": len(persisted.get("lines") or {}),
        "legacy_snapshot_version": cint(doc.get("custom_ledgix_fbr_snapshot_version")),
        "legacy_snapshot_json": doc.get("custom_ledgix_fbr_snapshot_json") or "",
    }


def run() -> dict:
    core._assert_safe_site()
    core._require_native_foundation()

    original_user = frappe.session.user
    original_profile_active = snapshots._profile_active
    original_queue = fbr_native.queue_native_for_fbr
    original_commit = frappe.db.commit

    queue_intercepts = []
    commit_intercepts = []
    created_invoice_names = []

    def _force_profile_active(company):
        return company == core.COMPANY

    def _no_network_queue(reference_doctype, reference_name, reason=None):
        queue_intercepts.append(
            {
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "reason": reason or "",
            }
        )
        return {
            "queued": False,
            "status": "V2 Snapshot Gate Bypass",
            "reason": "In-memory gate bypass; no FBR network call.",
        }

    def _no_commit(*args, **kwargs):
        commit_intercepts.append(len(commit_intercepts) + 1)
        return None

    result = None

    try:
        frappe.set_user("Administrator")
        snapshots._profile_active = _force_profile_active
        fbr_native.queue_native_for_fbr = _no_network_queue
        frappe.db.commit = _no_commit

        core._enable_fixture_items()
        price_list = core._new_price_list()

        # Main Counter POS intentionally has no persistent taxes_and_charges
        # template. Mirror the proven Phase-1 gate: create a temporary native
        # POS GST template and assign it only inside this rollback transaction.
        pos_template = core._new_pos_template()
        pos_profile = frappe.get_doc("POS Profile", "Main Counter POS")
        pos_profile.db_set(
            "taxes_and_charges",
            pos_template,
            update_modified=False,
        )
        frappe.clear_cache(doctype="POS Profile")

        sale = erpnext_selling.build_sales_invoice(
            customer=core._customer(),
            items=[{"item": core.ITEMS["ordinary"], "qty": 1}],
            company=core.COMPANY,
            selling_price_list=price_list,
            sale_channel="B2B",
            client_sale_id=f"V2-SNAPSHOT-SI-{frappe.generate_hash(length=10)}",
            allow_rate_override=False,
            update_stock=False,
            checkout_source="FBR V2 Snapshot Persistence Gate",
        )
        sale.insert(ignore_permissions=True)
        sale.submit()
        sale.reload()
        created_invoice_names.append(("Sales Invoice", sale.name))
        sale_ev = _snapshot_evidence(sale)

        credit = erpnext_selling.create_sales_return(
            sales_invoice=sale.name,
            return_items=[
                {
                    "sales_invoice_item": sale.items[0].name,
                    "qty": 1,
                }
            ],
            reason="FBR V2 immutable snapshot return gate",
            client_return_id=f"V2-SNAPSHOT-SIR-{frappe.generate_hash(length=10)}",
            checkout_source="FBR V2 Snapshot Persistence Gate",
        )
        credit.reload()
        created_invoice_names.append(("Sales Invoice", credit.name))
        credit_ev = _snapshot_evidence(credit)

        profile = frappe.get_doc("POS Profile", "Main Counter POS")
        if profile.taxes_and_charges != pos_template:
            frappe.throw(
                "Rollback-safe V2 snapshot gate failed to apply the temporary "
                "native POS tax template."
            )

        pos = erpnext_pos.build_pos_invoice(
            cart_items=[{"item": core.ITEMS["ordinary"], "qty": 1}],
            customer=profile.customer,
            price_list=price_list,
            client_sale_id=f"V2-SNAPSHOT-POS-{frappe.generate_hash(length=10)}",
            allow_rate_override=False,
            source="FBR V2 Snapshot Persistence Gate",
            company=core.COMPANY,
            pos_profile=profile.name,
        )
        erpnext_pos._default_draft_payment(pos, profile)
        pos.insert(ignore_permissions=True)
        pos.submit()
        pos.reload()
        created_invoice_names.append(("POS Invoice", pos.name))
        pos_ev = _snapshot_evidence(pos)

        pos_credit = make_sales_return(pos.name)
        erpnext_tax_authority.apply_sales_tax_authority(pos_credit)
        pos_credit.insert(ignore_permissions=True)
        pos_credit.submit()
        pos_credit.reload()
        created_invoice_names.append(("POS Invoice", pos_credit.name))
        pos_credit_ev = _snapshot_evidence(pos_credit)

        checks = {
            "sales_invoice_submitted": sale.docstatus == 1,
            "sales_invoice_snapshot_verified": sale_ev["snapshot_hash_verified"],
            "sales_invoice_one_line": sale_ev["line_count"] == 1,
            "sales_invoice_legacy_snapshot_untouched": (
                sale_ev["legacy_snapshot_version"] == 0
                and not sale_ev["legacy_snapshot_json"]
            ),
            "sales_return_submitted": credit.docstatus == 1,
            "sales_return_links_source": credit.return_against == sale.name,
            "sales_return_snapshot_verified": credit_ev["snapshot_hash_verified"],
            "sales_return_one_line": credit_ev["line_count"] == 1,
            "sales_return_legacy_snapshot_untouched": (
                credit_ev["legacy_snapshot_version"] == 0
                and not credit_ev["legacy_snapshot_json"]
            ),
            "pos_invoice_submitted": pos.docstatus == 1,
            "pos_invoice_snapshot_verified": pos_ev["snapshot_hash_verified"],
            "pos_invoice_one_line": pos_ev["line_count"] == 1,
            "pos_invoice_legacy_snapshot_untouched": (
                pos_ev["legacy_snapshot_version"] == 0
                and not pos_ev["legacy_snapshot_json"]
            ),
            "pos_return_submitted": pos_credit.docstatus == 1,
            "pos_return_links_source": pos_credit.return_against == pos.name,
            "pos_return_snapshot_verified": pos_credit_ev["snapshot_hash_verified"],
            "pos_return_one_line": pos_credit_ev["line_count"] == 1,
            "pos_return_legacy_snapshot_untouched": (
                pos_credit_ev["legacy_snapshot_version"] == 0
                and not pos_credit_ev["legacy_snapshot_json"]
            ),
        }

        failed = [name for name, passed in checks.items() if not passed]

        result = {
            "site": frappe.local.site,
            "authority": erpnext_tax_authority.current_tax_authority(),
            "snapshot_version": snapshots.SNAPSHOT_VERSION,
            "database_persistence": "ROLLBACK_PENDING_VERIFICATION",
            "fbr_network_calls": 0,
            "fbr_submit_hooks_intercepted_in_memory": len(queue_intercepts),
            "commit_calls_intercepted_in_memory": len(commit_intercepts),
            "checks": checks,
            "failed_checks": failed,
            "evidence": {
                "sales_invoice": sale_ev,
                "sales_return": credit_ev,
                "pos_invoice": pos_ev,
                "pos_return": pos_credit_ev,
            },
            "gate_passed": not failed,
        }

        if failed:
            frappe.throw(
                "FBR V2 snapshot persistence gate failed: " + ", ".join(failed)
            )

    finally:
        snapshots._profile_active = original_profile_active
        fbr_native.queue_native_for_fbr = original_queue
        frappe.db.commit = original_commit
        frappe.set_user(original_user)
        frappe.db.rollback()

    persisted = [
        {"doctype": doctype, "name": name}
        for doctype, name in created_invoice_names
        if frappe.db.exists(doctype, name)
    ]
    rollback_clean = not persisted

    result["post_rollback"] = {
        "persisted_gate_invoices": persisted,
        "rollback_clean": rollback_clean,
    }
    result["database_persistence"] = (
        "ROLLBACK_CONFIRMED"
        if rollback_clean
        else "ROLLBACK_VERIFICATION_FAILED"
    )
    result["gate_passed"] = bool(result["gate_passed"] and rollback_clean)

    if not rollback_clean:
        frappe.throw(
            "FBR V2 snapshot checks passed but rollback verification found "
            "persisted gate invoices."
        )

    return result
