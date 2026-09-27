from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fbr_v1.protocol.constants import SUCCESS_CODE


@dataclass(frozen=True)
class FiscalResponse:
    success: bool
    code: str
    invoice_number: str
    response: str
    errors: Any
    raw: dict[str, Any]


def parse_fiscal_response(payload: Any) -> FiscalResponse:
    """Parse documented Federal/PRAL fiscal-component response variants."""
    if not isinstance(payload, dict):
        return FiscalResponse(
            success=False,
            code="",
            invoice_number="",
            response="Non-object response from fiscal service.",
            errors=None,
            raw={},
        )

    code = str(payload.get("Code") or "").strip()
    invoice_number = str(
        payload.get("FBRInvoiceNumber") or payload.get("InvoiceNumber") or ""
    ).strip()
    message = str(payload.get("Response") or "").strip()
    errors = payload.get("Errors")

    return FiscalResponse(
        success=(code == SUCCESS_CODE and bool(invoice_number)),
        code=code,
        invoice_number=invoice_number,
        response=message,
        errors=errors,
        raw=dict(payload),
    )
