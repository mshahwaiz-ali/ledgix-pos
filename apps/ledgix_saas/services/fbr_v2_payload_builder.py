from __future__ import annotations

"""Canonical FBR V2 payload builder for ERPNext-native invoices.

The payload is derived only from:
- a submitted ERPNext Sales Invoice / POS Invoice,
- its hash-verified immutable FBR V2 snapshot,
- ERPNext-authoritative seller/buyer identity,
- reviewed V2 item/component mappings and cached official reference evidence.

This module performs no FBR network request and no database write. It does not
import the legacy FBR payload/settings/tax engine. Sandbox scenarioId is accepted
only as explicit certification context; it is never read from an item mapping.
"""

import frappe
from frappe.utils import cint, flt, getdate

from ledgix_saas.services import fbr_v2_readiness


SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}
MONEY_TOLERANCE = 0.02


def _text(value) -> str:
    return str(value or "").strip()


def _money(value) -> float:
    return flt(value, 2)


def _quantity(value) -> float:
    return flt(value, 4)


def _identifier(value) -> str:
    return _text(value).replace(" ", "").replace("-", "")


def _is_consolidated_pos_sales_invoice(doc) -> bool:
    return bool(
        doc.doctype == "Sales Invoice"
        and not cint(doc.get("is_return"))
        and frappe.db.exists(
            "POS Invoice",
            {"consolidated_invoice": doc.name, "docstatus": 1},
        )
    )


def _raise_readiness(errors: list[str]) -> None:
    if errors:
        frappe.throw(
            "FBR V2 payload input is not ready:\n- " + "\n- ".join(errors)
        )


def _line_item_payload(line: dict) -> dict:
    mapping = dict(line.get("fbr_mapping") or {})
    if not mapping:
        frappe.throw(
            f"{line.get('item_code') or 'Invoice line'} has no immutable V2 FBR Item Mapping."
        )
    if cint(mapping.get("needs_review")):
        frappe.throw(
            f"V2 FBR Item Mapping {mapping.get('name') or '[unknown]'} still Needs Review."
        )

    # SRO fields remain fail-closed until their exact Sandbox payload semantics
    # have been proven against the current FBR DI contract.
    if _text(mapping.get("sro_schedule_number")) or _text(
        mapping.get("sro_item_serial_number")
    ):
        frappe.throw(
            "FBR V2 SRO payload semantics are not yet Sandbox-certified."
        )

    required = {
        "hs_code": "HS Code",
        "fbr_uom": "FBR UOM",
        "sales_type": "FBR Sale Type",
        "fbr_rate_description": "FBR Rate Description",
    }
    missing = [
        label
        for fieldname, label in required.items()
        if not _text(mapping.get(fieldname))
    ]
    if missing:
        frappe.throw(
            f"{line.get('item_code') or 'Invoice line'} is missing "
            + ", ".join(missing)
            + "."
        )

    qty = _quantity(line.get("qty"))
    if qty <= 0:
        frappe.throw("Sale Invoice payload lines require a positive ERPNext quantity.")

    value_excluding_st = _money(line.get("net_amount"))
    transaction_amount = _money(line.get("amount"))
    if value_excluding_st < -MONEY_TOLERANCE or transaction_amount < -MONEY_TOLERANCE:
        frappe.throw("Sale Invoice payload lines cannot contain negative ERPNext values.")

    unit_discount = flt(line.get("discount_amount"))
    distributed_discount = flt(line.get("distributed_discount_amount"))
    if unit_discount < -MONEY_TOLERANCE or distributed_discount < -MONEY_TOLERANCE:
        frappe.throw("ERPNext commercial discount evidence cannot be negative.")

    # ERPNext amount - net_amount is NOT a safe discount calculation: inclusive
    # taxes reduce net_amount while leaving amount at the printed/gross value.
    # Freeze and use explicit ERPNext discount fields instead.
    discount = _money(
        max(unit_discount, 0) * qty
        + max(distributed_discount, 0)
    )
    if discount > MONEY_TOLERANCE:
        frappe.throw(
            "FBR V2 commercial discount payload semantics are not activated until "
            "explicit Sandbox proof."
        )

    components = dict(line.get("components") or {})
    sales_tax = _money(components.get("sales_tax"))
    sales_tax_withheld = _money(components.get("sales_tax_withheld_at_source"))
    extra_tax = _money(components.get("extra_tax"))
    further_tax = _money(components.get("further_tax"))
    fed_payable = _money(components.get("fed_payable"))

    financial_components = (sales_tax, extra_tax, further_tax, fed_payable)
    if any(value < -MONEY_TOLERANCE for value in financial_components):
        frappe.throw("Sale Invoice payload tax components cannot be negative.")
    if sales_tax_withheld < -MONEY_TOLERANCE:
        frappe.throw("Sales Tax Withheld FBR evidence cannot be negative on a sale.")

    # Sales Tax Withheld is non-posting FBR evidence and therefore must not
    # change ERPNext grand total or FBR totalValues reconciliation.
    total_values = _money(
        value_excluding_st
        + sales_tax
        + extra_tax
        + further_tax
        + fed_payable
    )
    notified_value = 0.0
    if _text(mapping.get("tax_basis")) == "Notified Retail Price":
        notified_value = _money(mapping.get("notified_retail_price"))
        if notified_value <= 0:
            frappe.throw(
                "Notified Retail Price mapping requires a positive immutable notified value."
            )

    return {
        "hsCode": _text(mapping.get("hs_code")),
        "productDescription": _text(line.get("item_name") or line.get("item_code")),
        "rate": _text(mapping.get("fbr_rate_description")),
        "uoM": _text(mapping.get("fbr_uom")),
        "quantity": qty,
        "totalValues": total_values,
        "valueSalesExcludingST": value_excluding_st,
        "fixedNotifiedValueOrRetailPrice": notified_value,
        "salesTaxApplicable": sales_tax,
        "salesTaxWithheldAtSource": sales_tax_withheld,
        "extraTax": extra_tax,
        "furtherTax": further_tax,
        "sroScheduleNo": "",
        "fedPayable": fed_payable,
        "discount": discount,
        "saleType": _text(mapping.get("sales_type")),
        "sroItemSerialNo": "",
    }


def build_payload_candidate(
    reference_doctype: str,
    reference_name: str,
    *,
    scenario_id: str | None = None,
) -> dict:
    """Build a deterministic, non-submitting FBR DI payload candidate."""

    reference_doctype = _text(reference_doctype)
    reference_name = _text(reference_name)
    if reference_doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("reference_doctype must be Sales Invoice or POS Invoice.")
    if not reference_name or not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw("Select an existing ERPNext invoice.")

    doc = frappe.get_doc(reference_doctype, reference_name)
    if cint(doc.docstatus) != 1:
        frappe.throw("FBR V2 payload requires a submitted ERPNext invoice.")
    if _is_consolidated_pos_sales_invoice(doc):
        frappe.throw(
            "Consolidated POS Sales Invoice is accounting-only; source POS Invoices own FBR payloads."
        )

    # Do not hardcode legacy Credit Note behavior into the V2 contract. The
    # current electronic-note/return mapping must first be certified in Sandbox.
    if cint(doc.get("is_return")):
        frappe.throw(
            "FBR V2 return payload is not activated until Debit/Credit Note semantics "
            "are proven in Sandbox."
        )

    readiness = fbr_v2_readiness.evaluate_invoice_readiness(
        reference_doctype,
        reference_name,
    )
    _raise_readiness(list(readiness.get("errors") or []))
    if not readiness.get("payload_input_ready"):
        frappe.throw("FBR V2 payload input readiness did not pass.")

    snapshot = dict(readiness.get("native_snapshot_candidate") or {})
    if snapshot.get("snapshot_source") != "persisted_v2" or not snapshot.get(
        "hash_verified"
    ):
        frappe.throw("FBR V2 payload requires hash-verified persisted snapshot evidence.")

    identity = dict(readiness.get("identity") or {})
    seller = dict(identity.get("seller") or {})
    buyer = dict(identity.get("buyer") or {})
    if not identity.get("ready"):
        _raise_readiness(list(identity.get("errors") or []))

    lines = list(snapshot.get("lines") or [])
    if not lines:
        frappe.throw("FBR V2 immutable snapshot contains no invoice lines.")

    items = [_line_item_payload(line) for line in lines]
    payload_total = _money(sum(flt(row.get("totalValues")) for row in items))
    erpnext_grand_total = _money(snapshot.get("grand_total"))
    difference = _money(payload_total - erpnext_grand_total)
    if abs(difference) > MONEY_TOLERANCE:
        frappe.throw(
            "FBR V2 payload totalValues do not reconcile to immutable ERPNext grand total: "
            f"payload {payload_total}, ERPNext {erpnext_grand_total}."
        )

    payload = {
        "invoiceType": "Sale Invoice",
        "invoiceDate": getdate(snapshot.get("posting_date") or doc.get("posting_date")).strftime(
            "%Y-%m-%d"
        ),
        "sellerNTNCNIC": _identifier(seller.get("ntn_cnic")),
        "sellerBusinessName": _text(seller.get("business_name")),
        "sellerProvince": _text(seller.get("province")),
        "sellerAddress": _text(seller.get("address")),
        "buyerNTNCNIC": _identifier(buyer.get("ntn_cnic")),
        "buyerBusinessName": _text(buyer.get("business_name")),
        "buyerProvince": _text(buyer.get("province")),
        "buyerAddress": _text(buyer.get("address")),
        "buyerRegistrationType": _text(buyer.get("registration_type")),
        "invoiceRefNo": "",
        "items": items,
    }

    explicit_scenario = _text(scenario_id)
    if explicit_scenario:
        profile = dict(readiness.get("profile") or {})
        if profile.get("mode") != "Sandbox":
            frappe.throw("scenarioId may only be supplied in explicit Sandbox context.")
        payload["scenarioId"] = explicit_scenario

    return {
        "payload": payload,
        "source": {
            "doctype": doc.doctype,
            "name": doc.name,
            "company": doc.company,
            "authority": "ERPNext Native",
            "snapshot_version": snapshot.get("snapshot_version"),
            "snapshot_hash": snapshot.get("snapshot_hash") or "",
        },
        "reconciliation": {
            "payload_total_values": payload_total,
            "erpnext_grand_total": erpnext_grand_total,
            "difference": difference,
            "passed": True,
            "sales_tax_withheld_non_posting": True,
        },
        "scenario_context": {
            "source": "explicit_certification_context" if explicit_scenario else "none",
            "scenario_id": explicit_scenario,
        },
        "readiness": {
            "payload_input_ready": True,
            "warnings": list(readiness.get("warnings") or []),
        },
        "database_write": False,
        "fbr_network_call": False,
        "contains_secrets": False,
    }
