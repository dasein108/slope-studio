# Paperclip Company Bootstrap: Slope Studio

This directory is a reviewable task package for creating a new Paperclip company that runs Slope Studio as an organization instead of a single internal pipeline.

Nothing here installs or imports anything by itself. After approval, the intended single command is:

```bash
paperclip/scripts/bootstrap_company.sh --dry-run
```

When the dry-run preview looks correct:

```bash
paperclip/scripts/bootstrap_company.sh --apply
```

## Goal

Create a Paperclip company named `Slope Studio` with native Paperclip parent goal:

> Unlock Youtube monetization

The company should operate the existing Slope Studio autopilot workflow through explicit roles, task ownership, reporting lines, recurring routines, and observability.

## What Will Be Created

- A portable Paperclip company package in `paperclip/company/`.
- A native Paperclip goal tree for unlocking YouTube monetization and a `Slope Studio` project.
- Agent roles mapped from the current Slope Studio skills and autopilot workflows.
- Recurring operational tasks for ideation, production, publishing, measurement, learning, observability, and daily reporting.
- A Secretary role that sends a daily Telegram report about company work.
- Native Paperclip settings tasks for channels, autopilot policy, budgets, and SEO/packaging policy.

## Package Format

This package follows Paperclip's markdown-first company package layout:

```text
paperclip/company/
  COMPANY.md
  .paperclip.yaml
  agents/<slug>/AGENTS.md
  projects/<slug>/PROJECT.md
  projects/<slug>/tasks/<slug>/TASK.md
```

`COMPANY.md`, `AGENTS.md`, `PROJECT.md`, and `TASK.md` are the importable
objects. `.paperclip.yaml` is only Paperclip-specific extension data: Codex
adapter/model defaults, sidebar hints, schedules, and environment inputs.

Current Paperclip company import does not import goals from package files, so
`paperclip/scripts/bootstrap_company.sh --apply` runs a post-import goal upsert
through the Paperclip API. The goal source files live under
`paperclip/company/goals/`.

## Roles

All agents use the `codex_local` adapter. Model assignments are synced from
the live Paperclip company: creative, production, QA, growth, and analytics
roles use `gpt-5.5`; CEO, Secretary, and Observability/Ops use `gpt-5.4-mini`.

The package intentionally does not require Paperclip company skills.

- `paperclip/company/agents/<slug>/AGENTS.md` holds role-specific operating instructions, handoffs, gates, and reporting duties.
- `paperclip/company/projects/slope-studio-company/settings/` holds settings docs that the native Paperclip tasks point at.

This keeps the management surface native to Paperclip: agents, tasks, comments, approvals, and recurring routines.

Important boundary: Slope Studio CLI commands are tooling, not the organization.
`daily-org-autopilot` may use commands like `studio marketing tick` to read what
is due, but it must delegate execution through Paperclip employees instead of
running the old/internal autopilot end-to-end.

| Role | Purpose |
|---|---|
| CEO / Operator | Owns company goal, approvals, budget, priorities, and final decisions. |
| Growth Lead | Owns growth strategy, SEO, bet selection, channel policy, and publish/package direction. |
| Screenwriter | Turns selected bets into scripts and rewrites after QA feedback. |
| Producer | Produces visuals, audio, final video, metadata mechanics, publish execution, and journal linking after QA pass. |
| QA / Critic | Runs script and final gates. Returns `PASS` or `FAIL`; can block paid stages and publishing. |
| Analytics & Learning | Measures subscriber/video performance, evaluates assumptions, and updates strategy. |
| Observability / Ops | Owns dashboards, cost telemetry, run health, missed routines, incidents, and operational drift. |
| Secretary | Sends a daily Telegram report covering work completed, blocked items, spend, next actions, and decisions needed. |

The normal production flow is:

```text
Growth Lead -> Screenwriter -> QA / Critic -> Producer -> QA / Critic -> publish/link -> Analytics & Learning
```

## Settings You Can Change From Paperclip

| Setting | Native Paperclip task | Runtime effect |
|---|---|---|
| YouTube channel(s) | `Manage YouTube channel settings` | Which `--channel` is used and which OAuth token is expected. |
| Budget | `Tune autopilot settings, budgets, and publishing policy` | Updates `studio marketing budget` / journal budget. |
| Videos per day | `Tune autopilot settings, budgets, and publishing policy` | Updates journal loop settings such as `daily_produce_cap`. |
| Maturation window | `Tune autopilot settings, budgets, and publishing policy` | Controls when Analytics & Learning measures. |
| Publish approval | `Tune autopilot settings, budgets, and publishing policy` | Controls whether public uploads need CEO approval. |
| SEO focus | `Manage SEO and packaging policy` | Changes title, keyword, description, tag, hook, and packaging rules. |
| Telegram reports | `Send daily Telegram company report` | Controls daily report content and delivery health. |

## Monetization Goal Metrics

Parent goal: `Unlock Youtube monetization`.

Full YPP monetization target:

- `1000` subscribers
- `4000` valid public watch hours in the last `12` months
- OR `10000000` valid public Shorts views in the last `90` days

Earlier YPP access target in eligible countries/regions:

- `500` subscribers
- `3` valid public uploads in the last `90` days
- `3000` valid public watch hours in the last `12` months
- OR `3000000` valid public Shorts views in the last `90` days

Readiness checks:

- channel follows YouTube channel monetization policies
- channel is in a YPP-supported country/region
- no active Community Guidelines strikes
- Google Account 2-Step Verification is enabled
- YouTube advanced features access is enabled
- active AdSense for YouTube account is linked or ready
- content is original/authentic, not mass-produced or repetitive

## Install And Run Paperclip

Use these after approval only.

1. Clone Paperclip:

```bash
git clone https://github.com/paperclipai/paperclip
cd paperclip
```

2. Install and start it using the project instructions from the Paperclip repo. If `paperclipai` is already installed globally, you can usually start the local service with:

```bash
paperclipai run
```

3. Confirm the API is reachable:

```bash
curl http://localhost:3100/api/health
```

4. From this Slope Studio repo, preview the company import:

```bash
paperclip/scripts/bootstrap_company.sh --dry-run
```

The preview should show one company, eight agents, one `Slope Studio` project, and seven tasks.
It will also print the native goal tree that will be upserted after `--apply`.
If agents or tasks show as zero, confirm you are importing `paperclip/company/`
and that the package contains `agents/<slug>/AGENTS.md` and
`projects/slope-studio-company/tasks/<slug>/TASK.md`.

5. Apply the import after approval:

```bash
paperclip/scripts/bootstrap_company.sh --apply
```

6. Open the Paperclip dashboard shown by the import output.

Agents wake natively. Paperclip runs agents on scheduled heartbeats and
event-based triggers (task assignment, `@`-mentions), so assigning an issue to
an agent enqueues its wake automatically. Use `.paperclip.yaml` routines for
scheduled work and native issue assignment for handoffs; do not run a repo-level
polling loop as the orchestration layer.

If assigned agents are not waking locally, confirm assignment triggers are
enabled in your Paperclip instance/version rather than adding a sidecar watcher.
For one-off manual or debug wakes only, call Paperclip directly:

```bash
paperclipai heartbeat run --agent-id <id> --source assignment --trigger system
```

## Telegram Secretary Setup

The package declares these environment inputs. Set them in Paperclip or in the runtime environment used by the Secretary agent:

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=...
```

`TELEGRAM_CHAT_ID` is also accepted as a backward-compatible alias, but
`TELEGRAM_CHANNEL_ID` is the preferred name for this package.

The Secretary's daily task should summarize:

- active and completed tasks
- blocked tasks and required decisions
- spend and run health
- published videos and subscriber movement
- next 24 hour plan

## Approval Checklist

- Confirm the role list is sufficient.
- Confirm `codex_local` and the GPT model assignments are correct for every agent.
- Confirm the company name `Slope Studio` and issue prefix.
- Confirm parent goal `Unlock Youtube monetization`.
- Confirm Telegram env variable names.
- Confirm whether `--apply` should import into a new company or an existing Paperclip company.
