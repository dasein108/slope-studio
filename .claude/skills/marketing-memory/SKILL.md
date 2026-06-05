---
name: marketing-memory
description: >
  Read this to understand HOW the growth loop remembers and self-improves — the journal
  (long-term strategy + episodic bet ledger), the backlog, episodic recall, per-run telemetry,
  and the cold-start phases. The reference any agent should read before operating the
  ideate→deploy→measure→learn loop or its lego-block skills.
---

# marketing-memory — how the loop remembers

The loop self-improves because every cycle **writes what it learned** and the next cycle
**reads it back**. There is no model retraining — improvement is in-context: the agent reflects
on outcomes, stores reusable lessons, and retrieves the relevant ones next time (the
Reflexion/ERL pattern; research in
[`docs/20-research/self-improving-loop.md`](../../../docs/20-research/self-improving-loop.md)).
Full human reference: [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).

## The stores (all per-channel)

Everything lives under `runs/_marketing/<channel>/` (omit `--channel` → `_default`).

| Store | Where | Role | Memory type |
|-------|-------|------|-------------|
| **Strategy** | `journal.json` → `strategy` | the distilled thesis: `niche`, `current_direction`, `winning_patterns`, `losing_patterns`, `next_seeds` | **long-term / semantic** — what works in general |
| **Entries** | `journal.json` → `entries[]` | one **episode** per bet, lifecycle `planned → deployed → measured`, holds idea/hook/assumption/goal/theme/tags + measured `metrics/virality/percentile/outcome/learnings` | **episodic** — what happened on each video |
| **Backlog** | the `entries[]` with `status: planned` | the queue of future bets, each tagged `explore: true/false` | working set |
| **Recall** | `studio/marketing/memory.py` | retrieves the **relevant** measured episodes for a query (lexical now, vector later) | retrieval / working memory |
| **Telemetry** | `runs/<run_id>/08_stats.json`, `08_comments.json` | raw measurement snapshots per video | episodic detail |
| **Renders** | `journal.md`, `report.md` | human-readable views | — |

The machine truth is `journal.json` (a pydantic `Journal`). `journal.md` is regenerated on every
save — never hand-edit it; edit `journal.json` (or use the helper commands) and it re-renders.

## Read/write per primitive (who touches what)

```
ideate   READ  strategy + recall(winners)         WRITE planned entries (backlog)
backlog  READ  planned entries                     WRITE (pick; no state change)
deploy   —                                          WRITE run_id/video_id, status=deployed
measure  READ  YouTube API                          WRITE metrics/virality/percentile/outcome, status=measured
learn    READ  measured entries + recall            WRITE strategy + per-entry learnings
```

The cycle closes because `learn`'s strategy + seeds are exactly what `ideate` reads next.

## Helper commands (NO LLM — pure I/O the agent drives)

```bash
studio marketing journal  --channel X            # print phase + strategy + bets table
studio marketing backlog  --channel X            # list planned bets + explore/exploit balance
studio marketing recall   "<query>" --channel X  # relevant measured episodes (the lessons)
studio marketing add      "<idea>" --hook .. --assumption .. --theme .. --tags a,b [--exploit]
studio marketing strategy --direction .. --winning "a;b" --losing "c" --seeds "x;y" [--note jID=text]
```
Deterministic steps stay scripted: `link` (bind run), `measure` (API + math). `ideate`/`learn`
also have scripted LLM fallbacks, but the **agent-driven** skills supersede them.

## Cold-start vs optimizing (the phase gate)

`deployed_count < bootstrap_target (10)` → **COLD START**: relative virality is meaningless, so
`measure` tags everything `cold-start` and `ideate` maximizes **diversity** (explore). At ≥10
deployed → **OPTIMIZING**: percentiles become real (`win` ≥P75 / `loss` ≤P25), and ideate/backlog
**exploit** the recalled winners while reserving ~40% for exploration. The journal tracks the
phase automatically (`Journal.in_cold_start`).

## Extending memory (roadmap)
- **Telemetry into episodes (T3):** capture per-video cost/duration/animators/fx/model from
  `runs/<id>/project.json` into the Entry — enables budget tracking + effect attribution.
- **Vector recall:** swap `memory._relevance` (lexical) for embeddings + a local vector index
  (research open-question Q9) when the journal outgrows lexical match.
- **Bandit selection:** replace the 60/40 explore/exploit with a warm-started contextual bandit
  (research F-SI6/F-SI7).
</content>
