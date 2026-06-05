---
name: marketing-learn
description: >
  Use after measuring to reflect on outcomes and update a channel's strategy — which
  pre-stated assumptions held vs were refuted, what patterns win/lose, the next direction and
  idea seeds. AGENT-driven reflection persisted to the journal. One lego-block of the growth
  loop; closes the cycle back into marketing-ideate.
---

# marketing-learn — reflect, then steer

This is where the loop self-improves. YOU reflect (the assumption testing is judgement, not a
formula); the CLI just persists what you conclude.

## Do this

1. **Read the measured portfolio** (best→worst) + relevant episodes:
   ```bash
   studio marketing journal --channel <name>
   studio marketing recall "<theme or direction under review>" --channel <name>
   ```
2. **Reflect** — for each measured bet compare its **pre-stated `assumption`** against the
   measured `virality`/`percentile`/`outcome` + top audience comments. Was it **held or
   refuted**? Then across the portfolio extract:
   - `winning_patterns` — traits of the ≥P75 bets,
   - `losing_patterns` — traits of the ≤P25 bets,
   - `current_direction` — a one-paragraph thesis for what to make next,
   - `next_seeds` — 3–5 concrete idea seeds.
   Be honest when an assumption was **refuted** — that's the signal that improves the next bet.
3. **Persist** (no LLM, just I/O):
   ```bash
   studio marketing strategy --channel <name> \
     --direction "<thesis paragraph>" \
     --winning "trait a;trait b" --losing "trait c" \
     --seeds "seed 1;seed 2;seed 3" \
     --note j0007=cosmic-scale shock hooks beat soft intros
   ```
   `--winning/--losing/--seeds` are `;`-separated; `--note ENTRY_ID=text` files a per-bet
   learning. Repeat `--note` calls for several bets.

## Fallback (scripted, non-agent)
`studio marketing learn --provider <llm>` runs the built-in LLM reflection and writes the
strategy for you. Use for a quick pass without agent reasoning.

## Memory touched
Writes the long-term `strategy` (direction + winning/losing patterns + next_seeds) and per-bet
`learnings`. Those feed straight back into **marketing-ideate**. Full model:
**marketing-memory** / [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
</content>
