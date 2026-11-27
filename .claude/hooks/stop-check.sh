#!/usr/bin/env bash
# Stop hook: block the end of a Claude turn while `make check` fails.
# Exit 0 = allow stop. Exit 2 = block; stderr is fed back to Claude.
set -uo pipefail

input="$(cat)"

# Already continuing because of this hook: don't loop forever.
if printf '%s' "$input" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0
[ -f Makefile ] || exit 0

log="$(mktemp -t grove-check.XXXXXX)"
trap 'rm -f "$log"' EXIT

if make check >"$log" 2>&1; then
  exit 0
fi

{
  echo "make check failed. Fix these before finishing (last 60 lines):"
  tail -n 60 "$log"
} >&2
exit 2
