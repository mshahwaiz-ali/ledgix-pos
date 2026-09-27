# FBR V1.2

Standalone Frappe/ERPNext application for the extracted FBR Digital Invoicing V1.2 runtime.

## App identity

- Technical app name: `fbr_v12`
- Desk title: **FBR V1.2**
- Runtime dependencies: **Frappe 15 + ERPNext 15**
- Python dependencies: `requests` and `PyQRCode`
- `ledgix_saas` is intentionally **not** a required app.

## Current extraction status

The FBR V1.2 runtime ownership cutover has been completed on the extraction branch for local validation:

- FBR DocTypes are owned by module **FBR V12** while their existing DocType names are preserved for data continuity.
- ERPNext FBR custom fields and the Third Schedule charge-type extension are owned by **FBR V12**.
- Sales Invoice and POS Invoice FBR hooks point to `fbr_v12.*`.
- FBR print formats, the **FBR V1.2** workspace and the `fbr-v12-center` Desk page are provided by this app.
- The extracted runtime contains no hard Python import dependency on `ledgix_saas`.
- Automatic FBR retransmission remains disabled; Production network cutover remains fail-closed.
- Local migration preserved existing FBR data and completed with the extracted app installed.

Standalone no-network runtime coverage verifies snapshot immutability, payload construction, transport policy and offline policy. A clean-site installation without `ledgix_saas` remains the final independence proof before the extraction PR is considered ready to merge.

## Compatibility

Existing fieldnames and DocType names that contain the `Ledgix` prefix are deliberately preserved during extraction to avoid destructive data/schema renames. They are compatibility identifiers, not runtime dependencies on `ledgix_saas`.

Production deployment is not part of this extraction branch validation and must remain a separate guarded step.
