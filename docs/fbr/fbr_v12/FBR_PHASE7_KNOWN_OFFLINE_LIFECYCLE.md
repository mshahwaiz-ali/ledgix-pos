# FBR Phase 7 — Known Offline and Reconciliation Lifecycle

**Status:** COMPLETE LOCALLY

Known Offline and ambiguous Production POST are separate state machines.

- declaration requires operator confirmation and performs no network call;
- durable `Offline Pending` stores issued-at, due-at and reason;
- upload window is client/provider configured, never hardcoded;
- controlled upload starts only from Offline Pending;
- prior Production POST blocks Known Offline;
- ambiguous POST remains `Reconciliation Required`;
- no automatic uploader/retry scheduler;
- return/note Known Offline is blocked pending Sandbox proof.

The final handoff patch exposes queue/declaration/upload in Tax & FBR Center using the backend role guards and typed confirmations.
