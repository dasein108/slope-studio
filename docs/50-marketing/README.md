# Marketing — the viral growth loop

> Operator playbook: the **`marketing-guru`** skill (`.claude/skills/marketing-guru/`).
> This doc is the architecture + CLI reference behind it.

Producing a Short is the `film-maker` half. **Growing a channel** is a different problem:
*what* to make, and *did it work?* `marketing-guru` answers both with a closed feedback
loop backed by a persistent per-channel **journal**.

```
ideate → deploy → measure → learn → ideate …
  bet     produce   virality   steer
          +publish  vs portfolio
```

## The loop

| Step | CLI | What it does |
|------|-----|--------------|
| 1 ideate | `studio marketing ideate` | LLM generates idea + hook + **assumption** + goal → `planned` journal entry. Biased by learned strategy + web-search trend signals (`--signals`). |
| 2 deploy | `film-maker` → `studio run … --publish-to youtube` then `studio marketing link <entry> <run>` | Produce + publish; bind the run + YouTube id to the bet. |
| 3 measure | `studio marketing measure` | Fetch stats + comments; score virality; rank **percentile within the channel**; tag win/loss/neutral. |
| 4 learn | `studio marketing learn` | LLM confirms/refutes each assumption vs results → updates `winning_patterns`, `losing_patterns`, `current_direction`, `next_seeds`. |

`studio marketing journal` shows state; `studio marketing report` writes the full brief.

## Cold start

Relative virality needs a baseline. The journal tracks a **`bootstrap_target` (10)**:
until 10 videos are deployed it stays in **cold-start** — `ideate` maximizes thematic
diversity (exploration), `measure` withholds win/loss verdicts. After 10 it switches to
**optimizing** — exploit winners, reserve ~1/3 for exploration. See
[`../../.claude/skills/marketing-guru/references/loop.md`](../../.claude/skills/marketing-guru/references/loop.md).

## Where things live (code map)

```
studio/
  marketing/
    journal.py    Entry / Strategy / Journal (pydantic) + json+md ledger I/O
    score.py      virality composite + portfolio percentile + win/loss verdict
    ideate.py     LLM: next bet(s) from strategy + trend signals (fallback: deterministic)
    learn.py      LLM: reflect on measured bets → update Strategy (fallback: heuristic)
  providers/
    analytics.py  YouTube Data API (stats, comments, recent uploads) + Analytics API
                  (retention, subs, best-effort) — reuses the publish OAuth token
  cli.py          `studio marketing` sub-app: ideate · link · measure · learn · journal · report
```

Journal lives at `runs/_marketing/<channel>/journal.json` (+ `journal.md`, `report.md`) —
under gitignored `runs/`, so it's local data, never committed. Per-run snapshots:
`runs/<id>/08_stats.json`, `08_comments.json`.

## Virality scoring (summary)

`0.5·log10(velocity+1) + 0.2·retention + 0.2·engagement + 0.1·sub-conversion`, then
percentile-ranked within the channel. Velocity (views/day) dominates; retention guards
against junk reach. Missing analytics-scope metrics degrade to zero contribution. Full
formula + tuning: [`scoring.md`](../../.claude/skills/marketing-guru/references/scoring.md).

## Data access & scopes

- views / likes / comments / comment text → **Data API v3**, `youtube.readonly` (already
  granted by publishing — **no re-auth**).
- retention / subscribersGained → **Analytics API v2**, needs `yt-analytics.readonly`
  (one-time re-auth; fetched best-effort so the loop runs without it).

Setup + quota: [`analytics.md`](../../.claude/skills/marketing-guru/references/analytics.md)
and [`../40-publishing/youtube.md`](../40-publishing/youtube.md).

## Trends research

The CLI is offline; the **skill** web-searches trends/narratives/hot themes and writes a
signals file that `ideate --signals` consumes. Method:
[`trends.md`](../../.claude/skills/marketing-guru/references/trends.md).
