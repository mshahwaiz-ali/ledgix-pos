#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

err() {
    printf '[ERROR] %s\n' "$*" >&2
}

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
    err "Missing required command: $PYTHON_BIN"
    exit 1
}

"$PYTHON_BIN" - "$REPO_ROOT" <<'PY'
import os
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1]).resolve()

custom_apps = (
    root / "frappe-bench" / "apps" / "ledgix_saas",
    root / "frappe-bench" / "apps" / "fbr_v1",
    root / "frappe-bench" / "apps" / "fbr_v12",
)

skip_dir_names = {
    ".git",
    ".agents",
    ".codex",
    ".secrets",
    "logs",
    "backups",
    "offline_bundle",
    "node_modules",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

skip_files = {
    "secrets.md",
    "production.secrets.md",
    "backups-index.md",
}

allowed_suffixes = {
    ".py",
    ".sh",
    ".js",
    ".json",
    ".toml",
    ".md",
    ".env",
    ".yml",
    ".yaml",
}

allow_words = (
    "redacted",
    "example",
    "placeholder",
    "changeme",
    "change_me",
    "change-this",
    "your-",
    "your_",
    "generated",
    "auto-generated",
    "press enter",
    "newstrongpassword",
    "[redacted]",
    "read -r -s -p",
    "${",
    "$",
)

patterns = [
    (
        "private key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?"
            r"PRIVATE KEY-----"
        ),
    ),
    (
        "bearer token",
        re.compile(
            r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}",
            re.IGNORECASE,
        ),
    ),
    (
        "fbr token assignment",
        re.compile(
            r"\b(?:sandbox|production)?_?fbr_?token\b"
            r"\s*[:=]\s*['\"]([^'\"]{16,})['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "api key assignment",
        re.compile(
            r"\b(?:api[_-]?key|secret[_-]?key|"
            r"access[_-]?token|auth[_-]?token)\b"
            r"\s*[:=]\s*['\"]([^'\"]{16,})['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "password assignment",
        re.compile(
            r"\b(?:db[_-]?password|database[_-]?password|password)"
            r"\b\s*[:=]\s*['\"]([^'\"]{12,})['\"]",
            re.IGNORECASE,
        ),
    ),
]


def is_allowed(value):
    lowered = value.lower()
    return any(word in lowered for word in allow_words)


def should_scan(path):
    if path.name in skip_files:
        return False

    suffix = path.suffix.lower()

    if suffix in allowed_suffixes:
        return True

    return path.name in {".env", ".gitignore"}


def walk_tree(base, skip_frappe_bench=False):
    base = base.resolve()

    if not base.exists():
        return

    for current, dirs, files in os.walk(base):
        current_path = pathlib.Path(current)

        dirs[:] = [
            name
            for name in dirs
            if name not in skip_dir_names
        ]

        if skip_frappe_bench and current_path == root:
            dirs[:] = [
                name
                for name in dirs
                if name != "frappe-bench"
            ]

        for filename in files:
            path = current_path / filename

            if should_scan(path):
                yield path


candidate_files = set()

# Scan normal repository content, but do not descend into the generated bench.
for path in walk_tree(root, skip_frappe_bench=True):
    candidate_files.add(path)

# Explicitly scan Ledgix-owned canonical source inside frappe-bench/apps.
for app_root in custom_apps:
    if not app_root.is_dir():
        raise SystemExit(
            f"[ERROR] canonical custom app missing: {app_root}"
        )

    for path in walk_tree(app_root):
        candidate_files.add(path)


findings = []

for path in sorted(candidate_files):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        continue

    for line_no, line in enumerate(lines, 1):
        if is_allowed(line):
            continue

        for label, pattern in patterns:
            match = pattern.search(line)

            if not match:
                continue

            value = (
                match.group(1)
                if match.groups()
                else match.group(0)
            )

            if is_allowed(value):
                continue

            findings.append(
                (
                    path.relative_to(root),
                    line_no,
                    label,
                )
            )


if findings:
    print(
        "[ERROR] potential committed secrets found:",
        file=sys.stderr,
    )

    for rel, line_no, label in findings:
        print(
            f"  {rel}:{line_no}: {label}",
            file=sys.stderr,
        )

    raise SystemExit(1)


custom_count = sum(
    1
    for path in candidate_files
    if any(
        app_root == path
        or app_root in path.parents
        for app_root in custom_apps
    )
)

print(
    "[OK] secret scan passed "
    f"({len(candidate_files)} files scanned; "
    f"{custom_count} canonical custom-app files)"
)
PY
