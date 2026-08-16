# Autopilot, Budget, And Publishing Policy

Owner: Growth Lead

This document defines how the autonomous company should run. The Paperclip UI
task for this is `Tune autopilot settings, budgets, and publishing policy`.

## Current Defaults

```yaml
channel: pilot-channel
target_duration_s: 60
default_tier: balanced
max_public_uploads_per_day: 3
daily_produce_cap: 3
min_hours_between_produces: 0
maturation_hours_before_measurement: 60
learn_every_measured_videos: 3
backlog_min: 3
cold_start_deployed_target: 10
publish_privacy_default: public
public_publish_requires_approval: false
budget:
  mode: per_video
  amount_usd: 0.60
```

## Runtime Commands

Budget:

```bash
studio marketing budget --channel pilot-channel --per-video 0.60
studio marketing budget --channel pilot-channel --for-duration 60
```

Read next due action:

```bash
studio marketing tick --channel pilot-channel --json
```

Headless fallback after approval:

```bash
studio marketing autopilot --channel pilot-channel --produce --tier balanced
```

## Journal Loop Settings

Some autopilot knobs live in:

```text
runs/_marketing/<channel>/journal.json
```

Relevant fields:

- `loop.maturation_hours`
- `loop.min_hours_between_produces`
- `loop.daily_produce_cap`
- `loop.learn_every`
- `loop.backlog_min`
- `loop.target_duration_s`
- `loop.select`
- `budget.mode`
- `budget.amount`

Agents may change these only when a Paperclip task/comment requests it or when
CEO policy authorizes it. Every change must be commented back with before/after.

## Changing Policy From Paperclip

Comment on the autopilot policy task:

```text
Change request:
Channel:
New value:
Duration:
Reason:
Success metric:
Rollback condition:
```

Examples:

```text
Change request: run one video per day maximum.
Channel: pilot-channel.
New value: daily_produce_cap=1.
Duration: until 10 deployed videos.
Reason: cold-start budget control.
Success metric: 10 tests completed under budget.
Rollback condition: CEO approves higher spend.
```

```text
Change request: optimize for SEO for the next 14 days.
Channel: pilot-channel.
New value: all new bets should include search keyword hypothesis and searchable title candidate.
Duration: 14 days.
Reason: subscriber conversion is main goal.
Success metric: higher search traffic and subs gained.
Rollback condition: SEO videos underperform P25 after maturation.
```

## Spend Policy

- Cheap/capped exploration is preferred until cold-start completes.
- `--max-cost` is whole-video budget: images, video clips, and music.
- Paid clips require estimate or budget cap.
- HARD COST CAP (2026-06-15): `studio run --channel <ch>` now AUTO-derives `--max-cost`
  from the channel budget (`budget.cap_for(duration)`) — the autonomous produce can no
  longer overspend even if the cap is omitted. The channel budget is the single source of
  the cap; keep it set (`studio marketing budget --channel <ch> --per-video N --max-per-video N`).
  ROOT CAUSE of j0032/SLO-75 ($2.81, kling×9): the OLD `studio run` ignored the channel
  budget and used its `--max-cost` default of $3, and the produce command omitted
  `--max-cost` — so kling×9 ($2.80) fit under $3. The budget was NOT empty; nothing read it.
  This auto-cap closes that gap by reading the budget for every `--channel` run.
- Prefer cheap clips: kenburns (free) or ltx (~$0.04/scene). kling (~$0.31/scene) blows a
  short's budget fast — only for a single hero scene, never all scenes.
- Only AI clips cost real money; images are ~$0.006, audio (freesound) is free, and LLM
  (script/critic + all agent reasoning) is on subscription = not metered. Optimize CLIP spend.
- Public publish is UNATTENDED (CEO disabled approval 2026-06-14). QA final PASS → Producer publishes + links directly, no CEO approval task.
- Never spend on visuals/clips downstream of `--script-provider stub`.

## Failure Policy

If a recurring task fails:

1. Mark or comment blocked in Paperclip.
2. Include the command and error summary.
3. Assign Observability / Ops if it is a system/process issue.
4. Assign the owning role if it is content, analytics, publishing, or policy.
