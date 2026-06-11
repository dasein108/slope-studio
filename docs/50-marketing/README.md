# Marketing — the viral growth loop

> Operator playbook: the **`marketing-guru`** umbrella skill (`.claude/skills/marketing-guru/`),
> which composes the per-step **lego-block skills** — `marketing-ideate`, `marketing-deploy`,
> `marketing-measure-learn` — plus the hands-off scheduled driver `marketing-autopilot`. The guru
> itself owns the thin read/pick/report helpers (journal state, backlog pick, growth brief). Any
> agent can invoke one step alone. This doc is the architecture + CLI reference behind them.
>
> **How memory works (the self-improving part):** [`memory.md`](memory.md) — the canonical
> reference for the journal / strategy / recall / cold-start model.

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
| 3 measure | `studio marketing measure` + `snapshots` | Fetch stats + comments; score virality; capture 1d/3d/7d/14d/30d age buckets; rank **percentile within the channel**; tag win/loss/neutral. |
| 4 analyze + learn | `insights` / `slice` / `compare` → `learn` | Surface hidden relations across theme/effects/animation/music/sfx/cost, then confirm/refute assumptions → update `winning_patterns`, `losing_patterns`, `current_direction`, `next_seeds`. |

`studio marketing journal` shows state; `studio marketing report` writes the full brief.

**Design rule — agent does the thinking, the CLI is I/O.** The creative steps (ideate, learn,
pick) are the **agent's** judgement, done in the lego-block skills; the `studio marketing`
commands are helpers: pure-I/O persistence (`add`, `strategy`, `budget`), retrieval (`recall`,
`backlog`, `journal`, `bandit`), and deterministic work (`link`, `measure`). `ideate`/`learn`
keep scripted LLM fallbacks for quick non-agent passes.

### Helper + autonomous commands

| Command | Role |
|---------|------|
| `add` | persist an agent-authored bet to the backlog (no LLM) |
| `backlog` | list planned bets + explore/exploit balance |
| `recall "<q>"` | episodic memory — relevant past measured bets (`memory.py`) |
| `strategy` | persist an agent's reflection (direction/patterns/seeds/per-bet note) |
| `budget` | set per-video / per-minute spend cap; `--for-duration` → a video's `--max-cost` (T4) |
| `bandit` | show the learned theme/tag win-rates + backlog ranking (T8) |
| `due-snapshots` | list videos ready for 1d/3d/7d/14d/30d measurement buckets |
| `snapshots` | fetch and persist age-bucket performance snapshots |
| `slice` | group performance by theme/effects/animators/music/sfx/model/cost features |
| `compare` | compare videos with one feature against videos without it |
| `insights` | emit the compact JSON strategy pack for `marketing-guru` |
| `export` | dump video-level analytics rows as CSV/JSON |
| `tick` | the autonomous engine's NEXT due action (read-only; T1) |
| `autopilot` | perform one due action (measure\|learn\|ideate\|produce\|idle); `--produce` gates spend |

## Autonomous loop (T1) — run it hands-off

The engine `loop.py` `plan(journal, now)` is a state machine over the clock: a published video
must mature **~48–72h** before its metrics mean anything, so each tick does the single action
that's DUE (priority **measure → learn → ideate → produce → idle**). `link` stamps `published_at`
(the maturation clock); `learn` stamps `last_learn_at`. The next bet to **produce** is chosen by a
warm-started **Thompson-sampling bandit** over theme+tags (`bandit.py`, T8 — replaces the fixed
60/40). Drive it continuously with the **`marketing-autopilot`** skill on a `/loop` / `/schedule`,
or `studio marketing autopilot` from cron. Cadence/maturation/picker knobs live in `Journal.loop`.

## Cold start

Relative virality needs a baseline. The journal tracks a **`bootstrap_target` (10)**:
until 10 videos are deployed it stays in **cold-start** — `ideate` maximizes thematic
diversity (exploration), `measure` withholds win/loss verdicts, and the bandit's picks are
exploratory (no relative signal yet). After 10 it switches to **optimizing** — the Thompson
bandit (T8) exploits winning theme/tag arms while wide posteriors keep exploring. See
[`../../.claude/skills/marketing-guru/references/loop.md`](../../.claude/skills/marketing-guru/references/loop.md).

## Age-bucket analytics

Do not compare a 1-day upload against a 30-day upload as if they had the same opportunity to
accumulate views. The measurement layer keeps fixed post-publish snapshots:

```bash
studio marketing due-snapshots --channel X
studio marketing snapshots     --channel X --buckets 1,3,7,14,30
studio marketing insights      --channel X --json
```

Use `slice` to find broad associations:

```bash
studio marketing slice --channel X --bucket 7d \
  --group-by theme,effects,animators,music_provider,sfx_provider --metric virality
```

Use `compare` for specific hypotheses:

```bash
studio marketing compare --channel X effects=glitch --bucket 14d --metric virality
studio marketing compare --channel X animators=parallax --bucket 7d --metric retention
studio marketing compare --channel X music_provider=synth --bucket 3d --metric virality_per_dollar
```

Read every result as **association, not causation**. The output includes sample counts and
examples because theme, publish timing, spend, script quality, and production choices are
confounded. Low `n` generates a testable next bet; it is not a rule.

## Where things live (code map)

```
studio/
  marketing/
    journal.py    Entry / Strategy / Journal / BudgetConfig / LoopConfig + json+md ledger I/O
                  (Entry also stores per-video production telemetry — cost/duration/effects)
    score.py      virality composite + portfolio percentile + win/loss verdict
    ideate.py     LLM: next bet(s) from strategy + recall + trend signals (fallback: deterministic)
    learn.py      LLM: reflect on measured bets → update Strategy (fallback: heuristic)
    memory.py     episodic recall — rank measured bets by relevance to a query (lexical, offline)
    telemetry.py  T3: pull cost/duration/animators/fx/model from a run manifest into the Entry
    analytics_tools.py  age buckets, slices, comparisons, insights, CSV/JSON export
    loop.py       T1 engine: plan() → the one DUE action; deferred-measurement state machine
    bandit.py     T8: warm-started Thompson sampling over theme+tags → next bet to produce
  providers/
    analytics.py  YouTube Data API (stats, comments, recent uploads) + Analytics API
                  (retention, subs, best-effort) — reuses the publish OAuth token
  cli.py          `studio marketing` sub-app: ideate · link · measure · snapshots · slice
                  · compare · insights · export · learn · journal · report · add · backlog
                  · recall · strategy · budget · bandit · tick · autopilot
```

Journal lives at `runs/_marketing/<channel>/journal.json` (+ `journal.md`, `report.md`) —
under gitignored `runs/`, so it's local data, never committed. Per-run snapshots:
`runs/<id>/08_stats.json`, `08_comments.json`.

## Virality scoring (summary)

`0.5·log10(velocity+1) + 0.2·retention + 0.2·engagement + 0.1·sub-conversion`, then
percentile-ranked within the channel. Velocity (views/day) dominates; retention guards
against junk reach. Missing analytics-scope metrics degrade to zero contribution. Full
formula + tuning: [`scoring.md`](../../.claude/skills/marketing-guru/references/scoring.md).

> **Research note (F-SI9, not yet applied):** verified platform signals say **retention/watch-time
> should lead, with shares/saves above likes** — the current velocity-first weights are a
> candidate re-tune. See [`../20-research/self-improving-loop.md`](../20-research/self-improving-loop.md).

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
