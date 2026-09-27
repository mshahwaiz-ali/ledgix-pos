from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


def _is_ledgix_payment(doc) -> bool:
    return bool(
        (doc.get("custom_ledgix_payment_source") or "").strip()
        or (doc.get("custom_ledgix_client_payment_id") or "").strip()
    )


def validate_ledgix_payment_entry(doc, method=None) -> None:
    """Enforce migrated Ledgix payment policy on native ERPNext Payment Entry.

    The financial transaction remains ERPNext-native. This hook only enforces
    product policy metadata that ERPNext does not know about by default.
    """

    if not _is_ledgix_payment(doc):
        return

    mode = (doc.mode_of_payment or "").strip()
    if not mode or not frappe.db.exists("Mode of Payment", mode):
        frappe.throw(_("A valid Mode of Payment is required for Ledgix payments."))

    meta = frappe.get_meta("Mode of Payment")
    fields = [
        "custom_ledgix_requires_reference",
        "custom_ledgix_allow_change",
        "custom_ledgix_legacy_method_type",
    ]
    if meta.has_field("enabled"):
        fields.append("enabled")
    policy = frappe.db.get_value("Mode of Payment", mode, fields, as_dict=True) or {}

    if "enabled" in policy and not cint(policy.enabled):
        frappe.throw(_("Mode of Payment {0} is disabled.").format(mode))

    if cint(policy.get("custom_ledgix_requires_reference")) and not (
        doc.reference_no or ""
    ).strip():
        frappe.throw(_("Reference number is required for Mode of Payment {0}.").format(mode))

    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode, "company": doc.company},
        "default_account",
    )
    if not account:
        frappe.throw(
            _("Mode of Payment {0} has no default account for Company {1}.").format(
                mode, doc.company
            )
        )

    expected = doc.paid_to if doc.payment_type == "Receive" else doc.paid_from
    if expected and expected != account:
        frappe.throw(
            _(
                "Ledgix Payment Entry account {0} does not match the configured {1} account {2}."
            ).format(expected, mode, account)
        )
