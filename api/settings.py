# ============================================================
# LEDGIX SETTINGS HELPERS
# ============================================================
# Shared stock-mode and theme helpers used by POS and Reports.
# Keep these stable because multiple pages depend on them.

import frappe
from frappe.utils import flt, cint
from ledgix_saas.api.security import (
    require_ledgix_admin_or_system_manager,
    require_ledgix_cashier_or_above,
)

def get_stock_control_mode():
    if not frappe.db.exists("DocType", "Ledgix Mode Settings"):
        return "Strict Inventory"

    mode = frappe.db.get_single_value("Ledgix Mode Settings", "stock_control_mode")

    if mode not in ["Strict Inventory", "Billing Only"]:
        return "Strict Inventory"

    return mode


@frappe.whitelist()
def get_pos_theme_settings():
    require_ledgix_cashier_or_above()

    default_settings = normalize_theme_settings({})

    if not frappe.db.exists("DocType", "Ledgix POS Theme Settings"):
        return default_settings

    try:
        settings = frappe.get_single("Ledgix POS Theme Settings")
        return normalize_theme_settings({
            "enable_custom_accent": settings.enable_custom_accent,
            "primary_accent_color": settings.primary_accent_color,
            "accent_hover": settings.accent_hover,
            "accent_soft": settings.accent_soft,
            "accent_soft_2": settings.accent_soft_2,
            "accent_border": settings.accent_border,
        })

    except Exception:
        return default_settings


@frappe.whitelist()
def save_pos_theme_settings(
    primary_accent_color=None,
    enable_custom_accent=1,
    accent_hover=None,
    accent_soft=None,
    accent_soft_2=None,
    accent_border=None,
):
    require_ledgix_admin_or_system_manager()

    enabled = cint(enable_custom_accent)
    doc = frappe.get_single("Ledgix POS Theme Settings")

    if not enabled:
        doc.enable_custom_accent = 0
        doc.primary_accent_color = ""
        doc.accent_hover = ""
        doc.accent_soft = ""
        doc.accent_soft_2 = ""
        doc.accent_border = ""
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache(doctype="Ledgix POS Theme Settings")

        return {
            "success": True,
            "theme_settings": get_pos_theme_settings(),
        }

    primary = normalize_hex(primary_accent_color)
    if not primary:
        frappe.throw("Primary Accent Color is required")

    doc.enable_custom_accent = 1
    doc.primary_accent_color = primary

    generated = build_theme_shades(primary)
    use_generated = cint(getattr(doc, "auto_generate_theme_shades", 1))

    doc.accent_hover = generated["accent_hover"] if use_generated or not accent_hover else accent_hover
    doc.accent_soft = generated["accent_soft"] if use_generated or not accent_soft else accent_soft
    doc.accent_soft_2 = generated["accent_soft_2"] if use_generated or not accent_soft_2 else accent_soft_2
    doc.accent_border = generated["accent_border"] if use_generated or not accent_border else accent_border

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache(doctype="Ledgix POS Theme Settings")

    return {
        "success": True,
        "theme_settings": get_pos_theme_settings(),
    }


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
        "accent_hover": normalize_hex(source.get("accent_hover")) or generated["accent_hover"],
        "accent_soft": source.get("accent_soft") or generated["accent_soft"],
        "accent_soft_2": source.get("accent_soft_2") or generated["accent_soft_2"],
        "accent_border": source.get("accent_border") or generated["accent_border"],
        "accent_ring": source.get("accent_ring") or generated["accent_ring"],
        "accent_rgb": rgb_string(primary),
        "accent_soft_hover": source.get("accent_soft_hover") or generated["accent_soft_hover"],
        "accent_border_strong": source.get("accent_border_strong") or generated["accent_border_strong"],
        "accent_track_bg": source.get("accent_track_bg") or generated["accent_track_bg"],
        "accent_track_border": source.get("accent_track_border") or generated["accent_track_border"],
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
    return get_stock_control_mode() == "Strict Inventory"


def sale_matches_current_stock_mode(sale_name):
    """
    Detects whether a submitted sale belongs to the current POS stock mode.

    Inventory Mode:
        Sale must have submitted stock movement(s).

    Billing Only Mode:
        Sale must not have submitted stock movement(s).
    """

    if not sale_name:
        return False

    has_stock_movement = frappe.db.exists(
        "Ledgix Stock Movement",
        {
            "reference_doctype": "Ledgix Sale",
            "reference_name": sale_name,
            "docstatus": 1
        }
    )

    if is_strict_inventory_mode():
        return bool(has_stock_movement)

    return not bool(has_stock_movement)
