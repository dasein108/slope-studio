"""One tick of the guerrilla loop: discover, rank, transcript, classify, highlight, compose,
judge, post.

Order matters, and it is a cost contract as much as a control-flow one. The breaker is checked
first so a suspected shadowban stops the tick before it can make things worse. Per candidate,
the transcript fetch runs before EVERYTHING else that costs an LLM call — it is a cached
network read, not a model call, and a video with no captions must be skippable at zero LLM
cost. The topic gate runs next, using an excerpt of that same transcript, so a video whose
subject is unclear still costs only one LLM call rather than the five a full pass (topic +
highlight + compose + critic) would run up. Only once topic passes does `highlight.best_moment`
run — it is itself several LLM calls on a long video — followed by compose and critic, both of
which now receive the moment/excerpt so generated comments react to something the video
actually said instead of paraphrasing its title.

Only the critic's #1 variant is tried first, but a `PostBlocked` of
`near_duplicate`, `repeats_opening`, or `style_overused` falls through to the
next-best `auto`-decision variant instead of abandoning the video outright:
compose already paid for several variants — with different wording and
different style tags precisely so another can be tried — and only the winner
happened to collide with recent posting history. Time-varying block reasons
(`channel_cooldown`, `too_soon`, `inactive_window`, `publish_blackout`) keep the
video's fate as-is — counted and moved past, left `pending` — except `daily_cap`,
which still ends the tick immediately. `denylist:*` and an exhausted
variant-fixable reason (every variant blocked) are different: nothing about a
later tick makes either outcome more likely to succeed, so the video is marked
`skipped_gate` and not reconsidered.

The spacing rail (`too_soon` in `post.post_comment`) allows at most one
successful post per tick, so a successful post ends the candidate loop
immediately — trying another candidate afterward can only pay for LLM calls on
a post that rail is guaranteed to block. `rank.rank_candidates` also gates on
this once, up front, before any candidate is even considered.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from studio.guerrilla import (
    compose,
    critic,
    discover,
    experiment,
    highlight,
    post,
    rails,
    rank,
    topic,
    track,
    transcript,
    watchlist,
)

# Window used to build the transcript excerpt handed to the topic gate and to the critic when no
# highlight moment was found yet — a bounded prefix rather than the whole transcript so a
# 25-minute video's excerpt still fits comfortably in a judge/classifier prompt. Once a moment
# IS found, the critic gets a window centered on it instead (see `_excerpt_for`), since that is
# the part of the transcript the composed comment is actually reacting to.
EXCERPT_FIRST_MINUTES = 300.0  # 5 minutes
# Half-width of the window around a found moment's timestamp used for the critic's excerpt — wide
# enough to give the judge surrounding context for the claim without re-sending the whole
# transcript.
EXCERPT_MOMENT_WINDOW = 120.0  # 2 minutes each side


def _excerpt_for(segments: list[transcript.Segment], moment: highlight.Moment | None = None) -> str:
    """Bounded transcript excerpt for an LLM prompt: centered on `moment` if one was found,
    otherwise the first `EXCERPT_FIRST_MINUTES` of the video (used for the topic gate, which
    runs before highlight, and as the critic's fallback when highlight found nothing)."""
    if moment is not None:
        return transcript.as_prompt(segments, moment.timestamp - EXCERPT_MOMENT_WINDOW,
                                    moment.timestamp + EXCERPT_MOMENT_WINDOW)
    return transcript.as_prompt(segments, 0.0, EXCERPT_FIRST_MINUTES)

# Exception types `_try_post` treats as a posting failure to classify and
# recover from, as opposed to letting propagate: googleapiclient's HTTP error
# type for real API responses (403/404/429/5xx), plus `OSError` — the base of
# `ssl.SSLError`, `socket.error`, `ConnectionError`, and `TimeoutError` — for
# the transport-level failures the SSL-ghost-success trap in
# `post.post_comment` exists to survive. A bare `except Exception` here would
# also swallow genuine programming bugs (a `KeyError` from a bad dict lookup,
# a `TypeError` from a bad call) and misreport them as `"transient"`,
# continuing the tick as if nothing were wrong — exactly the kind of defect
# this loop must not hide from whoever is watching the cron. Resolved lazily
# so this module doesn't hard-depend on `googleapiclient` being installed.
try:
    from googleapiclient.errors import HttpError as _HttpError
    _API_ERRORS: tuple[type[BaseException], ...] = (_HttpError, OSError)
except ImportError:  # pragma: no cover - installed via the `youtube` extra in prod
    _API_ERRORS = (OSError,)


@dataclass
class Config:
    daily_cap: int = 12
    dry_run: bool = False
    provider: str = ""
    publish_times: list[str] = field(default_factory=list)
    experiment_start: date | None = None
    gates: rank.Gates = field(default_factory=rank.Gates)
    channel: str = ""  # our internal channel/token name — only needed for the
                        # lazy `channel_info` lookup in `post.post_comment`'s
                        # ghost-post read-back; unused otherwise.
    cite_timestamps: bool = False  # off by default: the highlight stage's timestamps
                        # cluster near the video start regardless of where the quoted
                        # content actually is, and the "At 0:0X, when he says…" phrasing
                        # became a bot-detectable template. The moment still drives
                        # composition either way — this only suppresses citing its time.


@dataclass
class TickResult:
    discovered: int = 0
    considered: int = 0
    posted: int = 0
    queued: int = 0
    skipped: Counter = field(default_factory=Counter)
    blocked: Counter = field(default_factory=Counter)
    paused: bool = False
    proposed: list[dict] = field(default_factory=list)


def _mark(conn: sqlite3.Connection, video_id: str, decision: str, reason: str = "") -> None:
    conn.execute("UPDATE videos SET decision = ?, skip_reason = ? WHERE video_id = ?",
                 (decision, reason, video_id))
    conn.commit()


class PostOutcome(Enum):
    """What `_try_post` decided for one candidate video.

    `POSTED` and `HARD_STOP` both end the tick's candidate loop: `POSTED`
    because the spacing rail (`too_soon`) allows at most one successful post
    per tick regardless of which video it lands on, so trying another
    candidate afterward can only pay LLM calls for a post that rail is
    guaranteed to block; `HARD_STOP` because a daily cap or ban/quota signal
    means nothing this tick should proceed. `BLOCKED` means this particular
    video is done — for now, or permanently, `_try_post` already handled the
    marking either way — but a different candidate might still succeed, so the
    tick keeps going.
    """
    POSTED = "posted"
    BLOCKED = "blocked"
    HARD_STOP = "hard_stop"


def _try_post(conn: sqlite3.Connection, client, video, pairs: list[tuple[compose.Variant, critic.Verdict]],
              idx_by_id: dict[int, int], now: datetime, cfg: Config, r: TickResult) -> PostOutcome:
    """Attempt each `auto`-decision variant, best first."""
    # These three reasons are all variant-specific, not video-specific: compose
    # generated several variants precisely so a different one — different
    # wording, different style_tag — can be tried when the critic's #1 pick
    # happens to collide with recent posting history. Any other block reason
    # (denylist, daily_cap, channel_cooldown, ...) is either a property of the
    # video/timing rather than the variant, or something no later variant can
    # fix, so those still end the candidate outright.
    FALLTHROUGH_REASONS = {"near_duplicate", "repeats_opening", "style_overused"}
    exhausted_reason = ""
    for variant, verdict in pairs:
        if verdict.decision != "auto":
            continue
        try:
            post.post_comment(conn, client, video["video_id"], variant.text, variant.style_tag,
                              verdict, idx_by_id[id(variant)], now,
                              {"daily_cap": cfg.daily_cap, "publish_times": cfg.publish_times,
                               "channel": cfg.channel})
            r.posted += 1
            return PostOutcome.POSTED
        except post.PostBlocked as e:
            r.blocked[e.reason] += 1
            if e.reason in FALLTHROUGH_REASONS:
                exhausted_reason = e.reason
                continue  # compose gave us more than one shot; try the next best
            if e.reason.startswith("denylist"):
                # The LLM ignored the "never self-promote" instruction for this
                # video's composed text. Nothing about a later tick changes that
                # judgment, so don't re-pay to reconsider it.
                _mark(conn, video["video_id"], "skipped_gate", e.reason)
                return PostOutcome.BLOCKED
            return PostOutcome.HARD_STOP if e.reason == "daily_cap" else PostOutcome.BLOCKED
        except _API_ERRORS as e:
            kind = post.classify_error(e)
            r.blocked[kind] += 1
            if kind == "comments_disabled":
                _mark(conn, video["video_id"], "skipped_gate", "comments_disabled")
            return PostOutcome.HARD_STOP if kind in ("forbidden", "quota") else PostOutcome.BLOCKED
    if exhausted_reason:
        # Every `auto`-decision variant collided with recent posting history in
        # some variant-fixable way. Compose already spent its shots; a later
        # tick would just regenerate more of the same for the same video, not
        # a genuinely new attempt.
        _mark(conn, video["video_id"], "skipped_gate", f"{exhausted_reason}_exhausted")
    return PostOutcome.BLOCKED  # every eligible variant was blocked; nothing more to do here


def tick(conn: sqlite3.Connection, client, cfg: Config, now: datetime,
         complete=None, notify=None) -> TickResult:
    r = TickResult()

    if track.check_breaker(conn, notify=notify):
        r.paused = True
        return r

    if cfg.experiment_start is not None and \
            experiment.state_for(now.date(), cfg.experiment_start) == "off":
        r.blocked["switchback_off"] += 1
        return r

    for ch in watchlist.active(conn):
        try:
            r.discovered += len(discover.record_candidates(conn, client, ch["channel_id"], now))
        except Exception as e:
            # Only pause on errors that mean the channel is genuinely gone (deleted,
            # made private, or otherwise inaccessible to us) — 403/404. A transient
            # network blip or a momentary 5xx is not evidence of that, and pausing on
            # it silently drains the watchlist, the compounding asset the whole loop
            # depends on, with no record of why and no way back short of re-adding
            # the channel (which `watchlist.add` deliberately won't un-pause).
            kind = post.classify_error(e)
            r.blocked[f"discover_error:{kind}"] += 1
            if kind in ("forbidden", "not_found"):
                watchlist.set_status(conn, ch["channel_id"], "paused")

    for video in rank.rank_candidates(conn, now, cfg.gates, cfg.daily_cap, dry_run=cfg.dry_run):
        r.considered += 1

        # Cheapest possible gate first: a cached (network, not LLM) transcript read. A video
        # with no captions must cost zero LLM calls, so this has to happen before topic
        # classification (which now also wants transcript content) — never after.
        segments = transcript.cached(conn, video["video_id"])
        if not segments:
            _mark(conn, video["video_id"], "skipped_transcript", "no_transcript")
            r.skipped["skipped_transcript"] += 1
            continue

        t = topic.classify(video["title"], video["description"], cfg.provider, complete,
                           transcript_excerpt=_excerpt_for(segments))
        conn.execute("UPDATE videos SET topic = ?, topic_confidence = ? WHERE video_id = ?",
                     (t.topic, t.confidence, video["video_id"]))
        conn.commit()
        if not topic.is_clear(t):
            _mark(conn, video["video_id"], "skipped_topic", "unclear")
            r.skipped["skipped_topic"] += 1
            continue

        moment = highlight.best_moment(segments, video["title"], cfg.provider, complete)
        cite = cfg.cite_timestamps and moment is not None and highlight.should_cite(moment)
        excerpt = _excerpt_for(segments, moment)

        variants = compose.variants(video["title"], t.summary, cfg.provider, complete=complete,
                                    moment=moment, cite=cite)
        pairs = critic.ranked(variants, video["title"], t.summary, cfg.provider, complete,
                              transcript_excerpt=excerpt)
        if not pairs:
            _mark(conn, video["video_id"], "skipped_critic", "no_variants")
            r.skipped["skipped_critic"] += 1
            continue

        winner, verdict = pairs[0]
        if verdict.decision == "skip":
            _mark(conn, video["video_id"], "skipped_critic", "low_score")
            r.skipped["skipped_critic"] += 1
            continue

        if verdict.decision == "queue":
            _mark(conn, video["video_id"], "queued", winner.text)
            r.queued += 1
            continue

        if cfg.dry_run:
            # B3: the operator's pre-flight review is supposed to show comments
            # that already cleared the content rails — otherwise it reviews text
            # the live path would have rejected. Only the content rails run here
            # (denylist, near-duplicate against `recent_texts`, bad_timestamp
            # against the cached transcript); the time-varying
            # ones (spacing, active window, blackout, daily cap) depend on when
            # the real tick would run, not on the comment's content, and stay out
            # of dry-run evaluation entirely — see `rank_candidates(dry_run=...)`
            # and the fact that nothing below re-checks them.
            rule = rails.violates_denylist(winner.text)
            if rule:
                r.blocked[f"denylist:{rule}"] += 1
                continue
            recent = rails.recent_texts(conn)
            if rails.too_similar(winner.text, recent):
                r.blocked["near_duplicate"] += 1
                continue
            if rails.repeats_opening(winner.text, recent):
                r.blocked["repeats_opening"] += 1
                continue
            if rails.style_overused(winner.style_tag, rails.recent_styles(conn)):
                r.blocked["style_overused"] += 1
                continue
            # `segments` is already the same cached transcript fetched above for this
            # candidate — no need to hit the DB again.
            bad = rails.bad_timestamp(winner.text, segments)
            if bad:
                r.blocked["bad_timestamp"] += 1
                continue
            r.posted += 1
            r.proposed.append({
                "video_id": video["video_id"],
                "title": video["title"],
                "style_tag": winner.style_tag,
                "score": verdict.score,
                "text": winner.text,
            })
            continue

        idx_by_id = {id(v): i for i, v in enumerate(variants)}
        outcome = _try_post(conn, client, video, pairs, idx_by_id, now, cfg, r)
        if outcome is not PostOutcome.BLOCKED:
            break  # POSTED (too_soon allows at most one per tick) or HARD_STOP
    return r
