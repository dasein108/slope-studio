# How the Growth Loop Remembers (Memory Architecture)

The marketing loop **self-improves** because every cycle writes what it learned and the next
cycle reads it back — no model retraining, all in-context (the Reflexion/ERL pattern; research
in [`../20-research/self-improving-loop.md`](../20-research/self-improving-loop.md)). This page
is the **canonical reference** for that memory (for both humans and agents); the per-step
operators are the `marketing-*` lego-block skills, which link here.

## Two kinds of memory

| | Long-term (semantic) | Episodic |
|---|---|---|
| **What** | the distilled thesis — what works *in general* on this channel | what happened on *each individual* video |
| **Where** | `Strategy` in `journal.json` | `entries[]` in `journal.json` (+ per-run snapshots) |
| **Written by** | `learn` | `ideate` (the bet) → `deploy` → `measure` (the outcome) |
| **Read by** | `ideate` (steers the next bet) | `recall` (pulls the relevant past episodes) |

A bet is one **episode**: idea + hook + the falsifiable **assumption** it tests, tracked to its
measured outcome. Distilling many episodes into reusable patterns is the **strategy**. Retrieving
the *relevant* episodes for the next decision is **recall**.

## Where it all lives on disk

Per channel, under `runs/_marketing/<channel>/` (omit `--channel` → `_default`):

```
runs/_marketing/<channel>/
├── journal.json     # MACHINE TRUTH — pydantic Journal: strategy + entries[] + snapshots[]
├── journal.md       # human render, regenerated on every save (never hand-edit)
└── report.md        # full growth brief (studio marketing report; via marketing-guru)

runs/<run_id>/       # per-video, written at measure time
├── 08_stats.json    # views/likes/comments/virality snapshot
└── 08_comments.json # fetched comment threads
```

`journal.json` is the source of truth (`studio/marketing/journal.py`). `journal.md` is a view —
edit the JSON (or use helper commands), and it re-renders on save.

## The data model (`studio/marketing/journal.py`)

- **`Journal`** — `channel`, `bootstrap_target` (10), `budget`, `loop`, `last_learn_at`,
  `strategy`, `entries[]`. Derived: `deployed_count`, `in_cold_start`, `measured()`, `next_id()`.
- **`BudgetConfig`** (`Journal.budget`) — `mode` (`per_video` | `per_minute`) + `amount`.
  `cap_for(duration_s)` → the per-video `--max-cost` (T4). Set via `studio marketing budget`.
- **`LoopConfig`** (`Journal.loop`) — autonomous-driver cadence (T1): `maturation_hours`,
  `min_hours_between_produces`, `daily_produce_cap`, `learn_every`, `backlog_min`,
  `target_duration_s`, plus the next-bet picker `select` (`bandit` | `fifo`) + `prior_strength`
  (T8). `last_learn_at` tracks the last reflection so `learn` fires on NEW data.
- **`Strategy`** (long-term) — `niche`, `current_direction`, `winning_patterns[]`,
  `losing_patterns[]`, `next_seeds[]`, `updated_at`.
- **`Entry`** (episodic) — `id` (`jNNNN`), the bet (`idea`, `hook`, `assumption`, `goal`,
  `theme`, `tags[]`, `explore`), deployment (`status`, `run_id`, `video_id`, `video_url`,
  `published_at`), **production telemetry** (`cost_usd`, `duration_s`, `tier`, `video_model`,
  `animators[]`, `effects[]`, `providers{}`, `n_scenes`, music/sfx/tone/transition fields,
  counted animator/effect/atmosphere/transition usage), measurement (`metrics`, `snapshots[]`,
  `virality`, `percentile`, `outcome`, `comments_sample[]`, `learnings`).
- **`Metrics`** — views, likes, comments, retention, subs_gained, age_days, velocity,
  engagement, fetched_at.
- **`MetricSnapshot`** — a `Metrics` record captured near a fixed post-publish age bucket
  (`1d`, `3d`, `7d`, `14d`, `30d`) so the loop can compare videos at the same maturity.

> **Production telemetry (T3, shipped):** `link` captures per-video cost, duration, and the
> video technologies used (animators / fx / model / per-stage providers) from
> `runs/<id>/project.json` + `01_script.json` into the Entry — via
> `studio/marketing/telemetry.py`. This is what lets `learn` attribute success to *effects*, not
> just themes, and tracks spend per bet.

## Episodic recall (`studio/marketing/memory.py`)

`recall(journal, query, k)` returns the **measured** episodes most *relevant* to a query
(channel direction / niche / candidate theme), ranked by lexical overlap, ties broken by
virality so a relevant winner outranks a relevant flop. `ideate` and `learn` inject these as
lesson cards so the next decision reflects what actually worked — not just what's recent. Today
relevance is lexical (free, offline, zero deps); the seam to swap in embeddings + a local vector
index is `memory._relevance` (research open-question Q9).

CLI: `studio marketing recall "<query>" --channel <name>`.

## Age-bucket analytics

The flat `metrics` field is the latest measurement; `snapshots[]` keeps the time series needed
for strategy slices. Use:

```bash
studio marketing due-snapshots --channel X
studio marketing snapshots     --channel X --buckets 1,3,7,14,30
studio marketing insights      --channel X --json
studio marketing slice         --channel X --bucket 7d --group-by theme,effects,animators --metric virality
studio marketing compare       --channel X effects=glitch --bucket 14d --metric virality
studio marketing export        --channel X --format csv
```

`1d` is mostly early hook/packaging velocity; `3d` is the first useful maturation point; `7d`,
`14d`, and `30d` reveal durability. Slices are associations, not causal proof, and should always
be read with sample size and examples.

## How memory flows the loop

```
                 ┌──────────── strategy + next_seeds ───────────┐
                 ▼                                               │
   ideate ──writes──▶ backlog ──pick──▶ deploy ──▶ measure ──writes──▶ learn
   reads strategy     (planned          links run    writes            reads measured
   + recall(winners)   entries)         to entry     outcomes          + recall → writes strategy
```

| Step | Reads | Writes |
|------|-------|--------|
| `ideate` | strategy, `recall` | `planned` entries (backlog) |
| `backlog` | `planned` entries | — (picks; 60/40 balance) |
| `deploy` | — | `run_id`, `video_id`, `status: deployed` |
| `measure` | YouTube API | `metrics`, `virality`, `percentile`, `outcome`, `status: measured` + run snapshots |
| `learn` | measured entries, `recall` | `strategy` (direction + patterns + seeds), per-entry `learnings` |

The loop closes because `learn`'s output is exactly `ideate`'s input.

## Cold-start vs optimizing

`deployed_count < 10` → **cold-start**: no baseline, so `measure` tags everything `cold-start`
and `ideate` maximizes diversity (pure exploration). At ≥10 deployed → **optimizing**:
percentiles become meaningful (`win` ≥P75 / `loss` ≤P25 / `neutral`), and ideate/backlog exploit
the recalled winners while keeping ~40% exploration. `Journal.in_cold_start` gates this
automatically.

## Helper commands (no LLM — the agent drives the thinking)

```bash
studio marketing journal  --channel X            # phase + strategy + every bet's outcome
studio marketing backlog  --channel X            # planned bets + explore/exploit balance
studio marketing recall   "<query>" --channel X  # the relevant past lessons
studio marketing add      "<idea>" --hook .. --assumption .. --theme .. --tags a,b [--exploit]
studio marketing strategy --direction .. --winning "a;b" --losing "c" --seeds "x;y" [--note jID=text]
```
`link` and `measure` stay deterministic scripts (I/O + math). `ideate`/`learn` keep scripted LLM
fallbacks, but the agent-driven `marketing-*` skills are the primary path.

## Autonomous loop (T1)

The engine `studio/marketing/loop.py` `plan(journal, now)` is a pure decision over the clock —
it returns the single action that's DUE (priority: **measure matured videos → learn → refill
backlog → produce → idle**), because a published video must mature ~48–72h before its metrics
mean anything. `studio marketing tick` shows it; `studio marketing autopilot` performs one due
action; the **marketing-autopilot** skill (or `/loop` / `/schedule` / cron) runs it continuously.
`link` stamps `published_at` (maturation clock); `learn` stamps `last_learn_at`.

**Which bet to produce (T8, `studio/marketing/bandit.py`):** the produce step picks via a
warm-started **Thompson-sampling bandit** over the bet's theme + tags (the context known before
production), not first-in-queue. Reward = a measured win (percentile ≥75); the prior is
warm-started from the channel base rate so it doesn't over-explore (research F-SI6/F-SI7). The
RNG is seeded from journal state so `tick` and `autopilot` agree within a tick. `studio marketing
bandit` shows the learned per-feature win-rates; set `loop.select = "fifo"` to disable it.

## Roadmap (memory upgrades)
- **T3 — episode telemetry:** ✅ shipped — cost / duration / animators / fx / model / providers
  captured into each Entry at link (`studio/marketing/telemetry.py`).
- **T1 — autonomous driver:** ✅ shipped — `loop.py` decision engine + `tick`/`autopilot` +
  the marketing-autopilot skill.
- **T8 — bandit selection:** ✅ shipped — `bandit.py` warm-started Thompson sampling replaces
  the fixed 60/40 pick (research F-SI6/F-SI7).
- **Vector recall:** embeddings + local vector index in place of lexical overlap (Q9).
- **Contextual bandit:** replace the fixed 60/40 with a warm-started bandit over theme/effect
  features (research F-SI6/F-SI7), using the episodic store as its history.

See also: [`README.md`](README.md) (loop overview), the `marketing-guru` skill (agent orchestrator),
and [`../20-research/self-improving-loop.md`](../20-research/self-improving-loop.md) (why this shape).
