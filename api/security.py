import frappe


LEDGIX_CASHIER_OR_ABOVE = (
    "System Manager",
    "Ledgix Admin",
    "Ledgix Manager",
    "Ledgix Cashier",
)

LEDGIX_MANAGER_OR_ABOVE = (
    "System Manager",
    "Ledgix Admin",
    "Ledgix Manager",
)

LEDGIX_ADMIN_OR_SYSTEM_MANAGER = (
    "System Manager",
    "Ledgix Admin",
)


def has_any_role(roles):
    if isinstance(roles, str):
        roles = (roles,)

    required_roles = {role for role in roles or () if role}
    if not required_roles:
        return False

    user_roles = set(frappe.get_roles(frappe.session.user))
    return bool(required_roles.intersection(user_roles))


def require_ledgix_cashier_or_above():
    if not has_any_role(LEDGIX_CASHIER_OR_ABOVE):
        frappe.throw("You do not have permission to use Ledgix POS operations.", frappe.PermissionError)


def require_ledgix_manager_or_above():
    if not has_any_role(LEDGIX_MANAGER_OR_ABOVE):
        frappe.throw("You do not have permission to access Ledgix manager data.", frappe.PermissionError)


def require_ledgix_admin_or_system_manager():
    if not has_any_role(LEDGIX_ADMIN_OR_SYSTEM_MANAGER):
        frappe.throw("You do not have permission to manage Ledgix settings.", frappe.PermissionError)
