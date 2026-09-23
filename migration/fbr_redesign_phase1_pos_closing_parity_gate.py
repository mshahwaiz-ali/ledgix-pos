from __future__ import annotations

"""Rollback-safe Phase 1 proof for ERPNext POS Closing accounting consolidation.

This gate is deliberately separate from the already-green native core parity gate.
It uses the real Ledgix POS transaction path plus ERPNext POS Opening/Closing and
POS Invoice Merge Log machinery, but intercepts frappe.db.commit in-memory so the
test transaction can be rolled back completely on the integration site.

No ERPNext core file is modified.
No FBR network call is allowed.
"""

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api import fbr_native
from ledgix_saas.migration import fbr_redesign_phase1_native_core_parity_gate as core
from ledgix_saas.services import erpnext_pos, erpnext_tax_authority


PROFILE_SOURCE = "Main Counter POS"


def _available_cashier() -> str:
    rows = frappe.db.sql(
        """
        select u.name
        from `tabUser` u
        where u.enabled = 1
          and u.user_type = 'System User'
          and u.name not in (
              select poe.user
              from `tabPOS Opening Entry` poe
              where poe.status = 'Open'
                and poe.docstatus = 1
          )
        order by
          case when u.name = 'Administrator' then 1 else 0 end,
          u.name
        limit 1
        """,
        as_list=True,
    )
    if not rows:
        frappe.throw(
            "POS Closing parity requires one enabled System User who does not "
            "already have an open POS Opening Entry."
        )
    return str(rows[0][0])


def _main_counter_state() -> dict:
    open_entries = frappe.db.sql(
        """
        select name
        from `tabPOS Opening Entry`
        where pos_profile = %s
          and status = 'Open'
          and docstatus = 1
        order by name
        """,
        PROFILE_SOURCE,
        pluck=True,
    )
    unconsolidated = frappe.db.sql(
        """
        select name
        from `tabPOS Invoice`
        where pos_profile = %s
          and docstatus = 1
          and ifnull(consolidated_invoice, '') = ''
        order by name
        """,
        PROFILE_SOURCE,
        pluck=True,
    )
    return {
        "open_entries": list(open_entries),
        "unconsolidated_pos_invoices": list(unconsolidated),
        "taxes_and_charges": frappe.db.get_value(
            "POS Profile", PROFILE_SOURCE, "taxes_and_charges"
        ),
    }


def _new_isolated_profile(
    *,
    price_list: str,
    taxes_and_charges: str,
    cashier: str,
) -> object:
    source = frappe.get_doc("POS Profile", PROFILE_SOURCE)
    profile = frappe.copy_doc(source)

    profile.set("applicable_for_users", [])
    profile.append(
        "applicable_for_users",
        {
            "user": cashier,
            "default": 1,
        },
    )

    profile.disabled = 0
    profile.selling_price_list = price_list
    profile.taxes_and_charges = taxes_and_charges

    name = f"LEDGIX-P1-POS-CLOSING-{frappe.generate_hash(length=8).upper()}"
    profile.insert(ignore_permissions=True, set_name=name)
    frappe.clear_cache(doctype="POS Profile")
    return profile


def _create_opening(profile, cashier: str):
    original_user = frappe.session.user
    try:
        frappe.set_user(cashier)
        opening = erpnext_pos.open_shift(
            opening_cash=0,
            company=core.COMPANY,
            user=cashier,
            pos_profile=profile.name,
        )
        opening.reload()
        return opening
    finally:
        frappe.set_user(original_user)


def _create_sale(profile, price_list: str, cashier: str):
    original_user = frappe.session.user
    try:
        frappe.set_user(cashier)

        invoice = erpnext_pos.build_pos_invoice(
            cart_items=[{"item": core.ITEMS["ordinary"], "qty": 1}],
            customer=profile.customer,
            price_list=price_list,
            client_sale_id=f"NATIVE-CLOSING-POS-{frappe.generate_hash(length=10)}",
            allow_rate_override=False,
            source="Phase 1 POS Closing Parity Gate",
            company=core.COMPANY,
            pos_profile=profile.name,
        )
        erpnext_pos._default_draft_payment(invoice, profile)
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        invoice.reload()
        return invoice
    finally:
        frappe.set_user(original_user)


def _create_return(source, cashier: str):
    from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

    original_user = frappe.session.user
    try:
        frappe.set_user(cashier)

        credit = make_sales_return(source.name)
        erpnext_tax_authority.apply_sales_tax_authority(credit)
        credit.insert(ignore_permissions=True)
        credit.submit()
        credit.reload()
        return credit
    finally:
        frappe.set_user(original_user)


def _closing_preview(opening):
    from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import (
        make_closing_entry_from_opening,
    )

    return make_closing_entry_from_opening(opening)


def _account_net_credit(doc, account: str) -> float:
    if not account:
        return 0.0
    return core._net_credit(doc, account)


def _closing_case(
    *,
    profile,
    cashier: str,
    opening,
    sale,
    return_doc,
    commit_intercepts: list[dict],
) -> tuple[dict, list[tuple[str, str]]]:
    expected_pos_names = {sale.name, return_doc.name}

    preview = _closing_preview(opening)
    preview_names = {row.pos_invoice for row in preview.pos_transactions}
    if preview_names != expected_pos_names:
        frappe.throw(
            "Isolated POS Closing preview did not contain exactly the two gate "
            f"invoices. expected={sorted(expected_pos_names)} "
            f"actual={sorted(preview_names)}"
        )

    resolved_profile = erpnext_pos.profile_for_user(
        core.COMPANY,
        user=cashier,
    )
    if resolved_profile.name != profile.name:
        frappe.throw(
            "Temporary cashier did not resolve to the isolated parity POS Profile. "
            f"expected={profile.name} actual={resolved_profile.name}"
        )

    # Full sale + full refund means expected physical cash is back to zero.
    closed_opening, closing = erpnext_pos.close_shift(
        actual_cash=0,
        company=core.COMPANY,
        user=cashier,
    )

    sale.reload()
    return_doc.reload()
    closing.reload()
    closed_opening.reload()

    if not sale.consolidated_invoice:
        frappe.throw("ERPNext POS Closing did not create the consolidated Sales Invoice.")
    if not return_doc.consolidated_invoice:
        frappe.throw("ERPNext POS Closing did not create the consolidated return Sales Invoice.")

    consolidated_sale = frappe.get_doc("Sales Invoice", sale.consolidated_invoice)
    consolidated_return = frappe.get_doc("Sales Invoice", return_doc.consolidated_invoice)

    sale_ev = core._evidence(consolidated_sale)
    return_ev = core._evidence(consolidated_return)
    raw_sale_ev = core._evidence(sale)
    raw_return_ev = core._evidence(return_doc)

    sale_cash_account = (
        consolidated_sale.payments[0].account if consolidated_sale.payments else ""
    )
    return_cash_account = (
        consolidated_return.payments[0].account if consolidated_return.payments else ""
    )
    sale_income_account = (
        consolidated_sale.items[0].income_account if consolidated_sale.items else ""
    )
    return_income_account = (
        consolidated_return.items[0].income_account if consolidated_return.items else ""
    )

    sale_cash_net_credit = _account_net_credit(consolidated_sale, sale_cash_account)
    return_cash_net_credit = _account_net_credit(
        consolidated_return, return_cash_account
    )
    sale_income_net_credit = _account_net_credit(
        consolidated_sale, sale_income_account
    )
    return_income_net_credit = _account_net_credit(
        consolidated_return, return_income_account
    )

    merge_logs = frappe.get_all(
        "POS Invoice Merge Log",
        filters={"pos_closing_entry": closing.name},
        fields=[
            "name",
            "consolidated_invoice",
            "consolidated_credit_note",
        ],
        order_by="creation asc",
    )

    closing_pos_names = {row.pos_invoice for row in closing.pos_transactions}

    evidence = {
        "cashier": cashier,
        "temporary_pos_profile": profile.name,
        "opening_entry": opening.name,
        "closing_entry": closing.name,
        "closing_status": closing.status,
        "opening_status_after_close": closed_opening.status,
        "opening_pos_closing_entry": closed_opening.pos_closing_entry,
        "closing_pos_transactions": sorted(closing_pos_names),
        "merge_logs": [dict(row) for row in merge_logs],
        "commit_calls_intercepted": len(commit_intercepts),
        "raw_sale": raw_sale_ev,
        "raw_return": raw_return_ev,
        "consolidated_sale": sale_ev,
        "consolidated_return": return_ev,
        "consolidated_sale_name": consolidated_sale.name,
        "consolidated_return_name": consolidated_return.name,
        "consolidated_return_against": consolidated_return.return_against,
        "sale_cash_account": sale_cash_account,
        "return_cash_account": return_cash_account,
        "sale_income_account": sale_income_account,
        "return_income_account": return_income_account,
        "sale_cash_net_credit": flt(sale_cash_net_credit, 6),
        "return_cash_net_credit": flt(return_cash_net_credit, 6),
        "sale_income_net_credit": flt(sale_income_net_credit, 6),
        "return_income_net_credit": flt(return_income_net_credit, 6),
    }

    expected_sale_tax = abs(flt(sale.total_taxes_and_charges))
    expected_sale_net = abs(flt(sale.net_total))
    expected_sale_grand = abs(flt(sale.grand_total))

    checks = {
        "isolated_profile_used": sale.pos_profile == profile.name
        and return_doc.pos_profile == profile.name,
        "isolated_cashier_owns_raw_pos": sale.owner == cashier
        and return_doc.owner == cashier,
        "closing_contains_exact_gate_invoices": closing_pos_names
        == expected_pos_names,
        "closing_submitted": closing.docstatus == 1
        and closing.status == "Submitted",
        "opening_closed_by_closing": closed_opening.status == "Closed"
        and closed_opening.pos_closing_entry == closing.name,
        "merge_log_created": bool(merge_logs),
        "raw_sale_no_direct_gl": raw_sale_ev["gl_entry_count"] == 0
        and core._close(raw_sale_ev["gst_net_credit"], 0),
        "raw_return_no_direct_gl": raw_return_ev["gl_entry_count"] == 0
        and core._close(raw_return_ev["gst_net_credit"], 0),
        "raw_sale_native_template": core.STANDARD_TEMPLATE
        in raw_sale_ev["item_tax_templates"],
        "raw_return_native_template": core.STANDARD_TEMPLATE
        in raw_return_ev["item_tax_templates"],
        "sale_consolidated_link": sale.consolidated_invoice
        == consolidated_sale.name,
        "return_consolidated_link": return_doc.consolidated_invoice
        == consolidated_return.name,
        "credit_note_links_to_consolidated_sale": cint(
            consolidated_return.is_return
        )
        == 1
        and consolidated_return.return_against == consolidated_sale.name,
        "sale_net_preserved": core._close(
            sale_ev["net_total"], expected_sale_net
        ),
        "sale_tax_preserved": core._close(
            sale_ev["total_taxes_and_charges"], expected_sale_tax
        ),
        "sale_grand_preserved": core._close(
            sale_ev["grand_total"], expected_sale_grand
        ),
        "return_net_reversed": core._close(
            return_ev["net_total"], -expected_sale_net
        ),
        "return_tax_reversed": core._close(
            return_ev["total_taxes_and_charges"], -expected_sale_tax
        ),
        "return_grand_reversed": core._close(
            return_ev["grand_total"], -expected_sale_grand
        ),
        "sale_gst_gl_correct": core._close(
            sale_ev["gst_net_credit"], expected_sale_tax
        ),
        "return_gst_gl_reversed": core._close(
            return_ev["gst_net_credit"], -expected_sale_tax
        ),
        "sale_gl_exists": sale_ev["gl_entry_count"] > 0,
        "return_gl_exists": return_ev["gl_entry_count"] > 0,
        "sale_gl_balanced": sale_ev["gl_balanced"],
        "return_gl_balanced": return_ev["gl_balanced"],
        "sale_cash_debit_correct": bool(sale_cash_account)
        and core._close(sale_cash_net_credit, -expected_sale_grand),
        "return_cash_credit_correct": bool(return_cash_account)
        and core._close(return_cash_net_credit, expected_sale_grand),
        "sale_revenue_credit_correct": bool(sale_income_account)
        and core._close(sale_income_net_credit, expected_sale_net),
        "return_revenue_debit_correct": bool(return_income_account)
        and core._close(return_income_net_credit, -expected_sale_net),
        "gst_round_trip_zero": core._close(
            sale_ev["gst_net_credit"] + return_ev["gst_net_credit"], 0
        ),
        "cash_round_trip_zero": core._close(
            sale_cash_net_credit + return_cash_net_credit, 0
        ),
        "revenue_round_trip_zero": core._close(
            sale_income_net_credit + return_income_net_credit, 0
        ),
        "totals_round_trip_zero": core._close(
            sale_ev["grand_total"] + return_ev["grand_total"], 0
        ),
        "no_legacy_tax_rows_on_consolidated_sale": not sale_ev[
            "legacy_managed_rows"
        ],
        "no_legacy_tax_rows_on_consolidated_return": not return_ev[
            "legacy_managed_rows"
        ],
        "erpnext_commit_was_intercepted": len(commit_intercepts) >= 1,
    }

    created_records = [
        ("POS Opening Entry", opening.name),
        ("POS Invoice", sale.name),
        ("POS Invoice", return_doc.name),
        ("POS Closing Entry", closing.name),
        ("Sales Invoice", consolidated_sale.name),
        ("Sales Invoice", consolidated_return.name),
    ]
    created_records.extend(
        ("POS Invoice Merge Log", row["name"]) for row in merge_logs
    )

    return core._case("pos_closing_consolidated_gl", evidence, checks), created_records


def _post_rollback_evidence(
    *,
    created_records: list[tuple[str, str]],
    profile_name: str,
    price_list: str,
    pos_template: str,
    item_price_names: list[str],
    original_item_disabled: dict[str, int],
    main_state_before: dict,
) -> dict:
    persisted = []
    for doctype, name in created_records:
        if name and frappe.db.exists(doctype, name):
            persisted.append({"doctype": doctype, "name": name})

    for doctype, name in (
        ("POS Profile", profile_name),
        ("Price List", price_list),
        ("Sales Taxes and Charges Template", pos_template),
    ):
        if name and frappe.db.exists(doctype, name):
            persisted.append({"doctype": doctype, "name": name})

    for name in item_price_names:
        if name and frappe.db.exists("Item Price", name):
            persisted.append({"doctype": "Item Price", "name": name})

    current_item_disabled = {
        item_code: cint(frappe.db.get_value("Item", item_code, "disabled"))
        for item_code in original_item_disabled
    }
    main_state_after = _main_counter_state()

    consolidated_names = [
        name
        for doctype, name in created_records
        if doctype == "Sales Invoice" and name
    ]
    gl_rows_left = 0
    if consolidated_names:
        gl_rows_left = frappe.db.count(
            "GL Entry",
            {
                "voucher_type": "Sales Invoice",
                "voucher_no": ["in", consolidated_names],
            },
        )

    return {
        "persisted_gate_records": persisted,
        "gate_gl_rows_left": gl_rows_left,
        "fixture_item_disabled_before": original_item_disabled,
        "fixture_item_disabled_after": current_item_disabled,
        "main_counter_state_before": main_state_before,
        "main_counter_state_after": main_state_after,
        "rollback_clean": not persisted
        and gl_rows_left == 0
        and current_item_disabled == original_item_disabled
        and main_state_after == main_state_before,
    }


def run() -> dict:
    core._assert_safe_site()
    frappe.set_user("Administrator")
    core._require_native_foundation()

    original_user = frappe.session.user
    original_queue = fbr_native.queue_native_for_fbr
    original_commit = frappe.db.commit

    fbr_hook_intercepts: list[dict] = []
    commit_intercepts: list[dict] = []

    def _no_network_queue(reference_doctype, reference_name, reason=None):
        fbr_hook_intercepts.append(
            {
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "reason": reason or "",
            }
        )
        return {
            "queued": False,
            "status": "POS Closing Parity Gate Bypass",
            "reason": "In-memory test bypass; no FBR network call.",
        }

    def _no_commit(*args, **kwargs):
        commit_intercepts.append(
            {
                "index": len(commit_intercepts) + 1,
                "reason": "ERPNext POS consolidation commit intercepted in-memory",
            }
        )
        return None

    result = None
    created_records: list[tuple[str, str]] = []
    profile_name = ""
    price_list = ""
    pos_template = ""
    item_price_names: list[str] = []

    original_item_disabled = {
        item_code: cint(frappe.db.get_value("Item", item_code, "disabled"))
        for item_code in core.ITEMS.values()
    }
    main_state_before = _main_counter_state()

    try:
        # These two in-process substitutions happen before ANY gate write.
        # They are restored in finally.
        fbr_native.queue_native_for_fbr = _no_network_queue
        frappe.db.commit = _no_commit

        if frappe.db.commit is not _no_commit:
            frappe.throw("Could not install the in-memory database commit guard.")

        core._enable_fixture_items()
        price_list = core._new_price_list()
        pos_template = core._new_pos_template()

        item_price_names = frappe.get_all(
            "Item Price",
            filters={"price_list": price_list},
            pluck="name",
        )

        cashier = _available_cashier()
        profile = _new_isolated_profile(
            price_list=price_list,
            taxes_and_charges=pos_template,
            cashier=cashier,
        )
        profile_name = profile.name

        opening = _create_opening(profile, cashier)
        sale = _create_sale(profile, price_list, cashier)
        return_doc = _create_return(sale, cashier)

        case, created_records = _closing_case(
            profile=profile,
            cashier=cashier,
            opening=opening,
            sale=sale,
            return_doc=return_doc,
            commit_intercepts=commit_intercepts,
        )

        failed_checks = [
            name for name, passed in case["checks"].items() if not passed
        ]

        result = {
            "site": frappe.local.site,
            "authority": erpnext_tax_authority.current_tax_authority(),
            "database_persistence": "ROLLBACK_PENDING_VERIFICATION",
            "fbr_network_calls": 0,
            "fbr_submit_hooks_intercepted_in_memory": len(
                fbr_hook_intercepts
            ),
            "fbr_submit_hook_evidence": fbr_hook_intercepts,
            "erpnext_commit_calls_intercepted_in_memory": len(
                commit_intercepts
            ),
            "case_count": 1,
            "failed_cases": [] if case.get("passed") else [case["name"]],
            "failed_checks": failed_checks,
            "cases": {case["name"]: case},
            "gate_passed": bool(case.get("passed")),
            "scope_proven": [
                "Raw POS Invoice native tax and no direct GL",
                "Raw POS full return native tax reversal and no direct GL",
                "ERPNext POS Opening/Closing lifecycle",
                "ERPNext POS Invoice Merge Log consolidation",
                "Consolidated Sales Invoice GST GL",
                "Consolidated return/credit Sales Invoice GST reversal",
                "Cash and revenue GL direction",
                "Balanced consolidated sale and return GL",
                "No [LEDGIX-TAX] monetary rows",
            ],
        }

        if failed_checks:
            frappe.throw(
                "Phase 1 POS Closing parity checks failed: "
                + ", ".join(failed_checks)
            )

    finally:
        # Restore process-global state BEFORE ending the outer transaction.
        frappe.set_user(original_user)
        fbr_native.queue_native_for_fbr = original_queue
        frappe.db.commit = original_commit

        # Every fixture/master/invoice/GL row above must disappear here.
        frappe.db.rollback()

    post_rollback = _post_rollback_evidence(
        created_records=created_records,
        profile_name=profile_name,
        price_list=price_list,
        pos_template=pos_template,
        item_price_names=item_price_names,
        original_item_disabled=original_item_disabled,
        main_state_before=main_state_before,
    )

    result["post_rollback"] = post_rollback
    result["database_persistence"] = (
        "ROLLBACK_CONFIRMED"
        if post_rollback["rollback_clean"]
        else "ROLLBACK_VERIFICATION_FAILED"
    )
    result["gate_passed"] = bool(
        result["gate_passed"] and post_rollback["rollback_clean"]
    )

    if not post_rollback["rollback_clean"]:
        result["failed_cases"].append("post_rollback_cleanup")
        frappe.throw(
            "POS Closing parity accounting checks passed, but rollback "
            "verification found persisted gate state. No cleanup was attempted."
        )

    return result
