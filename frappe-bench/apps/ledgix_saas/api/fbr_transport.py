"""Retired generic fiscal HTTP compatibility. Federal V1 owns transport."""
import re
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_fbr_action

def safe_error(exc: Exception) -> str:
    value = str(exc or "")
    value = re.sub(
        r"Bearer\s+[^\s,;]+",
        "Bearer [REDACTED]",
        value,
        flags=re.IGNORECASE,
    )
    if "Bearer " in value:
        value = value.split("Bearer ", 1)[0].rstrip()
    return value or "FBR request failed."

def requests_available():
    return False

def ensure_requests_available():
    return reject_legacy_fbr_action()

def get_json(*args, **kwargs):
    return reject_legacy_fbr_action()

def post_json(*args, **kwargs):
    return reject_legacy_fbr_action()
