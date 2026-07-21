# Guerrilla Marketing — Design

**Date:** 2026-07-18
**Status:** Approved, ready for implementation planning

## Purpose

Attract subscribers to the PARADOX NOIR channel indirectly, by posting a small number of
high-quality, on-topic comments per day under other creators' new videos. The comment never
promotes the channel; its only job is to be interesting enough that readers click the
commenter's name.

This is gray-hat. Automated commenting is spam under YouTube policy, and comments posted via
the Data API carry the OAuth client id, so they are attributable. The design accepts that risk
and spends most of its complexity on reducing it.

## Scope Decisions

| Decision | Choice | Reason |
|---|---|---|
| Commenting identity | Main channel (PARADOX NOIR) | Best conversion — click name goes straight to the videos. Ban risk lands on the real asset, so rate discipline and the circuit breaker carry the load. |
| Discovery | Hybrid: curated watchlist + weekly search sweep | Watchlist polling costs 1 quota unit per channel and catches uploads within minutes. The sweep proposes new channels; the watchlist compounds. |
| Ranking | Hard gates + sort by channel median views | Cannot calibrate a learned score with zero data. All raw features are recorded from day one so a scoring model or bandit is trainable later without backfill. |
| Comment gate | Tiered: auto-post / Telegram queue / skip | Hands-off in the clear cases, human in the borderline ones, and approve-reject decisions become labeled data for the threshold. |
| Measurement | Proxy optimization plus periodic switchback | Per-comment attribution does not exist. Comment likes and replies give daily feedback; the switchback answers whether the bot is worth running at all. |

Separate from autopilot. Shares only the OAuth credentials helper in
`studio/providers/publish.py`.

## Measurement Ceiling

Stated plainly, because it constrains everything downstream.

Measurable per comment via `commentThreads.list` on our own comment ids: likes, replies,
creator heart, pinned, and survival status (live / deleted / held for review).

**Dislikes are not available.** YouTube removed public dislike counts in 2021. Out of scope.

**Per-comment attribution is not available.** No referrer, no UTM, no traffic source that
distinguishes a sub who arrived via a comment from any other channel-page visitor. Which
comment produced which subscriber is not knowable, only inferable in aggregate.

Expected outcome: 12-25 comments/day yields on the order of a few thousand comment
impressions, a fraction of a percent click-through, and single-digit subscriber gains per day
at best — plausibly indistinguishable from noise. The switchback experiment exists to reach
that verdict cheaply. The bot must be cheap to shut off.

## Architecture

New Typer sub-app `studio guerrilla`, mirroring `marketing_app` in `studio/cli.py`.

```
studio/guerrilla/
  db.py         SQLite schema and queries
  watchlist.py  add/remove/score target channels; weekly sweep proposes new ones
  discover.py   poll uploads playlists, produce candidate videos
  rank.py       hard gates plus sort
  topic.py      title+description to {topic, confidence}; low confidence skips
  compose.py    LLM generates 3 variants across style tags
  critic.py     scores variants; separately calibrated from the studio content critic
  post.py       commentThreads.insert, rate discipline, cooldown, deny-list
  track.py      re-read our comments for likes/replies/survival
  experiment.py switchback scheduler and readout
  loop.py       one tick: discover, rank, compose, gate, post
```

Boundaries: `discover`, `rank`, `topic`, and `critic` are pure functions over API data,
testable from fixtures with no network. `post.py` is the only module that writes to YouTube —
a single throttle chokepoint and a single place to audit for ban risk. `critic` is swappable
without touching `compose`.

`critic.py` must not reuse the `studio/` content critic, which declines everything (see the
`studio-critic-ceiling` finding). A reused critic would jam the queue at 100 percent.

Storage: `runs/_guerrilla/<channel>/guerrilla.db`, plus an exported `report.md`. SQLite rather
than the JSON ledger used by `studio/marketing/journal.py`, because every effectiveness
question this system asks is a GROUP BY.

### CLI

```
studio guerrilla watchlist add|list|sweep  --channel pilot-channel
studio guerrilla tick [--dry-run]
studio guerrilla run --daemon
studio guerrilla track
studio guerrilla report
studio guerrilla queue
```

## Data Model

```sql
channels
  channel_id PK, title, subs, median_views, upload_freq,
  topic_tags, status(active|paused|banned_us|rejected),
  added_at, added_by(seed|sweep|manual), last_commented_at

videos
  video_id PK, channel_id FK, title, description, published_at,
  seen_at, age_at_seen_min, comment_count_at_seen, view_count_at_seen,
  topic, topic_confidence,
  decision(posted|skipped_topic|skipped_gate|skipped_critic|queued),
  skip_reason

comments
  comment_id PK, video_id FK, text, variant_rank, critic_score,
  critic_breakdown JSON, style_tag, posted_at,
  first_comment BOOL, comment_position_at_post

comment_metrics
  comment_id FK, checked_at, likes, replies, hearted, pinned,
  status(live|deleted|held|unknown)

channel_daily
  date PK, subs_gained, views, channel_page_views,
  comments_posted, switchback_state(on|off), published_video BOOL
```

`videos` records skips as well as posts. Without them, skip rate by reason is invisible and
the gates can never be tuned — only survivors would ever be seen.

`channel_daily.published_video` is the confounder flag. Switchback readouts exclude days with
an upload, or the video's own subscriber spike swamps any comment effect.

`comments.style_tag` (`provocative_question`, `joke`, `contrarian_take`, `insight`) is the
grouping key for the effectiveness report, and the arm definition if a bandit is added later.

## The Tick

Runs every 20-40 minutes, jittered.

1. **discover** — poll uploads playlists of active watchlist channels via `playlistItems.list`
   (1 unit each). Insert new videos.
2. **rank** — gates: video age under 90 minutes, existing comments under 40, channel median
   views above 5,000, comments enabled, channel not on cooldown, daily cap not reached. Sort
   survivors by channel median views. Record every rejection with its reason.
3. **topic** — LLM reads title and description, returns `{topic, confidence}`. Below the
   confidence threshold the video is skipped as `skipped_topic`. Unclear subject matter is
   never guessed at.
4. **compose** — 3 variants across different style tags.
5. **critic** — scores each variant on on-topic, provocative-or-funny, not-generic,
   no-self-promo, not-offensive. High scores auto-post; borderline go to the Telegram queue;
   low scores skip the video.
6. **post** — insert the comment, record its position, sleep.

## Rate Discipline and Ban Rails

Enforced in `post.py`, the single write chokepoint.

- Daily cap configurable 10-25. Default 12; ramp only after two clean weeks.
- Minimum 12 minutes between comments, jittered plus or minus 40 percent. Never a fixed cadence.
- Active window matching a plausible human timezone, roughly 09:00-23:00 local. No 04:00 posting.
- At most one comment per target channel per 72 hours.
- Near-duplicate rejection: a candidate comment too similar to the last 200 posted (shingle or
  embedding similarity above threshold) is discarded. Near-duplicate text is what YouTube's
  spam filter actually matches on.
- Deny-list enforced in code, not entrusted to the LLM: no links, no channel name, no "check
  out", no emoji spam.
- Blackout window: no comments within 6 hours either side of our own publish. Keeps switchback
  days readable and separates comment-driven visitors from upload-driven ones.

### Circuit Breaker

`track` runs twice daily. If comment survival rate over the trailing 50 comments falls below
85 percent, the loop auto-pauses and sends a Telegram alert.

This is the most important ban defense in the design. Rate limits reduce risk; only the
breaker responds to it. Mass deletion or held-for-review status is the leading indicator of a
shadowban, and catching it at 15 percent attrition is materially different from discovering it
at 100 percent.

## Experiment Design

Switchback, enabled by default for the first 8 weeks: 4 days on, 2 days off.

The 2:1 imbalance means the off-state baseline accumulates at half the rate of the on-state,
so the readout needs roughly 8 weeks rather than 6 to reach comparable confidence. Accepted in
exchange for more posting days.

Days flagged `published_video` are dropped from the readout. Comparison metric is subscriber
gain rate in publish-free windows, with `channel_page_views` as a supporting signal.

Daily optimization targets the measurable proxies — comment likes, replies, survival rate —
grouped by `style_tag` and channel tier. The switchback validates that the proxy actually
moves subscribers.

## Error Handling

| Failure | Response |
|---|---|
| 403 `commentsDisabled` | Mark the video, skip, no retry. |
| 403 `forbidden` / `ineligible` | Hard stop the loop and alert. This is the ban signal. |
| 429 or quota exceeded | Pause until quota reset at midnight Pacific, then resume. |
| SSL or transient 5xx | One retry, then read back to verify before retrying again. A blind retry double-posts, and double-posting is itself a spam signal. Same trap as the upload ghost-success failure mode. |
| LLM emits self-promo despite the prompt | Deny-list in `post.py` discards the comment; incident logged. |
| Watchlist channel deleted or made private | Set `status=paused`; do not retry daily. |

Quota budget: default 10,000 units per day. `playlistItems.list` costs 1 unit,
`commentThreads.insert` 50, `search.list` 100. Posting is cheap; discovery must stay on
watchlist polling, with search reserved for the weekly sweep.

## Testing

- `discover`, `rank`, `topic`, and `critic` tested as pure functions over recorded API JSON in
  `tests/fixtures/guerrilla/`, covering the full gate matrix.
- `post.py` tested against a fake YouTube client, asserting each rail: daily cap, per-channel
  cooldown, jitter bounds, deny-list, blackout window, near-duplicate rejection.
- One integration test running a full tick end to end against the fake client.
- `experiment.py` readout tested against synthetic `channel_daily` data with a known injected
  effect — verifying both that it detects a real signal and that it reports null when there is
  none. The second case is the one that matters, given the likely outcome.
- Manual gate before the first live post: `studio guerrilla tick --dry-run` prints the twelve
  comments it would post. Ship only after a dry-run batch worth attaching the channel name to.

## Out of Scope

- Per-comment subscriber attribution (not technically possible).
- Dislike tracking (removed from the API).
- Reply threads and conversation follow-up on our own comments.
- Learned ranking model and bandit targeting — deferred until the data exists, which the schema
  provides for.
