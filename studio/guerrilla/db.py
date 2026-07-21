"""SQLite store for the guerrilla-marketing loop.

Relational rather than the JSON ledger used by `studio/marketing/journal.py`:
every effectiveness question this system asks ("which style earns likes?",
"which channel tier converts?") is a GROUP BY.

Skipped videos are recorded alongside posted ones. Without them the gates can
never be tuned — only survivors would ever be visible.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from studio import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    channel_id        TEXT PRIMARY KEY,
    title             TEXT NOT NULL DEFAULT '',
    subs              INTEGER NOT NULL DEFAULT 0,
    median_views      INTEGER NOT NULL DEFAULT 0,
    upload_freq       REAL    NOT NULL DEFAULT 0.0,
    topic_tags        TEXT    NOT NULL DEFAULT '',
    status            TEXT    NOT NULL DEFAULT 'active',
    added_at          TEXT    NOT NULL DEFAULT '',
    added_by          TEXT    NOT NULL DEFAULT 'manual',
    last_commented_at TEXT    NOT NULL DEFAULT '',
    uploads_playlist  TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS videos (
    video_id               TEXT PRIMARY KEY,
    channel_id             TEXT NOT NULL REFERENCES channels(channel_id),
    title                  TEXT NOT NULL DEFAULT '',
    description            TEXT NOT NULL DEFAULT '',
    published_at           TEXT NOT NULL DEFAULT '',
    seen_at                TEXT NOT NULL DEFAULT '',
    age_at_seen_min        REAL NOT NULL DEFAULT 0.0,
    comment_count_at_seen  INTEGER NOT NULL DEFAULT 0,
    view_count_at_seen     INTEGER NOT NULL DEFAULT 0,
    comments_enabled       INTEGER NOT NULL DEFAULT 1,
    topic                  TEXT NOT NULL DEFAULT '',
    topic_confidence       REAL NOT NULL DEFAULT 0.0,
    decision               TEXT NOT NULL DEFAULT 'pending',
    skip_reason            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS comments (
    comment_id                TEXT PRIMARY KEY,
    video_id                  TEXT NOT NULL REFERENCES videos(video_id),
    text                      TEXT NOT NULL,
    variant_rank              INTEGER NOT NULL DEFAULT 0,
    critic_score              REAL NOT NULL DEFAULT 0.0,
    critic_breakdown          TEXT NOT NULL DEFAULT '{}',
    style_tag                 TEXT NOT NULL DEFAULT '',
    posted_at                 TEXT NOT NULL DEFAULT '',
    first_comment             INTEGER NOT NULL DEFAULT 0,
    comment_position_at_post  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS comment_metrics (
    comment_id  TEXT NOT NULL REFERENCES comments(comment_id),
    checked_at  TEXT NOT NULL,
    likes       INTEGER NOT NULL DEFAULT 0,
    replies     INTEGER NOT NULL DEFAULT 0,
    hearted     INTEGER NOT NULL DEFAULT 0,
    pinned      INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (comment_id, checked_at)
);

CREATE TABLE IF NOT EXISTS channel_daily (
    date               TEXT PRIMARY KEY,
    subs_gained        INTEGER NOT NULL DEFAULT 0,
    views              INTEGER NOT NULL DEFAULT 0,
    channel_page_views INTEGER NOT NULL DEFAULT 0,
    comments_posted    INTEGER NOT NULL DEFAULT 0,
    switchback_state   TEXT NOT NULL DEFAULT 'off',
    published_video    INTEGER NOT NULL DEFAULT 0
);

-- Single-row table: persists whether the shadowban circuit breaker is tripped,
-- so the Telegram alert fires once per trip rather than on every tick while
-- the survival rate stays low, and `guerrilla approve` / `report.render` can
-- see the state without recomputing it. Cleared only by `guerrilla resume`.
CREATE TABLE IF NOT EXISTS breaker_state (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    tripped       INTEGER NOT NULL DEFAULT 0,
    tripped_at    TEXT    NOT NULL DEFAULT '',
    rate_at_trip  REAL    NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS transcripts (
    video_id   TEXT PRIMARY KEY REFERENCES videos(video_id),
    fetched_at TEXT NOT NULL DEFAULT '',
    duration   REAL NOT NULL DEFAULT 0.0,
    segments   TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_videos_decision ON videos(decision);
CREATE INDEX IF NOT EXISTS idx_comments_posted_at ON comments(posted_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path(channel: str) -> Path:
    return paths.guerrilla_dir(channel) / "guerrilla.db"


def _init(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def connect(channel: str) -> sqlite3.Connection:
    """Open (creating if needed) the channel's database."""
    path = db_path(channel)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL")
    return _init(conn)


def connect_memory() -> sqlite3.Connection:
    """An in-memory database with the same schema. For tests."""
    return _init(sqlite3.connect(":memory:"))
