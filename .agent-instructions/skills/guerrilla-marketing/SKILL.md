---
name: guerrilla-marketing
description: >
  Operator playbook for `studio guerrilla` — a bot that posts a capped number of
  on-topic, transcript-grounded comments per day under other creators' recent
  videos from the configured channel, to attract viewers indirectly. Use when the
  user wants to RUN the guerrilla comment loop (`tick`), DEPLOY the commenter to a
  VPS, GENERATE a preview batch to read before posting live, SHOW posted comment
  links, TUNE the age window / daily cap, CHECK the circuit breaker, MANAGE the
  watchlist, or DEBUG why nothing posted on a tick. Covers the full pipeline
  (discover → rank → transcript → topic → highlight → compose → critic → rails →
  post → track), the ban-defense gates, and the remote-deploy Makefile.
---

# guerrilla-marketing — indirect reach via grounded comments

`studio guerrilla` finds recent uploads on a watchlist of other creators' YouTube
channels, writes one comment that reacts to something specific the video actually
says, scores it with a critic, runs it through a set of rate-discipline rails, and —
only if everything passes — posts it from the configured channel. It then tracks
whether the comment survives and, over weeks, whether any of this moves subscribers.

**The mechanism is indirect.** Nobody clicks a link — there isn't one; the deny-list
makes posting one a code-level impossibility. The bet is that an interesting,
on-topic comment makes a reader click the commenter's *name*, which lands them on
the configured channel's own page. That's the whole conversion path: one good
comment, one profile click, maybe one subscribe.

**This is gray-hat and ToS-adjacent.** Automated commenting is spam under YouTube's
Terms of Service under any honest reading of the policy — nothing here asks
permission or hides behind a gray area. It just tries to stay far enough inside
YouTube's actual enforcement behavior (comment removal, shadow-holds, account flags)
to not get the channel banned. Every comment posts through the operator's own OAuth
client, so every comment is attributable to the real channel — there is no
throwaway identity absorbing the risk. Ban-defense is therefore the core design, not
an afterthought: a hard daily cap, per-channel cooldowns, a denylist that makes
self-promotion impossible in code (not just an LLM instruction), a near-duplicate
filter, style/opening diversity checks, and a circuit breaker that watches comment
survival and pages the operator when it drops. None of that makes this compliant —
it makes it a calculated, monitored bet.

## The pipeline

```
 watchlist channels
        │
        ▼
   DISCOVER  ── new uploads per watched channel (YouTube Data API, cheap quota)
        │
        ▼
     RANK    ── hard gates: age, comment count, channel size, cooldown, daily cap,
        │        active window (cheapest gate first — nothing paid runs yet)
        ▼
  TRANSCRIPT  ── cached fetch (network, not LLM); no captions → skip at zero LLM cost
        │
        ▼
    TOPIC     ── classify against a transcript excerpt; unclear topic → skip
        │
        ▼
  HIGHLIGHT   ── find one real, specific moment in the video to react to
        │
        ▼
   COMPOSE    ── several comment variants, each a different style + wording
        │
        ▼
    CRITIC    ── grounded judge scores each variant against the transcript excerpt
        │
        ▼
    RAILS     ── denylist, near-duplicate, opening-repeat, style-overuse,
        │        timestamp-verify, spacing, active-window, blackout
        ▼
     POST     ── the OAuth client posts the #1 surviving variant
        │
        ▼
    TRACK     ── re-check likes/replies/survival; the circuit breaker lives here
```

Order is a cost contract as much as control flow: the cheapest gate always runs
first, so a video that will never qualify (too old, too many comments already,
channel too small, on cooldown) is rejected before anything LLM-priced runs, and a
video whose topic is unclear is rejected before the more expensive highlight/compose/
critic chain. A comment that collides with recent posting history (near-duplicate,
same opening, style overused) falls through to the *next-best* composed variant
instead of abandoning the video outright — compose already paid for several for
exactly this reason.

## CLI surface

```bash
studio guerrilla --help   # always the live source of truth
```

| Command | What it does |
|---|---|
| `guerrilla watchlist add <UC...> --channel <ch> --title "..." --median-views N --tags "..."` | Add a target channel to comment on. No auto-discovery yet — `--median-views` is supplied by hand; lowballing it makes the channel-size gate reject that channel's videos for no reason. |
| `guerrilla watchlist list [--all]` | List active watchlist channels (`--all` includes paused/banned/rejected). |
| `guerrilla watchlist resume <UC...> --channel <ch>` | Un-pause a channel a transient discovery error paused. |
| `guerrilla tick --channel <ch> [--cap N] [--dry-run] [--max-age-min N] [--cite-timestamps]` | One full discover→post cycle. `--cap` is 10-25 (default 12). |
| `guerrilla track --channel <ch>` | Refresh likes/replies/survival on posted comments; evaluates the circuit breaker. |
| `guerrilla resume --channel <ch>` | Manually clear a tripped circuit breaker — only after investigating. |
| `guerrilla report --channel <ch> [--write]` | Effectiveness by style tag, skip-reason counts, switchback readout. |
| `guerrilla rollup --channel <ch> --channel-id <UC...> --start <d> --end <d> --experiment-start <d>` | Pull daily subs/views into `channel_daily` so `report`'s switchback section can resolve. |
| `guerrilla queue --channel <ch>` | List comments the critic scored into the "queue" band (3.0-4.0), awaiting approval. |
| `guerrilla approve <video_id> --channel <ch> [--cap N]` | Post one queued comment's exact proposed text through the same rails as a live tick. |

**`--dry-run` is the pre-flight review.** It runs discovery through the content
rails (denylist, near-duplicate, opening-repeat, style-overuse, timestamp-verify)
and prints every comment that *would* post, then stops — no YouTube write, no
rate-limit/cooldown state touched. It costs the same LLM calls a real tick would.
Read every line it prints before ever dropping the flag. This gate is not optional
and nothing skips it.

## The gates and rails

**Rank gates** (`rank.py`, cheapest first — reject before anything paid runs):

| Gate | Default | Why |
|---|---|---|
| age | < 90 min since publish | early enough to still hold a visible slot |
| comment count | < 40 existing comments | past this a new comment is buried |
| channel size | median views ≥ 5000 | below this there's no audience to reach |
| channel cooldown | 72h since last comment on that channel | spreads posts across the watchlist |
| active window | 09:00-23:00 UTC | a 4am comment reads as a bot |
| daily cap | 10-25/day, operator-set | the hard ceiling on total risk exposure |

**Content rails** (`rails.py`, checked immediately before every post):

| Rail | What it catches |
|---|---|
| deny-list | links, the channel's own name/aliases, self-promo phrasing ("subscribe", "check out my..."), hashtags, emoji spam — enforced in code, not just prompted against, so an LLM ignoring instructions once in a thousand tries still can't post it |
| near-duplicate | word-shingle (long comments) or character-gram (short comments) jaccard overlap against recently posted text — two different thresholds because the two representations behave differently at the same cutoff |
| opening-repeat | same first-4-words scaffold as a recent comment — catches template-driven phrasing that near-duplicate alone misses |
| style-overuse | the same style tag (`provocative_question` / `joke` / `contrarian_take` / `insight`) appearing ≥2 times in the last 5 posts |
| timestamp-verify | any cited `M:SS`/`H:MM:SS` must fall inside the video's real duration and land near an actual transcript segment — an unverifiable citation is treated as unsafe |
| spacing | at most one post per tick, jittered interval (~12min base ± jitter), never a fixed cadence |
| publish blackout | suppressed for a window around the operator's own uploads, so comment-driven and upload-driven traffic stay separable |

**The critic** scores every composed variant 0-5 against on-topic / provocative-or-
funny / not-generic criteria, grounded against the real transcript excerpt (a claim
the excerpt doesn't support scores 0, no partial credit). ≥4.0 auto-posts, 3.0-4.0
queues for `guerrilla approve`, below that is discarded.

**The circuit breaker** (`track.py`): every `track` run computes survival — the
fraction of the trailing 50 posted comments still live. Below 85%, the loop
auto-pauses (`tick` returns `PAUSED`, exits non-zero) and sends a notification.
Comments quietly disappearing or getting held for review is what a shadowban looks
like from the outside — there is no other signal for it. **The correct response is
to stop and investigate, never to lower the threshold.** Read `report`'s survival-
by-style breakdown to see whether it's concentrated on one channel, one style, or
one time window before deciding it's safe to `guerrilla resume`.

## Autonomous operation

`tick` is meant to run unattended on a cron-like schedule, roughly every 20-40
minutes across the active window — more often doesn't buy anything, since the
spacing rail already jitters pacing and discovery quota is cheap regardless of poll
frequency; the daily cap is the real limiter, not tick frequency. `track` should run
at least twice a day so a comment removed hours or days later still gets caught.
`rollup` needs to run daily once a switchback experiment is running, or `report`'s
effectiveness section stays `insufficient_data` indefinitely.

**`--cite-timestamps` defaults OFF, and the reason is worth keeping in mind before
turning it on:** the highlight stage's found-moment timestamps are unreliable —
in practice they cluster near the start of a video regardless of where the quoted
content actually is — and the "at 0:0X, when he says…" citation phrasing itself
became a recognizably bot-shaped template. The composed comment still reacts to the
found moment either way; turning citations on only changes whether it *names* a
time. Leave it off unless a specific need for cited timestamps has been verified
against real output.

**Ramp the daily cap slowly.** Start at the floor (10) and only raise it after
multiple clean weeks of `track` survival staying comfortably above the breaker
threshold — never raise it in response to the breaker firing, and never raise it
faster than the evidence supports.

## Remote deploy

Some networks can't reach YouTube's Data API, transcript endpoints, and LLM
providers reliably from wherever the operator drives from. `scripts/remote/guerrilla.mk`
deploys the guerrilla pipeline to **a VPS with clean, unrestricted internet access
to YouTube** and drives it from there, without touching anything else on the box.

Host, SSH key, and any per-operator overrides live in the gitignored
`scripts/remote/guerrilla.local.mk` — copy `scripts/remote/guerrilla.local.mk.example`
to it and fill in `REMOTE_HOST` / `SSH_KEY`. The tracked `guerrilla.mk` never
hardcodes a host or key path; it fails fast with a clear error if the local file is
missing.

```bash
make -f scripts/remote/guerrilla.mk deploy    # rsync code + secrets, install uv + deps
make -f scripts/remote/guerrilla.mk preview    # run a review batch on the VPS (posts nothing)
make -f scripts/remote/guerrilla.mk pull       # bring batch.json + the db back locally
make -f scripts/remote/guerrilla.mk posted     # list every comment actually posted, as YouTube links
make -f scripts/remote/guerrilla.mk shell      # interactive ssh into the deploy dir
make -f scripts/remote/guerrilla.mk sync-code  # push only code (no secrets) after a change
```

| Target | What it does |
|---|---|
| `deploy` | `sync-code` + `sync-secrets` + `setup` — full push and install |
| `sync-code` | Push only the `studio` package + preview runner (allow-listed, not the whole repo) |
| `sync-secrets` | Push `.env`, the channel's OAuth token, `client_secret.json` (locked to `0600`), and the watchlist db |
| `setup` | Install `uv` if missing, `uv sync --extra guerrilla --extra youtube` |
| `preview` | Run `scripts/guerrilla_preview.py` on the VPS — the same discover→rails pipeline, `post` is never even imported, so there is no code path to a live post |
| `pull` | Copy `batch.json` + the db back into `runs/_guerrilla_remote/` locally |
| `posted` | Query the remote db for every posted comment, printed as direct `youtube.com/watch?v=...&lc=...` links |
| `shell` | Interactive SSH into the remote deploy directory |

Overridable vars: `CHANNEL` (which `token_<channel>.json` to deploy and post from),
`TARGET` / `PER_CHANNEL` (preview batch sizing).

**Transcripts on a fresh network may need a proxy.** Some IPs — including some
datacenter/VPS ranges — are rate-limited or blocked by YouTube for caption
scraping. Set `TRANSCRIPT_PROXY_URL` (e.g. `http://user:pass@host:port`) in `.env`
to route transcript fetches through an HTTP proxy; leave it unset for a direct
connection. `transcript.py` retries a few times when a proxy is configured, since a
proxied fetch occasionally hands out a rate-limited exit and a retry lands a
working one.

## Hard operator rules

- **This posts from the real channel.** There is no disposable identity absorbing
  the risk — treat every comment the bot posts as if it carries the operator's name,
  because it does.
- **Ramp the daily cap slowly.** Start low, raise only after clean weeks, never in
  response to a breaker trip.
- **Always run `--dry-run` and read every comment before the first live post**, and
  again after any change to the composer, the critic, or the rails. This is a human
  gate, not a formality — if a comment reads as filler, as bait, or as something
  you'd wince at being asked about, the pipeline needs work before it posts, not
  after.
- **Never bypass the circuit breaker.** Lowering the survival threshold or hand-
  posting through a tripped breaker doesn't fix whatever tripped it — it just
  removes the only sensor that would have told the operator the channel was at
  risk. `guerrilla approve` itself refuses to post while the breaker is tripped.
- **Expect a `null` switchback verdict, and don't read that as failure.** YouTube's
  API exposes no per-comment attribution — there's no way to trace a subscriber back
  to a specific comment — so the switchback experiment (days on / days off,
  comparing subscriber gain) is the only design that can answer "does this move the
  needle at all" without that attribution, and it needs `MIN_DAYS_PER_ARM` in *each*
  arm before `report` returns anything but `insufficient_data`. A `null` result is
  the system doing its job cheaply; don't re-run hoping for a different answer, and
  don't read a `positive` verdict with a wide confidence interval as more certain
  than its `ci_low`/`ci_high` actually says.

## Full reference

[`docs/50-marketing/guerrilla/`](../../../docs/50-marketing/guerrilla/) — deeper
architecture notes. The module-level source (`studio/guerrilla/*.py`) is
extensively self-documented; when this skill and the code disagree, the code wins.
