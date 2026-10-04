#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BENCH_PY="$REPO_ROOT/frappe-bench/env/bin/python"

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
err() { printf '[ERROR] %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

section() {
  printf '\n'
  printf '==================================================\n'
  printf ' %s\n' "$*"
  printf '==================================================\n'
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

find_repo_files() {
  local pattern="$1"
  find "$REPO_ROOT" \
    \( -path "$REPO_ROOT/.git" \
    -o -path "$REPO_ROOT/.agents" \
    -o -path "$REPO_ROOT/.codex" \
    -o -path "$REPO_ROOT/frappe-bench" \
    -o -path "$REPO_ROOT/logs" \
    -o -path "$REPO_ROOT/logs/install" \
    -o -path "$REPO_ROOT/logs/deploy" \
    -o -path "$REPO_ROOT/backups" \
    -o -path "$REPO_ROOT/offline_bundle" \
    -o -path "$REPO_ROOT/node_modules" \
    -o -path "$REPO_ROOT/dist" \
    -o -path "$REPO_ROOT/build" \
    -o -path "*/build" \
    -o -path "*/dist" \
    \) -prune \
    -o -type f -name "$pattern" -print0
}

validate_shell() {
  section "Shell syntax"
  require_cmd bash
  local file count=0
  while IFS= read -r -d '' file; do
    info "bash -n ${file#$REPO_ROOT/}"
    bash -n "$file"
    count=$((count + 1))
  done < <(find_repo_files '*.sh')
  ok "validated $count shell file(s)"
}

validate_python() {
  section "Python syntax"
  require_cmd "$PYTHON_BIN"
  "$PYTHON_BIN" - "$REPO_ROOT" <<'PY'
import pathlib
import py_compile
import sys

root = pathlib.Path(sys.argv[1])
skip = {
    ".git",
    ".agents",
    ".codex",
    "frappe-bench",
    "logs",
    "logs/install",
    "backups",
    "offline_bundle",
    "node_modules",
    "build",
    "dist",
}
files = [
    path
    for path in root.rglob("*.py")
    if not any(part in skip for part in path.relative_to(root).parts)
]
for path in files:
    py_compile.compile(str(path), doraise=True)
print(f"[OK] validated {len(files)} Python file(s)")
PY
}

validate_json() {
  section "JSON syntax"
  require_cmd "$PYTHON_BIN"
  "$PYTHON_BIN" - "$REPO_ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
skip = {
    ".git",
    ".agents",
    ".codex",
    "frappe-bench",
    "logs",
    "logs/install",
    "backups",
    "offline_bundle",
    "node_modules",
    "build",
    "dist",
}
files = [
    path
    for path in root.rglob("*.json")
    if not any(part in skip for part in path.relative_to(root).parts)
]
for path in files:
    with path.open(encoding="utf-8") as handle:
        json.load(handle)
print(f"[OK] validated {len(files)} JSON file(s)")
PY
}

validate_toml() {
  section "TOML syntax"
  require_cmd "$PYTHON_BIN"
  "$PYTHON_BIN" - "$REPO_ROOT" <<'PY'
import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib

root = pathlib.Path(sys.argv[1])
skip = {
    ".git",
    ".agents",
    ".codex",
    "frappe-bench",
    "logs",
    "logs/install",
    "backups",
    "offline_bundle",
    "node_modules",
    "build",
    "dist",
}
files = [
    path
    for path in root.rglob("*.toml")
    if not any(part in skip for part in path.relative_to(root).parts)
]
for path in files:
    with path.open("rb") as handle:
        tomllib.load(handle)
print(f"[OK] validated {len(files)} TOML file(s)")
PY
}

validate_migration_module_names() {
  section "Migration module naming"
  require_cmd grep

  local migration_dir="$REPO_ROOT/frappe-bench/apps/ledgix_saas/migration"
  local bad_files=""
  local bad_refs=""
  local grep_targets=(
    "$REPO_ROOT/frappe-bench/apps/ledgix_saas"
    "$REPO_ROOT/scripts/core"
    "$REPO_ROOT/scripts/validation"
    "$REPO_ROOT/scripts/local"
    "$REPO_ROOT/scripts/release"
    "$REPO_ROOT/docs/architecture"
    "$REPO_ROOT/docs/fbr"
    "$REPO_ROOT/docs/local"
    "$REPO_ROOT/docs/operations"
    "$REPO_ROOT/docs/production"
  )

  if [[ -d "$migration_dir" ]]; then
    bad_files="$(find "$migration_dir" -maxdepth 1 -type f -regextype posix-extended -regex '.*_v[0-9]+\.py$' -print || true)"
  fi

  if [[ -n "$bad_files" ]]; then
    printf '%s\n' "$bad_files" >&2
    die "Version-suffixed migration modules are not allowed; use descriptive canonical/runtime/helper names."
  fi

  bad_refs="$(grep -R -n -E 'erpnext_[A-Za-z0-9_]+_v[0-9]+' \
    "${grep_targets[@]}" \
    --exclude-dir='__pycache__' \
    --exclude='*.pyc' || true)"

  if [[ -n "$bad_refs" ]]; then
    printf '%s\n' "$bad_refs" >&2
    die "Version-suffixed migration module references remain in source/scripts/current docs."
  fi

  ok "migration modules use descriptive names without _vN suffixes"
}

validate_apps() {
  section "Custom app packaging"
  require_cmd "$PYTHON_BIN"
  "$PYTHON_BIN" - "$REPO_ROOT" "$BENCH_PY" <<'PY'
import ast
import importlib
import os
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
bench_python = pathlib.Path(sys.argv[2])
apps_root = root / "frappe-bench" / "apps"
required = ("hooks.py", "__init__.py", "modules.txt")
key_imports = {
    "ledgix_saas": [
        "ledgix_saas",
        "ledgix_saas.hooks",
        "ledgix_saas.api.fbr_client",
        "ledgix_saas.api.fbr_payload",
        "ledgix_saas.api.fbr_submission",
        "ledgix_saas.api.taxation",
        "ledgix_saas.api.fbr_health",
        "ledgix_saas.validation",
    ],
}

if not apps_root.is_dir():
    raise SystemExit("[ERROR] canonical frappe-bench/apps directory is missing")

custom_app_names = ("ledgix_saas", "fbr_v1")
app_dirs = [
    apps_root / name
    for name in custom_app_names
    if (apps_root / name).is_dir()
]
if not app_dirs:
    raise SystemExit("[ERROR] no Ledgix-owned apps found under canonical frappe-bench/apps")


def fail(message):
    raise SystemExit(f"[ERROR] {message}")


def literal_hook_values(hooks_path, names):
    tree = ast.parse(hooks_path.read_text(encoding="utf-8"), filename=str(hooks_path))
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in names:
                try:
                    values[target.id] = ast.literal_eval(node.value)
                except Exception:
                    fail(f"{hooks_path} has a non-literal {target.id}; keep asset hook values static")
    return values


def flatten(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from flatten(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from flatten(item)


def validate_assets(app_name, app_dir):
    hooks_path = app_dir / "hooks.py"
    hook_values = literal_hook_values(
        hooks_path,
        {
            "app_include_css",
            "app_include_js",
            "web_include_css",
            "web_include_js",
        },
    )
    prefix = f"/assets/{app_name}/"
    for asset in flatten(hook_values):
        if not asset.startswith(prefix):
            continue
        public_path = app_dir / "public" / asset.removeprefix(prefix)
        if not public_path.is_file():
            fail(f"hook asset is missing: {asset} -> {public_path}")


def validate_imports(app_name):
    imports = key_imports.get(app_name, [app_name]) if bench_python.is_file() else [app_name]
    if bench_python.is_file():
        script = "import importlib\n" + "\n".join(
            f"importlib.import_module({name!r})" for name in imports
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{apps_root}:{env.get('PYTHONPATH', '')}"
        subprocess.run([str(bench_python), "-c", script], check=True, env=env)
    else:
        sys.path.insert(0, str(apps_root))
        importlib.import_module(app_name)



for app_dir in app_dirs:
    app_name = app_dir.name
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", app_name):
        fail(f"app folder is not a valid Python import name: {app_name}")

    source_root = app_dir
    if not (source_root / "hooks.py").is_file():
        nested = app_dir / app_name
        if (nested / "hooks.py").is_file():
            source_root = nested

    for filename in required:
        if not (source_root / filename).is_file():
            fail(f"{app_name} is missing required source file: {filename}")

    if not any(
        (app_dir / filename).is_file()
        for filename in ("pyproject.toml", "setup.py", "setup.cfg")
    ):
        fail(f"{app_name} is missing package metadata")

    validate_assets(app_name, source_root)
    validate_imports(app_name)
    print(f"[OK] app packaging validated: {app_name}")
PY
}


validate_canonical_custom_app_sources() {
  section "Canonical custom app source syntax"
  require_cmd "$PYTHON_BIN"

  "$PYTHON_BIN" - "$REPO_ROOT" <<'PYAPP'
import json
import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

root = pathlib.Path(sys.argv[1])
apps_root = root / "frappe-bench" / "apps"
app_names = ("ledgix_saas", "fbr_v1")

python_count = 0
json_count = 0
toml_count = 0

for app_name in app_names:
    app_root = apps_root / app_name

    if not app_root.is_dir():
        raise SystemExit(
            f"[ERROR] canonical custom app missing: {app_root}"
        )

    for path in app_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue

        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
        python_count += 1

    for path in app_root.rglob("*.json"):
        with path.open(encoding="utf-8") as handle:
            json.load(handle)
        json_count += 1

    for path in app_root.rglob("*.toml"):
        with path.open("rb") as handle:
            tomllib.load(handle)
        toml_count += 1

if python_count == 0:
    raise SystemExit(
        "[ERROR] zero canonical custom-app Python files validated"
    )

if json_count == 0:
    raise SystemExit(
        "[ERROR] zero canonical custom-app JSON files validated"
    )

if toml_count == 0:
    raise SystemExit(
        "[ERROR] zero canonical custom-app TOML files validated"
    )

print(
    "[OK] canonical custom app syntax validated: "
    f"python={python_count}, "
    f"json={json_count}, "
    f"toml={toml_count}"
)
PYAPP
}

main() {
  section "Repository validation"
  printf 'Repo root: %s\n' "$REPO_ROOT"
  validate_shell
  validate_python
  validate_json
  validate_toml
  validate_canonical_custom_app_sources
  validate_migration_module_names
  validate_apps
  ok "repository validation passed"
}

main "$@"

"$PYTHON_BIN" "$REPO_ROOT/scripts/validation/check_fiscal_architecture.py"
