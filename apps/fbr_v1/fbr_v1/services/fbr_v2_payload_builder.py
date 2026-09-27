"""Retired DI/V2 entry points. Historical schema and records are preserved."""
import frappe


def retired(*args, **kwargs):
    frappe.throw("DI/V2 service is retired. Use Federal POS/IMS V1; historical data is not reinterpreted.")


_text = retired
_money = retired
_quantity = retired
_identifier = retired
_is_consolidated_pos_sales_invoice = retired
_raise_readiness = retired
_line_item_payload = retired
build_payload_candidate = retired
