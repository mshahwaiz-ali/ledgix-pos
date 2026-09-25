# Ledgix POS — Users, Roles and Navigation

**Audience:** Client administrators and managers

## 1. Purpose

This guide explains:

- which Ledgix role to assign;
- what each role normally sees;
- how Business Profile changes navigation;
- why visible screens and actual permission are different.

Use named users for real staff.

Do not use the Administrator account as the normal daily business login.

---

## 2. Main Ledgix roles

Current Ledgix roles:

- Ledgix Cashier;
- Ledgix Manager;
- Ledgix Admin.

ERPNext/Frappe also has:

- System Manager.

---

## 3. Ledgix Cashier

Best for:

- counter staff;
- retail checkout staff.

Typical access includes:

- Ledgix POS;
- sales/customer/item information required by the product;
- POS Invoice-related operation allowed by the actual ERPNext permission setup.

When POS is enabled, Cashier normally lands directly on:

    Ledgix POS

Cashier should not be used for:

- FBR administration;
- system configuration;
- purchasing administration;
- high-level accounting setup.

---

## 4. Ledgix Manager

Best for:

- branch/store manager;
- operations manager;
- inventory supervisor;
- finance/operations reviewer.

Typical Ledgix navigation can include, when enabled by the Business Profile:

- Ledgix Workspace;
- POS;
- Sales Invoices;
- POS Invoices;
- Customers;
- POS Openings/Closings;
- Items / pricing;
- purchasing;
- Inventory Intelligence;
- Warehouses;
- advanced stock screens;
- Ledgix reports;
- ERPNext accounting reports;
- Tax & FBR Center;
- FBR Submission Logs in read/operational scope.

Manager access depends on actual server permissions.

---

## 5. Ledgix Admin

Best for:

- client application administrator;
- senior finance/operations administrator;
- implementation owner.

Typical capabilities include:

- everything relevant to Manager;
- Setup Wizard;
- Business Profile;
- Brand Settings;
- User Profiles;
- FBR Integration Profile configuration;
- higher-level FBR operational actions.

Ledgix Admin is not the same as unrestricted system superuser.

Safety controls still apply.

For example, a Ledgix Admin cannot legitimately bypass:

- FBR Sandbox certification;
- Production arming/cutover requirements;
- Reconciliation Required;
- native ERPNext accounting/stock rules.

---

## 6. System Manager

System Manager is the Frappe/ERPNext platform administration role.

Use it for:

- full ERPNext configuration;
- system-level administration;
- technical setup when required.

Do not give System Manager to every business user.

Least privilege is safer and easier to audit.

---

## 7. Named operational users

Before handover, Ledgix readiness expects:

- at least one enabled named user with an operational Ledgix role.

Administrator and Guest do not count as the client's named operating user.

For POS-enabled clients, the system also expects/warns for a named Ledgix Cashier.

---

## 8. Suggested role assignment

### Small shop

Owner/administrator:

- Ledgix Admin.

Store manager:

- Ledgix Manager.

Counter operators:

- Ledgix Cashier.

### Larger retail

Application owner:

- Ledgix Admin.

Branch/stock supervisors:

- Ledgix Manager.

Cashiers:

- Ledgix Cashier.

Accountants may also require standard ERPNext accounting roles based on duties.

### B2B business

Application owner:

- Ledgix Admin.

Sales/operations supervisor:

- Ledgix Manager.

Sales/accounting users should receive the appropriate native ERPNext roles/permissions for the records they maintain.

---

## 9. Business Profile affects navigation

Ledgix Business Profile controls which product areas are shown.

For example:

- Invoice + FBR Only hides POS/inventory/buying product areas;
- Small Retail shows POS, normal inventory and buying;
- Full Retail also shows advanced stock controls;
- B2B focuses on invoice/customer/account workflows;
- Mixed shows both retail and B2B capabilities.

This makes the workspace easier to use.

---

## 10. Business Profile is not security

Important:

> Hiding a feature does not remove the need for actual server permission.

And:

> Showing a feature does not automatically give the user permission to use it.

Security comes from ERPNext/Frappe roles and permissions plus server-side Ledgix checks.

---

## 11. Ledgix Workspace

For Manager/Admin users, the Ledgix Workspace can show cards such as:

- Sales & POS;
- Catalog & Pricing;
- Purchasing;
- Inventory;
- Reports & Accounting;
- Tax & FBR;
- Administration.

The exact links depend on:

- user role;
- selected Business Profile.

---

## 12. Cashier landing

If the user is a Ledgix Cashier and POS is enabled, Ledgix routes the user toward:

    Ledgix POS

This keeps cashier navigation focused.

If POS is not part of the selected profile, the user should not be routed into a POS workflow that the client does not use.

---

## 13. Sales/POS navigation

Depending on profile and role, users may see:

- Ledgix POS;
- Sales Invoices;
- POS Invoices;
- Customers;
- Payment Entries;
- POS Openings;
- POS Closings.

Managers/Admins see more back-office links than Cashiers.

---

## 14. Catalog & Pricing navigation

Manager/Admin/System-level product navigation can include:

- Items;
- Item Groups;
- Price Lists;
- Item Prices;
- Pricing Rules.

Cashiers normally consume the configured catalog/pricing through POS rather than maintaining it.

---

## 15. Purchasing navigation

When buying is enabled, Manager/Admin/System users can see:

- Purchase Orders;
- Purchase Receipts;
- Purchase Invoices;
- Suppliers.

Cashier is not the intended purchasing administrator.

---

## 16. Inventory navigation

When inventory is enabled, Manager/Admin/System users can see:

- Inventory Intelligence;
- Warehouses.

When advanced inventory is enabled, they can additionally see:

- Stock Entries;
- Stock Reconciliation;
- Batches;
- Serial Numbers.

---

## 17. Reports & Accounting

Manager/Admin/System users can access relevant reports when the profile enables them, such as:

- Sales Report;
- Sales Return Report;
- Purchase Report;
- Customer Statement;
- Stock Balance;
- Stock Ledger;
- Accounts Receivable;
- General Ledger;
- Profit and Loss Statement.

Actual ERPNext permissions still apply.

---

## 18. Tax & FBR navigation

When FBR is enabled, Manager/Admin/System users can see the Tax & FBR area.

Typical current links include:

- Tax & FBR Center;
- FBR Integration Profiles;
- FBR Submission Logs;
- related FBR classification/reference evidence.

Configuration actions are more restricted than viewing.

---

## 19. Administration navigation

Ledgix Admin/System Manager can access administration items such as:

- Setup Wizard;
- Business Profile;
- Brand Settings;
- User Profiles.

Managers are not the intended primary application-configuration owners.

---

## 20. Creating a user

Use the normal ERPNext/Frappe User screen.

For a business user:

1. create User with correct email/name;
2. enable user;
3. assign appropriate Ledgix role;
4. assign any required standard ERPNext roles;
5. apply Company/User Permissions where required;
6. test login;
7. test only the real duties for that user.

---

## 21. Do not over-assign roles

Avoid assigning:

- Ledgix Cashier;
- Ledgix Manager;
- Ledgix Admin;
- System Manager

all to every user.

Choose the minimum role required.

Over-permission makes mistakes and unauthorized configuration changes more likely.

---

## 22. Company restrictions

For sites using multiple ERPNext Companies, use appropriate ERPNext User Permissions/roles.

A user who operates Company A should not automatically manage Company B.

This is especially important for:

- accounts;
- warehouses;
- FBR configuration;
- invoices;
- payment records.

---

## 23. Password/account policy

Recommended:

- unique user per employee;
- strong password;
- no shared administrator account;
- disable user when employee leaves;
- review permissions periodically.

Do not send credentials in public chat/tickets/screenshots.

---

## 24. FBR role boundary

FBR has additional safety restrictions.

Typical view/manager actions may be available to:

- Ledgix Manager;
- Ledgix Admin;
- System Manager.

Sensitive actions such as controlled FBR submit/reconciliation/offline operations are restricted to:

- Ledgix Admin;
- System Manager

under current server rules.

Even these roles cannot bypass compliance readiness.

---

## 25. Submission Logs

FBR Submission Logs are compliance evidence.

Users should treat them as audit records.

Do not manually edit them to make an invoice appear successful.

If a log/status is wrong, escalate for technical investigation.

---

## 26. Historical Ledgix records

Migrated sites can contain old historical Ledgix business records.

These may appear read-only.

That is intentional.

Staff should create/correct current business activity in ERPNext/Ledgix current workflows, not old historical ledgers.

---

## 27. Troubleshooting access

If a user cannot see something:

1. confirm selected Business Profile enables the feature;
2. confirm user's Ledgix role;
3. confirm standard ERPNext role/permission;
4. confirm Company/User Permission restrictions;
5. refresh/clear cache after an approved permission change if required.

Do not immediately give System Manager.

---

## 28. Role checklist before handover

- [ ] named Ledgix Admin exists
- [ ] named Manager exists where needed
- [ ] POS clients have named Cashier(s)
- [ ] each user has only required Ledgix role
- [ ] required ERPNext roles assigned
- [ ] Company/User Permissions tested
- [ ] each user can log in
- [ ] cashier lands on intended POS screen
- [ ] manager sees intended reports/workflows
- [ ] admin sees setup screens
- [ ] unauthorized screens/actions are not available

---

## 29. Summary

> **Use Cashier for counter operations, Manager for operational supervision, Admin for Ledgix configuration, and System Manager only for true system administration; Business Profile controls navigation, while ERPNext/Frappe permissions remain the actual security authority.**
