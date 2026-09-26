# FBR V1 / Tier-1 POS

This folder is the authority workspace for the `fbr_v1` redesign.

The app is bootstrapped from the frozen V1.2 implementation only to reuse safe Frappe/ERPNext structure. No inherited V1.2 endpoint, payload, token flow, POS registration rule, QR format, offline behavior, return behavior, reporting behavior, or certification rule is considered valid for V1 until supported by the V1 / Tier-1 documentation.

## Next work

1. Inventory authoritative FBR V1 / Tier-1 source documents.
2. Extract the exact registration, authentication and endpoint contract.
3. Define invoice/return payload schemas and response/error handling.
4. Define POS identity, QR/printing and offline rules.
5. Map requirements to ERPNext-native accounting without modifying ERPNext core.
6. Replace inherited V1.2 runtime pieces incrementally with tests and no-network gates.
