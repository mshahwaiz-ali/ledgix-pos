// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ledgix POS Theme Settings", {
    enable_custom_accent(frm) {
        if (frm.doc.enable_custom_accent) return;
        clear_theme_fields(frm);
    },

    before_save(frm) {
        if (frm.doc.enable_custom_accent) return;
        clear_theme_doc_fields(frm);
    },

    primary_accent_color(frm) {

        if (!frm.doc.auto_generate_theme_shades) return;
        if (!frm.doc.primary_accent_color) return;

        const shades = generate_accent_shades(frm.doc.primary_accent_color);

        frm.set_value("accent_hover", shades.hover);
        frm.set_value("accent_soft", shades.soft);
        frm.set_value("accent_soft_2", shades.soft_2);
        frm.set_value("accent_border", shades.border);
    },

    after_save(frm) {
        const theme = build_form_theme_settings(frm.doc);
        clear_theme_cache_if_disabled(theme);

        if (window.LedgixTheme?.apply) {
            window.LedgixTheme.apply(theme, { broadcast: true });
            return;
        }

        window.dispatchEvent(new CustomEvent("ledgix:theme-updated", {
            detail: { theme }
        }));
    },
});

function clear_theme_fields(frm) {
    ["primary_accent_color", "accent_hover", "accent_soft", "accent_soft_2", "accent_border"].forEach((fieldname) => {
        if (frm.doc[fieldname]) {
            frm.set_value(fieldname, "");
        }
    });
}

function clear_theme_doc_fields(frm) {
    ["primary_accent_color", "accent_hover", "accent_soft", "accent_soft_2", "accent_border"].forEach((fieldname) => {
        frm.doc[fieldname] = "";
    });
}

function clear_theme_cache_if_disabled(theme) {
    if (theme && theme.enable_custom_accent && theme.primary_accent_color) return;
    try {
        window.localStorage.removeItem("ledgix_theme_settings");
        window.localStorage.removeItem("ledgix_theme_primary_accent");
        window.localStorage.removeItem("ledgix_pos_theme");
    } catch (e) {}
}

function build_form_theme_settings(doc) {
    const primary = normalize_hex(doc.primary_accent_color);
    if (!doc.enable_custom_accent || !primary) {
        return {
            enable_custom_accent: 0,
            primary_accent_color: "",
            accent_hover: "",
            accent_soft: "",
            accent_soft_2: "",
            accent_border: "",
            accent_ring: "",
            accent_rgb: "",
            accent_soft_hover: "",
            accent_border_strong: "",
            accent_track_bg: "",
            accent_track_border: "",
        };
    }
    const shades = generate_accent_shades(primary);
    const rgb = hex_to_rgb(primary);
    const rgb_string = `${rgb.r}, ${rgb.g}, ${rgb.b}`;

    return {
        enable_custom_accent: 1,
        primary_accent_color: primary,
        accent_hover: doc.accent_hover || shades.hover,
        accent_soft: doc.accent_soft || shades.soft,
        accent_soft_2: doc.accent_soft_2 || shades.soft_2,
        accent_border: doc.accent_border || shades.border,
        accent_ring: `rgba(${rgb_string}, 0.18)`,
        accent_rgb: rgb_string,
        accent_soft_hover: `rgba(${rgb_string}, 0.14)`,
        accent_border_strong: `rgba(${rgb_string}, 0.42)`,
        accent_track_bg: `rgba(${rgb_string}, 0.12)`,
        accent_track_border: `rgba(${rgb_string}, 0.30)`,
    };
}

function generate_accent_shades(hex) {
    return {
        hover: darken_hex(hex, 10),
        soft: mix_hex(hex, "#ffffff", 90),
        soft_2: mix_hex(hex, "#ffffff", 84),
        border: mix_hex(hex, "#ffffff", 62),
    };
}

function normalize_hex(hex) {
    const value = String(hex || "").trim();
    if (/^#[0-9a-fA-F]{6}$/.test(value)) return value.toLowerCase();
    if (/^[0-9a-fA-F]{6}$/.test(value)) return `#${value.toLowerCase()}`;
    if (/^#[0-9a-fA-F]{3}$/.test(value)) {
        return `#${value.slice(1).split("").map((char) => char + char).join("")}`.toLowerCase();
    }
    return "";
}

function darken_hex(hex, percent) {

    const rgb = hex_to_rgb(hex);

    if (!rgb) return hex;

    const factor = (100 - percent) / 100;

    return rgb_to_hex({
        r: Math.round(rgb.r * factor),
        g: Math.round(rgb.g * factor),
        b: Math.round(rgb.b * factor),
    });
}

function mix_hex(hex_a, hex_b, percent_b) {

    const a = hex_to_rgb(hex_a);
    const b = hex_to_rgb(hex_b);

    if (!a || !b) return hex_a;

    const p = percent_b / 100;

    return rgb_to_hex({
        r: Math.round(a.r * (1 - p) + b.r * p),
        g: Math.round(a.g * (1 - p) + b.g * p),
        b: Math.round(a.b * (1 - p) + b.b * p),
    });
}

function hex_to_rgb(hex) {

    if (!hex) return null;

    hex = hex.replace("#", "").trim();

    if (hex.length === 3) {
        hex = hex.split("").map((c) => c + c).join("");
    }

    if (hex.length !== 6) return null;

    return {
        r: parseInt(hex.substring(0, 2), 16),
        g: parseInt(hex.substring(2, 4), 16),
        b: parseInt(hex.substring(4, 6), 16),
    };
}

function rgb_to_hex({ r, g, b }) {

    return (
        "#" +
        [r, g, b]
            .map((value) =>
                Math.max(0, Math.min(255, value))
                    .toString(16)
                    .padStart(2, "0")
            )
            .join("")
    );
}
