---
name: marketing-measure-learn
description: >
  Use 48–72h+ after publishing to CLOSE the loop: first MEASURE (fetch stats + comments, score
  each deployed bet's virality relative to the channel's own portfolio — deterministic), then
  LEARN (reflect on which pre-stated assumptions held vs were refuted, extract win/lose patterns,
  set the next direction + idea seeds — agent-driven). One lego-block of the
  ideate→deploy→measure→learn growth loop; feeds back into marketing-ideate.
---

# marketing-measure-learn — score, then steer

Measure and learn always run as a pair: first get the numbers (a deterministic API + math
step), then reflect on them (agent judgement). Do them in order.

## Step 1 — MEASURE (deterministic)

```bash
studio marketing measure --channel <name> --comments-n 60
```
Fetches views/likes/comments (+ retention & subs gained if the analytics scope is granted),
computes a **virality composite** (log-damped view-velocity + retention + engagement +
sub-conversion), ranks every video into a **percentile within this channel's own portfolio**,
and tags each `win` (≥P75) / `loss` (≤P25) / `neutral` / `cold-start`. Writes back to the
journal and drops `08_stats.json` + `08_comments.json` into each run dir.

Watch for:
- **Wait for watch time** — measuring same-day gives noise. 48–72h+ minimum.
- **Cold-start (<10 deployed):** percentiles are meaningless; every outcome is `cold-start`.
- **Retention/subs** need one extra OAuth scope; fetched best-effort, the loop runs fine
  without. See [`../marketing-guru/references/analytics.md`](../marketing-guru/references/analytics.md).
- **Scoring weights** (0.5 velocity / 0.2 retention / 0.2 engagement / 0.1 subs) are slated to
  be re-tuned to a retention-first order per research finding F-SI9 — see
  [`../marketing-guru/references/scoring.md`](../marketing-guru/references/scoring.md) and
  [`docs/20-research/self-improving-loop.md`](../../../docs/20-research/self-improving-loop.md).

## Step 1.5 — SNAPSHOT + SLICE (deterministic analysis)

Before changing strategy, collect age-bucket snapshots and ask the CLI for the hidden-relation
pack. This is what lets the agent compare effects/cost/theme/music/sfx/animation at consistent
ages instead of mixing a 1-day video with a 30-day video.

```bash
studio marketing due-snapshots --channel <name>
studio marketing snapshots     --channel <name> --buckets 1,3,7,14,30
studio marketing insights      --channel <name> --json
```

Use focused slices/comparisons when a pattern looks interesting:

```bash
studio marketing slice --channel <name> --bucket 7d \
  --group-by theme,effects,animators,music_provider,sfx_provider --metric virality

studio marketing compare --channel <name> effects=glitch --bucket 14d --metric virality
studio marketing compare --channel <name> animators=parallax --bucket 7d --metric retention
studio marketing compare --channel <name> music_provider=synth --bucket 3d --metric virality_per_dollar
```

Interpret these as **associations, not causation**. Always check `n`, best/worst examples, and
confounders such as topic quality, publish timing, spend, and whether the video is still too young.

## Step 2 — LEARN (agent-driven reflection)

This is where the loop self-improves. YOU reflect (assumption testing is judgement, not a
formula); the CLI just persists what you conclude.

1. **Read the measured portfolio** (best→worst) + relevant episodes:
   ```bash
   studio marketing journal --channel <name>
   studio marketing recall "<theme or direction under review>" --channel <name>
   studio marketing insights --channel <name> --json
   ```
2. **Reflect** — for each measured bet compare its **pre-stated `assumption`** against the
   measured `virality`/`percentile`/`outcome`, age-bucket snapshots, slice results, and top
   audience comments. Was it **held or refuted**? Then across the portfolio extract:
   - `winning_patterns` — traits of the ≥P75 bets,
   - `losing_patterns` — traits of the ≤P25 bets,
   - production correlations — effects/animation/music/sfx/cost formats that look promising or weak,
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
   learning. Repeat `--note` for several bets.

The strategy + seeds you write here are exactly what **marketing-ideate** reads next — the
cycle closes.

## Scripted fallback (non-agent)
For a quick non-agent reflection: `studio marketing learn --provider <llm>` runs the built-in
LLM reflection and writes the strategy. (`measure` is already a deterministic script — no
fallback needed.)

Memory model (journal / strategy / recall, who writes what): [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
