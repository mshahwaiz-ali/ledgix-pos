# Federal Tier-1 POS / IMS V1 Production Checklist

This checklist is not a claim of FBR certification. Every item requires client-specific evidence.

- [ ] Approved immutable release SHA includes `fbr_v1`.
- [ ] Company legal name, tax ID, registered Address, and province are verified.
- [ ] Production Integration Profile uses `Federal POS/IMS V1` and the correct provider.
- [ ] All used Item/PCT, Tax Component, and Mode of Payment mappings are reviewed against native ERPNext authority.
- [ ] Production POS Device has matching Company/POS Profile, valid POSID, software registration, supported topology, and Operational state.
- [ ] Local IMS package/version/installation evidence exists when applicable.
- [ ] Receipt QR encodes the authoritative FBR invoice number at 7x7 mm; undocumented digital-signature behavior remains fail-closed.
- [ ] Production credential is stored through a supported Password control; no legacy DI fallback exists.
- [ ] Statutory Re.1 FBR POS Service Fee uses a dedicated ERPNext Liability account and native Actual charge; no undocumented V1 wire field is added.
- [ ] Real V1 Sandbox transport acceptance exists for required flows; unresolved ambiguity is zero.
- [ ] Separate external Production approval reference and readable File evidence are verified by System Manager with server-stamped user and time.
- [ ] Unsupported Debit/tax/currency/discount cases are absent or blocked.
- [ ] Verified backup, rollback evidence, and release identity are current.
- [ ] No `Offline Pending`, unresolved correction, or `Reconciliation Required` state exists.
- [ ] General cutover, Production cutover, and `production_post_armed` remain off until the approved window.
- [ ] Operators, support/rollback owners, and FBR/PRAL escalation contact are assigned.
- [ ] The cutovers are enabled deliberately in the approved order; only System Manager arms posting.
- [ ] First Production fiscalization is observed; request/response hashes, FBR number, receipt/QR, and log evidence are retained.
- [ ] Any uncertain outcome stops further sending and enters reconciliation.

Software implementation is verified locally; real Sandbox acceptance and Production activation remain external/pending.
