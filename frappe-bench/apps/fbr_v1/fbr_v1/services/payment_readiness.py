"""Current POS/B2B tender coverage, read-only and without transport."""
import frappe
from frappe.utils import cint

PAYMENT_CODES = {"1 - Cash", "2 - Card", "3 - Gift Voucher", "4 - Loyalty Card", "6 - Cheque"}


def current_pos_profiles(company, devices=None):
    # Ledgix erpnext_pos.boot uses profile_for_user/payment_methods for both
    # Retail and B2B. Every enabled Company profile is selectable by its users.
    names = set(frappe.get_all("POS Profile", filters={"company": company, "disabled": 0},
        pluck="name", limit_page_length=0))
    if devices is None:
        devices = frappe.get_all("Ledgix FBR POS Device", filters={"company": company, "active": 1},
            fields=["name", "pos_profile"], limit_page_length=0)
    names.update(d.get("pos_profile") for d in devices if d.get("pos_profile"))
    profiles, blockers = [], []
    for name in sorted(names):
        profile = frappe.get_doc("POS Profile", name)
        if profile.get("company") != company or cint(profile.get("disabled")):
            blockers.append(f"POS Profile {name} must be enabled and belong to {company}.")
        else:
            profiles.append(profile)
    return profiles, blockers


def get_payment_readiness(company, devices=None):
    profiles, blockers = current_pos_profiles(company, devices)
    required, sources = set(), []
    for profile in profiles:
        modes = sorted({row.get("mode_of_payment") for row in profile.get("payments") or [] if row.get("mode_of_payment")})
        if not modes:
            blockers.append(f"POS Profile {profile.name} has no configured payment modes.")
        required.update(modes)
        sources.append({"pos_profile": profile.name, "paths": ["POS Invoice", "Ledgix B2B tender"], "modes": modes})
    if not profiles:
        blockers.append("Configure an active Company POS Profile for the current POS/B2B payment selection.")
    mapped = []
    for mode in sorted(required):
        row = frappe.db.get_value("Mode of Payment", mode,
            ["enabled", "custom_ledgix_fbr_v1_payment_mode"], as_dict=True)
        if row and cint(row.get("enabled")) and row.get("custom_ledgix_fbr_v1_payment_mode") in PAYMENT_CODES:
            mapped.append(mode)
    missing = sorted(required - set(mapped))
    blockers.extend(f"Mode of Payment {mode} requires an enabled, valid Federal V1 payment mapping." for mode in missing)
    return {"ready": not blockers, "required_modes": sorted(required), "mapped_modes": mapped,
            "missing_modes": missing, "required_count": len(required), "mapped_count": len(mapped),
            "sources": sources, "blockers": blockers, "database_write": False, "fbr_network_call": False}
