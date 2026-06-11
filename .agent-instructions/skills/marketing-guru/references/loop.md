# The growth loop — strategy & cadence

## Why a loop (not one-shot ideation)

A single "viral idea" is a guess. The loop turns guessing into **learning**: every video
is a falsifiable bet (idea + hook + *assumption* + goal). Measuring it against the
channel's own history tells you whether the assumption held, and that verdict steers the
next bet. Over cycles the channel converges on what *its* audience rewards — which is not
what works for some other channel.

## Two phases

### Cold start (videos 1–10) — EXPLORE
There is no baseline yet, so "viral relative to the channel" is undefined. Goal: **map
the space**. Make bets as *different* as possible — vary theme, hook archetype (question /
bold claim / countdown / "you were lied to" / visual shock), emotion (awe, fear,
curiosity, outrage), and pacing. Don't optimize; sample widely. `ideate` does this
automatically while `journal.in_cold_start` is true and tags entries `explore=True`.
`measure` marks everything `cold-start` (no win/loss verdict yet).

### Optimizing (11+) — EXPLOIT + a little EXPLORE
Once ~10 videos have real watch time, `measure` ranks them into percentiles and `learn`
extracts winning vs losing patterns. Now bias new bets toward winners — but keep **~1 in
3 as an exploration bet** into adjacent territory so the channel doesn't overfit to a
local maximum and go stale.

## Cadence (don't measure too early)

YouTube Shorts get most of their early reach in the first few days, but watch-time and
retention need a window to stabilize. **Give a video 48–72h minimum** (ideally a week)
before treating its virality score as real. Measuring an hour after upload compares a
fresh video against mature ones and produces garbage percentiles. The `age_days` term in
velocity partly compensates, but young videos are still noisy — weight recent verdicts
lightly until they age.

## What "viral" means here

Not raw views — **velocity + retention + engagement, ranked against your own median.** A
2k-view video on a 500-view channel is viral *for that channel*; the same on a 1M channel
is a flop. Relative percentile is the honest signal. See `scoring.md`.

## Anti-patterns

- **Chasing one whale.** A single mega-hit can be luck. Trust patterns across ≥3 winners.
- **Refusing to kill a thesis.** If the assumption was refuted, say so and move on — that
  is the loop working, not failing.
- **Re-deploying near-identical ideas.** `ideate` is told what's been tried; keep variety.
- **Premature optimization.** Don't exploit before the cold-start 10 are in and measured.
