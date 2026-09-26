from __future__ import annotations

"""ERPNext-native per-line tax capture for the FBR V2 redesign.

This module does not calculate tax with Ledgix formulas. It instruments the
pinned ERPNext taxes_and_totals engine and records the engine's own per-line
results. It is not wired into invoice submission or FBR transport yet.

Pinned compatibility target: ERPNext 15.121.3.
"""

from collections import defaultdict

import frappe
from frappe.utils import cint, flt, getdate

from erpnext.controllers.taxes_and_totals import (
    calculate_taxes_and_totals as ERPNextTaxesAndTotals,
)


SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}
MAPPING_DOCTYPE = "Ledgix FBR Item Mapping"
COMPONENT_MAPPING_DOCTYPE = "Ledgix FBR Tax Component Mapping"
MONEY_TOLERANCE = 0.011
NOT_APPLICABLE_TAX = "N/A"
WITHHELD_COMPONENT = "Sales Tax Withheld At Source"

COMPONENT_FIELD = {
    "Sales Tax Applicable": "sales_tax",
    "Sales Tax Withheld At Source": "sales_tax_withheld_at_source",
    "Extra Tax": "extra_tax",
    "Further Tax": "further_tax",
    "FED Payable": "fed_payable",
}


def _row_key(row, prefix: str) -> str:
    return str(row.get("name") or f"{prefix}-{row.get('idx') or 0}")


class ERPNextNativeTaxCollector(ERPNextTaxesAndTotals):
    """Capture ERPNext's own per-item/per-tax-row calculation results.

    Additional-discount processing in ERPNext performs a second _calculate()
    pass. Resetting the capture at _calculate() means the retained data is the
    final pass after native discount distribution.
    """

    def __init__(self, doc):
        self.line_tax_capture: dict[str, dict[str, dict]] = {}
        super().__init__(doc)

    def _calculate(self):
        self.line_tax_capture = {}
        return super()._calculate()

    def get_current_tax_and_net_amount(self, item, tax, item_tax_map):
        current_net_amount, current_tax_amount = super().get_current_tax_and_net_amount(
            item,
            tax,
            item_tax_map,
        )

        # ERPNext custom charge types calculate against get_item_taxable_base()
        # while the standard method leaves current_net_amount at zero. Capture
        # that resolver-provided base only as evidence; Ledgix does not calculate tax.
        capture_taxable_base = current_net_amount
        if tax.get("charge_type") not in {
            "Actual",
            "On Net Total",
            "On Previous Row Amount",
            "On Previous Row Total",
            "On Item Quantity",
        }:
            capture_taxable_base = self.get_item_taxable_base(item, tax)

        item_key = _row_key(item, "item")
        tax_key = _row_key(tax, "tax")
        self.line_tax_capture.setdefault(item_key, {})[tax_key] = {
            "item_row": item_key,
            "item_idx": item.get("idx"),
            "item_code": item.get("item_code") or "",
            "tax_row": tax_key,
            "tax_idx": tax.get("idx"),
            "account_head": tax.get("account_head") or "",
            "charge_type": tax.get("charge_type") or "",
            "included_in_print_rate": bool(cint(tax.get("included_in_print_rate"))),
            "tax_rate": flt(self._get_tax_rate(tax, item_tax_map)),
            "taxable_base": flt(capture_taxable_base),
            "tax_amount": flt(current_tax_amount),
        }
        return current_net_amount, current_tax_amount


def _assert_capture_supported(doc) -> None:
    if not doc or doc.doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("Native FBR V2 tax capture requires Sales Invoice or POS Invoice.")

    if cint(
        frappe.db.get_single_value("Accounts Settings", "round_row_wise_tax")
    ):
        frappe.throw(
            "FBR V2 native line capture is not yet enabled when ERPNext "
            "Round Tax Amount Row-wise is on. Keep this fail-closed until "
            "row-wise rounding parity is runtime-proven."
        )


def _active_component_mappings(company: str) -> dict[str, str]:
    rows = frappe.get_all(
        COMPONENT_MAPPING_DOCTYPE,
        filters={"company": company, "active": 1},
        fields=["account_head", "component"],
        limit_page_length=0,
    )
    mappings = {}
    for row in rows:
        account = str(row.get("account_head") or "").strip()
        component = str(row.get("component") or "").strip()
        if not account or component not in COMPONENT_FIELD:
            frappe.throw(
                f"Invalid active FBR Tax Component Mapping for {account or '[blank account]'}."
            )
        if account in mappings and mappings[account] != component:
            frappe.throw(
                f"ERPNext tax Account {account} has multiple active FBR component meanings."
            )
        mappings[account] = component
    return mappings



def _collect_non_posting_withheld_rows(
    doc,
    item,
    collector,
    component_mappings: dict[str, str],
) -> list[dict]:
    # Rate source: ERPNext Item Tax Template. Amount calculation: ERPNext's
    # own On Item Quantity primitive. The transient row is never appended to
    # invoice.taxes, so it cannot affect receivable, grand total, or GL.
    item_tax_map = collector._load_item_tax_rate(item.get("item_tax_rate"))
    if not item_tax_map:
        return []

    financial_accounts = {
        str(row.get("account_head") or "").strip()
        for row in doc.get("taxes") or []
        if str(row.get("account_head") or "").strip()
    }

    captures = []
    for account, component in component_mappings.items():
        if component != WITHHELD_COMPONENT:
            continue

        if account in financial_accounts:
            frappe.throw(
                f"Sales Tax Withheld At Source Account {account} is present in "
                "financial invoice taxes. Withheld evidence must be non-posting."
            )

        raw_rate = item_tax_map.get(account)
        if raw_rate in (None, "", NOT_APPLICABLE_TAX):
            continue
        if abs(flt(raw_rate)) <= 0.000001:
            continue

        tax = frappe.new_doc("Sales Taxes and Charges")

        # This row is intentionally transient/non-posting, but ERPNext's
        # precision resolver still needs the child-table relationship in
        # order to resolve Sales Taxes and Charges.rate metadata correctly.
        tax.parenttype = doc.doctype
        tax.parentfield = "taxes"
        tax.parent = doc.name or f"new-{doc.doctype}"

        tax.charge_type = "On Item Quantity"
        tax.account_head = account
        tax.rate = 0
        tax.included_in_print_rate = 0
        tax.dont_recompute_tax = 1

        current_net_amount, current_tax_amount = (
            ERPNextTaxesAndTotals.get_current_tax_and_net_amount(
                collector,
                item,
                tax,
                item_tax_map,
            )
        )

        captures.append(
            {
                "item_row": _row_key(item, "item"),
                "item_idx": item.get("idx"),
                "item_code": item.get("item_code") or "",
                "tax_row": f"non-posting:{account}",
                "tax_idx": None,
                "account_head": account,
                "charge_type": "On Item Quantity",
                "included_in_print_rate": False,
                "tax_rate": flt(collector._get_tax_rate(tax, item_tax_map)),
                "taxable_base": flt(current_net_amount),
                "tax_amount": flt(current_tax_amount),
                "non_posting_fbr_evidence": True,
                "authority_source": (
                    "ERPNext Item Tax Template + ERPNext On Item Quantity"
                ),
            }
        )

    return captures

def _matching_item_mapping(company: str, item_code: str, posting_date) -> dict | None:
    rows = frappe.get_all(
        MAPPING_DOCTYPE,
        filters={
            "company": company,
            "erpnext_item": item_code,
            "active": 1,
        },
        fields=[
            "name",
            "effective_from",
            "effective_to",
            "needs_review",
            "hs_code",
            "fbr_uom",
            "sales_type",
            "fbr_rate_description",
            "tax_basis",
            "notified_retail_price",
            "sro_schedule_number",
            "sro_item_serial_number",
            "reference_version",
        ],
        order_by="effective_from desc, creation desc",
        limit_page_length=0,
    )

    date = getdate(posting_date)
    matches = []
    for row in rows:
        start = getdate(row.get("effective_from")) if row.get("effective_from") else None
        end = getdate(row.get("effective_to")) if row.get("effective_to") else None
        if start and date < start:
            continue
        if end and date > end:
            continue
        matches.append(dict(row))

    if len(matches) > 1:
        frappe.throw(
            f"Multiple active FBR Item Mappings overlap for {item_code} on {date}."
        )
    return matches[0] if matches else None


def _reconcile_mapped_tax_rows(doc, collector, component_mappings: dict[str, str]) -> dict:
    by_tax_row = defaultdict(float)
    for line_rows in collector.line_tax_capture.values():
        for tax_row_key, capture in line_rows.items():
            if capture["account_head"] in component_mappings:
                by_tax_row[tax_row_key] += flt(capture["tax_amount"])

    checks = []
    for tax in doc.get("taxes") or []:
        account = str(tax.get("account_head") or "").strip()
        component = component_mappings.get(account)
        if not component:
            continue

        if component == WITHHELD_COMPONENT:
            frappe.throw(
                f"Sales Tax Withheld At Source Account {account} must not be "
                "present in financial invoice taxes."
            )

        if tax.get("charge_type") == "Actual":
            frappe.throw(
                f"Mapped FBR tax Account {account} uses ERPNext charge type Actual. "
                "Pinned v15.121.3 applies final Actual-row distribution adjustment "
                "outside the per-line calculation hook, so V2 refuses to guess a line split."
            )

        if getattr(tax, "category", None) == "Valuation":
            frappe.throw(
                f"Mapped FBR tax Account {account} is a Valuation-only tax row."
            )

        tax_key = _row_key(tax, "tax")
        captured = flt(by_tax_row.get(tax_key))
        authoritative = flt(tax.get("tax_amount_after_discount_amount"))
        difference = abs(captured - authoritative)
        checks.append(
            {
                "tax_row": tax_key,
                "account_head": account,
                "component": component,
                "charge_type": tax.get("charge_type") or "",
                "captured": captured,
                "authoritative": authoritative,
                "difference": difference,
                "passed": difference <= MONEY_TOLERANCE,
            }
        )
        if difference > MONEY_TOLERANCE:
            frappe.throw(
                f"ERPNext native line-tax capture did not reconcile for {account}: "
                f"captured {captured}, authoritative {authoritative}."
            )

    return {
        "checks": checks,
        "passed": all(row["passed"] for row in checks),
    }


def collect_native_tax_breakdown(doc) -> dict:
    """Recalculate *doc* with ERPNext's engine and capture its native line taxes.

    The caller owns document lifecycle. This method performs no database write
    and no FBR network request.
    """

    _assert_capture_supported(doc)
    collector = ERPNextNativeTaxCollector(doc)
    component_mappings = _active_component_mappings(doc.company)
    reconciliation = _reconcile_mapped_tax_rows(
        doc,
        collector,
        component_mappings,
    )

    lines = []
    posting_date = doc.get("posting_date") or doc.get("transaction_date")
    for item in doc.get("items") or []:
        item_key = _row_key(item, "item")
        mapping = _matching_item_mapping(
            doc.company,
            item.get("item_code"),
            posting_date,
        )

        components = {field: 0.0 for field in COMPONENT_FIELD.values()}
        component_rows = []
        for capture in collector.line_tax_capture.get(item_key, {}).values():
            component = component_mappings.get(capture["account_head"])
            if not component:
                continue
            fieldname = COMPONENT_FIELD[component]
            components[fieldname] += flt(capture["tax_amount"])
            component_rows.append(
                {
                    **capture,
                    "component": component,
                    "snapshot_field": fieldname,
                }
            )

        for capture in _collect_non_posting_withheld_rows(
            doc,
            item,
            collector,
            component_mappings,
        ):
            component = WITHHELD_COMPONENT
            fieldname = COMPONENT_FIELD[component]
            components[fieldname] += flt(capture["tax_amount"])
            component_rows.append(
                {
                    **capture,
                    "component": component,
                    "snapshot_field": fieldname,
                }
            )

        lines.append(
            {
                "item_row": item_key,
                "idx": item.get("idx"),
                "item_code": item.get("item_code") or "",
                "item_name": item.get("item_name") or "",
                "qty": flt(item.get("qty")),
                "price_list_rate": flt(item.get("price_list_rate")),
                "rate_with_margin": flt(item.get("rate_with_margin")),
                "rate": flt(item.get("rate")),
                "discount_percentage": flt(item.get("discount_percentage")),
                "discount_amount": flt(item.get("discount_amount")),
                "distributed_discount_amount": flt(
                    item.get("distributed_discount_amount")
                ),
                "amount": flt(item.get("amount")),
                "net_rate": flt(item.get("net_rate")),
                "net_amount": flt(item.get("net_amount")),
                "item_tax_template": item.get("item_tax_template") or "",
                "item_tax_rate": item.get("item_tax_rate") or "",
                "fbr_mapping": mapping or {},
                "components": components,
                "component_rows": component_rows,
            }
        )

    return {
        "authority": "ERPNext Native",
        "source_doctype": doc.doctype,
        "source_name": doc.name or "",
        "company": doc.company,
        "posting_date": posting_date,
        "currency": doc.get("currency") or "",
        "net_total": flt(doc.get("net_total")),
        "total_taxes_and_charges": flt(doc.get("total_taxes_and_charges")),
        "grand_total": flt(doc.get("grand_total")),
        "component_mappings": component_mappings,
        "line_count": len(lines),
        "lines": lines,
        "reconciliation": reconciliation,
        "database_write": False,
        "fbr_network_call": False,
    }


def build_snapshot_candidate(reference_doctype: str, reference_name: str) -> dict:
    """Read an ERPNext invoice and build a non-persisted V2 snapshot candidate."""

    reference_doctype = str(reference_doctype or "").strip()
    reference_name = str(reference_name or "").strip()
    if reference_doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("reference_doctype must be Sales Invoice or POS Invoice.")
    if not reference_name or not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw("Select an existing ERPNext invoice.")

    source = frappe.get_doc(reference_doctype, reference_name)

    # Recalculate a detached in-memory document so this diagnostic cannot alter
    # the persisted invoice. Submitted returns are intentionally excluded from
    # after-the-fact reconstruction; their final V2 snapshot must be captured
    # during the draft/submission lifecycle.
    if cint(source.get("is_return")) and cint(source.docstatus) == 1:
        frappe.throw(
            "Submitted return snapshots must not be reconstructed after the fact. "
            "Capture V2 return evidence during the native draft/submission lifecycle."
        )

    clone = frappe.get_doc(source.as_dict())
    result = collect_native_tax_breakdown(clone)
    result["source_docstatus"] = cint(source.docstatus)
    result["diagnostic_clone"] = True
    return result
