from __future__ import annotations

"""Stable imports for callers of the former pinned-v15 reporting shim.

The canonical service now owns native POS cost resolution. Importing this module
has no global mutation and cannot change another caller's reporting behavior.
"""

from ledgix_saas.services.erpnext_reporting import (
    inventory_intelligence,
    report_summary,
    sales_return_rows,
    sales_rows,
)
