# Codex Adapter — Slope Studio

This file is intentionally thin. The single source of truth for project instructions is
`.agent-instructions/shared.md`.

## Required Read Order

1. Read `.agent-instructions/shared.md`.
2. For workflow-specific work, use the matching Codex skill adapter in `.codex/skills/<skill>/`.
3. That adapter points to the canonical skill body under `.agent-instructions/skills/<skill>/`.

## Codex-Specific Notes

- Keep this adapter small. Do not copy project rules or skill workflows here.
- If this file conflicts with `.agent-instructions/shared.md`, the shared file wins unless the
  conflict is purely about Codex mechanics.
- Commit only when the user explicitly asks.
