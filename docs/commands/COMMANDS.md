# Commands

## Local Development

```bash
./scripts/core/install.sh
./scripts/core/site_setup.sh
./scripts/core/start.sh --background
./scripts/core/start.sh --status
./scripts/core/start.sh --smoke --site ledgix-erpnext.local
./scripts/core/start.sh --stop
```

## Validation

```bash
./scripts/validation/validate_repo.sh
./scripts/validation/check_secrets.sh
./scripts/validation/ci_local.sh
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
./deploy/production_setup.sh --action status
./deploy/production_setup.sh --action backup
./deploy/production_setup.sh --action deploy-update
./deploy/smoke_test.sh --site ledgix-erpnext.local --offline
./deploy/smoke_test.sh --site ledgix-erpnext.local --online --url https://domain.example
```

Production uses Supervisor and Nginx. Do not use `bench start` for public/EC2 production.
