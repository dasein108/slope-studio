#!/usr/bin/env bash
# Activate the Slope Studio git guardrails (SLO-33) for this clone.
# Points git at the tracked hooks dir so the secret-scan pre-commit runs on every commit,
# including autonomous agents that share this repo. Run once per clone.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chmod +x "$ROOT/scripts/hooks/"* "$ROOT/scripts/safe-commit.sh" 2>/dev/null || true
git -C "$ROOT" config core.hooksPath scripts/hooks
echo "Guardrails active: core.hooksPath=scripts/hooks (pre-commit secret scan enabled)."
echo "Disable with: git config --unset core.hooksPath"
