# Federal Tier-1 POS / IMS V1 Sandbox to Production Activation

This page is a production index. The current operational authority is [`../fbr/fbr_v1/FBR_V1_SETUP_AND_ACTIVATION.md`](../fbr/fbr_v1/FBR_V1_SETUP_AND_ACTIVATION.md), followed by the [`FBR_V1_PRODUCTION_CHECKLIST.md`](../fbr/fbr_v1/FBR_V1_PRODUCTION_CHECKLIST.md).

Local software validation does not establish regulatory approval. Sandbox transport acceptance and external Production/go-live approval are separate evidence gates.

## Sequence

1. Complete ERPNext seller identity and native Company, Address, tax, item, payment, warehouse, and POS configuration.
2. Configure **Ledgix FBR Integration Profile**, current mappings, and **Ledgix FBR POS Device** with both network gates off.
3. Obtain real client/provider authority, POSID/software/onboarding, retention, and topology evidence.
4. Enter the Sandbox credential through the supported Frappe Password control.
5. Approve only the general runtime gate for a controlled real Sandbox exercise. Retain actual evidence and reconcile every ambiguous outcome.
6. Record documented QR acceptance after external testing; unsupported signature contracts remain unresolved.
7. Obtain a separate V1 Production credential and explicit external Production approval reference plus uploaded File evidence. A System Manager verifies that evidence through the profile; server-stamped verification user/time are required. Verify backup/release identity and clear all offline/reconciliation blockers.
8. During an approved window, have a System Manager enable the independent Production gate and `production_post_armed`; manually observe the first Production fiscalization.

Do not use `scripts/archive/fbr_v12/configure_fbr_sandbox_local.sh`, `scripts/archive/fbr_v12/run_fbr_sandbox_exercise_local.sh`, `scripts/archive/fbr_v12/run_fbr_activation_readiness_gate.sh`, `scripts/archive/fbr_v12/run_fbr_activation_static_gate.sh`, or `scripts/archive/fbr_v12/run_fbr_client_certification_handoff_gate.sh` for current V1. They target the frozen `ledgix_saas` Digital Invoicing V1.2 workflow.

Do not invent a replacement network script, copy V1.2 validate/post/reference behavior, expose tokens, or claim Sandbox/Production acceptance without real external evidence.

The deprecated `sandbox_certification_complete` compatibility alias means transport acceptance only. Current release logic uses the canonical acceptance field and never consumes that alias or infers external approval. Production configuration readiness excludes posting arm and cutovers; strict release requires each independently.
