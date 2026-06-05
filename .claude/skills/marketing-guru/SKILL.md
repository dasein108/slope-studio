---
name: marketing-guru
description: >
  Viral-growth operator for Slope Studio channels. Use when the user wants to grow a
  YouTube Shorts / TikTok channel: brainstorm viral/trending ideas + hooks, decide what
  to make next, fetch published-video stats and audience comments, measure how viral a
  video was relative to the channel, learn what works, and run the ideate→deploy→measure→
  learn growth loop. Pairs with the `film-maker` skill (it produces/publishes; this
  decides WHAT to make and judges how it did). Also: web-search trends, narratives, and
  hot themes to seed new ideas.
---

# marketing-guru — the viral growth loop

Your job is to make a channel go viral by running a **closed feedback loop** backed by
a persistent **journal** (`runs/_marketing/<channel>/journal.json`). You don't guess
once — you bet, deploy, measure against the channel's own history, learn, and bet again.

```
   ┌──────────────────────────────────────────────────────────────┐
   │  1 IDEATE   viral idea + hook + ASSUMPTION + goal  → journal   │
   │  2 DEPLOY   produce + publish via film-maker       → link run  │
   │  3 MEASURE  stats + comments → virality vs portfolio          │
   │  4 LEARN    confirm/refute assumption → next direction ───┐    │
   └──────────────────────────────────────────────────────────│────┘
                          ▲                                     │
                          └─────────────────────────────────────┘
```

**The cold-start rule:** relative virality is meaningless until the channel has a
baseline. Deploy the **first ~10 videos as diverse EXPLORATION bets** (vary theme, hook
style, emotion). Only after `BOOTSTRAP_TARGET` (10) videos does `measure` rank winners
vs losers and `learn` start exploiting. The journal tracks this phase automatically.

Everything is **per-channel** — pass `--channel <name>` (mirrors the publish OAuth token
`token_<name>.json`). Omit for the default journal.

## 0. Setup check

```bash
cd /Users/dasein/dev/slope-studio
source .venv/bin/activate 2>/dev/null || { uv venv && source .venv/bin/activate && uv pip install -e ".[fal,youtube]"; }
studio marketing --help
studio yt-channel --channel <name>   # confirm WHICH channel the token points at
```
Reading stats/comments needs the `youtube.readonly` scope publishing already grants — no
re-auth. **Retention/watch-time** needs one extra scope; it's fetched best-effort and the
loop runs fine without it. To unlock it see [`references/analytics.md`](references/analytics.md).

## 1. IDEATE — make the next bet

Before generating, **gather live signal** so ideas ride current narratives, not stale
training data. Use your `WebSearch` tool (and Context7 for any platform/API specifics):
- trending formats + hooks on YouTube Shorts / TikTok in the channel's niche,
- hot themes, news pegs, seasonal narratives, rising search terms,
- what comparable channels are blowing up with this week.

Write a short bullet list of those signals to a file, then feed it in:

```bash
# (skill writes /tmp/signals.md from your web search, then:)
studio marketing ideate --channel <name> --provider gpt-4o-mini \
  --signals /tmp/signals.md --niche "unusual knowledge: science, mystery, cosmos" --n 3
```
Each idea becomes a `planned` journal entry holding the **idea, hook, assumption
(why it should go viral), and goal**. The command prints a ready-to-run `studio run …`
deploy line per idea. No LLM key → it still emits solid fallback bets.

In **cold start** ask for diversity (`--n 3` across different themes). Once optimizing,
`ideate` automatically leans on the learned winning patterns + `next_seeds`.

## 2. DEPLOY — produce + publish, then link

Hand the deploy command to the **`film-maker` skill** (it owns the pipeline). Typical:

```bash
studio run "<the idea>" --duration 60 --tier cheap \
  --publish-to youtube --privacy public --channel <name>
```
Capture the run id, then bind it to the journal bet so measurement can find the video:

```bash
studio marketing link <entry_id> <run_id> --channel <name>
# pulls the YouTube video id from runs/<run_id>/07_publish.json automatically
```
Repeat 1–2 until ~10 videos are live (the cold-start portfolio).

## 3. MEASURE — score virality relative to the channel

```bash
studio marketing measure --channel <name>
```
Fetches views/likes/comments (+ retention & subs if scoped), computes a **virality
composite** (log-damped view-velocity + retention + engagement + sub-conversion), then
**ranks every video into a percentile within this channel's own portfolio** and tags each
`win` (≥P75) / `loss` (≤P25) / `neutral` / `cold-start`. Writes back to the journal and
drops `08_stats.json` + `08_comments.json` into each run dir. Scoring details + how to
tune the weights: [`references/scoring.md`](references/scoring.md).

## 4. LEARN — confirm/refute the assumption, steer next

```bash
studio marketing learn --channel <name> --provider gpt-4o-mini
studio marketing journal --channel <name>      # see strategy + every bet's outcome
```
The LLM compares each bet's **pre-stated assumption** against its measured virality +
top audience comments, then updates the journal's `Strategy`: `winning_patterns`,
`losing_patterns`, `current_direction`, and `next_seeds`. Those feed straight back into
step 1 — the loop tightens each cycle. `report` writes the whole brief to
`runs/_marketing/<name>/report.md`.

## Driving the whole loop (what you actually do)

1. `studio marketing journal --channel X` — read the current phase + direction first.
2. **Web-search** trends → write signals file.
3. `studio marketing ideate … --signals …` — record bets.
4. For each bet: invoke **film-maker** to `studio run … --publish-to youtube`, then
   `studio marketing link`.
5. Wait for real watch time to accrue (give Shorts **48–72h+** before judging — see
   [`references/loop.md`](references/loop.md) for cadence).
6. `studio marketing measure` then `studio marketing learn`.
7. Back to 1 — now exploiting what won.

**Always report:** the channel's phase (cold-start N/10 vs optimizing), the latest
winners/losers with their assumptions (held or refuted), the current direction, and the
next concrete bets. Be honest when a bet's assumption was **refuted** — that's the point.

## Deeper references (read before non-trivial work)
- [`references/loop.md`](references/loop.md) — the full loop, cold-start strategy, cadence, exploration vs exploitation.
- [`references/scoring.md`](references/scoring.md) — virality composite, percentiles, tuning weights.
- [`references/analytics.md`](references/analytics.md) — YouTube scopes, retention re-auth, quota, what each metric means.
- [`references/trends.md`](references/trends.md) — how to web-search trends/narratives and turn them into a signals file.
- Architecture + commands reference: [`docs/50-marketing/`](../../../docs/50-marketing/).
- Producing the videos: the **`film-maker`** skill.
