from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from ledgix_saas.services import erpnext_selling


def _parse(value):
    return frappe.parse_json(value) if isinstance(value, str) else value


def _require_manager() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}):
        frappe.throw(_("Manager or Admin access is required."), frappe.PermissionError)


def _require_admin() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin"}):
        frappe.throw(_("Admin access is required."), frappe.PermissionError)


def _allow_rate_override() -> bool:
    return bool(
        set(frappe.get_roles(frappe.session.user)).intersection(
            {"System Manager", "Ledgix Admin", "Ledgix Manager"}
        )
    )


def _invoice_items_from_cart(cart_items) -> list[dict]:
    rows = _parse(cart_items) or []
    result = []
    for row in rows:
        result.append(
            {
                "item": row.get("item") or row.get("item_code"),
                "qty": row.get("qty") or row.get("quantity"),
                "uom": row.get("uom"),
                "override_rate": row.get("override_rate"),
                "warehouse": row.get("warehouse"),
            }
        )
    return result


def _auto_allocations(customer: str, amount: float) -> list[dict]:
    credit = erpnext_selling.get_customer_receivables(customer)
    remaining = flt(amount)
    allocations = []
    for row in credit.get("invoices") or []:
        if remaining <= 0:
            break
        outstanding = flt(row.get("outstanding"))
        if outstanding <= 0:
            continue
        allocated = min(remaining, outstanding)
        allocations.append(
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": row["invoice"],
                "allocated_amount": allocated,
            }
        )
        remaining -= allocated
    return allocations


@frappe.whitelist()
def preview_b2b_invoice(
    customer,
    items=None,
    price_list=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    _require_manager()
    return erpnext_selling.preview_sales_invoice(
        customer=customer,
        items=_invoice_items_from_cart(items),
        selling_price_list=price_list,
        sale_channel="B2B",
        due_date=due_date,
        discount_type=discount_type,
        discount_value=discount_value,
        allow_rate_override=_allow_rate_override(),
        update_stock=False,
        checkout_source="Ledgix B2B Preview",
    )


@frappe.whitelist()
def create_b2b_invoice(
    customer,
    items=None,
    price_list=None,
    client_sale_id=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    _require_manager()
    invoice = erpnext_selling.create_sales_invoice(
        customer=customer,
        items=_invoice_items_from_cart(items),
        selling_price_list=price_list,
        sale_channel="B2B",
        client_sale_id=client_sale_id,
        due_date=due_date,
        discount_type=discount_type,
        discount_value=discount_value,
        allow_rate_override=_allow_rate_override(),
        update_stock=False,
        checkout_source="Ledgix B2B Checkout",
        submit=True,
    )
    return erpnext_selling.invoice_summary(invoice, include_items=True)


@frappe.whitelist()
def complete_b2b_sale(
    customer,
    cart_items=None,
    tenders=None,
    price_list=None,
    client_sale_id=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    """Compatibility boundary for the current Ledgix POS B2B checkout UI.

    The UI may still be the old Ledgix page until Phase 8, but this path writes
    only ERPNext Sales Invoice / Payment Entry financial documents.
    """

    _require_manager()
    invoice = erpnext_selling.create_sales_invoice(
        customer=customer,
        items=_invoice_items_from_cart(cart_items),
        selling_price_list=price_list,
        sale_channel="B2B",
        client_sale_id=client_sale_id,
        due_date=due_date,
        discount_type=discount_type,
        discount_value=discount_value,
        allow_rate_override=_allow_rate_override(),
        update_stock=False,
        checkout_source="Ledgix POS B2B Checkout",
        submit=True,
    )
    duplicate = bool(getattr(invoice.flags, "ledgix_duplicate_client_sale", False))

    payments = []
    if not duplicate:
        for index, tender in enumerate(_parse(tenders) or [], start=1):
            amount = flt(tender.get("amount"))
            method = tender.get("payment_method") or tender.get("mode_of_payment")
            if amount <= 0 or not method:
                continue
            allocation = min(amount, max(flt(invoice.outstanding_amount), 0))
            if allocation <= 0:
                break
            payment = erpnext_selling.post_customer_payment(
                customer=invoice.customer,
                mode_of_payment=method,
                amount=amount,
                allocations=[
                    {
                        "reference_name": invoice.name,
                        "allocated_amount": allocation,
                    }
                ],
                client_payment_id=(
                    f"{client_sale_id}:PAY:{index}" if client_sale_id else None
                ),
                reference_number=tender.get("reference_number") or tender.get("reference_no"),
                payment_source="Ledgix POS B2B Checkout",
            )
            payments.append(payment.name)
            invoice.reload()

    invoice.reload()
    result = erpnext_selling.invoice_summary(invoice, include_items=False)
    result.update(
        {
            "success": True,
            "sale": invoice.name,
            "invoice_number": invoice.name,
            "paid_amount": flt(invoice.grand_total - invoice.outstanding_amount, 2),
            "remaining_amount": max(flt(invoice.outstanding_amount, 2), 0),
            "change_amount": 0.0,
            "payment_status": (
                "Paid"
                if abs(flt(invoice.outstanding_amount)) <= 0.005
                else "Partial"
                if flt(invoice.outstanding_amount) < flt(invoice.grand_total) - 0.005
                else "Unpaid"
            ),
            "payments": payments,
            "print_mode": "A4",
            "duplicate": duplicate,
            "financial_authority": "ERPNext",
        }
    )
    return result


@frappe.whitelist()
def get_customer_credit(customer):
    _require_manager()
    return erpnext_selling.get_customer_receivables(customer)


@frappe.whitelist()
def get_customer_open_invoices(customer):
    _require_manager()
    return erpnext_selling.get_customer_receivables(customer)


@frappe.whitelist()
def post_customer_payment(
    customer,
    payment_method,
    amount,
    allocations=None,
    reference_number=None,
    client_payment_id=None,
):
    _require_manager()
    allocations = _parse(allocations) or _auto_allocations(customer, flt(amount))
    if not allocations:
        frappe.throw(_("No open ERPNext Sales Invoice is available for allocation."))
    payment = erpnext_selling.post_customer_payment(
        customer=customer,
        mode_of_payment=payment_method,
        amount=amount,
        allocations=allocations,
        reference_number=reference_number,
        client_payment_id=client_payment_id,
        payment_source="Ledgix B2B Customer Payment",
    )
    return {
        "payment": payment.name,
        "docstatus": payment.docstatus,
        "amount": flt(payment.paid_amount, 2),
        "allocated_amount": flt(payment.total_allocated_amount, 2),
        "unallocated_amount": flt(payment.unallocated_amount, 2),
        "credit": erpnext_selling.get_customer_receivables(customer),
        "authority": "ERPNext Payment Entry",
    }


@frappe.whitelist()
def cancel_customer_payment(payment, reason):
    _require_admin()
    doc = erpnext_selling.cancel_payment_entry(payment, reason)
    return {
        "payment": doc.name,
        "docstatus": doc.docstatus,
        "cancelled": doc.docstatus == 2,
        "customer": doc.party if doc.party_type == "Customer" else None,
        "reason": reason,
    }


@frappe.whitelist()
def create_credit_note(
    sales_invoice,
    return_items=None,
    reason=None,
    client_return_id=None,
):
    _require_manager()
    note = erpnext_selling.create_sales_return(
        sales_invoice=sales_invoice,
        return_items=_parse(return_items),
        reason=reason,
        client_return_id=client_return_id,
    )
    return erpnext_selling.invoice_summary(note, include_items=True)


@frappe.whitelist()
def refund_credit_note(
    credit_note,
    payment_method,
    amount=None,
    client_payment_id=None,
    reference_number=None,
):
    _require_manager()
    payment = erpnext_selling.refund_credit_note(
        credit_note=credit_note,
        mode_of_payment=payment_method,
        amount=amount,
        client_payment_id=client_payment_id,
        reference_number=reference_number,
    )
    return {
        "payment": payment.name,
        "docstatus": payment.docstatus,
        "payment_type": payment.payment_type,
        "paid_amount": flt(payment.paid_amount, 2),
        "unallocated_amount": flt(payment.unallocated_amount, 2),
    }


@frappe.whitelist()
def create_exchange(
    sales_invoice,
    return_items=None,
    replacement_items=None,
    reason=None,
    exchange_reference=None,
    client_return_id=None,
    client_sale_id=None,
    price_list=None,
):
    _require_manager()
    result = erpnext_selling.create_exchange(
        sales_invoice=sales_invoice,
        return_items=_parse(return_items),
        replacement_items=_invoice_items_from_cart(replacement_items),
        reason=reason,
        exchange_reference=exchange_reference,
        client_return_id=client_return_id,
        client_sale_id=client_sale_id,
        selling_price_list=price_list,
    )
    return {
        "exchange_reference": exchange_reference,
        "credit_note": erpnext_selling.invoice_summary(result["credit_note"], include_items=True),
        "replacement_invoice": erpnext_selling.invoice_summary(
            result["replacement_invoice"], include_items=True
        ),
        "authority": "ERPNext Sales Invoice / Credit Note",
    }
