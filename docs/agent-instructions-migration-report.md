# Agent Instructions Migration Report

Date: 2026-06-11

## Goal

Make Slope Studio instructions project-scoped and shared by Codex, Claude Code, and any future
agent without duplicating operational rules or skill bodies.

## Inputs Reviewed

- `CLAUDE.md`
- `.claude/skills/*`
- `.claude/skills/marketing-guru/references/*`
- `README.md`
- `docs/README.md`
- `docs/00-overview/operator-guide.md`
- `docs/10-architecture/module-map.md`
- `pyproject.toml`
- `Makefile`

No project-local Cursor rules were found (`.cursorrules`, `.cursor/rules`, or `*.mdc`). No
project-local ChatGPT custom-instructions file was found in the repository or the shallow user config
search. The migration therefore treats the existing Claude instructions, skills, README, and docs as
the authoritative source set.

## New Structure

```text
.agent-instructions/
  shared.md
  skills/
    film-maker/
    sound-designer/
    youtube-branding/
    marketing-guru/
    marketing-ideate/
    marketing-deploy/
    marketing-measure-learn/
    marketing-autopilot/
AGENTS.md
CLAUDE.md
GLOBAL_AGENTS.md
.codex/skills/*/SKILL.md
.claude/skills/*/SKILL.md
```

## Single Source Of Truth

- `.agent-instructions/shared.md` is the canonical project instruction file.
- `.agent-instructions/skills/*` contains the canonical workflow bodies and bundled resources.
- `AGENTS.md` is now a thin Codex adapter.
- `CLAUDE.md` is now a thin Claude Code adapter.
- `.codex/skills/*/SKILL.md` and `.claude/skills/*/SKILL.md` keep only trigger metadata plus a
  pointer to the canonical skill.
- `GLOBAL_AGENTS.md` now explicitly avoids globalizing Slope Studio behavior.

The only intentional duplication is minimal tool-discovery metadata in skill adapter frontmatter.
Operational instructions, references, guides, example specs, and helper scripts live in the common
layer.

## Rules Preserved In The Shared Layer

- `studio run "<idea>" --run-id <id>` re-scripts from the passed idea; use per-stage commands to
  resume existing runs.
- `--script-provider stub` is wiring-only and must not feed paid visuals/clips.
- All ffmpeg shelling belongs in `studio/ffmpeg.py`.
- `--max-cost` is a whole-video budget and AI video pricing is per-second.
- Captions cannot rely on ffmpeg `drawtext`, `subtitles`, or `ass` on this machine.
- Per-video build scripts belong in `builds/`.
- TikTok public publishing is audit-gated; YouTube is the practical default.
- Secrets, tokens, generated runs, raw media, and local OAuth files stay out of git.

## Validation Notes

- Agent-specific support files were removed from `.codex/skills` and `.claude/skills` after moving
  their canonical copies under `.agent-instructions/skills`.
- Adapters now point agents back to `.agent-instructions`.
- Existing unrelated untracked files were not modified:
  - `.claude/scheduled_tasks.lock`
  - `token_pilot-channel.json.bak`

## Follow-Up

- If Cursor or ChatGPT instructions exist outside the searched locations, add them to this report and
  merge any project-specific rules into `.agent-instructions/shared.md`.
- If a future agent needs different discovery metadata, add a thin adapter only; do not copy the
  canonical instruction bodies.
