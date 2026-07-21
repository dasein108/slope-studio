"""Hard gates plus a simple sort.

Deliberately not a learned score: there is no data to calibrate one on day one.
The gates encode the real constraints — a comment on a 2M-sub channel's video
lands 800th and is invisible, so "biggest channel" is the wrong target. Every
raw feature is recorded in `videos`, so a scoring model or bandit can be trained
later without a backfill.
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from studio.guerrilla import discover, post, rails, watchlist

# Gate reasons that reflect a condition that will clear on its own on a later
# tick (the active window opens, the daily cap resets tomorrow, the per-channel
# cooldown expires). Recording these as `skipped_gate` would permanently retire
# a video that is otherwise still a fine candidate — so `rank_candidates` leaves
# the row `pending` instead of marking it, and simply doesn't select it this
# tick. `channel_cooldown` belongs here for the same reason `_try_post` treats
# it as time-varying rather than a hard stop: it clears in 72h on its own.
_TIME_VARYING_REASONS = frozenset({"inactive_window", "daily_cap", "channel_cooldown"})


@dataclass(frozen=True)
class Gates:
    max_age_min: float = 90.0        # be early enough to hold a top slot
    max_comments: int = 40           # past this, a new comment is buried
    min_median_views: int = 5000     # below this there is no audience to reach


def evaluate(video, channel, now: datetime, gates: Gates,
             comments_enabled: bool = True, daily_posted: int = 0,
             daily_cap: int | None = None) -> tuple[bool, str]:
    """(passed, reason). reason is '' when passed.

    `daily_cap=None` skips the daily-cap check — callers that only care about
    the per-video gates (e.g. direct unit tests) don't have to thread a cap
    through. `rank_candidates` always supplies one.
    """
    if not comments_enabled:
        return False, "comments_disabled"
    # Gate before spending: a video the tick provably cannot post right now
    # must never reach `topic.classify` / `compose.variants` / `critic.ranked`
    # — each candidate that goes further costs three paid LLM calls whether
    # or not anything ever gets posted for it.
    if not rails.in_active_window(now):
        return False, "inactive_window"
    if daily_cap is not None and daily_posted >= daily_cap:
        return False, "daily_cap"
    if discover.age_minutes(video["published_at"], now) > gates.max_age_min:
        return False, "too_old"
    if video["comment_count_at_seen"] > gates.max_comments:
        return False, "too_many_comments"
    if channel["median_views"] < gates.min_median_views:
        return False, "channel_too_small"
    if watchlist.on_cooldown(channel, now):
        return False, "channel_cooldown"
    return True, ""


def rank_candidates(conn: sqlite3.Connection, now: datetime,
                    gates: Gates | None = None, daily_cap: int = 12,
                    dry_run: bool = False) -> list[sqlite3.Row]:
    """Pending videos that pass every gate, best first. Records rejections —
    except the time-varying ones (`inactive_window`, `daily_cap`,
    `channel_cooldown`), which are left `pending` so a later tick reconsiders
    them once the condition clears.

    `dry_run=True` skips the spacing pre-gate below: a dry run never posts, so
    `too_soon` (which only exists to space out real posts) can never fire for
    it, and the operator's pre-flight batch is built by evaluating every
    candidate regardless of when the real tick would next be allowed to post."""
    gates = gates or Gates()

    # The spacing rail (`too_soon` in `post.post_comment`) allows at most one
    # comment per tick, and its minimum gap doesn't depend on which candidate
    # ends up posting — so check it ONCE, up front, against the tick's shared
    # clock, before any candidate pays for `topic.classify` / `compose.variants`
    # / `critic.ranked`. At cron cadences under ~17 minutes (the rail's widest
    # jittered gap), skipping this would mean every one of the tick's
    # candidates pays three LLM calls only to be blocked as `too_soon` by the
    # real chokepoint. Like the other time-varying gates, this doesn't mark
    # anything — the window will open on a later tick. Inert in a dry run —
    # see the docstring above.
    if not dry_run:
        elapsed = post.seconds_since_last_post(conn, now)
        if elapsed is not None and elapsed < rails.next_delay_seconds(random.Random()):
            return []

    # A channel that went inactive (paused/banned/rejected) will never again
    # be polled by `discover`, so its pending videos would otherwise sit in
    # `pending` forever — invisible to the report and silently skipped by the
    # `c.status = 'active'` join below on every tick, but never recorded as
    # skipped. Retire them explicitly.
    conn.execute(
        """UPDATE videos SET decision = 'skipped_gate', skip_reason = 'channel_inactive'
           WHERE decision = 'pending' AND channel_id IN
             (SELECT channel_id FROM channels WHERE status != 'active')""")

    daily_posted = post.posted_today(conn, now)
    rows = list(conn.execute(
        """SELECT v.*, c.median_views, c.last_commented_at, c.channel_id AS ch_id
           FROM videos v JOIN channels c ON c.channel_id = v.channel_id
           WHERE v.decision = 'pending' AND c.status = 'active'
           ORDER BY c.median_views DESC"""))
    passed = []
    for r in rows:
        ok, why = evaluate(r, r, now, gates, bool(r["comments_enabled"]),
                           daily_posted, daily_cap)
        if ok:
            passed.append(r)
        elif why not in _TIME_VARYING_REASONS:
            conn.execute(
                "UPDATE videos SET decision = 'skipped_gate', skip_reason = ? WHERE video_id = ?",
                (why, r["video_id"]))
    conn.commit()
    return passed
