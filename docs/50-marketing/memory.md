# How the Growth Loop Remembers (Memory Architecture)

The marketing loop **self-improves** because every cycle writes what it learned and the next
cycle reads it back — no model retraining, all in-context (the Reflexion/ERL pattern; research
in [`../20-research/self-improving-loop.md`](../20-research/self-improving-loop.md)). This page
is the human reference for that memory. The agent-facing version is the **`marketing-memory`**
skill; the per-step operators are the `marketing-*` lego-block skills.

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
├── journal.json     # MACHINE TRUTH — pydantic Journal: strategy + entries[]
├── journal.md       # human render, regenerated on every save (never hand-edit)
└── report.md        # full growth brief (marketing-report)

runs/<run_id>/       # per-video, written at measure time
├── 08_stats.json    # views/likes/comments/virality snapshot
└── 08_comments.json # fetched comment threads
```

`journal.json` is the source of truth (`studio/marketing/journal.py`). `journal.md` is a view —
edit the JSON (or use helper commands), and it re-renders on save.

## The data model (`studio/marketing/journal.py`)

- **`Journal`** — `channel`, `bootstrap_target` (10), `strategy`, `entries[]`. Derived:
  `deployed_count`, `in_cold_start`, `measured()`, `next_id()`.
- **`Strategy`** (long-term) — `niche`, `current_direction`, `winning_patterns[]`,
  `losing_patterns[]`, `next_seeds[]`, `updated_at`.
- **`Entry`** (episodic) — `id` (`jNNNN`), the bet (`idea`, `hook`, `assumption`, `goal`,
  `theme`, `tags[]`, `explore`), deployment (`status`, `run_id`, `video_id`, `video_url`,
  `published_at`), measurement (`metrics`, `virality`, `percentile`, `outcome`,
  `comments_sample[]`, `learnings`).
- **`Metrics`** — views, likes, comments, retention, subs_gained, age_days, velocity,
  engagement, fetched_at.

> The Entry does **not** yet store per-video cost, duration, or the animators/fx/model used —
> capturing that from `runs/<id>/project.json` (roadmap T3) is what unlocks budget tracking and
> *video-technology* attribution (which effects correlate with success).

## Episodic recall (`studio/marketing/memory.py`)

`recall(journal, query, k)` returns the **measured** episodes most *relevant* to a query
(channel direction / niche / candidate theme), ranked by lexical overlap, ties broken by
virality so a relevant winner outranks a relevant flop. `ideate` and `learn` inject these as
lesson cards so the next decision reflects what actually worked — not just what's recent. Today
relevance is lexical (free, offline, zero deps); the seam to swap in embeddings + a local vector
index is `memory._relevance` (research open-question Q9).

CLI: `studio marketing recall "<query>" --channel <name>`.

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

## Roadmap (memory upgrades)
- **T3 — episode telemetry:** capture cost / duration / animators / fx / model into each Entry.
- **Vector recall:** embeddings + local vector index in place of lexical overlap (Q9).
- **Contextual bandit:** replace the fixed 60/40 with a warm-started bandit over theme/effect
  features (research F-SI6/F-SI7), using the episodic store as its history.

See also: [`README.md`](README.md) (loop overview), the `marketing-memory` skill (agent view),
and [`../20-research/self-improving-loop.md`](../20-research/self-improving-loop.md) (why this shape).
</content>
