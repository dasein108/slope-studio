# Operations

How to run `studio guerrilla` day to day: the one-command manual runner, the full CLI, scheduling
options, tuning the two knobs that matter most, reading the effectiveness report, and — honestly —
what quality of comment to expect from it. See [`architecture.md`](architecture.md) for why any of
this works the way it does, and [`deploy.md`](deploy.md) if you're running this from a remote VPS
rather than locally.

## The one command you need

When running against a remote VPS, `scripts/guerrilla` is the single entry point. It drives the
whole thing from your machine — each command pushes your local state to the VPS, runs there, and
pulls the updated database back, so **your machine stays the source of truth** (a wiped VPS heals
itself on the next run).

```bash
scripts/guerrilla            # post one comment now (a single tick)
scripts/guerrilla preview     # generate a review batch and post NOTHING — read it first
scripts/guerrilla posted      # list every comment you've posted, as clickable links
scripts/guerrilla track       # refresh metrics + run the shadowban circuit breaker
scripts/guerrilla report      # effectiveness by style + the switchback verdict
scripts/guerrilla --help      # everything, including CAP= / MAX_AGE_MIN= overrides
```

First time only: `cp scripts/remote/guerrilla.local.mk.example scripts/remote/guerrilla.local.mk`,
set your `REMOTE_HOST` + `SSH_KEY` in it, then `scripts/guerrilla deploy`. That's it — after that,
`scripts/guerrilla` whenever you want a comment posted. The rest of this page is the underlying
CLI (what `scripts/guerrilla` runs on the VPS) and the details behind each step.

## Setup

Install the two optional extras this pipeline needs — `guerrilla` (transcript fetching) and
`youtube` (the Data API client):

```bash
uv pip install -e ".[guerrilla,youtube]"
# or, with uv sync:
uv sync --extra guerrilla --extra youtube
```

You need an OAuth token authorized for the channel you're posting from, with the
`youtube.force-ssl` scope (this is what permits writing comments on other people's videos) —
the same `token_<channel>.json` mechanism used by `studio publish`; see
[`../../40-publishing/youtube.md`](../../40-publishing/youtube.md) for the one-time setup.

## The CLI

Every command takes `--channel <name>`, which selects `runs/_guerrilla/<name>/guerrilla.db` and
the matching `token_<name>.json`. There is no default — always pass it explicitly.

### Watchlist

The watchlist is the compounding asset of the whole loop: polling a known channel's uploads
playlist costs 1 quota unit, discovering one by search costs 100.

```bash
studio guerrilla watchlist add <UC...channel-id> --channel <name> \
  [--title "..."] [--median-views 12000] [--tags "philosophy,paradox"]

studio guerrilla watchlist list --channel <name> [--all]   # --all also shows paused channels

studio guerrilla watchlist resume <UC...channel-id> --channel <name>
```

`discover` auto-pauses a watchlist channel (`status = paused`) if it starts returning 403/404 —
deleted, made private, or otherwise inaccessible. `watchlist resume` un-pauses it manually, e.g.
after confirming a channel that looked gone is actually back, or after a transient error paused
it in error.

### `tick` — one pass of the pipeline

```bash
studio guerrilla tick --channel <name> \
  [--cap 12]                 # daily cap, 10-25, default 12
  [--dry-run]                # do everything except post; prints every candidate comment
  [--provider ...]           # override the LLM provider for this tick
  [--experiment-start YYYY-MM-DD]   # enable switchback gating (suppressed on OFF days)
  [--cite-timestamps]        # opt in to citing the found moment's timestamp (default off)
  [--max-age-min 90]         # only consider videos younger than this many minutes
```

Runs one full `discover → rank → transcript → topic → highlight → compose → critic → rails →
post` cycle and prints a summary: `discovered=`, `considered=`, `posted=`, `queued=`, plus
`skipped:` and `blocked:` breakdowns by reason. If the circuit breaker is tripped, it prints
`PAUSED` and exits nonzero without doing anything else.

**Always run with `--dry-run` first** after any change to the composer, the critic, or the
rails, and read every proposed comment before letting a live tick post. `--dry-run` runs the
full content pipeline (topic → highlight → compose → critic → the content rails — deny-list,
near-duplicate, timestamp verification) so what you review is exactly what a live tick would
have posted; only the time-varying rails (spacing, active window, blackout, daily cap), which
depend on *when* the real tick runs rather than on the comment's content, are skipped.

### `track` — refresh survival + check the breaker

```bash
studio guerrilla track --channel <name>
```

Re-reads the most recently posted comments' likes/replies/status and prints the current
survival rate. Exits nonzero (and prints `breaker tripped`) if survival has fallen below the
threshold. Run this on its own schedule, independent of `tick` — see below.

### `resume` — clear a tripped breaker

```bash
studio guerrilla resume --channel <name>
```

Deliberately manual. Only run this after you've actually investigated why comments were removed
— a script that auto-clears once the rate happens to recover would defeat the entire point of
having a breaker.

### `report` — effectiveness

```bash
studio guerrilla report --channel <name> [--write]
```

Prints a Markdown report (see [Reading the report](#reading-the-report) below); `--write` also
saves it to `runs/_guerrilla/<name>/report.md`.

### `rollup` — populate the switchback's raw data

```bash
studio guerrilla rollup --channel <name> \
  --channel-id <your-channel's-UC...-id> \
  --start YYYY-MM-DD --end YYYY-MM-DD \
  --experiment-start YYYY-MM-DD
```

Pulls daily views/subscribers-gained from the YouTube Analytics API into `channel_daily` so
`report`'s switchback section has something to compare. Needs the `yt-analytics.readonly` scope
in addition to the Data API scopes — a one-time re-authorization if your token doesn't already
have it.

### `queue` / `approve` — the human-in-the-loop path

Comments the critic scores as borderline (mean 3.0–4.0) land in the queue instead of
auto-posting or being discarded:

```bash
studio guerrilla queue --channel <name>              # list what's waiting

studio guerrilla approve <video_id> --channel <name> [--cap 12]
```

`approve` posts the queued text through the exact same `post.post_comment` chokepoint a live
tick uses — every rail still applies, including the circuit breaker (it refuses to hand-post
through a suspected shadowban).

## Autonomous scheduling

There's no built-in daemon — `tick` and `track` are single passes meant to be scheduled
externally (cron, systemd timer, or your platform's equivalent).

**Local execution** — if the scheduling machine can reach YouTube, schedule the CLI directly:

```cron
*/30 9-22 * * * cd <deploy-dir> && uv run --extra guerrilla --extra youtube \
  studio guerrilla tick --channel <name> --cap 10 --max-age-min 1440 >> logs/tick.log 2>&1
0 6,18 * * * cd <deploy-dir> && uv run --extra guerrilla --extra youtube \
  studio guerrilla track --channel <name> >> logs/track.log 2>&1
```

**Remote execution (VPS)** — when YouTube is only reachable from a remote box, drive it with the
sync-wrapped Makefile so **your local machine stays the source of truth for the database**.
Schedule the *Makefile targets locally*; each pushes state up, execs on the VPS, and pulls the
mutated db + logs back (see [`deploy.md`](deploy.md)):

```cron
*/35 9-22 * * * cd <repo> && make -f scripts/remote/guerrilla.mk tick  >> ~/guerrilla-tick.log 2>&1
0 6,18 * * *   cd <repo> && make -f scripts/remote/guerrilla.mk track >> ~/guerrilla-track.log 2>&1
```

⚠️ Do **not** also run a cron *on the VPS* that mutates the db — it would fight the push, and the
next local operation would overwrite its work. Pick one scheduler; let local own the state.

Notes:

- The spacing rail allows at most one successful post per tick and enforces its own ~12-minute
  (±40%) minimum gap between posts, so scheduling `tick` more often than that gap doesn't post
  faster — it just spends more invocations finding nothing to do.
- `considered=0` in a tick's summary almost always means no watchlist channel has uploaded
  inside the current age window — this is normal for channels that upload weekly or less often,
  not a sign anything is broken.
- Keep `track` on its own schedule, separate from `tick` — it's what actually watches for a
  shadowban, and it should run even on days the switchback experiment suppresses posting.

## Tuning the age window and daily cap

**`--max-age-min`** controls how old a candidate video is allowed to be (default 90 minutes —
early enough to hold a visible slot before the thread fills up). If your watchlist channels
upload infrequently, a 90-minute window may rarely see a fresh video at all; widening it (e.g.
`1440` for 24 hours, or further) catches a backlog of still-quiet videos at the cost of landing
comments on slightly less-fresh threads — the `max_comments` gate (default 40) still filters out
threads that have gotten too crowded regardless of age.

> **Gotcha:** a video that fails the age gate is marked `skipped_gate: too_old` — a **permanent**
> mark, because a video only ever gets older, never younger. If you widen `--max-age-min` later,
> videos that were already marked `too_old` under the narrower window are **not**
> auto-reconsidered; they stay skipped. Reset them manually after widening the window:
>
> ```python
> from studio.guerrilla import db
> conn = db.connect("<name>")
> conn.execute(
>     "UPDATE videos SET decision = 'pending', skip_reason = '' "
>     "WHERE decision = 'skipped_gate' AND skip_reason = 'too_old'")
> conn.commit()
> ```

**`--cap`** (10–25, default 12) is the daily posting cap. Ramp it up only after a couple of
clean weeks with a healthy survival rate — a sudden jump in posting volume is itself a signal
platforms watch for, independent of anything about the comments' content.

## Reading the report

`studio guerrilla report --channel <name>` renders four sections:

1. **Headline numbers** — comments posted, candidate videos seen, and the current survival
   rate. If nothing has been tracked yet, survival prints `n/a (no tracked comments)` rather
   than a misleading `100%`. If the circuit breaker is tripped, this section calls it out
   explicitly with the timestamp and the rate that tripped it.
2. **By style tag** — mean likes, mean replies, and survival rate per `style_tag`
   (`provocative_question` / `joke` / `contrarian_take` / `insight`), sorted best first. This is
   the table that should steer which styles the composer leans on over time.
3. **Why videos were skipped** — a breakdown of skip reasons and their counts. A reason that's
   climbing (e.g. `too_many_comments` dominating) is a signal the gates need retuning, not that
   the pipeline is broken.
4. **Switchback readout** — `verdict` (`positive` / `negative` / `null` / `insufficient_data`),
   the on/off arm means, the lift, and its 95% confidence interval. A `null` verdict is flagged
   explicitly as a legitimate result worth considering stopping over, not a failure of the
   experiment. If any off days were contaminated (posting happened despite the calendar saying
   off), the report warns that the readout is unreliable until that's fixed — don't trust the
   verdict in that case.

## Content quality — the honest picture

State this plainly, because it should shape how much you rely on auto-post versus the
human-in-the-loop path: **the automated comment quality has a modest ceiling.** Evaluation
across several batches found that a title-only composer (no transcript grounding) produces
comments that share an obvious template fingerprint — the same rhetorical mold ("If X, then
Y?" → a hedged-reviewer voice → "why do we…?") repeated across otherwise-unrelated videos, which
is exactly the kind of pattern that gets a channel's comments mass-flagged. Grounding the
composer in a real transcript excerpt raises specificity noticeably, but turning timestamp
citation **on** trades that fingerprint for two new problems: timestamps that are wrong often
enough to be a visible credibility error, and a new template of their own ("at 0:0X, when he
says…") appearing across most of a batch.

**Grounding the comment in a real transcript moment, with timestamp citation left off, is what
makes the output specific and on-topic rather than templated** — and it's the configuration this
pipeline runs autonomously by default (`--cite-timestamps` is opt-in). Even at that
configuration, the result is comments that are specific, on-topic, and occasionally genuinely
good — not a subscriber firehose. Some residual tics remain (a tendency toward tag-questions, an
overly enthusiastic voice) that prompt engineering alone hasn't fully eliminated.

If quality matters more than volume for your use case, use the `queue`/`approve` path: let the
critic hold borderline comments instead of auto-posting them, review the queue, and post only
the ones you'd actually stand behind. That trades throughput for a human editorial pass, which is
the more reliable way to raise the ceiling described above.
