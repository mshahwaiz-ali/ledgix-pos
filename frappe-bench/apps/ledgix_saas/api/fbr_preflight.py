from __future__ import annotations

"""Compatibility wrapper for the retired legacy FBR preflight surface.

The authoritative readiness model is ERPNext-native FBR V2. This module is kept
only so historical callers receive the V2 readiness result rather than reviving
Ledgix FBR Settings or the old custom tax/FBR engine.
"""

import frappe

from ledgix_saas.api import fbr_v2_center


@frappe.whitelist()
def get_fbr_readiness():
    """Return V2 Tax & FBR Center readiness without any FBR network call."""

    return fbr_v2_center.get_fbr_readiness()
