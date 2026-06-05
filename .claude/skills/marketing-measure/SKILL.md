---
name: marketing-measure
description: >
  Use to fetch a channel's published-video stats + comments and score each deployed bet's
  virality RELATIVE to the channel's own portfolio. Deterministic (YouTube API + math), not
  agent-judged. Run 48–72h+ after publishing. One lego-block of the growth loop; precedes
  marketing-learn.
---

# marketing-measure — score virality vs the channel

A deterministic step (good as a script — it's API I/O + fixed math). Run it, then read the
results; the interpretation/learning is **marketing-learn**.

## Do this

```bash
studio marketing measure --channel <name> --comments-n 60
```
Fetches views/likes/comments (+ retention & subs gained if the analytics scope is granted),
computes a **virality composite** (log-damped view-velocity + retention + engagement +
sub-conversion), ranks every video into a **percentile within this channel's own portfolio**,
and tags each `win` (≥P75) / `loss` (≤P25) / `neutral` / `cold-start`. Writes back to the
journal and drops `08_stats.json` + `08_comments.json` into each run dir.

## Watch for
- **Wait for watch time** — measuring same-day gives noise. 48–72h+ minimum.
- **Cold-start (<10 deployed):** percentiles are meaningless; every outcome is `cold-start`.
- **Retention/subs** need one extra OAuth scope; fetched best-effort, loop runs fine without.
  See [`../marketing-guru/references/analytics.md`](../marketing-guru/references/analytics.md).
- **Scoring weights** (0.5 velocity / 0.2 retention / 0.2 engagement / 0.1 subs) are slated to
  be re-tuned to a retention-first order per research finding F-SI9 — see
  [`docs/20-research/self-improving-loop.md`](../../../docs/20-research/self-improving-loop.md)
  and [`../marketing-guru/references/scoring.md`](../marketing-guru/references/scoring.md).

## Memory touched
Writes `metrics`, `virality`, `percentile`, `outcome`, `comments_sample`, `status: measured`
onto each deployed entry. Full model: **marketing-memory** /
[`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
</content>
