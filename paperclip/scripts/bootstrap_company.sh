#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE_DIR="$ROOT/paperclip/company"
API_BASE="${PAPERCLIP_API_URL:-http://localhost:3100}"
COMPANY_NAME="${PAPERCLIP_COMPANY_NAME:-Slope Studio}"
MODE="${1:---dry-run}"

usage() {
  cat <<'USAGE'
Usage:
  paperclip/scripts/bootstrap_company.sh --dry-run
  paperclip/scripts/bootstrap_company.sh --apply

Environment:
  PAPERCLIP_API_URL       default: http://localhost:3100
  PAPERCLIP_COMPANY_NAME  default: Slope Studio

This script does not install Paperclip. It imports the local portable company
package only when --apply is passed. --dry-run is the safe default.

After --apply, it also creates or updates native Paperclip goals:
  - Unlock Youtube monetization
  - Reach 1000 subscribers
  - Reach YPP traffic threshold
  - Pass YPP readiness checks

It also ensures the Slope Studio project uses the real local workspace:
  /Users/dasein/dev/slope-studio
USAGE
}

if [ "$MODE" = "--help" ] || [ "$MODE" = "-h" ]; then
  usage
  exit 0
fi

if ! command -v paperclipai >/dev/null 2>&1; then
  echo "paperclipai was not found on PATH. Install/run Paperclip first, then retry." >&2
  exit 1
fi

if [ ! -f "$PACKAGE_DIR/COMPANY.md" ]; then
  echo "Company package is missing: $PACKAGE_DIR/COMPANY.md" >&2
  exit 1
fi

if [ ! -f "$PACKAGE_DIR/.paperclip.yaml" ]; then
  echo "Paperclip extension metadata missing: $PACKAGE_DIR/.paperclip.yaml" >&2
  exit 1
fi

AGENT_COUNT="$(find "$PACKAGE_DIR/agents" -mindepth 2 -maxdepth 2 -name AGENTS.md -type f | wc -l | tr -d ' ')"
PROJECT_COUNT="$(find "$PACKAGE_DIR/projects" -mindepth 2 -maxdepth 2 -name PROJECT.md -type f | wc -l | tr -d ' ')"
TASK_COUNT="$(find "$PACKAGE_DIR/projects" -mindepth 4 -maxdepth 4 -name TASK.md -type f | wc -l | tr -d ' ')"
GOAL_COUNT="$(find "$PACKAGE_DIR/goals" -mindepth 2 -maxdepth 2 -name GOAL.md -type f | wc -l | tr -d ' ')"

if [ "$AGENT_COUNT" -eq 0 ]; then
  echo "No agents found. Expected files like agents/<slug>/AGENTS.md" >&2
  exit 1
fi

if [ "$PROJECT_COUNT" -eq 0 ]; then
  echo "No projects found. Expected files like projects/<slug>/PROJECT.md" >&2
  exit 1
fi

if [ "$TASK_COUNT" -eq 0 ]; then
  echo "No tasks found. Expected files like projects/<slug>/tasks/<slug>/TASK.md" >&2
  exit 1
fi

echo "Importing package: $PACKAGE_DIR"
echo "Detected: 1 company, $AGENT_COUNT agents, $PROJECT_COUNT project(s), $TASK_COUNT task(s), $GOAL_COUNT goal source file(s)"

case "$MODE" in
  --dry-run)
    echo "Will upsert native Paperclip goal tree after apply:"
    echo "  Unlock Youtube monetization"
    echo "    - Reach 1000 subscribers"
    echo "    - Reach YPP traffic threshold"
    echo "    - Pass YPP readiness checks"
    paperclipai company import "$PACKAGE_DIR" \
      --target new \
      --new-company-name "$COMPANY_NAME" \
      --include company,agents,projects,issues \
      --collision skip \
      --api-base "$API_BASE" \
      --dry-run
    ;;
  --apply)
    paperclipai company import "$PACKAGE_DIR" \
      --target new \
      --new-company-name "$COMPANY_NAME" \
      --include company,agents,projects,issues \
      --collision skip \
      --api-base "$API_BASE" \
      --yes
    ruby "$ROOT/paperclip/scripts/bootstrap_goals.rb"
    ruby "$ROOT/paperclip/scripts/bootstrap_workspace.rb"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
