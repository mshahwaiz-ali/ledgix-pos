# Federal Tier-1 POS / IMS V1 Production Checklist

This checklist is not a claim of FBR certification. Every item requires client-specific evidence.

- [ ] Approved immutable release SHA includes `fbr_v1`.
- [ ] Company legal name, tax ID, registered Address, and province are verified.
- [ ] Production Integration Profile uses `Federal POS/IMS V1` and the correct provider.
- [ ] Authority, activation, and six-year retention references/evidence are complete.
- [ ] All used Item/PCT, Tax Component, and Mode of Payment mappings are reviewed against native ERPNext authority.
- [ ] Production POS Device has matching Company/POS Profile, valid POSID, software registration, supported topology, onboarding evidence, and Operational state.
- [ ] Local IMS package/version/installation evidence exists when applicable.
- [ ] Current QR encoding and fiscal-signature behavior were externally verified on the actual component, with references/attachments.
- [ ] Production credential is stored through a supported Password control; no legacy DI fallback exists.
- [ ] Real Sandbox acceptance exists for required flows; unresolved ambiguity is zero.
- [ ] Unsupported Debit/tax/currency/discount cases are absent or blocked.
- [ ] Verified backup, rollback evidence, and release identity are current.
- [ ] No `Offline Pending`, unresolved correction, or `Reconciliation Required` state exists.
- [ ] General cutover, Production cutover, and `production_post_armed` remain off until the approved window.
- [ ] Operators, support/rollback owners, and FBR/PRAL escalation contact are assigned.
- [ ] The three controls are enabled deliberately in the approved order.
- [ ] First Production fiscalization is observed; request/response hashes, FBR number, receipt/QR, and log evidence are retained.
- [ ] Any uncertain outcome stops further sending and enters reconciliation.

Software implementation is verified locally; real Sandbox acceptance and Production activation remain external/pending.
