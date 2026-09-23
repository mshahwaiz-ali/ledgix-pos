from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import cint, flt, nowdate

from ledgix_saas.api import fbr_native
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.services import erpnext_pos, erpnext_selling, erpnext_tax_authority


COMPANY = "Ledgix ERPNext Integration"
GST_ACCOUNT = "GST - LEI"

STANDARD_TEMPLATE = "Ledgix Sales Tax 18 - LEI"
ZERO_TEMPLATE = "Ledgix Sales Tax Zero Rated - LEI"
EXEMPT_TEMPLATE = "Ledgix Sales Tax Exempt - LEI"

ITEMS = {
    "ordinary": "LEDGIX-P4-ORDINARY",
    "inclusive": "LEDGIX-P4-INCLUSIVE",
    "zero": "LEDGIX-P4-ZERO",
    "exempt": "LEDGIX-P4-EXEMPT",
    "mixed_standard": "LEDGIX-P4-MIX-A",
    "return": "LEDGIX-P4-RETURN",
}

MONEY_TOLERANCE = 0.02
LEGACY_PREFIX = "[LEDGIX-TAX]"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing native parity gate on {frappe.local.site!r}; "
            f"restricted to {INTEGRATION_SITE!r}."
        )


def _close(a, b, tolerance=MONEY_TOLERANCE) -> bool:
    return abs(flt(a) - flt(b)) <= tolerance


def _require_native_foundation() -> None:
    if erpnext_tax_authority.current_tax_authority() != "ERPNext Native":
        frappe.throw("Phase 1 parity requires ERPNext Native as the active tax authority.")

    if not frappe.db.exists("Company", COMPANY):
        frappe.throw(f"Missing Company {COMPANY}.")

    if not frappe.db.exists("Account", GST_ACCOUNT):
        frappe.throw(f"Missing native GST account {GST_ACCOUNT}.")

    for template in (STANDARD_TEMPLATE, ZERO_TEMPLATE, EXEMPT_TEMPLATE):
        if not frappe.db.exists("Item Tax Template", template):
            frappe.throw(f"Missing native Item Tax Template {template}.")

    if not cint(
        frappe.db.get_single_value(
            "Accounts Settings",
            "add_taxes_from_item_tax_template",
        )
    ):
        frappe.throw("Automatically Add Taxes from Item Tax Template must be enabled.")

    for item_code in ITEMS.values():
        if not frappe.db.exists("Item", item_code):
            frappe.throw(f"Missing Phase 4 parity fixture Item {item_code}.")

    profile = frappe.get_doc("POS Profile", "Main Counter POS")
    if cint(profile.disabled):
        frappe.throw("Main Counter POS must be enabled for native parity.")
    if profile.company != COMPANY:
        frappe.throw("Main Counter POS belongs to another Company.")
    if not erpnext_pos.payment_methods(profile):
        frappe.throw("Main Counter POS has no usable payment method.")


def _enable_fixture_items() -> None:
    for item_code in ITEMS.values():
        frappe.db.set_value(
            "Item",
            item_code,
            "disabled",
            0,
            update_modified=False,
        )
    frappe.clear_cache(doctype="Item")


def _new_price_list() -> str:
    token = frappe.generate_hash(length=8).upper()
    name = f"LEDGIX Native Gate {token}"
    currency = frappe.db.get_value("Company", COMPANY, "default_currency") or "PKR"

    doc = frappe.get_doc(
        {
            "doctype": "Price List",
            "price_list_name": name,
            "selling": 1,
            "buying": 0,
            "currency": currency,
        }
    )
    doc.insert(ignore_permissions=True)

    price = frappe.get_doc(
        {
            "doctype": "Item Price",
            "price_list": doc.name,
            "item_code": ITEMS["ordinary"],
            "uom": "Nos",
            "price_list_rate": 1000,
            "currency": currency,
        }
    )
    price.insert(ignore_permissions=True)
    return doc.name

def _new_pos_template() -> str:
    token = frappe.generate_hash(length=8).upper()
    title = f"Ledgix Native Gate POS 18 {token}"

    doc = frappe.get_doc(
        {
            "doctype": "Sales Taxes and Charges Template",
            "title": title,
            "company": COMPANY,
            "disabled": 0,
            "is_default": 0,
            "taxes": [
                {
                    "charge_type": "On Net Total",
                    "account_head": GST_ACCOUNT,
                    "description": "Native POS GST 18%",
                    "rate": 18,
                    "included_in_print_rate": 0,
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _new_inclusive_template() -> str:
    token = frappe.generate_hash(length=8).upper()
    title = f"Ledgix Native Gate Inclusive 18 {token}"

    doc = frappe.get_doc(
        {
            "doctype": "Sales Taxes and Charges Template",
            "title": title,
            "company": COMPANY,
            "disabled": 0,
            "is_default": 0,
            "taxes": [
                {
                    "charge_type": "On Net Total",
                    "account_head": GST_ACCOUNT,
                    "description": "Native gate inclusive GST 18%",
                    "rate": 18,
                    "included_in_print_rate": 1,
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _customer() -> str:
    profile = frappe.get_doc("POS Profile", "Main Counter POS")
    customer = str(profile.customer or "").strip()
    if not customer or not frappe.db.exists("Customer", customer):
        frappe.throw("Main Counter POS needs a valid default Customer.")
    return customer


def _direct_sales_invoice(
    rows: list[dict],
    *,
    taxes_and_charges: str | None = None,
    remarks: str,
):
    currency = frappe.db.get_value("Company", COMPANY, "default_currency") or "PKR"
    doc = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "company": COMPANY,
            "customer": _customer(),
            "posting_date": nowdate(),
            "due_date": nowdate(),
            "currency": currency,
            "update_stock": 0,
            "ignore_pricing_rule": 1,
            "taxes_and_charges": taxes_and_charges or "",
            "remarks": remarks,
            "items": [
                {
                    "item_code": row["item_code"],
                    "qty": row.get("qty", 1),
                    "uom": row.get("uom", "Nos"),
                    "rate": row["rate"],
                    "price_list_rate": row["rate"],
                }
                for row in rows
            ],
        }
    )

    doc.set_missing_values()

    if taxes_and_charges and not doc.get("taxes"):
        from erpnext.accounts.services.taxes import TaxService

        TaxService(doc).append_taxes_from_master()

    erpnext_tax_authority.apply_sales_tax_authority(doc)
    doc.insert(ignore_permissions=True)
    doc.submit()
    doc.reload()
    return doc


def _gl_rows(doc) -> list[dict]:
    return [
        dict(row)
        for row in frappe.get_all(
            "GL Entry",
            filters={
                "voucher_type": doc.doctype,
                "voucher_no": doc.name,
                "is_cancelled": 0,
            },
            fields=["account", "debit", "credit"],
            order_by="name asc",
            limit_page_length=0,
        )
    ]


def _net_credit(doc, account: str) -> float:
    rows = [row for row in _gl_rows(doc) if row["account"] == account]
    return flt(sum(flt(row["credit"]) - flt(row["debit"]) for row in rows), 6)


def _gl_balanced(doc) -> bool:
    rows = _gl_rows(doc)
    debit = sum(flt(row["debit"]) for row in rows)
    credit = sum(flt(row["credit"]) for row in rows)
    return _close(debit, credit)


def _legacy_rows(doc) -> list[int]:
    return [
        int(row.idx or 0)
        for row in (doc.get("taxes") or [])
        if str(row.description or "").startswith(LEGACY_PREFIX)
    ]


def _tax_rows(doc) -> list[dict]:
    return [
        {
            "idx": row.idx,
            "charge_type": row.charge_type,
            "account_head": row.account_head,
            "rate": flt(row.rate),
            "tax_amount": flt(row.tax_amount),
            "included_in_print_rate": cint(row.included_in_print_rate),
            "description": row.description or "",
        }
        for row in (doc.get("taxes") or [])
    ]


def _evidence(doc) -> dict:
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "docstatus": doc.docstatus,
        "is_return": cint(doc.get("is_return")),
        "return_against": doc.get("return_against") or "",
        "net_total": flt(doc.net_total, 6),
        "total_taxes_and_charges": flt(doc.total_taxes_and_charges, 6),
        "grand_total": flt(doc.grand_total, 6),
        "rounded_total": flt(doc.get("rounded_total"), 6),
        "paid_amount": flt(doc.get("paid_amount"), 6),
        "tax_rows": _tax_rows(doc),
        "legacy_managed_rows": _legacy_rows(doc),
        "gst_net_credit": _net_credit(doc, GST_ACCOUNT),
        "gl_balanced": _gl_balanced(doc),
        "gl_entry_count": len(_gl_rows(doc)),
        "item_tax_templates": [
            row.item_tax_template or ""
            for row in (doc.get("items") or [])
        ],
        "item_tax_rates": [
            row.item_tax_rate or ""
            for row in (doc.get("items") or [])
        ],
    }


def _case(name: str, evidence: dict, checks: dict) -> dict:
    return {
        "name": name,
        "passed": all(checks.values()),
        "checks": checks,
        "evidence": evidence,
    }


def _standard_sales_invoice(price_list: str) -> tuple[dict, object]:
    invoice = erpnext_selling.build_sales_invoice(
        customer=_customer(),
        items=[{"item": ITEMS["ordinary"], "qty": 1}],
        company=COMPANY,
        selling_price_list=price_list,
        sale_channel="B2B",
        client_sale_id=f"NATIVE-GATE-SI-{frappe.generate_hash(length=10)}",
        allow_rate_override=False,
        update_stock=False,
        checkout_source="Phase 1 Native Core Parity Gate",
    )
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    invoice.reload()

    ev = _evidence(invoice)
    expected_tax = flt(ev["net_total"] * 0.18, 6)
    checks = {
        "submitted": invoice.docstatus == 1,
        "native_template_resolved": STANDARD_TEMPLATE in ev["item_tax_templates"],
        "tax_is_18_percent": _close(ev["total_taxes_and_charges"], expected_tax),
        "grand_total_correct": _close(
            ev["grand_total"],
            ev["net_total"] + expected_tax,
        ),
        "gst_gl_correct": _close(ev["gst_net_credit"], expected_tax),
        "gl_balanced": ev["gl_balanced"],
        "no_legacy_tax_rows": not ev["legacy_managed_rows"],
    }
    return _case("sales_invoice_standard_18", ev, checks), invoice


def _standard_pos_invoice(price_list: str) -> tuple[dict, object]:
    profile = frappe.get_doc("POS Profile", "Main Counter POS")

    invoice = erpnext_pos.build_pos_invoice(
        cart_items=[{"item": ITEMS["ordinary"], "qty": 1}],
        customer=profile.customer,
        price_list=price_list,
        client_sale_id=f"NATIVE-GATE-POS-{frappe.generate_hash(length=10)}",
        allow_rate_override=False,
        source="Phase 1 Native Core Parity Gate",
        company=COMPANY,
        pos_profile=profile.name,
    )
    erpnext_pos._default_draft_payment(invoice, profile)
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    invoice.reload()

    ev = _evidence(invoice)
    expected_tax = flt(ev["net_total"] * 0.18, 6)
    checks = {
        "submitted": invoice.docstatus == 1,
        "native_template_resolved": STANDARD_TEMPLATE in ev["item_tax_templates"],
        "tax_is_18_percent": _close(ev["total_taxes_and_charges"], expected_tax),
        "grand_total_correct": _close(
            ev["grand_total"],
            ev["net_total"] + expected_tax,
        ),
        "fully_paid": _close(
            ev["paid_amount"],
            flt(invoice.rounded_total or invoice.grand_total),
        ),
        "no_direct_pos_gl_expected": ev["gl_entry_count"] == 0 and _close(ev["gst_net_credit"], 0),
        "gl_balanced": ev["gl_balanced"],
        "no_legacy_tax_rows": not ev["legacy_managed_rows"],
    }
    return _case("pos_invoice_standard_18", ev, checks), invoice


def _inclusive_case(inclusive_template: str) -> dict:
    invoice = _direct_sales_invoice(
        [{"item_code": ITEMS["inclusive"], "rate": 1180}],
        taxes_and_charges=inclusive_template,
        remarks="Phase 1 Native Gate Inclusive",
    )
    ev = _evidence(invoice)
    checks = {
        "submitted": invoice.docstatus == 1,
        "net_total_1000": _close(ev["net_total"], 1000),
        "included_tax_180": _close(ev["total_taxes_and_charges"], 180),
        "grand_total_1180": _close(ev["grand_total"], 1180),
        "gst_gl_180": _close(ev["gst_net_credit"], 180),
        "inclusive_row_present": any(
            row["account_head"] == GST_ACCOUNT
            and row["included_in_print_rate"] == 1
            for row in ev["tax_rows"]
        ),
        "gl_balanced": ev["gl_balanced"],
        "no_legacy_tax_rows": not ev["legacy_managed_rows"],
    }
    return _case("sales_invoice_inclusive_18", ev, checks)


def _zero_case() -> dict:
    invoice = _direct_sales_invoice(
        [{"item_code": ITEMS["zero"], "rate": 1000}],
        remarks="Phase 1 Native Gate Zero Rated",
    )
    ev = _evidence(invoice)
    checks = {
        "submitted": invoice.docstatus == 1,
        "zero_template_resolved": ZERO_TEMPLATE in ev["item_tax_templates"],
        "tax_zero": _close(ev["total_taxes_and_charges"], 0),
        "grand_total_1000": _close(ev["grand_total"], 1000),
        "gst_gl_zero": _close(ev["gst_net_credit"], 0),
        "gl_balanced": ev["gl_balanced"],
        "no_legacy_tax_rows": not ev["legacy_managed_rows"],
    }
    return _case("sales_invoice_zero_rated", ev, checks)


def _exempt_case() -> dict:
    invoice = _direct_sales_invoice(
        [{"item_code": ITEMS["exempt"], "rate": 1000}],
        remarks="Phase 1 Native Gate Exempt",
    )
    ev = _evidence(invoice)
    checks = {
        "submitted": invoice.docstatus == 1,
        "exempt_template_resolved": EXEMPT_TEMPLATE in ev["item_tax_templates"],
        "tax_zero": _close(ev["total_taxes_and_charges"], 0),
        "grand_total_1000": _close(ev["grand_total"], 1000),
        "gst_gl_zero": _close(ev["gst_net_credit"], 0),
        "gl_balanced": ev["gl_balanced"],
        "no_legacy_tax_rows": not ev["legacy_managed_rows"],
    }
    return _case("sales_invoice_exempt", ev, checks)


def _mixed_case() -> dict:
    invoice = _direct_sales_invoice(
        [
            {"item_code": ITEMS["mixed_standard"], "rate": 1000},
            {"item_code": ITEMS["zero"], "rate": 1000},
            {"item_code": ITEMS["exempt"], "rate": 1000},
        ],
        remarks="Phase 1 Native Gate Mixed",
    )
    ev = _evidence(invoice)
    checks = {
        "submitted": invoice.docstatus == 1,
        "net_total_3000": _close(ev["net_total"], 3000),
        "only_standard_line_taxed": _close(ev["total_taxes_and_charges"], 180),
        "grand_total_3180": _close(ev["grand_total"], 3180),
        "gst_gl_180": _close(ev["gst_net_credit"], 180),
        "all_three_native_templates": {
            STANDARD_TEMPLATE,
            ZERO_TEMPLATE,
            EXEMPT_TEMPLATE,
        }.issubset(set(ev["item_tax_templates"])),
        "gl_balanced": ev["gl_balanced"],
        "no_legacy_tax_rows": not ev["legacy_managed_rows"],
    }
    return _case("sales_invoice_mixed_standard_zero_exempt", ev, checks)


def _sales_return_case() -> dict:
    source = _direct_sales_invoice(
        [{"item_code": ITEMS["return"], "rate": 1000}],
        remarks="Phase 1 Native Gate Sales Return Source",
    )

    credit = erpnext_selling.create_sales_return(
        sales_invoice=source.name,
        return_items=[
            {
                "sales_invoice_item": source.items[0].name,
                "qty": 1,
            }
        ],
        reason="Phase 1 native parity rollback test",
        client_return_id=f"NATIVE-GATE-SIR-{frappe.generate_hash(length=10)}",
        checkout_source="Phase 1 Native Core Parity Gate",
    )
    credit.reload()

    ev = _evidence(credit)
    checks = {
        "submitted": credit.docstatus == 1,
        "is_return": cint(credit.is_return) == 1,
        "return_against_source": credit.return_against == source.name,
        "net_total_minus_1000": _close(ev["net_total"], -1000),
        "tax_minus_180": _close(ev["total_taxes_and_charges"], -180),
        "grand_total_minus_1180": _close(ev["grand_total"], -1180),
        "gst_gl_reversed": _close(ev["gst_net_credit"], -180),
        "gl_balanced": ev["gl_balanced"],
        "no_legacy_tax_rows": not ev["legacy_managed_rows"],
    }
    return _case("sales_invoice_full_return", ev, checks)


def _pos_return_case(pos_source) -> dict:
    from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

    credit = make_sales_return(pos_source.name)
    erpnext_tax_authority.apply_sales_tax_authority(credit)

    # ERPNext's return mapper carries repayment rows from the source POS Invoice.
    credit.insert(ignore_permissions=True)
    credit.submit()
    credit.reload()

    ev = _evidence(credit)
    expected_net = -abs(flt(pos_source.net_total))
    expected_tax = -abs(flt(pos_source.total_taxes_and_charges))
    expected_grand = -abs(flt(pos_source.grand_total))

    checks = {
        "submitted": credit.docstatus == 1,
        "is_return": cint(credit.is_return) == 1,
        "return_against_source": credit.return_against == pos_source.name,
        "net_total_reversed": _close(ev["net_total"], expected_net),
        "tax_reversed": _close(ev["total_taxes_and_charges"], expected_tax),
        "grand_total_reversed": _close(ev["grand_total"], expected_grand),
        "no_direct_pos_return_gl_expected": ev["gl_entry_count"] == 0 and _close(ev["gst_net_credit"], 0),
        "gl_balanced": ev["gl_balanced"],
        "no_legacy_tax_rows": not ev["legacy_managed_rows"],
    }
    return _case("pos_invoice_full_return", ev, checks)


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")
    _require_native_foundation()

    original_queue = fbr_native.queue_native_for_fbr
    fbr_hook_intercepts = []

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
            "status": "Native Parity Gate Bypass",
            "reason": "In-memory test bypass; no FBR network call.",
        }

    result = None

    try:
        # Critical: neutralize the submit hook only in this Python process.
        fbr_native.queue_native_for_fbr = _no_network_queue

        _enable_fixture_items()
        price_list = _new_price_list()
        inclusive_template = _new_inclusive_template()
        pos_template = _new_pos_template()

        pos_profile = frappe.get_doc("POS Profile", "Main Counter POS")
        pos_profile.db_set(
            "taxes_and_charges",
            pos_template,
            update_modified=False,
        )
        frappe.clear_cache(doctype="POS Profile")

        cases = {}

        cases["sales_invoice_standard_18"], _ = _standard_sales_invoice(price_list)
        cases["sales_invoice_inclusive_18"] = _inclusive_case(inclusive_template)
        cases["sales_invoice_zero_rated"] = _zero_case()
        cases["sales_invoice_exempt"] = _exempt_case()
        cases["sales_invoice_mixed"] = _mixed_case()

        cases["pos_invoice_standard_18"], pos_source = _standard_pos_invoice(price_list)
        cases["sales_invoice_full_return"] = _sales_return_case()
        cases["pos_invoice_full_return"] = _pos_return_case(pos_source)

        failed = [
            name
            for name, case in cases.items()
            if not case.get("passed")
        ]

        result = {
            "site": frappe.local.site,
            "authority": erpnext_tax_authority.current_tax_authority(),
            "database_persistence": "ROLLBACK",
            "fbr_network_calls": 0,
            "fbr_submit_hooks_intercepted_in_memory": len(fbr_hook_intercepts),
            "fbr_submit_hook_evidence": fbr_hook_intercepts,
            "case_count": len(cases),
            "failed_cases": failed,
            "cases": cases,
            "gate_passed": not failed and len(cases) == 8,
            "scope_proven": [
                "Sales Invoice standard 18%",
                "Sales Invoice tax-inclusive 18%",
                "Sales Invoice zero-rated",
                "Sales Invoice exempt/not-applicable",
                "Sales Invoice mixed standard/zero/exempt",
                "POS Invoice standard 18%",
                "Sales Invoice full native return",
                "POS Invoice full native return",
                "Raw POS Invoice correctly defers GL to POS Closing consolidation",
                "ERPNext Sales Invoice GL uses GST - LEI",
                "No [LEDGIX-TAX] rows",
            ],
            "scope_outside_this_core_gate": [
                "Third Schedule / notified retail value - proven by dedicated Phase 1 gate",
                "Extra Tax - proven by dedicated Phase 1 gate",
                "Further Tax - proven by dedicated Phase 1 gate",
                "FED - proven by dedicated Phase 1 gate",
                "POS Closing consolidated Sales Invoice/Credit Note GL - proven by dedicated Phase 1 gate",
                "Sales Tax Withheld invoice/FBR evidence treatment - proven by dedicated Phase 1 gate",
                "Sales Tax Withheld buyer net-payment settlement accounting - unresolved",
            ],
        }

        if failed:
            frappe.throw(
                "Phase 1 native core parity gate failed: "
                + ", ".join(failed)
            )

    finally:
        fbr_native.queue_native_for_fbr = original_queue
        # Intentionally remove every master, invoice, payment and GL row created
        # by this gate. Evidence above is captured before this rollback.
        frappe.db.rollback()

    return result
