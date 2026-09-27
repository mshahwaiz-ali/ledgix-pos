# Commands

## Local Development

```bash
./install.sh
./site_setup.sh
./start.sh --background
./start.sh --status
./start.sh --smoke --site ledgix-erpnext.local
./start.sh --stop
```

## Validation

```bash
./scripts/validate_repo.sh
./scripts/check_secrets.sh
./scripts/ci_local.sh
```

## Site/App Checks

```bash
cd frappe-bench
bench --site ledgix-erpnext.local list-apps
bench --site ledgix-erpnext.local migrate
bench --site ledgix-erpnext.local execute ledgix_saas.validation.run_all
# Use docs/fbr/fbr_v1/README.md for current Federal V1 readiness and health actions.
```

## Production

```bash
./deploy/production_setup.sh
./deploy/status.sh
./deploy/backup.sh
./deploy/deploy_update.sh
./deploy/smoke_test.sh --site ledgix-erpnext.local --offline
./deploy/smoke_test.sh --site ledgix-erpnext.local --online --url https://domain.example
```

Production uses Supervisor and Nginx. Do not use `bench start` for public/EC2 production.
