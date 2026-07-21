# Architecture

Everything below lives in `studio/guerrilla/` (one module per responsibility) plus the
`studio guerrilla` Typer sub-app in `studio/cli.py`. See [`README.md`](README.md) for the
one-paragraph pitch and [`operations.md`](operations.md) for how to run it.

## Modules

| Module | Responsibility |
|---|---|
| `db.py` | SQLite store (`runs/_guerrilla/<channel>/guerrilla.db`), schema for 6 tables |
| `client.py` | Builds the authorized YouTube Data API resource |
| `watchlist.py` | The target-channel list + a 72h per-channel cooldown |
| `discover.py` | Polls watchlist channels' uploads playlists for candidate videos |
| `rank.py` | Hard gates (age, comment count, channel size, cooldown, comments-enabled) + sort |
| `transcript.py` | Fetches + caches video transcripts; the foundation for grounding |
| `topic.py` | Classifies a video's subject; skips rather than guesses when unclear |
| `highlight.py` | Picks the single most comment-worthy verbatim moment in a transcript |
| `compose.py` | Generates comment variants that react to that moment |
| `critic.py` | Scores variants; three criteria are disqualifying, not just averaged |
| `rails.py` | Pure ban-defense predicates — deny-list, near-duplicate, spacing, timing |
| `post.py` | The ONLY module that writes to YouTube; every rail is re-checked here |
| `track.py` | Re-reads posted comments; the shadowban circuit breaker |
| `experiment.py` | The switchback (4-on/2-off) schedule and readout |
| `rollup.py` | Populates `channel_daily` from the YouTube Analytics API |
| `report.py` | Renders effectiveness by style tag, skip reasons, and the switchback verdict |
| `loop.py` | The tick — orchestrates every module above, in a specific order |

`discover`, `rank`, `topic`, and `critic` are pure functions over API data — testable from
fixtures with no network. `post.py` is the single throttle chokepoint: nothing else calls
`commentThreads.insert`, so there is exactly one place to audit for ban risk. `critic` is
deliberately **not** the `studio/stages/critic.py` content critic used by the video pipeline —
that one is calibrated to decline nearly everything, which is fine for a single video render
and fatal for a gate that has to pass roughly a dozen comments a day.

## Pipeline order is a cost contract

```
discover → rank → transcript → topic → highlight → compose → critic → rails → post
```

The order is not incidental — each stage is more expensive than the last, so a candidate that's
going to fail should fail as early and as cheaply as possible:

1. **The circuit breaker is checked first**, before anything else runs, so a suspected
   shadowban stops the tick before it can make things worse.
2. **`transcript` runs before any LLM call.** It's a cached network read, not a model call, so
   a video with no captions must be skippable at zero LLM cost.
3. **`topic` runs next**, using an excerpt of that same transcript, so a video whose subject is
   unclear costs only one LLM call rather than the four or five a full pass (highlight + compose
   + critic) would run up.
4. **`highlight` runs only once topic passes** — it's itself several LLM calls on a long video
   (see below), so it must not run on videos that are about to be skipped anyway.
5. **`compose` and `critic` run last**, and both receive the found moment/excerpt so generated
   comments react to something the video actually said, not a paraphrase of its title.

If the critic's #1-ranked variant is blocked by a rail for a reason specific to *that variant*
(near-duplicate text, a repeated opening, an over-used style tag), the tick falls through to the
next-best `auto`-decision variant instead of abandoning the video — `compose` already paid for
several variants with different wording and different style tags for exactly this reason. A
reason that depends on *when* the tick runs rather than what the comment says (channel cooldown,
outside the active window, a publish blackout) leaves the video's fate as-is so a later tick can
reconsider it — except the daily cap, which ends the tick immediately. A reason nothing about a
later tick can fix (a deny-list hit, or every variant exhausted) retires the video permanently as
`skipped_gate`.

The spacing rail allows at most one successful post per tick, so a successful post ends the
candidate loop immediately: trying another candidate afterward could only pay for LLM calls on a
post that rail is guaranteed to block anyway. `rank.rank_candidates` also checks this once, up
front, before any candidate is even considered — at cron cadences shorter than the rail's widest
jittered gap, skipping that pre-check would mean every candidate in the tick pays for three LLM
calls only to be blocked at the very end.

## The gates (`rank.py`)

Deliberately not a learned score — there's no data to calibrate one on day one. The gates
encode the real constraint that a comment on a huge channel's video lands hundreds deep and is
invisible, so "biggest channel" is the wrong target. Every raw feature is recorded regardless of
outcome, so a scoring model or bandit could be trained later without a backfill.

| Gate | Default | Reason |
|---|---|---|
| `max_age_min` | 90 minutes | early enough to hold a visible slot among top comments |
| `max_comments` | 40 | past this, a new comment is buried in the thread |
| `min_median_views` | 5,000 | below this there's no audience to reach |
| comments enabled | — | can't post if disabled |
| channel not on cooldown | 72h | see `watchlist.on_cooldown` |
| daily cap not reached | 12 (10–25 configurable) | see below |

Gate checks run **before** any LLM call — `evaluate()` returns `(passed, reason)` and a
candidate that fails is recorded with its reason (except the time-varying ones below, which are
left `pending` so a later tick can reconsider once the condition clears): `inactive_window`,
`daily_cap`, and `channel_cooldown`. Everything else — `too_old`, `too_many_comments`,
`channel_too_small`, `comments_disabled` — is a permanent verdict; a video's age only increases,
so `too_old` in particular never becomes true again on its own (see the tuning note in
[`operations.md`](operations.md#tuning-the-age-window)).

## Transcript grounding (`transcript.py`, `highlight.py`)

`transcript.py` fetches and normalizes captions via `youtube-transcript-api`, an unofficial
scraper with no support contract — every failure (no captions, a network hiccup, a
library-version shape change) collapses to "no transcript" rather than raising, so callers never
need their own try/except. Results are cached per video in the `transcripts` table; a present
row (even with empty `segments`) means "already tried," so a caption-less video isn't re-fetched
and re-failed on every tick.

Fetching can optionally route through an HTTP proxy: set `TRANSCRIPT_PROXY_URL` (e.g.
`http://user:pass@host:port`) in `.env`. Some networks and datacenter IPs are rate-limited or
blocked by YouTube for caption scraping, so a long-running loop deployed somewhere with that
problem may need one. Left unset, transcripts are fetched directly — fine for occasional local
use.

`highlight.py` then chunks the transcript into ~4-minute windows and asks the LLM for the
single most comment-worthy moment in each, keeping the highest-scoring one across the whole
video. Each candidate moment gets a **citability** score (0–5): how self-contained is it — could
a stranger scrolling the comments understand the reference without having watched the video? The
`quote` field must be copied verbatim from the transcript so a later rail (`bad_timestamp`) can
verify it. Whether a comment is *allowed* to cite the timestamp out loud is a separate, narrower
decision — `should_cite()` requires citability ≥ 4.0 **and** the tick's `--cite-timestamps` flag,
which defaults **off**: found timestamps cluster near the video start regardless of where the
quoted content actually is, and phrasing like "at 0:0X, when he says…" became a detectable
template on its own. The moment still drives what the comment reacts to either way — the flag
only controls whether the reaction is allowed to name a time.

## Composition and the critic

### `compose.py`

Generates several comment variants (`STYLE_TAGS`: `provocative_question`, `joke`,
`contrarian_take`, `insight`), each under 280 characters (longer comments collapse behind "Read
more" and lose their pull). The prompt is long and specific because the failure mode is
templating, not off-topic content: it explicitly bans the two rhetorical molds that read as bot
tells on YouTube — the "If X, then Y?" / "What if…" opener, and the softer "hedged-reviewer"
voice ("really challenges conventional understanding…", "it raises the question of…"). When a
grounded `Moment` from `highlight.py` is supplied, the prompt instructs the model to react to
that one real thing rather than summarize the video's thesis.

### `critic.py`

Scores each variant 0–5 on six criteria — `on_topic`, `provocative_or_funny`, `not_generic`,
`no_self_promo`, `not_offensive`, and (only when a transcript excerpt is available) `grounded`.
Three of those are **disqualifying** rather than averaged into the mean: `no_self_promo`,
`not_offensive`, and `grounded`. A comment that promotes the channel, insults someone, or
fabricates a specific about the video isn't "below average" — it's unpostable regardless of how
well everything else scores.

| Threshold | Value | Decision |
|---|---|---|
| mean score | ≥ 4.0 | `auto` — eligible to post automatically |
| mean score | ≥ 3.0 | `queue` — held for human review (`guerrilla queue`/`approve`) |
| mean score | < 3.0, or any disqualifying criterion < 3.0 | `skip` |

`grounded` only enters the prompt (and therefore the mean, and the disqualify check) when a
transcript excerpt is actually supplied — without one, behavior is identical to the pre-grounding
critic. When present, it checks every factual claim the comment makes against the excerpt as
ground truth; a comment that asserts a specific number, name, or quote the excerpt doesn't
support scores 0 with no partial credit.

## Rails — the ban defense (`rails.py`, `post.py`)

`rails.py` is deliberately pure predicates with no network dependency, so every rule is
exhaustively testable. `post.py` is the only caller, and it re-checks every rail immediately
before the insert — the same rail is evaluated once (cheaply, at rank/dry-run time to filter
candidates) and then again at the actual write, since state can change between the two.

| Rail | Rule |
|---|---|
| Deny-list | code-enforced regexes for links, the channel's own name/aliases, self-promo phrases, hashtags, emoji spam — never entrusted to the LLM's instructions alone |
| Near-duplicate | word-shingle Jaccard similarity ≥ 0.3 (or ≥ 0.5 on short text, which falls back to character bigrams) against the last 200 posted comments |
| Repeated opening | first 4 words match a recent comment's opening — catches a bot reusing the same sentence scaffold even when the rest of the text differs enough to dodge near-duplicate detection |
| Style overused | the same `style_tag` appears twice or more in the last 5 posts — forces rotation across the four tags |
| Active window | comments only post 09:00–23:00 UTC — a 04:00 post reads as a bot |
| Publish blackout | no comments within 6 hours either side of the channel's own uploads, so comment-driven visitors stay separable from upload-driven ones (this is what makes the switchback readout interpretable) |
| Minimum spacing | ~12 minutes between comments, jittered ±40% — never a fixed cadence |
| Timestamp verification | a comment that cites a timestamp is rejected unless a transcript segment actually exists near that time (only engages when citation is on, which is off by default) |
| Per-channel cooldown | at most one comment per target channel per 72 hours |

`too_similar` and `_negates` are worth noting specifically: two texts that differ only by a
negation ("makes sense" vs "makes no sense") score high on shingle overlap but mean the opposite
thing, so the near-duplicate check explicitly excludes negation flips from counting as a
duplicate.

## Circuit breaker (`track.py`)

Survival rate is the single most important number this system produces: rate limits reduce ban
risk, but only the breaker actually **responds** to evidence of one. Comments quietly deleted or
held for review is what a shadowban looks like from the outside, and catching it at 15%
attrition is a very different outcome from finding it at 100%.

- `track` re-reads the most recent posted comments' status via `commentThreads.list`: `live`,
  `deleted` (absent from the response), or `held`.
- `survival_rate()` is the fraction still `live` over a trailing window of 50.
- Below **85%** survival, with at least **10** comments tracked (a single deletion out of one or
  two shouldn't trip anything — that's noise, not a mass removal), the breaker trips: it's
  persisted so the alert fires once per trip rather than repeatedly, a Telegram notification goes
  out, and `tick` / `approve` both refuse to post while it's tripped.
- Clearing it is **manual only** (`guerrilla resume`) — an auto-clear once the rate recovers
  would defeat the point of stopping to investigate.

## Switchback experiment (`experiment.py`, `rollup.py`)

Per-comment attribution doesn't exist — YouTube exposes no referrer that distinguishes a
subscriber who arrived via a comment from any other channel-page visitor. So causality has to
come from turning the whole system on and off and comparing subscriber gain across the two
states.

- **Schedule:** 4 days on, 2 days off (`ON_DAYS` / `OFF_DAYS`), gated by an
  `--experiment-start` date passed to `tick`. On an off day the tick short-circuits before doing
  anything.
- **Why the 2:1 imbalance:** it favors more posting days, at the cost of the off-state baseline
  accumulating more slowly — a readable answer takes roughly 8 weeks rather than 6.
- **Minimum sample:** `MIN_DAYS_PER_ARM = 20`. Below 20 days in either arm, `readout()` reports
  `insufficient_data` rather than a number — the plain percentile bootstrap's false-positive rate
  only approaches nominal once each arm has close to 20 days.
- **Confound control:** `channel_daily.published_video` flags days with one of the channel's own
  uploads; those days are dropped from the comparison entirely, because a fresh upload's own
  subscriber spike would otherwise swamp any comment effect.
- **Contamination check:** an off day with `comments_posted > 0` means the tick ran anyway (the
  calendar gate wasn't actually wired into that run) — such days are excluded and counted
  separately as `contaminated_days` rather than silently comparing two "on" populations while
  labeling one of them "off".
- **Readout:** a bootstrap 95% CI on the difference in mean subscribers/day between the on and
  off arms. `positive` if the CI's low bound is above zero, `negative` if the high bound is below
  zero, otherwise `null`. A null verdict is treated as a real, useful, and expected answer, not a
  failure — the module's whole purpose is to report that honestly rather than to manufacture an
  effect.
- **Populating it:** `rollup` pulls daily views/subscribers from the YouTube Analytics API
  (`youtubeAnalytics v2`, a different service and scope from the Data API used everywhere else)
  and writes `channel_daily` rows. Without running it, `experiment.readout` always reports
  `insufficient_data`.

## Data model (`db.py`)

SQLite (`runs/_guerrilla/<channel>/guerrilla.db`) rather than the JSON ledger the video-marketing
loop uses — every effectiveness question this system asks ("which style earns likes?", "which
channel tier converts?") is naturally a `GROUP BY`.

| Table | Key columns | Purpose |
|---|---|---|
| `channels` | `channel_id` PK, `title`, `subs`, `median_views`, `status`, `last_commented_at`, `uploads_playlist` | the watchlist |
| `videos` | `video_id` PK, `channel_id` FK, `published_at`, `age_at_seen_min`, `comment_count_at_seen`, `topic`, `topic_confidence`, `decision`, `skip_reason` | every candidate seen, posted or not |
| `comments` | `comment_id` PK, `video_id` FK, `text`, `variant_rank`, `critic_score`, `critic_breakdown` (JSON), `style_tag`, `posted_at`, `first_comment`, `comment_position_at_post` | every comment actually posted |
| `comment_metrics` | `(comment_id, checked_at)` PK, `likes`, `replies`, `hearted`, `pinned`, `status` | survival + engagement history from `track` |
| `channel_daily` | `date` PK, `subs_gained`, `views`, `comments_posted`, `switchback_state`, `published_video` | the switchback's raw material |
| `breaker_state` | single row: `tripped`, `tripped_at`, `rate_at_trip` | circuit breaker persistence |
| `transcripts` | `video_id` PK, `fetched_at`, `duration`, `segments` (JSON) | transcript cache |

`videos` deliberately records skips alongside posts — without that, only survivors would ever be
visible and the gates could never be tuned. `decision` moves through
`pending → posted | queued | skipped_topic | skipped_gate | skipped_critic`.

## Where to go next

[`operations.md`](operations.md) covers running all of this day to day; [`deploy.md`](deploy.md)
covers pushing it to a remote VPS.
