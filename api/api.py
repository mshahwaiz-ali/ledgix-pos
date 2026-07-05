# ============================================================
# LEDGIX PUBLIC API WRAPPERS
# ============================================================

from ledgix_saas.api.settings import (
    get_stock_control_mode,
    get_pos_theme_settings,
    save_pos_theme_settings,
    is_strict_inventory_mode,
    sale_matches_current_stock_mode,
)

from ledgix_saas.api.dashboard import (
    normalize_date_range,
    get_sales_last_7_days,
    get_profit_last_7_days,
    get_sales_insight,
    get_profit_margin_insight,
)

from ledgix_saas.api.shifts import (
    get_active_shift_info,
    open_pos_shift,
    close_pos_shift,
)

from ledgix_saas.api.pos import (
    get_item_by_barcode_or_sku,
    get_pos_boot_data,
    search_pos_items,
    create_pos_sale,
    hold_pos_sale,
    get_held_pos_sales,
    resume_held_pos_sale,
    delete_held_pos_sale,
    get_pos_sale_for_return,
    create_pos_sales_return,
    get_recent_pos_sales,
    get_pos_sale_receipt_data,
)

from ledgix_saas.api.reports import (
    get_sales_report_data,
    get_purchase_report_data,
    get_return_report_data,
    get_stock_report_data,
    get_profit_report_data,
    get_customer_statement,
    get_supplier_statement,
    search_report_parties,
    get_reports_boot_data,
)

