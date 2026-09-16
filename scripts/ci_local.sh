#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

printf '[INFO] Running local CI checks from %s\n' "$REPO_ROOT"
bash "$SCRIPT_DIR/validate_repo.sh"
bash "$SCRIPT_DIR/validate_doctype_names.sh"
bash "$SCRIPT_DIR/validate_erpnext_dependency.sh"
bash "$SCRIPT_DIR/check_secrets.sh"
printf '[OK] local CI checks passed\n'