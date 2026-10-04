#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
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
apps_root = root / "frappe-bench" / "apps"
app_names = ("ledgix_saas", "fbr_v1")

errors = []
checked = 0


def scrub(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", (value or "").lower())
    return re.sub(r"_+", "_", value).strip("_")


for app_name in app_names:
    app_root = apps_root / app_name

    if not app_root.is_dir():
        errors.append(f"canonical app directory missing: {app_root}")
        continue

    for doctype_root in app_root.rglob("doctype"):
        if not doctype_root.is_dir():
            continue

        for package in sorted(
            path for path in doctype_root.iterdir()
            if path.is_dir()
        ):
            if package.name.startswith("__"):
                continue

            json_path = package / f"{package.name}.json"

            if not json_path.is_file():
                continue

            checked += 1

            try:
                payload = json.loads(
                    json_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                errors.append(
                    f"{json_path.relative_to(root)}: invalid JSON: {exc}"
                )
                continue

            if payload.get("doctype") != "DocType":
                errors.append(
                    f"{json_path.relative_to(root)}: "
                    f"expected doctype='DocType', "
                    f"got {payload.get('doctype')!r}"
                )
                continue

            doctype_name = str(
                payload.get("name") or ""
            ).strip()

            if not doctype_name:
                errors.append(
                    f"{json_path.relative_to(root)}: missing DocType name"
                )
                continue

            expected_package = scrub(doctype_name)

            if package.name != expected_package:
                errors.append(
                    f"{package.relative_to(root)}: "
                    f"folder {package.name!r} does not match "
                    f"DocType {doctype_name!r} -> "
                    f"{expected_package!r}"
                )

            if json_path.name != f"{expected_package}.json":
                errors.append(
                    f"{json_path.relative_to(root)}: "
                    f"JSON filename must be "
                    f"{expected_package}.json"
                )

if errors:
    print("[ERROR] Frappe DocType naming validation failed:")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

if checked == 0:
    raise SystemExit(
        "[ERROR] zero custom DocType packages were validated"
    )

print(f"[OK] validated {checked} custom DocType package name(s)")
PY
