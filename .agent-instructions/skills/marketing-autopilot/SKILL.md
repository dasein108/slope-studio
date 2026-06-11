---
name: marketing-autopilot
description: >
  Use SPECIFICALLY for hands-off SCHEDULING of the growth loop — the unattended driver that keeps
  a channel turning on a cron/interval with no operator in the seat. Each tick it asks the engine
  what's due (measure matured videos / reflect / refill the backlog / produce the next bet) and
  does that ONE action, handling the deferred-measurement timing automatically — then defers the
  actual step-level work to the per-step skills. Set it on a recurring schedule (the /loop or
  /schedule skill, or cron). For a single manual step, invoke that step's skill directly instead.
---

# marketing-autopilot — run the loop on its own

The loop self-improves only if it keeps turning. This driver turns it. The hard part —
**a published video must mature ~48–72h before its metrics mean anything** — is handled by the
engine (`studio/marketing/loop.py`): it's a state machine over time, so each tick does the single
action that's actually *due*, never blindly publish→measure in one go.

## One tick = ask the engine, do the one due action

```bash
studio marketing tick --channel <name> --json
```
Returns the next action with everything you need:

| `next` | what to do (agent-driven) |
|--------|---------------------------|
| `measure` | `studio marketing measure --channel <name>` — `measure_due` videos have matured |
| `learn` | invoke **marketing-measure-learn** (its learn step: reflect → strategy); enough new measurements accrued |
| `ideate` | invoke **marketing-ideate** (web-search + recall → bets); backlog is low |
| `produce` | invoke **marketing-deploy** for `produce_entry` at `produce_max_cost` |
| `idle` | nothing due — sleep until the next tick (maturation / cadence wait) |

Do that ONE action, then tick again. Prefer the **lego-block skills** for the creative steps
(ideate/learn/produce) so the *thinking* is yours; `measure` is deterministic.

## Running it continuously

Pick a cadence (ticks every few hours are plenty — the engine gates the real timing):
- **Agent-driven (smartest):** use the **/loop** skill to re-invoke this skill on an interval,
  or **/schedule** to register a cron routine. Each firing: `tick --json` → do the due action.
- **Headless (no agent):** `studio marketing autopilot --channel <name> [--produce]` does one
  tick using the SCRIPTED ideate/learn fallbacks. Producing spends money + publishes, so it's
  **gated behind `--produce`**. Wire it to cron for fully unattended operation.

## Before first run — configure the channel

```bash
studio marketing budget --channel <name> --per-minute 0.40   # or --per-video 0.60  (sizes --max-cost)
studio marketing tick   --channel <name>                     # see what it would do
```
Cadence/maturation knobs live in `Journal.loop` (`maturation_hours` 60, `min_hours_between_produces`
20, `daily_produce_cap` 2, `learn_every` 3, `backlog_min` 2, `target_duration_s` 60) — edit
`runs/_marketing/<name>/journal.json` to tune.

## Cold-start
While `< 10` videos are deployed the engine/ideate stay in **exploration** (diverse bets); it
won't over-exploit a baseline that doesn't exist yet. Measurement still runs, but outcomes read
`cold-start` until the portfolio is big enough to rank.

## Memory
Reads the whole journal to decide; each delegated step writes its own slice. `learn` stamps
`last_learn_at`; `link` stamps `published_at` (the maturation clock). Memory model:
[`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
