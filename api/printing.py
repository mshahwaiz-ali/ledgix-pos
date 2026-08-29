from __future__ import annotations

from base64 import b64encode
from io import BytesIO


def get_fbr_qr_data_uri(fbr_invoice_number) -> str:
    """Return a self-contained SVG QR for the unique FBR invoice number.

    FBR electronic-invoicing rules require the receipt/invoice QR to be generated
    from the unique FBR invoice number. Frappe 15 already depends on PyQRCode, so
    print formats can stay offline/self-contained without an external QR service.
    """
    value = str(fbr_invoice_number or "").strip()
    if not value:
        return ""

    from pyqrcode import create as qrcreate

    qr = qrcreate(value, error="L", version=2)
    stream = BytesIO()
    try:
        qr.svg(stream, scale=4, background="#ffffff", module_color="#000000")
        encoded = b64encode(stream.getvalue()).decode("ascii")
    finally:
        stream.close()

    return f"data:image/svg+xml;base64,{encoded}"
