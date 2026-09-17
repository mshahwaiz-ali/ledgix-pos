# Ledgix Production Security

**Status:** CURRENT

## 1. Secret handling

Never commit or publish:

- FBR Sandbox/Production tokens;
- API keys;
- Administrator/user passwords;
- database credentials;
- private keys/certificates;
- `.env` or secret files;
- `site_config.json` or recovery copies containing encryption/database data;
- database/public/private backup archives;
- raw evidence files containing secrets.

Current local credentials are kept under:

```text
.secrets/sites/<site>.env
```

Current production provisioning stores owner-only per-site credentials outside the repository, defaulting to:

```text
~/.config/ledgix/sites/<site>.env
```

Older `secrets.md` / `deploy/production.secrets.md` files are not the current credential-storage contract. If an old production helper artifact exists, migrate/relocate it through the supported production workflow and remove unnecessary plaintext copies.

Run the repository secret scan before commits/releases:

```bash
bash scripts/check_secrets.sh
```

## 2. Production service boundary

- Use Nginx and Supervisor for live production.
- Never use `bench start` as the live process manager.
- Keep MariaDB and Redis on private/local interfaces.
- Restrict SSH through firewall/security-group policy.
- Use HTTPS before sensitive live integrations are activated.
- Keep OS, database and runtime packages patched under a controlled maintenance process.
- Use the repository's immutable-release deployment tools rather than ad-hoc code copies.

## 3. Tenant isolation

Ledgix uses one Frappe site/database per client.

Do not share between tenants:

- site databases;
- site config/secrets;
- FBR tokens;
- seller identities;
- backup sets;
- acceptance/release evidence that contains client-specific information.

A shared bench may use one application revision, but business data and credentials remain site-isolated.

## 4. Authorization

- Frappe/ERPNext permissions remain security authority.
- Business Profile feature visibility does not grant permission.
- Named operational users should be used for client activity; do not use `Administrator` as the normal cashier/manager identity.
- Production activation actions such as FBR arming must remain restricted to authorized administrative roles.
- Legacy frozen DocTypes must not be unfrozen to bypass current permissions/workflows.

## 5. ERPNext authority safety

Do not create parallel Ledgix financial/stock authorities.

Current business writes belong to ERPNext-native documents. Frozen historical Ledgix ledgers remain read-only audit/migration evidence.

This reduces reconciliation and privilege ambiguity across sales, payments and stock.

## 6. FBR safety

- Token values must never be printed in logs, smoke output, screenshots or tickets.
- Readiness checks should record token presence only.
- Real FBR traffic must use the guarded native ERPNext FBR path.
- Historical `Ledgix Sale` submission is retired.
- Production posting requires the explicit Production interlock.
- `scheduler_events = {}` is intentional for FBR retransmission safety.
- An ambiguous Production POST becomes `Reconciliation Required` and must be externally reconciled before retransmission.
- Never fabricate FBR invoice numbers, Sandbox success, official responses or certification evidence.

## 7. Backup security

Backup sets can contain client financial data, private files and encryption material.

- keep backup metadata/config inputs owner-only;
- keep protected off-host/off-server copies according to client policy;
- verify checksums before relying on a recovery point;
- do not place backup archives in Git or public object storage;
- restore with the matching application release family and correct encryption key handling.

See `docs/production/backup_restore_rollback.md`.

## 8. Production approval

A deployment is not approved solely because the application starts.

Use `docs/production/PRODUCTION_CHECKLIST.md` and `docs/production/final_release_gate.md` for the final security/operations acceptance boundary.
