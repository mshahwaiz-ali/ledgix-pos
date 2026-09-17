#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_DIR="${ROOT_DIR}/frappe-bench"
SITE="${1:-ledgix-erpnext.local}"
APP="ledgix_saas"

if [[ "${SITE}" != *.local ]]; then
  echo "Refusing retail operating-data preparation for non-local site: ${SITE}" >&2
  exit 2
fi

if [[ ! -d "${BENCH_DIR}" ]]; then
  echo "Bench directory not found: ${BENCH_DIR}" >&2
  exit 2
fi

SRC_APP="${ROOT_DIR}/apps/${APP}"
DEST_APP="${BENCH_DIR}/apps/${APP}"
TMP_APP="${BENCH_DIR}/apps/.${APP}.retail-data.$$"
BENCH_PYTHON="${BENCH_DIR}/env/bin/python"

if [[ ! -d "${SRC_APP}" || ! -x "${BENCH_PYTHON}" ]]; then
  echo "Ledgix source app or bench Python is missing." >&2
  exit 2
fi

echo "== Ledgix retail operating data: sync current app =="
rm -rf "${TMP_APP}"
cp -a "${SRC_APP}" "${TMP_APP}"
rm -rf "${DEST_APP}"
mv "${TMP_APP}" "${DEST_APP}"
"${BENCH_PYTHON}" -m pip install -e "${DEST_APP}"
if [[ -f "${ROOT_DIR}/deploy/repair_apps_txt.sh" ]]; then
  BENCH_DIR="${BENCH_DIR}" bash "${ROOT_DIR}/deploy/repair_apps_txt.sh"
fi

cd "${BENCH_DIR}"

echo "== Ledgix retail operating data: preflight =="
bench --site "${SITE}" list-apps

echo "== Ledgix retail operating data: safe backup =="
bench --site "${SITE}" backup --with-files

echo "== Ledgix retail operating data: pre-load inspection =="
bench --site "${SITE}" execute ledgix_saas.setup.demo_data.inspect_site

# Do not cancel/delete the current managed retail history on normal reruns.
# The seed is marker-idempotent and ERPNext POS closings create merge-log/audit
# links that should be preserved. A destructive reset, if ever required, must be
# an explicit separate maintenance operation.
echo "== Ledgix retail operating data: safely retire old Ledgix demo/spike masters =="
bench --site "${SITE}" execute ledgix_saas.setup.retail_cleanup_safe.cleanup_old_local_artifacts

echo "== Ledgix retail operating data: create/reuse ERPNext-authoritative operating history =="
bench --site "${SITE}" execute ledgix_saas.setup.retail_v15_compat.seed

echo "== Ledgix retail operating data: post-load old-artifact cleanup =="
bench --site "${SITE}" execute ledgix_saas.setup.retail_cleanup_safe.cleanup_old_local_artifacts

echo "== Ledgix retail operating data: verify =="
bench --site "${SITE}" execute ledgix_saas.setup.retail_v15_compat.verify

echo "== Ledgix retail operating data: complete =="
