"""The target-channel watchlist — the compounding asset of the loop.

Polling a known channel's uploads playlist costs 1 quota unit; discovering one
by search costs 100. The watchlist is what keeps the daily loop cheap.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from studio.guerrilla import db

COOLDOWN_HOURS = 72  # at most one comment per target channel per 3 days


def add(conn: sqlite3.Connection, channel_id: str, title: str = "", subs: int = 0,
        median_views: int = 0, topic_tags: str = "", added_by: str = "manual",
        uploads_playlist: str = "") -> None:
    """Insert or refresh a target channel. Preserves status and last_commented_at."""
    conn.execute(
        """INSERT INTO channels (channel_id, title, subs, median_views, topic_tags,
                                 added_at, added_by, uploads_playlist)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(channel_id) DO UPDATE SET
             title = excluded.title,
             subs = excluded.subs,
             median_views = excluded.median_views,
             topic_tags = excluded.topic_tags,
             uploads_playlist = CASE WHEN excluded.uploads_playlist != ''
                                     THEN excluded.uploads_playlist
                                     ELSE channels.uploads_playlist END""",
        (channel_id, title, subs, median_views, topic_tags, db.now_iso(),
         added_by, uploads_playlist),
    )
    conn.commit()


def active(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM channels WHERE status = 'active' ORDER BY median_views DESC"))


def all_channels(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every watchlist channel regardless of status, active first. Lets the
    operator see paused channels — `active()` alone hides them, and since
    `add()` deliberately preserves `status`, a paused channel is otherwise
    invisible until explicitly resumed."""
    return list(conn.execute(
        """SELECT * FROM channels
           ORDER BY (status = 'active') DESC, median_views DESC"""))


def set_status(conn: sqlite3.Connection, channel_id: str, status: str) -> None:
    conn.execute("UPDATE channels SET status = ? WHERE channel_id = ?", (status, channel_id))
    conn.commit()


def mark_commented(conn: sqlite3.Connection, channel_id: str, when: str = "") -> None:
    conn.execute("UPDATE channels SET last_commented_at = ? WHERE channel_id = ?",
                 (when or db.now_iso(), channel_id))
    conn.commit()


def on_cooldown(row: sqlite3.Row, now: datetime, hours: int = COOLDOWN_HOURS) -> bool:
    """True while the channel is inside its per-channel quiet period."""
    last = row["last_commented_at"]
    if not last:
        return False
    dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt) < timedelta(hours=hours)
