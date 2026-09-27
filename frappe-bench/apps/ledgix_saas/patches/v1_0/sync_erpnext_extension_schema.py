from ledgix_saas.setup.erpnext_extensions import sync_all


def execute():
    """Install the idempotent ERPNext extension schema introduced in migration Phase 3."""

    sync_all()
