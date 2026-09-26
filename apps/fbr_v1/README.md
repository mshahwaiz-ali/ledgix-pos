# FBR V1

Bootstrap Frappe/ERPNext application for the FBR V1 / Tier-1 POS integration redesign.

## Identity

- Technical app name: `fbr_v1`
- Desk/module title: **FBR V1**
- Runtime base: Frappe 15 + ERPNext 15
- Starting point: the frozen `fbr_v12` extraction, copied only to accelerate redesign.

## Status

This is a **bootstrap clone**, not a claim that inherited V1.2 behavior is valid for FBR V1 / Tier-1 POS.

Internal modules that still use `v2` terminology are inherited scaffolding. Their endpoints, payload fields, token flow, POS registration rules, QR/printing behavior, offline behavior, returns and certification rules must be checked against authoritative FBR V1 / Tier-1 documentation before real use.

## Isolation

The Python/Frappe package is `fbr_v1`, separate from `fbr_v12`. Package imports and module ownership are renamed to `fbr_v1` / **FBR V1**.

Compatibility DocType and field identifiers inherited from V1.2 are intentionally left for the next design phase. Until that redesign is complete, do not install `fbr_v1` alongside `fbr_v12` on the same site.

## Documentation

- V1 / Tier-1 work: `docs/fbr/fbr_v1/`
- Frozen V1.2 reference docs: `docs/fbr/fbr_v12/`
