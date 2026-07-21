"""Populate channel_daily from the YouTube Analytics API.

The switchback readout compares subscriber gain on ON days against OFF days, so
somebody has to write those days down. This is that job. Without it,
`experiment.readout` has nothing to read and always reports insufficient_data.

Note this is youtubeAnalytics v2, a different service from the Data API used
everywhere else in this package, and it is queried by date range rather than by
video.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from studio.guerrilla import experiment

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


def build(channel: str = ""):
    """Authorized youtubeAnalytics resource. Needs the analytics scope granted."""
    from googleapiclient.discovery import build as _build

    from studio.guerrilla.client import SCOPES
    from studio.providers.publish import _creds

    return _build("youtubeAnalytics", "v2",
                  credentials=_creds(channel, SCOPES + [ANALYTICS_SCOPE]))


def daily_rows(analytics, channel_id: str, start: date, end: date) -> list[dict]:
    """One row per day of views and subscribers gained."""
    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        metrics="views,subscribersGained",
        dimensions="day",
        sort="day",
    ).execute()
    out = []
    for row in resp.get("rows", []):
        out.append({"date": row[0], "views": int(row[1]), "subs_gained": int(row[2])})
    return out


def _comments_on(conn: sqlite3.Connection, day: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) c FROM comments WHERE substr(posted_at, 1, 10) = ?",
        (day,)).fetchone()["c"]


def run(conn: sqlite3.Connection, analytics, channel_id: str, start: date, end: date,
        experiment_start: date, publish_dates: set[str]) -> int:
    """Fill channel_daily for the range. Returns the number of days written."""
    rows = daily_rows(analytics, channel_id, start, end)
    for r in rows:
        day = date.fromisoformat(r["date"])
        experiment.record_day(
            conn, r["date"],
            subs_gained=r["subs_gained"],
            views=r["views"],
            channel_page_views=0,
            comments_posted=_comments_on(conn, r["date"]),
            state=experiment.state_for(day, experiment_start),
            published_video=r["date"] in publish_dates,
        )
    return len(rows)
