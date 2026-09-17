"""Compatibility entrypoint for Ledgix local demo data.

The original pre-cutover seeder wrote legacy Ledgix Item/Sale/Purchase/Payment
DocTypes. Phase 12 froze those records as historical evidence, so all new demo
operations must use the ERPNext-authoritative V2 seed instead.
"""

from ledgix_saas.setup.erpnext_demo_data import (  # noqa: F401
    SEED,
    cleanup_seed_transactions,
    inspect_site,
    seed,
    verify,
)

__all__ = [
    "SEED",
    "inspect_site",
    "cleanup_seed_transactions",
    "seed",
    "verify",
]
