# Ledgix Planning Index

## Active architecture plan

Use **`erpnext_core_migration_plan.md`** as the current master architecture and implementation plan.

It defines the active direction:

- Frappe v15 + ERPNext v15 + `ledgix_saas`
- ERPNext as the authoritative business engine
- Ledgix as the product, FBR/compliance, UX, intelligence and branding layer
- one business concept = one source of truth
- staged migration with reconciliation before legacy retirement

## Historical plan

`new_plan.md` is retained as historical design context only.

Its earlier **"No ERPNext dependency"** direction has been superseded by `erpnext_core_migration_plan.md` and must not be used as the implementation authority for new work.
