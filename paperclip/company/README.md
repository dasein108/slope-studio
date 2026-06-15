# Slope Studio

Portable Paperclip company package for running Slope Studio as an organization.

Parent goal: Unlock Youtube monetization.

The package imports agents, the Slope Studio project, and recurring tasks.
It intentionally does not define company skills.

Paperclip imports the canonical markdown objects:

- `COMPANY.md`
- `agents/<slug>/AGENTS.md`
- `projects/slope-studio-company/PROJECT.md`
- `projects/slope-studio-company/tasks/<slug>/TASK.md`

`.paperclip.yaml` is extension metadata for Codex adapter defaults, schedules,
sidebar hints, and runtime environment inputs. It is not the primary object
manifest. Every agent is configured there with `codex_local` and the GPT model
assignment synced from the live Paperclip company.

Current Paperclip company import does not import `GOAL.md` files directly. The
bootstrap script creates or updates the native Paperclip goal tree after import.
