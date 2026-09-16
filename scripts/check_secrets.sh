#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

err() { printf '[ERROR] %s\n' "$*" >&2; }
ok() { printf '[OK] %s\n' "$*"; }

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  err "Missing required command: $PYTHON_BIN"
  exit 1
}

"$PYTHON_BIN" - "$REPO_ROOT" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
skip_dirs = {
    ".git",
    ".agents",
    ".codex",
    ".secrets",
    "frappe-bench",
    "logs",
    "logs/install",
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
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE)),
    ("fbr token assignment", re.compile(r"\b(?:sandbox|production)?_?fbr_?token\b\s*[:=]\s*['\"]([^'\"]{16,})['\"]", re.IGNORECASE)),
    ("api key assignment", re.compile(r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*['\"]([^'\"]{16,})['\"]", re.IGNORECASE)),
    ("password assignment", re.compile(r"\b(?:db[_-]?password|database[_-]?password|password)\b\s*[:=]\s*['\"]([^'\"]{12,})['\"]", re.IGNORECASE)),
]


def should_scan(path):
    rel = path.relative_to(root)
    if any(part in skip_dirs for part in rel.parts):
        return False
    if path.name in skip_files:
        return False
    if path.suffix.lower() in allowed_suffixes:
        return True
    return path.name in {".env", ".gitignore"}


def is_allowed(line):
    lowered = line.lower()
    return any(word in lowered for word in allow_words)


findings = []
for path in sorted(root.rglob("*")):
    if not path.is_file() or not should_scan(path):
        continue
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
            value = match.group(1) if match.groups() else match.group(0)
            if is_allowed(value):
                continue
            findings.append((path.relative_to(root), line_no, label))

if findings:
    print("[ERROR] potential committed secrets found:", file=sys.stderr)
    for rel, line_no, label in findings:
        print(f"  {rel}:{line_no}: {label}", file=sys.stderr)
    sys.exit(1)

print("[OK] secret scan passed")
PY
