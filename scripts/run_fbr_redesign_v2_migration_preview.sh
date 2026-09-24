#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

printf '==================================================\n'
printf ' FBR Redesign V2 Migration Preview - RETIRED\n'
printf '==================================================\n'
printf 'Repo: %s\n' "$ROOT_DIR"
printf 'Branch: %s\n' "$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || true)"
printf 'Commit: %s\n' "$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD 2>/dev/null || true)"
printf '\n'
printf '[RETIRED] The legacy V2 migration preview/apply path is no longer an authority.\n' >&2
printf '[RETIRED] It must not read or copy old FBR Settings, credentials, or Item Tax Profile data.\n' >&2
printf '[RETIRED] Use current V2 Integration Profiles/mappings and the dedicated controlled legacy DB cleanup phase.\n' >&2
printf '[SAFETY] No database command and no FBR network call were executed.\n' >&2
exit 2
