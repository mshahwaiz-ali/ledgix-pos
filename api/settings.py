# ============================================================
# LEDGIX COMPATIBILITY SETTINGS HELPERS
# ============================================================
# V2 has one inventory-authoritative transaction model and one branding source.
# These functions keep older public API paths importable without re-introducing
# the retired Billing Only / POS Theme settings into current product behavior.

import frappe
from frappe.utils import cint

from ledgix_saas.api.security import (
    require_ledgix_admin_or_system_manager,
    require_ledgix_cashier_or_above,
)


def get_stock_control_mode():
    """Compatibility value for older callers.

    New V2 sales always post through the authoritative stock service. The old
    site-wide Billing Only switch is retired because it made purchases stock-aware
    while allowing sales to bypass inventory.
    """
    return "Strict Inventory"


@frappe.whitelist()
def get_pos_theme_settings():
    """Compatibility read backed by the single Ledgix Brand Settings source."""
    require_ledgix_cashier_or_above()
    primary = ""
    if frappe.db.exists("DocType", "Ledgix Brand Settings"):
        primary = frappe.db.get_single_value("Ledgix Brand Settings", "primary_brand_color") or ""
    return normalize_theme_settings({
        "enable_custom_accent": 1 if primary else 0,
        "primary_accent_color": primary,
    })


@frappe.whitelist()
def save_pos_theme_settings(*args, **kwargs):
    """Retained method path with an explicit migration message for old clients."""
    require_ledgix_admin_or_system_manager()
    frappe.throw(
        "POS Theme Settings were retired in Ledgix V2. Configure the site brand color in Ledgix Brand Settings."
    )


def normalize_theme_settings(settings):
    source = settings or {}
    primary = normalize_hex(source.get("primary_accent_color"))
    enabled = 1 if cint(source.get("enable_custom_accent")) and primary else 0

    if not enabled:
        return {
            "enable_custom_accent": 0,
            "primary_accent_color": "",
            "accent_hover": "",
            "accent_soft": "",
            "accent_soft_2": "",
            "accent_border": "",
            "accent_ring": "",
            "accent_rgb": "",
            "accent_soft_hover": "",
            "accent_border_strong": "",
            "accent_track_bg": "",
            "accent_track_border": "",
        }

    generated = build_theme_shades(primary)
    return {
        "enable_custom_accent": enabled,
        "primary_accent_color": primary,
        "accent_hover": generated["accent_hover"],
        "accent_soft": generated["accent_soft"],
        "accent_soft_2": generated["accent_soft_2"],
        "accent_border": generated["accent_border"],
        "accent_ring": generated["accent_ring"],
        "accent_rgb": rgb_string(primary),
        "accent_soft_hover": generated["accent_soft_hover"],
        "accent_border_strong": generated["accent_border_strong"],
        "accent_track_bg": generated["accent_track_bg"],
        "accent_track_border": generated["accent_track_border"],
    }


def normalize_hex(value):
    text = str(value or "").strip()
    if (
        len(text) == 7
        and text.startswith("#")
        and all(char in "0123456789abcdefABCDEF" for char in text[1:])
    ):
        return text.lower()
    if len(text) == 6 and all(char in "0123456789abcdefABCDEF" for char in text):
        return f"#{text.lower()}"
    if (
        len(text) == 4
        and text.startswith("#")
        and all(char in "0123456789abcdefABCDEF" for char in text[1:])
    ):
        return "#" + "".join(char * 2 for char in text[1:]).lower()
    return ""


def hex_to_rgb(hex_color):
    color = normalize_hex(hex_color)
    if not color:
        return None
    return (
        int(color[1:3], 16),
        int(color[3:5], 16),
        int(color[5:7], 16),
    )


def rgb_string(hex_color):
    rgb = hex_to_rgb(hex_color)
    if not rgb:
        return ""
    r, g, b = rgb
    return f"{r}, {g}, {b}"


def mix_hex(hex_color, target, percent_target):
    rgb = hex_to_rgb(hex_color)
    if not rgb:
        return ""
    r, g, b = rgb
    tr, tg, tb = (0, 0, 0) if target == "black" else (255, 255, 255)
    p = max(0, min(100, percent_target)) / 100
    return "#{:02x}{:02x}{:02x}".format(
        round(r * (1 - p) + tr * p),
        round(g * (1 - p) + tg * p),
        round(b * (1 - p) + tb * p),
    )


def build_theme_shades(primary):
    rgb = hex_to_rgb(primary)
    if not rgb:
        return {}
    r, g, b = rgb
    return {
        "accent_hover": mix_hex(primary, "black", 18),
        "accent_soft": f"rgba({r}, {g}, {b}, 0.10)",
        "accent_soft_2": f"rgba({r}, {g}, {b}, 0.16)",
        "accent_border": f"rgba({r}, {g}, {b}, 0.28)",
        "accent_ring": f"rgba({r}, {g}, {b}, 0.18)",
        "accent_soft_hover": f"rgba({r}, {g}, {b}, 0.14)",
        "accent_border_strong": f"rgba({r}, {g}, {b}, 0.42)",
        "accent_track_bg": f"rgba({r}, {g}, {b}, 0.12)",
        "accent_track_border": f"rgba({r}, {g}, {b}, 0.30)",
    }


def is_strict_inventory_mode():
    return True


def sale_matches_current_stock_mode(sale_name):
    """Compatibility guard for historical return/search APIs.

    Historical Billing Only sales may legitimately have no stock movement. They
    remain readable/returnable; the Sales Return controller decides stock impact
    from the original sale's actual posted movements.
    """
    if not sale_name:
        return False
    return bool(frappe.db.exists("Ledgix Sale", {"name": sale_name, "docstatus": 1}))
