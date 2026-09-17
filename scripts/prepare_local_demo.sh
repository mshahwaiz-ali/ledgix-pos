#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_DIR="${ROOT_DIR}/frappe-bench"
SITE="${1:-ledgix-erpnext.local}"

if [[ "${SITE}" != *.local ]]; then
  echo "Refusing demo preparation for non-local site: ${SITE}" >&2
  exit 2
fi

if [[ ! -d "${BENCH_DIR}" ]]; then
  echo "Bench directory not found: ${BENCH_DIR}" >&2
  exit 2
fi

cd "${BENCH_DIR}"

echo "== Ledgix local demo: preflight =="
bench --site "${SITE}" list-apps

echo "== Ledgix local demo: safe backup =="
bench --site "${SITE}" backup --with-files

echo "== Ledgix local demo: pre-seed inspection =="
bench --site "${SITE}" execute ledgix_saas.setup.demo_data.inspect_site

echo "== Ledgix local demo: clear only prior V2 seed transactions =="
bench --site "${SITE}" execute ledgix_saas.setup.demo_data.cleanup_seed_transactions

echo "== Ledgix local demo: seed ERPNext-authoritative data =="
bench --site "${SITE}" execute ledgix_saas.setup.demo_data.seed

echo "== Ledgix local demo: verify =="
bench --site "${SITE}" execute ledgix_saas.setup.demo_data.verify

echo "== Ledgix local demo: complete =="
