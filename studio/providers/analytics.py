"""Post-publish data for the marketing-guru loop — stats, comments, retention.

Reuses the SAME per-channel OAuth token as publishing (`token_<channel>.json`).
Views/likes/comments + comment text come from the YouTube Data API v3 and need only
the `youtube.readonly` scope that publishing already grants — no re-auth.

Retention (averageViewPercentage) comes from the YouTube Analytics API, which needs
the extra `yt-analytics.readonly` scope. We fetch it BEST-EFFORT: if the token lacks
the scope (or the call fails), retention is left None and the loop carries on with
velocity + engagement. To unlock retention, add the scope (see
docs/50-marketing/analytics.md) and re-auth once.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from studio.providers import publish as pub

# extra scope for retention/watch-time time-series (additive to publish.SCOPES)
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"

_VID_RE = re.compile(r"[?&]v=([\w-]{6,})")


def video_id_from_url(url: str) -> str:
    """Pull the video id out of a publish-receipt URL/note."""
    m = _VID_RE.search(url or "")
    return m.group(1) if m else ""


def _yt(channel: str = ""):
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=pub._creds(channel))


def _analytics(channel: str = ""):
    from googleapiclient.discovery import build

    # request the superset so the token (re)grants both upload and analytics scopes.
    creds = pub._creds(channel, scopes=pub.SCOPES + [ANALYTICS_SCOPE])
    return build("youtubeAnalytics", "v2", credentials=creds)


def _age_days(published_at: str) -> float:
    if not published_at:
        return 0.0
    dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    return round((datetime.now(timezone.utc) - dt).total_seconds() / 86400.0, 2)


def video_stats(video_ids: list[str], channel: str = "") -> dict[str, dict]:
    """Batch-fetch snippet+statistics for up to 50 ids. Returns {video_id: {...}}."""
    ids = [v for v in video_ids if v]
    if not ids:
        return {}
    yt = _yt(channel)
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        resp = yt.videos().list(part="snippet,statistics", id=",".join(batch)).execute()
        for it in resp.get("items", []):
            st = it.get("statistics", {})
            sn = it.get("snippet", {})
            pub_at = sn.get("publishedAt", "")
            out[it["id"]] = {
                "title": sn.get("title", ""),
                "published_at": pub_at,
                "age_days": _age_days(pub_at),
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
            }
    return out


def retention(video_id: str, channel: str = "") -> float | None:
    """averageViewPercentage (0-100) for a video. None if scope/data unavailable."""
    if not video_id:
        return None
    try:
        ya = _analytics(channel)
        resp = ya.reports().query(
            ids="channel==MINE", startDate="2005-01-01",
            endDate=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            metrics="averageViewPercentage,subscribersGained",
            filters=f"video=={video_id}",
        ).execute()
        rows = resp.get("rows", [])
        return round(float(rows[0][0]), 2) if rows else None
    except Exception:
        return None  # missing scope or no data — degrade gracefully


def subs_gained(video_id: str, channel: str = "") -> int:
    if not video_id:
        return 0
    try:
        ya = _analytics(channel)
        resp = ya.reports().query(
            ids="channel==MINE", startDate="2005-01-01",
            endDate=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            metrics="subscribersGained", filters=f"video=={video_id}",
        ).execute()
        rows = resp.get("rows", [])
        return int(rows[0][0]) if rows else 0
    except Exception:
        return 0


def comments(video_id: str, channel: str = "", limit: int = 100) -> list[dict]:
    """Top comment threads (by relevance). [{author, text, likes, published_at}]."""
    if not video_id:
        return []
    yt = _yt(channel)
    out: list[dict] = []
    page = None
    try:
        while len(out) < limit:
            resp = yt.commentThreads().list(
                part="snippet", videoId=video_id, order="relevance",
                maxResults=min(100, limit - len(out)), pageToken=page,
                textFormat="plainText",
            ).execute()
            for it in resp.get("items", []):
                c = it["snippet"]["topLevelComment"]["snippet"]
                out.append({
                    "author": c.get("authorDisplayName", ""),
                    "text": c.get("textDisplay", ""),
                    "likes": int(c.get("likeCount", 0)),
                    "published_at": c.get("publishedAt", ""),
                })
            page = resp.get("nextPageToken")
            if not page:
                break
    except Exception:
        pass  # comments disabled / quota — return whatever we got
    return out


def recent_uploads(channel: str = "", n: int = 25) -> list[dict]:
    """Most recent uploads for the bound channel: [{video_id, title, published_at}]."""
    yt = _yt(channel)
    ch = yt.channels().list(part="contentDetails", mine=True).execute().get("items", [])
    if not ch:
        return []
    uploads = ch[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(
        part="contentDetails,snippet", playlistId=uploads, maxResults=min(50, n),
    ).execute().get("items", [])
    return [{
        "video_id": it["contentDetails"]["videoId"],
        "title": it["snippet"]["title"],
        "published_at": it["contentDetails"].get("videoPublishedAt", ""),
    } for it in items[:n]]
