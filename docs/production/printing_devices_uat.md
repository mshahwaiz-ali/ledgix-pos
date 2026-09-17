# Ledgix Printing, Devices and Profile UAT

This acceptance layer validates the real operator/browser/printer workflow after the machine-verifiable ERPNext/Ledgix setup is green.

## Authority

Active business documents remain ERPNext-native. Ledgix prints:

- **A4:** `Ledgix ERPNext Tax Invoice` on `Sales Invoice`;
- **thermal:** `Ledgix ERPNext POS Receipt` on `POS Invoice` when POS is enabled.

Legacy Ledgix Sale formats remain historical/audit surfaces only and are not active transaction authority.

Both native formats already expose persisted FBR reference/QR areas. Actual FBR reference/QR print proof is performed only after real Sandbox/Production evidence exists; missing client token does not block print/device tooling readiness.

## Manual UAT evidence

Physical hardware behavior cannot be truthfully auto-passed. `ledgix_saas.api.release_acceptance.record_manual_uat_evidence` records explicit human UAT under:

```text
private/ledgix-acceptance/manual-uat.json
```

The directory is owner-only and the evidence file is mode `0600`. Recording requires the exact phrase:

```text
RECORD LEDGIX MANUAL UAT
```

## Required baseline checks

All profiles:

- `sales_invoice_a4` — render/print the A4 Sales Invoice/Credit Note as applicable;
- `role_boundary` — verify the **role boundary** by confirming a lower-privilege user cannot access an admin-only operation.

POS-enabled profiles additionally require:

- `pos_thermal_receipt` — receipt is readable at the configured thermal width;
- `barcode_item_selection` — barcode/scanner or equivalent item-selection path works;
- `checkout_payment` — checkout and configured payment flow complete correctly;
- `pos_return` — native POS return path is usable;
- `pos_closing` — ERPNext POS Closing flow completes;
- `stock_effect` — expected ERPNext stock effect is visible;
- `cashier_device_login` — named cashier can sign in and use the intended workstation/browser.

Buying-enabled profiles additionally require:

- `purchase_receipt_valuation` — purchasing/receipt/valuation workflow is accepted;
- `stock_entry_reconciliation` — Stock Entry/Reconciliation workflow is accepted.

## Device notes

Record the actual browser/workstation, receipt printer model/paper width, barcode scanner mode, and any cash-drawer dependency in the evidence notes. Normal hardware differences must not create a client code fork.

A keyboard-wedge barcode scanner should be verified through the same item-selection field used by the normal POS flow. Printer output should be checked for clipping, margins, totals, tax detail, return labeling, and readable QR/reference areas where real FBR evidence exists.

## Separation from external FBR certification

Manual print/device UAT and FBR certification are separate evidence streams. With no FBR token available, complete the non-FBR print/device checks and retain FBR QR/reference certification as an external pending item. Never fabricate an official FBR number or QR code to close UAT.
