---
name: marketing-guru
description: >
  Umbrella orchestrator for a Slope Studio channel's viral-growth loop. Use when the user wants
  to RUN THE WHOLE ideate→deploy→measure→learn cycle (or doesn't know which step they need). It
  composes the per-primitive lego-block skills (marketing-ideate, marketing-backlog,
  marketing-deploy, marketing-measure, marketing-learn, marketing-journal, marketing-report) and
  marketing-memory. For a single step, invoke that step's skill directly.
---

# marketing-guru — orchestrate the growth loop

Make a channel go viral by running a **closed feedback loop** backed by a persistent
**journal**. You don't guess once — you bet, deploy, measure against the channel's own history,
learn, and bet again. Each step is its own **lego-block skill** any agent can use alone; this
skill is the conductor.

```
   ┌──────────────────────────────────────────────────────────────┐
   │  IDEATE  → BACKLOG → DEPLOY → (wait 48-72h) → MEASURE → LEARN  │
   │     ▲                                                      │   │
   │     └──────────── strategy + next_seeds ◀─────────────────┘   │
   └──────────────────────────────────────────────────────────────┘
```

## The lego blocks (invoke any one directly)

| Step | Skill | One-liner | CLI it drives |
|------|-------|-----------|---------------|
| 0 | **marketing-journal** | read phase + strategy + bets (start here) | `journal` · `backlog` · `recall` |
| 1 | **marketing-ideate** | agent generates falsifiable bets → backlog | `add` (· `ideate` fallback) |
| 2 | **marketing-backlog** | pick the next bet (60/40 explore/exploit) | `backlog` |
| 3 | **marketing-deploy** | produce+publish via film-maker, then link | `studio run` · `link` |
| 4 | **marketing-measure** | score virality vs the channel (wait 48-72h) | `measure` |
| 5 | **marketing-learn** | reflect → update strategy + seeds | `strategy` (· `learn` fallback) |
| — | **marketing-report** | write the growth brief to disk | `report` |
| ref | **marketing-memory** | how the journal/recall/phases persist | — |

**Design rule:** the *thinking* (what to make, which bet, what was learned) is the **agent's**,
done in the skills; the `studio marketing` CLI commands are **helpers** — pure I/O for persistence
(`add`/`strategy`), retrieval (`recall`/`backlog`/`journal`), and deterministic work (`link`,
`measure`). `ideate`/`learn` keep scripted LLM fallbacks for quick non-agent passes.

## Run the whole loop

1. **marketing-journal** — read the current phase + direction first.
2. **marketing-ideate** — web-search trends + recall winners → write bets to the backlog.
3. **marketing-backlog** — pick the next bet per 60/40 (all-explore in cold-start).
4. **marketing-deploy** — produce + publish (film-maker), sized to the per-video budget, then link.
5. **wait 48-72h+** for watch time to accrue.
6. **marketing-measure** → **marketing-learn** — score, then reflect into strategy.
7. Back to 1 — now exploiting what won. **marketing-report** snapshots the cycle.

**The cold-start rule:** relative virality is meaningless until ~10 videos exist. Deploy the
first **10 as diverse EXPLORATION bets**; only then does `measure` rank winners and `learn` start
exploiting. The journal tracks the phase automatically.

Everything is **per-channel** — pass `--channel <name>` (mirrors the publish OAuth token
`token_<name>.json`). Omit for the default journal.

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
- **marketing-memory** skill + [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md) — how memory works.
- [`references/loop.md`](references/loop.md) · [`references/scoring.md`](references/scoring.md) · [`references/analytics.md`](references/analytics.md) · [`references/trends.md`](references/trends.md).
- Architecture + full command reference: [`docs/50-marketing/`](../../../docs/50-marketing/).
- Producing videos: the **film-maker** skill. Why this shape: [`docs/20-research/self-improving-loop.md`](../../../docs/20-research/self-improving-loop.md).
</content>
