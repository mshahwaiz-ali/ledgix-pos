# Phase 12 Legacy Business Test Retirement

The legacy Ledgix business ledgers are frozen historical audit data after the ERPNext cutover.

The executable pre-cutover business-engine tests were preserved in Git at:

- Commit: `808f384311b0545e1d3e39791f085db5678832bb`
- Repository paths: the same paths used by the import-safe retirement stubs.

## Policy

- Do not unfreeze legacy business ledgers to run historical tests.
- Do not use `legacy_write_bypass` to make historical business tests pass.
- Current behavioral coverage belongs to ERPNext-native Phase 6-10 gates and FBR V2 gates.
- The historical test modules remain as import-safe skipped stubs so broad test discovery does not fail on stale imports.
- `test_ledgix_user_profile.py` remains active because most of that suite still validates current role/workspace behavior; only the two tests that create legacy Customers are skipped.
- `Ledgix FBR Settings` retirement tests remain active and are not part of the business-engine retirement set.

## Native Coverage

- Selling / receivables: Phase 6
- Buying / inventory / stock: Phase 7
- POS / holds / returns: Phase 8
- FBR source cutover: Phase 9
- Print / reporting: Phase 10
- Legacy freeze / audit-only state: Phase 12
- FBR V2 snapshot / payload / readiness: FBR V2 contract and runtime gates
