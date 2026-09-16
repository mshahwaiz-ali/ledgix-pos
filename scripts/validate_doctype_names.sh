#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

printf '\n==================================================\n'
printf ' Frappe DocType naming\n'
printf '==================================================\n'

"$PYTHON_BIN" - "$REPO_ROOT" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
apps_root = root / "apps"
errors = []
checked = 0


def scrub(value: str) -> str:
    # Equivalent naming shape required by Frappe DocType package paths:
    # lowercase snake_case derived from the DocType name.
    value = re.sub(r"[^a-z0-9]+", "_", (value or "").lower())
    return re.sub(r"_+", "_", value).strip("_")


for doctype_root in apps_root.rglob("doctype"):
    if not doctype_root.is_dir():
        continue
    for package in sorted(path for path in doctype_root.iterdir() if path.is_dir()):
        if package.name.startswith("__"):
            continue

        json_path = package / f"{package.name}.json"
        if not json_path.is_file():
            # Non-DocType helper folders are not treated as DocType packages.
            continue

        checked += 1
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{json_path.relative_to(root)}: invalid JSON: {exc}")
            continue

        if payload.get("doctype") != "DocType":
            errors.append(
                f"{json_path.relative_to(root)}: expected doctype='DocType', got {payload.get('doctype')!r}"
            )
            continue

        doctype_name = str(payload.get("name") or "").strip()
        if not doctype_name:
            errors.append(f"{json_path.relative_to(root)}: missing DocType name")
            continue

        expected_package = scrub(doctype_name)
        if package.name != expected_package:
            errors.append(
                f"{package.relative_to(root)}: folder name {package.name!r} does not match "
                f"DocType {doctype_name!r} -> {expected_package!r}"
            )

        if json_path.name != f"{expected_package}.json":
            errors.append(
                f"{json_path.relative_to(root)}: JSON filename must be {expected_package}.json"
            )

        controller = package / f"{expected_package}.py"
        same_stem_python = [
            path for path in package.glob("*.py")
            if path.name not in {"__init__.py"} and not path.name.startswith("test_")
        ]
        if same_stem_python and not controller.is_file():
            errors.append(
                f"{package.relative_to(root)}: controller files exist but canonical "
                f"{expected_package}.py is missing"
            )

if errors:
    print("[ERROR] Frappe DocType naming validation failed:")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print(f"[OK] validated {checked} DocType package name(s)")
PY