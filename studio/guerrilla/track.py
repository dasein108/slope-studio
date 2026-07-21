"""Re-read our own comments and watch for mass removal.

Survival rate is the single most important number this system produces. Rate
limits reduce ban risk; only the breaker RESPONDS to it. Comments quietly
deleted or held for review is what a shadowban looks like from the outside, and
catching it at 15% attrition is a different outcome than finding it at 100%.
"""

from __future__ import annotations

import sqlite3

from studio.guerrilla import db

BREAKER_THRESHOLD = 0.85
BREAKER_WINDOW = 50
# A single deleted comment out of one or two tracked reads as 0% survival —
# without a floor, that would trip the breaker (and halt the cron until a
# manual `guerrilla resume`) on noise: a commenter deleting their own reply, a
# moderation-queue race, not a genuine mass removal. Comfortably below
# BREAKER_WINDOW so a real mass deletion still trips promptly once enough
# comments exist to judge.
MIN_BREAKER_SAMPLE = 10


def refresh(conn: sqlite3.Connection, client, limit: int = 200) -> int:
    """Re-check the most recent comments. Returns how many were checked."""
    ids = [r["comment_id"] for r in conn.execute(
        "SELECT comment_id FROM comments ORDER BY posted_at DESC LIMIT ?", (limit,))]
    if not ids:
        return 0

    checked_at = db.now_iso()
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        resp = client.commentThreads().list(part="snippet", id=",".join(batch)).execute()
        found = {}
        for it in resp.get("items", []):
            sn = it["snippet"]
            top = sn["topLevelComment"]["snippet"]
            found[it["id"]] = {
                "likes": int(top.get("likeCount", 0)),
                "replies": int(sn.get("totalReplyCount", 0)),
                "hearted": 1 if top.get("viewerRating") == "like" else 0,
                "pinned": 0,
                "status": "live" if sn.get("isPublic", True) else "held",
            }
        for cid in batch:
            m = found.get(cid, {"likes": 0, "replies": 0, "hearted": 0,
                                "pinned": 0, "status": "deleted"})
            conn.execute(
                """INSERT OR REPLACE INTO comment_metrics
                   (comment_id, checked_at, likes, replies, hearted, pinned, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cid, checked_at, m["likes"], m["replies"], m["hearted"],
                 m["pinned"], m["status"]))
    conn.commit()
    return len(ids)


def _tracked_statuses(conn: sqlite3.Connection, window: int = BREAKER_WINDOW) -> list[str]:
    """Latest status per comment, trailing `window` comments by posted_at. Shared
    by `survival_rate` (which reports on whatever it finds) and `check_breaker`
    (which additionally needs the sample count, not just the ratio)."""
    rows = conn.execute(
        """SELECT m.status FROM comment_metrics m
           JOIN (SELECT comment_id, MAX(checked_at) AS latest
                 FROM comment_metrics GROUP BY comment_id) l
             ON l.comment_id = m.comment_id AND l.latest = m.checked_at
           JOIN comments c ON c.comment_id = m.comment_id
           ORDER BY c.posted_at DESC LIMIT ?""", (window,))
    return [r["status"] for r in rows]


def survival_rate(conn: sqlite3.Connection, window: int = BREAKER_WINDOW) -> float:
    """Fraction of the trailing `window` comments still live at their last check."""
    statuses = _tracked_statuses(conn, window)
    if not statuses:
        return 1.0
    live = sum(1 for s in statuses if s == "live")
    return round(live / len(statuses), 4)


def breaker_status(conn: sqlite3.Connection) -> dict:
    """Persisted breaker state: {tripped, tripped_at, rate_at_trip}."""
    row = conn.execute("SELECT * FROM breaker_state WHERE id = 1").fetchone()
    if not row:
        return {"tripped": False, "tripped_at": "", "rate_at_trip": 0.0}
    return {"tripped": bool(row["tripped"]), "tripped_at": row["tripped_at"],
            "rate_at_trip": row["rate_at_trip"]}


def is_tripped(conn: sqlite3.Connection) -> bool:
    return breaker_status(conn)["tripped"]


def trip_breaker(conn: sqlite3.Connection, rate: float) -> None:
    """Persist the trip so `check_breaker` stops re-alerting and `guerrilla
    approve` can refuse to post while a suspected shadowban is unresolved."""
    conn.execute(
        """INSERT INTO breaker_state (id, tripped, tripped_at, rate_at_trip)
           VALUES (1, 1, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             tripped = 1, tripped_at = excluded.tripped_at,
             rate_at_trip = excluded.rate_at_trip""",
        (db.now_iso(), rate))
    conn.commit()


def resume(conn: sqlite3.Connection) -> None:
    """Clear a tripped breaker. Deliberately manual — an auto-clear (e.g. once
    the rate recovers) would defeat the point of stopping to investigate."""
    conn.execute(
        """INSERT INTO breaker_state (id, tripped, tripped_at, rate_at_trip)
           VALUES (1, 0, '', 0.0)
           ON CONFLICT(id) DO UPDATE SET tripped = 0, tripped_at = '', rate_at_trip = 0.0""")
    conn.commit()


def check_breaker(conn: sqlite3.Connection, notify=None) -> bool:
    """True if the loop should auto-pause. Sends the Telegram alert only on the
    tick that actually trips the breaker — once persisted, later calls return
    True again without re-alerting, until `resume` clears it.

    Requires at least `MIN_BREAKER_SAMPLE` tracked comments before a low rate
    can trip anything — see that constant's docstring for why."""
    if is_tripped(conn):
        return True
    if notify is None:
        from studio.notify import telegram
        notify = telegram
    statuses = _tracked_statuses(conn)
    if len(statuses) < MIN_BREAKER_SAMPLE:
        return False
    live = sum(1 for s in statuses if s == "live")
    rate = round(live / len(statuses), 4)
    if rate >= BREAKER_THRESHOLD:
        return False
    trip_breaker(conn, rate)
    notify(f"⚠️ guerrilla: comment survival {rate:.0%} is below "
           f"{BREAKER_THRESHOLD:.0%} — loop paused. Possible shadowban; "
           f"investigate before resuming.")
    return True
