from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from fbr_v1.protocol.constants import HEADER_INVOICE_TYPES, ITEM_INVOICE_TYPES, PAYMENT_MODES


class ProtocolValidationError(ValueError):
    """Raised when data does not match the documented FBR V1 wire contract."""


def _text(value: Any, label: str, *, required: bool = False, max_length: int | None = None) -> str:
    text = "" if value is None else str(value).strip()
    if required and not text:
        raise ProtocolValidationError(f"{label} is required.")
    if max_length is not None and len(text) > max_length:
        raise ProtocolValidationError(f"{label} exceeds {max_length} characters.")
    return text


def _number(value: Any, label: str, *, non_negative: bool = True) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolValidationError(f"{label} must be numeric.") from exc
    if non_negative and number < 0:
        raise ProtocolValidationError(f"{label} cannot be negative.")
    return number


def _format_datetime(value: str | datetime) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return _text(value, "DateTime", required=True)


@dataclass(frozen=True)
class InvoiceItem:
    item_code: str
    item_name: str
    quantity: float
    pct_code: str
    tax_rate: float
    sale_value: float
    total_amount: float
    tax_charged: float
    discount: float = 0.0
    further_tax: float = 0.0
    invoice_type: int = 1
    ref_usin: str | None = None

    def __post_init__(self) -> None:
        _text(self.item_code, "ItemCode", required=True, max_length=50)
        _text(self.item_name, "ItemName", required=True, max_length=150)
        pct = _text(self.pct_code, "PCTCode", required=True)
        if len(pct) > 8:
            raise ProtocolValidationError("PCTCode exceeds the documented 8-character limit.")
        _number(self.quantity, "Quantity")
        _number(self.tax_rate, "TaxRate")
        _number(self.sale_value, "SaleValue")
        _number(self.total_amount, "TotalAmount")
        _number(self.tax_charged, "TaxCharged")
        _number(self.discount, "Discount")
        _number(self.further_tax, "FurtherTax")
        if int(self.invoice_type) not in ITEM_INVOICE_TYPES:
            allowed = ", ".join(str(value) for value in sorted(ITEM_INVOICE_TYPES))
            raise ProtocolValidationError(
                f"Unsupported item InvoiceType {self.invoice_type}; documented values: {allowed}."
            )
        if self.ref_usin is not None:
            _text(self.ref_usin, "RefUSIN", max_length=50)

    def to_payload(self) -> dict[str, Any]:
        return {
            "ItemCode": _text(self.item_code, "ItemCode", required=True, max_length=50),
            "ItemName": _text(self.item_name, "ItemName", required=True, max_length=150),
            "Quantity": _number(self.quantity, "Quantity"),
            "PCTCode": _text(self.pct_code, "PCTCode", required=True),
            "TaxRate": _number(self.tax_rate, "TaxRate"),
            "SaleValue": _number(self.sale_value, "SaleValue"),
            "TotalAmount": _number(self.total_amount, "TotalAmount"),
            "TaxCharged": _number(self.tax_charged, "TaxCharged"),
            "Discount": _number(self.discount, "Discount"),
            "FurtherTax": _number(self.further_tax, "FurtherTax"),
            "InvoiceType": int(self.invoice_type),
            "RefUSIN": _text(self.ref_usin, "RefUSIN", max_length=50) or None,
        }


@dataclass(frozen=True)
class Invoice:
    pos_id: int
    usin: str
    date_time: str | datetime
    total_bill_amount: float
    total_quantity: float
    total_sale_value: float
    total_tax_charged: float
    payment_mode: int
    items: tuple[InvoiceItem, ...] | list[InvoiceItem] = field(default_factory=tuple)
    invoice_number: str = ""
    buyer_ntn: str = ""
    buyer_cnic: str = ""
    buyer_name: str = ""
    buyer_phone_number: str = ""
    discount: float = 0.0
    further_tax: float = 0.0
    ref_usin: str | None = None
    invoice_type: int = 1

    def __post_init__(self) -> None:
        try:
            pos_id = int(self.pos_id)
        except (TypeError, ValueError) as exc:
            raise ProtocolValidationError("POSID must be an integer.") from exc
        if pos_id <= 0:
            raise ProtocolValidationError("POSID must be greater than zero.")

        _text(self.invoice_number, "InvoiceNumber", max_length=30)
        _text(self.usin, "USIN", required=True, max_length=50)
        _format_datetime(self.date_time)
        _text(self.buyer_name, "BuyerName", max_length=150)
        _text(self.buyer_ntn, "BuyerNTN")
        _text(self.buyer_cnic, "BuyerCNIC", max_length=13)
        _text(self.buyer_phone_number, "BuyerPhoneNumber", max_length=20)
        _number(self.total_bill_amount, "TotalBillAmount")
        _number(self.total_quantity, "TotalQuantity")
        _number(self.total_sale_value, "TotalSaleValue")
        _number(self.total_tax_charged, "TotalTaxCharged")
        _number(self.discount, "Discount")
        _number(self.further_tax, "FurtherTax")

        if int(self.payment_mode) not in PAYMENT_MODES:
            allowed = ", ".join(str(value) for value in sorted(PAYMENT_MODES))
            raise ProtocolValidationError(
                f"Unsupported PaymentMode {self.payment_mode}; documented values: {allowed}."
            )
        if int(self.invoice_type) not in HEADER_INVOICE_TYPES:
            allowed = ", ".join(str(value) for value in sorted(HEADER_INVOICE_TYPES))
            raise ProtocolValidationError(
                f"Unsupported InvoiceType {self.invoice_type}; documented values: {allowed}."
            )
        if self.ref_usin is not None:
            _text(self.ref_usin, "RefUSIN", max_length=50)
        if not self.items:
            raise ProtocolValidationError("Items must contain at least one invoice item.")
        for item in self.items:
            if not isinstance(item, InvoiceItem):
                raise ProtocolValidationError("Items must contain InvoiceItem values.")

    @classmethod
    def from_items(cls, *, items: Iterable[InvoiceItem], **values: Any) -> "Invoice":
        return cls(items=tuple(items), **values)

    def to_payload(self) -> dict[str, Any]:
        """Serialize exact documented FBR POS/IMS field names.

        Monetary values are supplied by ERPNext. This class does not calculate tax.
        """
        return {
            "InvoiceNumber": _text(self.invoice_number, "InvoiceNumber", max_length=30),
            "POSID": int(self.pos_id),
            "USIN": _text(self.usin, "USIN", required=True, max_length=50),
            "DateTime": _format_datetime(self.date_time),
            "BuyerNTN": _text(self.buyer_ntn, "BuyerNTN"),
            "BuyerCNIC": _text(self.buyer_cnic, "BuyerCNIC", max_length=13),
            "BuyerName": _text(self.buyer_name, "BuyerName", max_length=150),
            "BuyerPhoneNumber": _text(self.buyer_phone_number, "BuyerPhoneNumber", max_length=20),
            "TotalBillAmount": _number(self.total_bill_amount, "TotalBillAmount"),
            "TotalQuantity": _number(self.total_quantity, "TotalQuantity"),
            "TotalSaleValue": _number(self.total_sale_value, "TotalSaleValue"),
            "TotalTaxCharged": _number(self.total_tax_charged, "TotalTaxCharged"),
            "Discount": _number(self.discount, "Discount"),
            "FurtherTax": _number(self.further_tax, "FurtherTax"),
            "PaymentMode": int(self.payment_mode),
            "RefUSIN": _text(self.ref_usin, "RefUSIN", max_length=50) or None,
            "InvoiceType": int(self.invoice_type),
            "Items": [item.to_payload() for item in self.items],
        }
