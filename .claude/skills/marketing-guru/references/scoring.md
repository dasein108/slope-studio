# Virality scoring

Code: `studio/marketing/score.py`. Two layers — an absolute composite per video, then a
percentile rank within the channel's portfolio (the real verdict).

## Absolute composite — `virality(metrics)`

```
score = 0.5 · log10(velocity + 1)          # views/day, log-damped (one whale ≠ 10×)
      + 0.2 · retention/100                  # averageViewPercentage (0 if no scope)
      + 0.2 · min(engagement·20, 1)          # (likes+comments)/views, ~5% saturates
      + 0.1 · min(subs_conv·50, 1)           # subs_gained/views, ~2% saturates
```
- **velocity = views / age_days** — the closest proxy to "spreading fast". Log-damped so a
  single viral spike doesn't drown out the pattern across many videos.
- **retention** guards against junk reach (thumbnail/hook bait that nobody watches).
- **engagement** and **sub-conversion** reward videos that *do something* to the viewer.
- Missing signals degrade gracefully (retention/subs → 0 contribution), so the score still
  works on the readonly scope alone.

## Relative verdict — `relativize(scores)` + `outcome(...)`

Each video's composite is converted to a **percentile (0–100) within this channel's
measured set**. Then: `≥P75 → win`, `≤P25 → loss`, else `neutral`. While in cold start
(`< BOOTSTRAP_TARGET = 10` deployed) every video is tagged `cold-start` — no verdict,
because there's no trustworthy baseline.

This is deliberate: "viral" is **relative to your own median**, not an absolute view count.

## Tuning

The weights (`W_VELOCITY`, `W_RETENTION`, …) and thresholds (`WIN_PCTILE`, `LOSS_PCTILE`)
are heuristics at the top of `score.py`. Once a channel has 20–30 videos, inspect whether
the composite agrees with intuition and adjust:
- Shorts channels live or die on **retention** → consider raising `W_RETENTION`.
- Channels optimizing for subscriber growth → raise `W_SUBS`.
- If everything clusters as `neutral`, widen the win/loss percentile gap.

After changing weights, re-run `studio marketing measure` to rescore the whole portfolio.
