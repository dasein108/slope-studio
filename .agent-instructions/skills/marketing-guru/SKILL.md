---
name: marketing-guru
description: >
  Umbrella orchestrator for a Slope Studio channel's viral-growth loop. Use when the user wants
  to RUN THE WHOLE ideate→deploy→measure→learn cycle, or doesn't know which step they need, or
  wants to READ channel state / PICK the next bet / WRITE a growth brief (journal · backlog ·
  report all live here). It composes the per-step lego-block skills (marketing-ideate,
  marketing-deploy, marketing-measure-learn) and the hands-off driver (marketing-autopilot).
  For one creative step, invoke that step's skill directly.
---

# marketing-guru — orchestrate the growth loop

Make a channel go viral by running a **closed feedback loop** backed by a persistent
**journal**. You don't guess once — you bet, deploy, measure against the channel's own history,
learn, and bet again. The creative steps are their own **lego-block skills** any agent can use
alone; this skill is the conductor, and it also owns the thin read/pick/report helpers.

```
   ┌──────────────────────────────────────────────────────────────┐
   │  IDEATE  → BACKLOG → DEPLOY → (wait 48-72h) → MEASURE → LEARN  │
   │     ▲                                                      │   │
   │     └──────────── strategy + next_seeds ◀─────────────────┘   │
   └──────────────────────────────────────────────────────────────┘
```

## The skills (invoke any one directly)

| Step | Skill / here | One-liner | CLI it drives |
|------|--------------|-----------|---------------|
| setup | **youtube-branding** | channel identity: banner/avatar/logo + keywords/description (once / on rebrand) | `studio brand` |
| 0 | **guru: journal** | read phase + strategy + bets (start here) | `journal` · `recall` |
| 1 | **marketing-ideate** | agent generates falsifiable bets → backlog | `add` (· `ideate` fallback) |
| 2 | **guru: backlog** | pick the next bet (bandit, 60/40 fallback) | `backlog` · `bandit` |
| 3 | **marketing-deploy** | produce+publish via film-maker, then link | `studio run` · `link` |
| 4+5 | **marketing-measure-learn** | score virality, then reflect → strategy (wait 48-72h) | `measure` · `strategy` |
| — | **guru: report** | write the growth brief to disk | `report` |
| ⟳ | **marketing-autopilot** | run the WHOLE loop on a schedule (deferred-measurement aware) | `tick` · `autopilot` |

**Design rule:** the *thinking* (what to make, which bet, what was learned) is the **agent's**,
done in the skills; the `studio marketing` CLI commands are **helpers** — pure I/O for persistence
(`add`/`strategy`), retrieval (`recall`/`backlog`/`journal`/`bandit`), and deterministic work
(`link`, `measure`). `ideate`/`learn` keep scripted LLM fallbacks for quick non-agent passes.

## Run the whole loop

0. **youtube-branding** *(once, before the loop)* — if the channel has no banner/avatar/logo
   yet (or is rebranding), generate the brand kit with `studio brand <spec.json>`.
1. **journal** *(below)* — read the current phase + direction first.
2. **marketing-ideate** — web-search trends + recall winners → write bets to the backlog.
3. **backlog** *(below)* — pick the next bet.
4. **marketing-deploy** — produce + publish (film-maker), sized to the per-video budget, then link.
5. **wait 48-72h+** for watch time to accrue.
6. **marketing-measure-learn** — score, then reflect into strategy.
7. Back to 2 — now exploiting what won. **report** *(below)* snapshots the cycle.

To run all of this **hands-off on a schedule**, use **marketing-autopilot** — it asks the engine
what's due each tick (measure / learn / ideate / produce / idle) and does that one action,
handling the 48–72h measurement-maturation wait for you.

**The cold-start rule (stated once, here):** relative virality is meaningless until ~10 videos
exist. Deploy the first **10 as diverse EXPLORATION bets**; only then does `measure` rank winners
and `learn` start exploiting. The journal tracks the phase automatically (`Journal.in_cold_start`).
Full memory + phase model: [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).

Everything is **per-channel** — pass `--channel <name>` (mirrors the publish OAuth token
`token_<name>.json`). Omit for the default journal.

## journal — read the loop's state (read-only)

The first thing to run before any decision, so bets reflect the current direction.
```bash
studio marketing journal --channel <name>            # phase + strategy + every bet's outcome table
studio marketing backlog --channel <name>            # planned (queued) bets + explore/exploit mix
studio marketing recall  "<query>" --channel <name>  # past MEASURED bets most relevant to a query
```
You'll see the **phase** (`COLD START n/10` vs `OPTIMIZING`), the `Strategy` (niche,
current_direction, winning/losing patterns, next_seeds), and a table of every bet (id · status ·
idea · virality · percentile · outcome). Durable store: `runs/_marketing/<name>/journal.json`
(machine truth) + `journal.md` (human render, regenerated on save — never hand-edit). Per-video
snapshots: `runs/<run_id>/08_stats.json`, `08_comments.json`.

## backlog — pick what to make next

The backlog = every journal entry with `status: planned`. Review it, then choose the next bet to
hand to **marketing-deploy**. The CLI lists; YOU decide.
```bash
studio marketing backlog --channel <name>   # planned bets tagged explore/exploit + counts
studio marketing bandit  --channel <name>   # the SHIPPED selector's learned theme/tag win-rates
```
- **Primary selector:** the shipped **Thompson bandit** (T8) over theme+tags — `studio marketing
  bandit` shows what it favors and how it ranks the backlog; the autopilot picks with it.
- **Fallback heuristic (manual picks):** ~**60% exploitation** (proven winning patterns) / ~**40%
  exploration** (fresh themes) — use this when you're choosing by hand rather than via the bandit.
- **Cold-start (<10 deployed): everything is exploration** regardless of tags — no baseline yet.

Sanity-check a candidate isn't a near-dupe of a past loser with `recall "<idea/theme>"`. Empty
backlog → run **marketing-ideate** first. No delete command yet (roadmap T2) — edit
`runs/_marketing/<name>/journal.json` to prune, or leave stale bets unpicked.

## report — write the growth brief

```bash
studio marketing report --channel <name> --provider <llm>
```
Writes `runs/_marketing/<name>/report.md` — the channel's phase, current direction, winners/losers
with their assumptions (held or refuted), and the next bets. Run it after **marketing-measure-learn**
so it reflects the latest cycle. For a quick interactive read instead of a file, just run
`studio marketing journal`.

## Setup check
```bash
cd /Users/dasein/dev/slope-studio
source .venv/bin/activate 2>/dev/null || { uv venv && source .venv/bin/activate && uv pip install -e ".[fal,youtube]"; }
studio marketing --help
studio yt-channel --channel <name>   # confirm WHICH channel the token points at
```

## Always report
The channel's phase (cold-start N/10 vs optimizing), latest winners/losers with their
assumptions (held or refuted), the current direction, and the next concrete bets. Be honest when
a bet's assumption was **refuted** — that's the point.

## Deeper references
- **Memory & phases:** [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md) — the canonical reference for how the journal/recall/strategy/cold-start persist and self-improve.
- [`references/loop.md`](references/loop.md) · [`references/scoring.md`](references/scoring.md) · [`references/analytics.md`](references/analytics.md) · [`references/trends.md`](references/trends.md).
- Architecture + full command reference: [`docs/50-marketing/`](../../../docs/50-marketing/).
- Producing videos: the **film-maker** skill. Why this shape: [`docs/20-research/self-improving-loop.md`](../../../docs/20-research/self-improving-loop.md).
