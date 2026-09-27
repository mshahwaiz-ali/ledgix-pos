"""Formatting normalization only; no undocumented NTN length constraint."""
import re


def normalize_tax_id(raw):
    value = re.sub(r"[\s-]", "", str(raw or ""))
    if str(raw or "").strip() and not value:
        raise ValueError("Tax ID contains formatting but no digits.")
    if value and (not value.isascii() or not value.isdigit()):
        raise ValueError("Tax ID must contain decimal digits with only spaces or hyphens as formatting.")
    return value, ("CNIC" if len(value) == 13 else "NTN") if value else ""
