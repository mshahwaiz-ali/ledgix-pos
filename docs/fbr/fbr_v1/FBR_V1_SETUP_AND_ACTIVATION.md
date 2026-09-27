# Federal Tier-1 POS / IMS V1 Setup and Activation

This guide separates software configuration from inputs only the client, FBR, PRAL, or an authorized integrator can supply.

## Software setup

Install Frappe, ERPNext, `ledgix_saas`, and `fbr_v1`; do not install frozen `fbr_v12` as a second active integration. Verify ERPNext Company legal name, tax ID, registered Address/province, accounts, warehouses, POS Profile, customers, items, taxes, and Modes of Payment.

In **Ledgix FBR Integration Profile**, select the Company, keep protocol `Federal POS/IMS V1`, use Sandbox during testing, select provider type, record real authority and six-year retention-policy references/evidence, select a default device where appropriate, and enter credentials only through supported Desk/Frappe Password controls. Keep `production_post_armed` off. `Operator Confirmed` offline policy requires its own authority reference/evidence.

In **Ledgix FBR POS Device**, select the same Company/POS Profile, enter authoritative POSID and software registration number, select the explicit environment and `Cloud API` or `Local IMS - Server Reachable`, and record Production onboarding evidence. Local IMS Production also requires package/version/installation evidence. Mark QR/signature verified only after external testing of the actual authorized component.

Configure Mode of Payment codes, Tax Component mappings to native ERPNext tax accounts, and reviewed Item/PCT mappings. Unsupported components and unreviewed mappings remain blockers.

## External inputs

The client/provider supplies registration/authority evidence, POSID/software/onboarding proof, applicable IMS package proof, Sandbox token and acceptance, QR/signature verification, Production token and activation approval/evidence, and any offline authority. Tokens belong in supported Password controls, never Git, commands, screenshots, or documents.

Operators must not invent endpoint URLs. Endpoints are software-owned constants. Digital Invoicing V1.2 endpoints, `scenarioId`, reference sync, and validation/post workflows are not current V1 setup.

## Runtime gates

Both site-config gates default off:

```json
{
  "fbr_v1_network_cutover_active": 0,
  "fbr_v1_production_cutover_active": 0
}
```

The general gate is required for real traffic. Production additionally requires its separate gate; general cutover alone never authorizes Production. Change these only through an approved deployment process. Keep both off during installation, migration, mapping, and review. Do not enable Production or arm it before approval, verified backup/release identity, complete evidence, and zero unresolved reconciliation.

## Acceptance sequence

1. Complete ERPNext and V1 setup with both gates off.
2. Confirm invoice readiness from a submitted native invoice and immutable snapshot.
3. Securely enter the real Sandbox token and approve general cutover for controlled Sandbox traffic.
4. Retain real outcomes and reconcile every ambiguity.
5. Obtain Production credential, authority, activation, device, QR/signature, retention, backup, and release evidence.
6. Complete the [Production checklist](FBR_V1_PRODUCTION_CHECKLIST.md).
7. In the approved window, enable Production cutover and arm Production deliberately.
8. Manually observe the first Production fiscalization and retain its evidence.

Software implementation is verified locally; real Sandbox acceptance and Production activation remain external/pending.
