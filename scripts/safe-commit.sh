#!/usr/bin/env bash
# safe-commit (SLO-33) — the ONLY sanctioned commit path for agents.
# Usage: scripts/safe-commit.sh <path> [<path>...] -m "message"
# Refuses blanket staging (`git add -A`/`.`) — explicit paths only — then commits, which
# triggers the pre-commit secret scan. Prevents the `git add -A` accidents that leak secrets.
set -uo pipefail
msg=""; paths=()
while [ $# -gt 0 ]; do
  case "$1" in
    -m) msg="${2:-}"; shift 2;;
    -A|--all|.) echo "refused: blanket staging is banned (SLO-33) — list explicit paths." >&2; exit 2;;
    *) paths+=("$1"); shift;;
  esac
done
[ "${#paths[@]}" -eq 0 ] && { echo "usage: safe-commit <path...> -m <msg>" >&2; exit 2; }
[ -z "$msg" ] && { echo "commit message required (-m)" >&2; exit 2; }
git add -- "${paths[@]}"
git commit -m "$msg"
