#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" - "$REPO_ROOT" <<'PY'
import ast
import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

root = pathlib.Path(sys.argv[1])
app = root / "apps" / "ledgix_saas"
hooks_path = app / "hooks.py"
pyproject_path = app / "pyproject.toml"
install_path = root / "install.sh"
prod_wrapper_path = root / "deploy" / "production_setup.sh"
prod_helper_path = root / "deploy" / "ensure_erpnext.sh"
deploy_update_path = root / "deploy" / "deploy_update_safe.sh"


def fail(message: str) -> None:
    raise SystemExit(f"[ERROR] {message}")


def literal_assignment(path: pathlib.Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    return None


required_apps = literal_assignment(hooks_path, "required_apps")
if not isinstance(required_apps, (list, tuple)) or "erpnext" not in required_apps:
    fail('hooks.py must declare required_apps = ["erpnext"]')

with pyproject_path.open("rb") as handle:
    pyproject = tomllib.load(handle)

frappe_deps = pyproject.get("tool", {}).get("bench", {}).get("frappe-dependencies", {})
for dependency in ("frappe", "erpnext"):
    spec = frappe_deps.get(dependency)
    if not isinstance(spec, str):
        fail(f"pyproject.toml is missing {dependency} in tool.bench.frappe-dependencies")
    if ">=15" not in spec or "<16" not in spec:
        fail(f"{dependency} dependency must stay on the supported v15 range; found {spec!r}")

install_text = install_path.read_text(encoding="utf-8")
for token in ("ERPNEXT_BRANCH", "ERPNEXT_REPO", "ensure_erpnext_app", "validate_framework_alignment"):
    if token not in install_text:
        fail(f"install.sh is missing ERPNext dependency plumbing token: {token}")

if not prod_helper_path.is_file():
    fail("deploy/ensure_erpnext.sh is missing")

# Fresh production installation is allowed to provision the ERPNext dependency.
prod_wrapper_text = prod_wrapper_path.read_text(encoding="utf-8")
if "ensure_erpnext_bench" not in prod_wrapper_text or "ensure_erpnext.sh" not in prod_wrapper_text:
    fail("production_setup.sh is not wired to the ERPNext dependency helper for fresh installs")

# An existing-site Ledgix release is deliberately different: ERPNext/Frappe are
# immutable prerequisites. The updater must verify the exact installed stack and
# fail closed instead of silently installing, pulling, or upgrading framework apps.
deploy_update_text = deploy_update_path.read_text(encoding="utf-8")
for token in (
    "PINNED STACK CHECK",
    "list-apps",
    "LEDGIX_EXPECTED_FRAPPE_VERSION",
    "LEDGIX_EXPECTED_ERPNEXT_VERSION",
    "Frappe version mismatch",
    "ERPNext version mismatch",
    "ledgix_saas is not installed on the target site",
):
    if token not in deploy_update_text:
        fail(f"deploy_update_safe.sh is missing pinned-stack prerequisite check: {token}")

for forbidden in (
    "ensure_erpnext.sh",
    "bench get-app erpnext",
    "install-app erpnext",
):
    if forbidden in deploy_update_text:
        fail(
            "deploy_update_safe.sh must not install or mutate ERPNext during an existing-site Ledgix release; "
            f"found forbidden token: {forbidden}"
        )

print("[OK] ERPNext v15 dependency contract validated")
PY
