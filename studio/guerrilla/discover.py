"""Find candidate videos by polling watchlist channels' uploads playlists.

Quota: channels.list = 1 unit, playlistItems.list = 1 unit, videos.list = 1 unit.
A 60-channel watchlist polled every 30 minutes costs well under the 10,000/day
default. Search (100 units) is reserved for the weekly sweep.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from studio.guerrilla import db


def uploads_playlist_id(client, channel_id: str) -> str:
    items = client.channels().list(part="contentDetails", id=channel_id).execute().get("items", [])
    if not items:
        return ""
    return items[0]["contentDetails"]["relatedPlaylists"].get("uploads", "")


def recent_uploads(client, playlist_id: str, max_results: int = 5) -> list[dict]:
    resp = client.playlistItems().list(
        part="snippet", playlistId=playlist_id, maxResults=max_results).execute()
    out = []
    for it in resp.get("items", []):
        sn = it["snippet"]
        out.append({
            "video_id": sn["resourceId"]["videoId"],
            "title": sn.get("title", ""),
            "description": sn.get("description", ""),
            "published_at": sn.get("publishedAt", ""),
        })
    return out


def video_stats(client, video_ids: list[str]) -> dict[str, dict]:
    """Batch-fetch view/comment counts for up to 50 ids at a time."""
    ids = [v for v in video_ids if v]
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        resp = client.videos().list(
            part="snippet,statistics,status", id=",".join(batch)).execute()
        for it in resp.get("items", []):
            st = it.get("statistics", {})
            # YouTube omits commentCount entirely when comments are disabled.
            enabled = it.get("_comments_enabled", "commentCount" in st)
            out[it["id"]] = {
                "views": int(st.get("viewCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "comments_enabled": bool(enabled),
            }
    return out


def age_minutes(published_at: str, now: datetime) -> float:
    """Minutes between `published_at` and `now`. Shared with `rank.evaluate`, which
    must judge a pending video's CURRENT age rather than the `age_at_seen_min`
    snapshot recorded here at discovery time — that snapshot only ever reflects
    the video's age the moment it was first seen, and a video left `pending` for
    days would otherwise pass the age gate forever.

    An unknown/empty `published_at` fails CLOSED (infinitely old) rather than
    open (age zero) — the latter would let a video with a blank timestamp pass
    the age gate forever, exactly the bug this function exists to prevent for
    stale `pending` rows."""
    if not published_at:
        return float("inf")
    dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return round((now - dt).total_seconds() / 60.0, 1)


def record_candidates(conn: sqlite3.Connection, client, channel_id: str,
                      now: datetime) -> list[str]:
    """Poll one channel and insert any videos not already seen. Returns new ids."""
    row = conn.execute("SELECT uploads_playlist FROM channels WHERE channel_id = ?",
                       (channel_id,)).fetchone()
    playlist = row["uploads_playlist"] if row else ""
    if not playlist:
        playlist = uploads_playlist_id(client, channel_id)
        if not playlist:
            return []
        conn.execute("UPDATE channels SET uploads_playlist = ? WHERE channel_id = ?",
                     (playlist, channel_id))
        conn.commit()

    uploads = recent_uploads(client, playlist)
    known = {r["video_id"] for r in conn.execute("SELECT video_id FROM videos")}
    fresh = [u for u in uploads if u["video_id"] not in known]
    if not fresh:
        return []

    stats = video_stats(client, [u["video_id"] for u in fresh])
    seen_at = db.now_iso()
    for u in fresh:
        s = stats.get(u["video_id"], {})
        conn.execute(
            """INSERT INTO videos (video_id, channel_id, title, description, published_at,
                                   seen_at, age_at_seen_min, comment_count_at_seen,
                                   view_count_at_seen, comments_enabled, decision)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (u["video_id"], channel_id, u["title"], u["description"], u["published_at"],
             seen_at, age_minutes(u["published_at"], now),
             s.get("comments", 0), s.get("views", 0),
             1 if s.get("comments_enabled", True) else 0),
        )
    conn.commit()
    return [u["video_id"] for u in fresh]
