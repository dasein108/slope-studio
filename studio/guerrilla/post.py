"""The only module that writes to YouTube.

Every rail is checked here, immediately before the insert, so there is exactly
one place to audit for ban risk. A caller cannot bypass it, because nothing else
calls commentThreads.insert.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timezone

from studio.guerrilla import rails, transcript, watchlist


class PostBlocked(Exception):
    """A rail refused the comment. Not an error — the expected common case."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def classify_error(exc: Exception) -> str:
    """Map an API exception to a handling strategy."""
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "resp", None), "status", 0)
    blob = f"{getattr(exc, 'reason', '')} {exc}".lower()
    if "commentsdisabled" in blob or "commentthreadnotfound" in blob:
        return "comments_disabled"
    if "quota" in blob or "ratelimit" in blob or status == 429:
        return "quota"
    if status == 403:
        return "forbidden"
    if status == 404:
        return "not_found"
    return "transient"


def posted_today(conn: sqlite3.Connection, now: datetime) -> int:
    day = now.date().isoformat()
    return conn.execute(
        "SELECT COUNT(*) c FROM comments WHERE substr(posted_at, 1, 10) = ?",
        (day,)).fetchone()["c"]


def _iso(now: datetime) -> str:
    """Format `now` the way `db.now_iso()` formats the real clock.

    Recording is stamped from the same `now` the rails were just evaluated
    against, rather than a fresh `db.now_iso()` wall-clock read. Otherwise the
    `channel_cooldown` and `too_soon` rails — which compare stored timestamps
    against the caller's `now` — would drift against whatever they just wrote
    under test, or by the (usually negligible, but not guaranteed) gap between
    rail evaluation and the DB write in production.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).isoformat(timespec="seconds")


def last_posted_at(conn: sqlite3.Connection) -> datetime | None:
    """Timestamp of the most recent comment we've posted, or None if we never
    have. Public so `rank.rank_candidates` can gate a whole tick on it without
    duplicating this query."""
    row = conn.execute(
        "SELECT posted_at FROM comments ORDER BY posted_at DESC LIMIT 1").fetchone()
    if not row or not row["posted_at"]:
        return None
    dt = datetime.fromisoformat(row["posted_at"].replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def seconds_since_last_post(conn: sqlite3.Connection, now: datetime) -> float | None:
    """Seconds between `now` and the most recent comment, or None if we've
    never posted. Shared by the `too_soon` chokepoint below and by
    `rank.rank_candidates`'s once-per-tick spacing pre-gate, so both compare
    against the same clock-normalization logic."""
    last_posted = last_posted_at(conn)
    if last_posted is None:
        return None
    now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return (now_utc.astimezone(timezone.utc) - last_posted).total_seconds()


def insert(client, video_id: str, text: str) -> str:
    """Raw commentThreads.insert. 50 quota units."""
    resp = client.commentThreads().insert(part="snippet", body={"snippet": {
        "videoId": video_id,
        "topLevelComment": {"snippet": {"textOriginal": text}},
    }}).execute()
    return resp["id"]


def _find_landed(client, video_id: str, text: str, our_channel_id: str) -> str | None:
    """Read back the video's recent comment threads to check whether OUR `text`
    is already there. Returns the comment id if so, else None.

    Exists for the SSL-ghost-success trap: `insert` can reach YouTube, write the
    comment, and then raise on the response (an SSL failure reading it back) —
    the comment then exists on YouTube but nothing in `comments` knows about it,
    so it's invisible to the daily cap and the near-duplicate check, and never
    tracked for survival. The operator has been bitten by exactly this failure
    mode on video uploads before. A blind retry would risk a genuine double
    post, which is itself a spam signal — so this reads back instead of retrying.

    Text alone is not enough: a busy video can carry a pre-existing comment from
    a different author that is byte-identical to ours (a common reaction phrase,
    or someone quoting the video the same way we did). Matching on text alone
    would claim a stranger's comment as ours and start tracking THEM for
    survival, feeding the circuit breaker and the style-tag report with data
    that was never ours. `commentThreads.list`'s snippet exposes
    `authorChannelId` on the top-level comment, so require both: our channel id
    AND our text. If `our_channel_id` is unknown (couldn't be resolved), no
    candidate can ever match — the caller's original error propagates, which is
    the safe default (a missed recovery, never a false claim).

    Residual false-negative window (not fixed here, and not cheaply fixable):
    `maxResults=20` with `order="time"` means a genuinely-landed comment can
    scroll out of the first page on a busy video before this read runs, and
    YouTube's comment listing is eventually consistent — the write can be
    visible to `insert`'s caller before a subsequent `list` call reflects it.
    Both cases make this return None for a comment that really is ours, causing
    an unnecessary (but safe — not a double-post) error. Do not widen `maxResults`
    to paper over this; it doesn't close the eventual-consistency gap and just
    spends more quota per ghost-post check.
    """
    if not our_channel_id:
        return None
    resp = client.commentThreads().list(
        part="snippet", videoId=video_id, order="time", maxResults=20).execute()
    for item in resp.get("items", []):
        top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        author = top.get("authorChannelId", {}).get("value", "")
        if author != our_channel_id:
            continue
        if top.get("textOriginal") == text or top.get("textDisplay") == text:
            return item["id"]
    return None


def post_comment(conn: sqlite3.Connection, client, video_id: str, text: str,
                 style_tag: str, verdict, variant_rank: int, now: datetime,
                 cfg: dict) -> str:
    """Check every rail, post, and record. Raises PostBlocked if a rail refuses."""
    if posted_today(conn, now) >= cfg.get("daily_cap", 12):
        raise PostBlocked("daily_cap")
    if not rails.in_active_window(now):
        raise PostBlocked("inactive_window")
    if rails.in_blackout(now, cfg.get("publish_times", [])):
        raise PostBlocked("publish_blackout")

    video = conn.execute(
        "SELECT channel_id, comment_count_at_seen FROM videos WHERE video_id = ?",
        (video_id,)).fetchone()
    if video:
        channel = conn.execute(
            "SELECT * FROM channels WHERE channel_id = ?", (video["channel_id"],)).fetchone()
        # `rank.rank_candidates` checks this too, but only once per tick against a
        # snapshot taken before any posting happens this tick — two candidates from
        # the same channel would both read the snapshot as clear. This is the
        # chokepoint; it must not trust that snapshot.
        if channel and watchlist.on_cooldown(channel, now):
            raise PostBlocked("channel_cooldown")

    rule = rails.violates_denylist(text)
    if rule:
        raise PostBlocked(f"denylist:{rule}")
    recent = rails.recent_texts(conn)
    if rails.too_similar(text, recent):
        raise PostBlocked("near_duplicate")
    if rails.repeats_opening(text, recent):
        raise PostBlocked("repeats_opening")
    if rails.style_overused(style_tag, rails.recent_styles(conn)):
        raise PostBlocked("style_overused")
    # Cached, so a video already checked this tick (or an earlier one) costs no
    # fetch here — only ever a DB read. A video with no transcript on record
    # yields `[]`, which `bad_timestamp` fails closed against: it rejects any
    # cited timestamp rather than letting an unverifiable one through.
    segments = transcript.cached(conn, video_id)
    bad = rails.bad_timestamp(text, segments)
    if bad:
        raise PostBlocked("bad_timestamp")

    elapsed = seconds_since_last_post(conn, now)
    if elapsed is not None:
        rng = cfg.get("rng") or random.Random()
        if elapsed < rails.next_delay_seconds(rng):
            raise PostBlocked("too_soon")

    position = video["comment_count_at_seen"] if video else 0

    try:
        comment_id = insert(client, video_id, text)
    except Exception as e:
        # A `transient` error (SSL failure, 5xx) means we don't know whether the
        # write reached YouTube before the response failed. Read back rather than
        # assume either way: if the comment is there, record it like any other
        # successful post; if not, this really was a failure and propagates as
        # one. Never blind-retry the insert itself here — see `_find_landed`.
        if classify_error(e) != "transient":
            raise
        # Resolved lazily — only the ghost-post trap needs to know our own
        # channel id, so a normal tick never pays for this lookup. A caller
        # can pass a pre-resolved id via `our_channel_id` (tests do, to stay
        # network-free); otherwise, if it also passed our internal channel
        # token via `channel`, resolve it through the same OAuth binding
        # `client` itself uses. With neither, `_find_landed` can't verify
        # authorship and safely refuses to claim anything.
        our_channel_id = cfg.get("our_channel_id")
        if our_channel_id is None:
            channel_token = cfg.get("channel")
            if channel_token:
                from studio.providers.publish import channel_info
                our_channel_id = channel_info(channel_token).get("id", "")
            else:
                our_channel_id = ""
        landed_id = _find_landed(client, video_id, text, our_channel_id)
        if landed_id is None:
            raise
        comment_id = landed_id

    conn.execute(
        """INSERT INTO comments (comment_id, video_id, text, variant_rank, critic_score,
                                 critic_breakdown, style_tag, posted_at, first_comment,
                                 comment_position_at_post)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (comment_id, video_id, text, variant_rank, verdict.score,
         json.dumps(verdict.breakdown), style_tag, _iso(now),
         1 if position == 0 else 0, position))
    conn.execute("UPDATE videos SET decision = 'posted' WHERE video_id = ?", (video_id,))
    conn.commit()
    if video:
        watchlist.mark_commented(conn, video["channel_id"], _iso(now))
    return comment_id
