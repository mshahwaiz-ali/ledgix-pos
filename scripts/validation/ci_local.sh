#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

printf '[INFO] Running local CI checks from %s\n' "$REPO_ROOT"
bash "$REPO_ROOT/scripts/validation/validate_repo.sh"
bash "$REPO_ROOT/scripts/validation/validate_doctype_names.sh"
bash "$REPO_ROOT/scripts/validation/validate_erpnext_dependency.sh"
bash "$REPO_ROOT/scripts/validation/check_secrets.sh"
printf '[OK] local CI checks passed\n'