# Guerrilla Marketing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `studio guerrilla` — a rate-disciplined bot that posts 10-25 on-topic comments per day under adjacent creators' new YouTube videos, tracks their reception, and measures via switchback whether the activity moves subscribers at all.

**Architecture:** A new `studio/guerrilla/` package behind a Typer sub-app, storing everything in SQLite at `runs/_guerrilla/<channel>/guerrilla.db`. Discovery, ranking, topic classification, composition, critique, and the rate rails are pure functions over data — testable from fixtures with no network. Exactly two modules touch the YouTube API (`client.py` builds the resource; `post.py` writes), so the ban surface is auditable in one place.

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, stdlib `sqlite3`, `google-api-python-client` (existing `youtube` extra), `studio.providers.llm` for LLM calls, `studio.notify` for Telegram, pytest.

**Spec:** `docs/superpowers/specs/2026-07-18-guerrilla-marketing-design.md`
**Branch:** `feat/guerrilla-marketing` (already exists, spec already committed)

## Global Constraints

- Python >= 3.11. Ruff line-length 120 (`pyproject.toml`).
- No new third-party dependencies. Statistics use stdlib `random` and `statistics` — do NOT add scipy or numpy.
- Every module imports `googleapiclient` **lazily inside functions**, matching `studio/providers/publish.py` and `analytics.py`. The `youtube` extra is optional; a top-level import breaks keyless test runs.
- Comments must never contain a link, the channel name, or self-promotion. This is enforced in code by a deny-list, never entrusted to the LLM.
- Daily cap configurable 10-25, **default 12**. Ramp to 25 only after two clean weeks.
- Switchback default: 4 days ON, 2 days OFF, 8-week horizon.
- Circuit breaker: comment survival rate below **0.85** over the trailing 50 comments auto-pauses the loop.
- Dislikes are out of scope — the API does not expose them.
- Timestamps stored as ISO-8601 UTC strings with `timespec="seconds"`, matching `studio/marketing/journal.py`.
- Tests live in `tests/` as flat `test_guerrilla_<area>.py` files, matching the existing convention. Run with `uv run pytest`.

## Deviations From The Spec

Three additions, made for testability. Flagged rather than silently introduced:

1. **`client.py` added.** The spec has `discover`/`post`/`track` each calling the API. A single injection point lets every other module take a `client` argument and be tested against a fake.
2. **`rails.py` split out of `post.py`.** The spec puts rate discipline in `post.py`. The predicates (deny-list, similarity, active window, blackout) are pure and deserve tests that need no client; `post.py` keeps the I/O and calls them.
3. **`report.py` added.** Effectiveness reporting is separate from switchback mechanics, so `experiment.py` stays focused on scheduling and readout.

## File Structure

| File | Responsibility |
|---|---|
| `studio/guerrilla/__init__.py` | Package marker |
| `studio/guerrilla/db.py` | SQLite schema, connection, path |
| `studio/guerrilla/client.py` | Build the YouTube API resource; single injection point |
| `studio/guerrilla/watchlist.py` | Target-channel CRUD, cooldown predicate |
| `studio/guerrilla/discover.py` | Poll uploads playlists, record candidate videos |
| `studio/guerrilla/rank.py` | Hard gates and sorting |
| `studio/guerrilla/topic.py` | Title+description to `{topic, confidence}` |
| `studio/guerrilla/compose.py` | Generate 3 comment variants |
| `studio/guerrilla/critic.py` | Score variants, decide auto/queue/skip |
| `studio/guerrilla/rails.py` | Pure rate-discipline predicates |
| `studio/guerrilla/post.py` | `commentThreads.insert`, error classification |
| `studio/guerrilla/track.py` | Refresh comment metrics, survival rate, breaker |
| `studio/guerrilla/experiment.py` | Switchback schedule and readout |
| `studio/guerrilla/report.py` | Effectiveness report by style tag and channel tier |
| `studio/guerrilla/loop.py` | One tick, orchestrating the above |
| `studio/paths.py` | Modify: add `guerrilla_dir()` |
| `studio/cli.py` | Modify: add the `guerrilla` Typer sub-app |
| `tests/fixtures/guerrilla/fake_yt.py` | Fake YouTube client used by every test |

---

### Task 1: Database schema and paths

**Files:**
- Create: `studio/guerrilla/__init__.py`
- Create: `studio/guerrilla/db.py`
- Modify: `studio/paths.py` (add `guerrilla_dir`, next to `brand_dir`)
- Test: `tests/test_guerrilla_db.py`

**Interfaces:**
- Consumes: `studio.paths.RUNS_ROOT`
- Produces: `db.db_path(channel) -> Path`, `db.connect(channel) -> sqlite3.Connection`, `db.connect_memory() -> sqlite3.Connection`, `db.now_iso() -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_db.py
from studio.guerrilla import db


def test_connect_memory_creates_all_tables():
    conn = db.connect_memory()
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"channels", "videos", "comments",
            "comment_metrics", "channel_daily"} <= names


def test_rows_are_mappings():
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id, title) VALUES ('UC1', 'Test')")
    row = conn.execute("SELECT * FROM channels").fetchone()
    assert row["title"] == "Test"
    assert row["status"] == "active"


def test_db_path_is_per_channel():
    assert db.db_path("pilot-channel").as_posix() == \
        "runs/_guerrilla/pilot-channel/guerrilla.db"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.guerrilla'`

- [ ] **Step 3: Write the implementation**

Create `studio/guerrilla/__init__.py` as an empty file.

Add to `studio/paths.py`, immediately after `brand_dir`:

```python
def guerrilla_dir(channel: str) -> Path:
    """Guerrilla-marketing state (SQLite db + reports) for one channel."""
    return RUNS_ROOT / "_guerrilla" / channel
```

Create `studio/guerrilla/db.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_db.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/__init__.py studio/guerrilla/db.py studio/paths.py tests/test_guerrilla_db.py
git commit -m "feat(guerrilla): sqlite schema and per-channel db paths"
```

---

### Task 2: Fake YouTube client and the real client builder

**Files:**
- Create: `studio/guerrilla/client.py`
- Create: `tests/fixtures/guerrilla/__init__.py`
- Create: `tests/fixtures/guerrilla/fake_yt.py`
- Test: `tests/test_guerrilla_fake_client.py`

**Interfaces:**
- Consumes: `studio.providers.publish._creds`
- Produces: `client.build(channel) -> Resource`, `client.SCOPES`, and the test double `FakeYouTube(videos=..., playlists=..., threads=...)` exposing `.videos()`, `.playlistItems()`, `.channels()`, `.commentThreads()`, `.search()` with `.list(...).execute()` and `.insert(...).execute()`, plus `.posted` recording every insert and `.raise_on_insert` to force errors.

The fake mimics the shape of `googleapiclient`'s chained builder so the same code path runs in tests and production. Every later task depends on it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_fake_client.py
import pytest

from tests.fixtures.guerrilla.fake_yt import FakeYouTube, FakeHttpError


def test_playlist_items_returns_seeded_videos():
    yt = FakeYouTube(playlists={"PL1": [
        {"video_id": "v1", "title": "A", "description": "d", "published_at": "2026-07-18T10:00:00Z"},
    ]})
    resp = yt.playlistItems().list(part="snippet", playlistId="PL1", maxResults=5).execute()
    assert resp["items"][0]["snippet"]["resourceId"]["videoId"] == "v1"


def test_videos_list_returns_statistics():
    yt = FakeYouTube(videos={"v1": {"views": 900, "comments": 3, "comments_enabled": True}})
    resp = yt.videos().list(part="snippet,statistics", id="v1").execute()
    assert resp["items"][0]["statistics"]["commentCount"] == "3"


def test_insert_records_the_comment_and_returns_an_id():
    yt = FakeYouTube()
    cid = yt.commentThreads().insert(part="snippet", body={
        "snippet": {"videoId": "v1", "topLevelComment": {"snippet": {"textOriginal": "hi"}}}
    }).execute()["id"]
    assert yt.posted == [("v1", "hi")]
    assert cid.startswith("c-")


def test_insert_can_be_forced_to_raise():
    yt = FakeYouTube()
    yt.raise_on_insert = FakeHttpError(403, "commentsDisabled")
    with pytest.raises(FakeHttpError):
        yt.commentThreads().insert(part="snippet", body={
            "snippet": {"videoId": "v1", "topLevelComment": {"snippet": {"textOriginal": "hi"}}}
        }).execute()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_fake_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.fixtures'`

- [ ] **Step 3: Write the implementation**

Create empty `tests/fixtures/__init__.py` and `tests/fixtures/guerrilla/__init__.py`.

Create `tests/fixtures/guerrilla/fake_yt.py`:

```python
"""A fake YouTube Data API resource.

Mimics googleapiclient's chained builder (`yt.videos().list(...).execute()`) so
production code paths run unchanged under test. Records every comment insert in
`.posted` and can be forced to raise via `.raise_on_insert`.
"""

from __future__ import annotations


class FakeHttpError(Exception):
    """Stands in for googleapiclient.errors.HttpError."""

    def __init__(self, status: int, reason: str):
        super().__init__(f"{status} {reason}")
        self.status_code = status
        self.reason = reason


class _Req:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class FakeYouTube:
    def __init__(self, videos=None, playlists=None, threads=None, channels=None, search=None):
        # videos: {video_id: {views, comments, comments_enabled, title, description, published_at}}
        self.videos_data = videos or {}
        # playlists: {playlist_id: [ {video_id, title, description, published_at}, ... ]}
        self.playlists_data = playlists or {}
        # threads: {comment_id: {likes, replies, hearted, pinned, status}}
        self.threads_data = threads or {}
        # channels: {channel_id: {uploads_playlist, title, subs}}
        self.channels_data = channels or {}
        self.search_data = search or []
        self.posted: list[tuple[str, str]] = []
        self.raise_on_insert: Exception | None = None
        self._next_id = 0

    # ---- resource accessors -------------------------------------------------
    def videos(self):
        return _Videos(self)

    def playlistItems(self):
        return _PlaylistItems(self)

    def channels(self):
        return _Channels(self)

    def commentThreads(self):
        return _CommentThreads(self)

    def search(self):
        return _Search(self)


class _Videos:
    def __init__(self, yt):
        self.yt = yt

    def list(self, part="", id="", **kw):
        def run():
            items = []
            for vid in [v for v in id.split(",") if v]:
                d = self.yt.videos_data.get(vid)
                if d is None:
                    continue
                items.append({
                    "id": vid,
                    "snippet": {
                        "title": d.get("title", ""),
                        "description": d.get("description", ""),
                        "publishedAt": d.get("published_at", ""),
                        "channelId": d.get("channel_id", ""),
                    },
                    "statistics": {
                        "viewCount": str(d.get("views", 0)),
                        "commentCount": str(d.get("comments", 0)),
                    },
                    "status": {"madeForKids": d.get("made_for_kids", False)},
                    "_comments_enabled": d.get("comments_enabled", True),
                })
            return {"items": items}
        return _Req(run)


class _PlaylistItems:
    def __init__(self, yt):
        self.yt = yt

    def list(self, part="", playlistId="", maxResults=5, **kw):
        def run():
            entries = self.yt.playlists_data.get(playlistId, [])[:maxResults]
            return {"items": [{
                "snippet": {
                    "resourceId": {"videoId": e["video_id"]},
                    "title": e.get("title", ""),
                    "description": e.get("description", ""),
                    "publishedAt": e.get("published_at", ""),
                }
            } for e in entries]}
        return _Req(run)


class _Channels:
    def __init__(self, yt):
        self.yt = yt

    def list(self, part="", id="", **kw):
        def run():
            items = []
            for cid in [c for c in id.split(",") if c]:
                d = self.yt.channels_data.get(cid, {})
                items.append({
                    "id": cid,
                    "snippet": {"title": d.get("title", "")},
                    "statistics": {"subscriberCount": str(d.get("subs", 0))},
                    "contentDetails": {"relatedPlaylists": {
                        "uploads": d.get("uploads_playlist", "")}},
                })
            return {"items": items}
        return _Req(run)


class _CommentThreads:
    def __init__(self, yt):
        self.yt = yt

    def insert(self, part="", body=None):
        def run():
            if self.yt.raise_on_insert is not None:
                raise self.yt.raise_on_insert
            sn = body["snippet"]
            text = sn["topLevelComment"]["snippet"]["textOriginal"]
            self.yt.posted.append((sn["videoId"], text))
            self.yt._next_id += 1
            return {"id": f"c-{self.yt._next_id}"}
        return _Req(run)

    def list(self, part="", id="", **kw):
        def run():
            items = []
            for cid in [c for c in id.split(",") if c]:
                d = self.yt.threads_data.get(cid)
                if d is None:
                    continue  # absent from the response == deleted
                items.append({
                    "id": cid,
                    "snippet": {
                        "totalReplyCount": d.get("replies", 0),
                        "topLevelComment": {"snippet": {
                            "likeCount": d.get("likes", 0),
                            "viewerRating": "like" if d.get("hearted") else "none",
                        }},
                        "isPublic": d.get("status", "live") != "held",
                    },
                })
            return {"items": items}
        return _Req(run)


class _Search:
    def __init__(self, yt):
        self.yt = yt

    def list(self, **kw):
        def run():
            return {"items": self.yt.search_data}
        return _Req(run)
```

Create `studio/guerrilla/client.py`:

```python
"""The single point where a real YouTube API resource is constructed.

Every other module takes a `client` argument, so tests inject the fake in
`tests/fixtures/guerrilla/fake_yt.py` and never touch the network.
"""

from __future__ import annotations

# force-ssl is what permits writing comments on other people's videos.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def build(channel: str = ""):
    """Authorized YouTube Data API resource for `channel`'s token."""
    from googleapiclient.discovery import build as _build

    from studio.providers.publish import _creds

    return _build("youtube", "v3", credentials=_creds(channel, SCOPES))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_fake_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/client.py tests/fixtures tests/test_guerrilla_fake_client.py
git commit -m "feat(guerrilla): youtube client builder and fake test double"
```

---

### Task 3: Watchlist store

**Files:**
- Create: `studio/guerrilla/watchlist.py`
- Test: `tests/test_guerrilla_watchlist.py`

**Interfaces:**
- Consumes: `db.connect_memory`, `db.now_iso`
- Produces: `watchlist.add(conn, channel_id, title="", subs=0, median_views=0, topic_tags="", added_by="manual", uploads_playlist="") -> None`, `watchlist.active(conn) -> list[sqlite3.Row]`, `watchlist.set_status(conn, channel_id, status) -> None`, `watchlist.mark_commented(conn, channel_id, when) -> None`, `watchlist.on_cooldown(row, now, hours=72) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_watchlist.py
from datetime import datetime, timedelta, timezone

from studio.guerrilla import db, watchlist


def _conn():
    return db.connect_memory()


def test_add_then_active_lists_it():
    conn = _conn()
    watchlist.add(conn, "UC1", title="Deep Thoughts", median_views=20000)
    rows = watchlist.active(conn)
    assert [r["channel_id"] for r in rows] == ["UC1"]
    assert rows[0]["median_views"] == 20000


def test_add_is_idempotent_and_updates_stats():
    conn = _conn()
    watchlist.add(conn, "UC1", title="Old", median_views=100)
    watchlist.add(conn, "UC1", title="New", median_views=500)
    rows = watchlist.active(conn)
    assert len(rows) == 1
    assert rows[0]["title"] == "New" and rows[0]["median_views"] == 500


def test_paused_channels_are_not_active():
    conn = _conn()
    watchlist.add(conn, "UC1")
    watchlist.set_status(conn, "UC1", "paused")
    assert watchlist.active(conn) == []


def test_cooldown_blocks_for_72h_then_clears():
    now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    conn = _conn()
    watchlist.add(conn, "UC1")
    watchlist.mark_commented(conn, "UC1", (now - timedelta(hours=10)).isoformat())
    row = watchlist.active(conn)[0]
    assert watchlist.on_cooldown(row, now) is True

    watchlist.mark_commented(conn, "UC1", (now - timedelta(hours=80)).isoformat())
    row = watchlist.active(conn)[0]
    assert watchlist.on_cooldown(row, now) is False


def test_never_commented_channel_is_not_on_cooldown():
    now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    conn = _conn()
    watchlist.add(conn, "UC1")
    assert watchlist.on_cooldown(watchlist.active(conn)[0], now) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_watchlist.py -v`
Expected: FAIL with `ImportError: cannot import name 'watchlist'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/watchlist.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_watchlist.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/watchlist.py tests/test_guerrilla_watchlist.py
git commit -m "feat(guerrilla): watchlist store with per-channel cooldown"
```

---

### Task 4: Discovery

**Files:**
- Create: `studio/guerrilla/discover.py`
- Test: `tests/test_guerrilla_discover.py`

**Interfaces:**
- Consumes: `watchlist.active`, `db.now_iso`, `FakeYouTube`
- Produces: `discover.uploads_playlist_id(client, channel_id) -> str`, `discover.recent_uploads(client, playlist_id, max_results=5) -> list[dict]` (keys `video_id/title/description/published_at`), `discover.video_stats(client, video_ids) -> dict[str, dict]` (keys `views/comments/comments_enabled`), `discover.record_candidates(conn, client, channel_id, now) -> list[str]` returning newly-inserted video ids

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_discover.py
from datetime import datetime, timezone

from studio.guerrilla import db, discover, watchlist
from tests.fixtures.guerrilla.fake_yt import FakeYouTube

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def _yt():
    return FakeYouTube(
        channels={"UC1": {"uploads_playlist": "UU1", "title": "Deep Thoughts", "subs": 50000}},
        playlists={"UU1": [
            {"video_id": "v1", "title": "The Ship of Theseus",
             "description": "A paradox about identity.",
             "published_at": "2026-07-18T11:30:00Z"},
        ]},
        videos={"v1": {"views": 800, "comments": 4, "comments_enabled": True}},
    )


def test_uploads_playlist_id_is_read_from_the_api():
    assert discover.uploads_playlist_id(_yt(), "UC1") == "UU1"


def test_recent_uploads_normalizes_playlist_items():
    got = discover.recent_uploads(_yt(), "UU1")
    assert got == [{"video_id": "v1", "title": "The Ship of Theseus",
                    "description": "A paradox about identity.",
                    "published_at": "2026-07-18T11:30:00Z"}]


def test_video_stats_reports_comments_enabled():
    st = discover.video_stats(_yt(), ["v1"])
    assert st["v1"] == {"views": 800, "comments": 4, "comments_enabled": True}


def test_record_candidates_inserts_with_age_and_stats():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", uploads_playlist="UU1")
    new = discover.record_candidates(conn, _yt(), "UC1", NOW)
    assert new == ["v1"]
    row = conn.execute("SELECT * FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["age_at_seen_min"] == 30.0
    assert row["comment_count_at_seen"] == 4
    assert row["view_count_at_seen"] == 800
    assert row["comments_enabled"] == 1
    assert row["decision"] == "pending"


def test_record_candidates_is_idempotent():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", uploads_playlist="UU1")
    discover.record_candidates(conn, _yt(), "UC1", NOW)
    assert discover.record_candidates(conn, _yt(), "UC1", NOW) == []
    assert conn.execute("SELECT COUNT(*) c FROM videos").fetchone()["c"] == 1


def test_missing_uploads_playlist_is_fetched_and_cached():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1")  # no playlist yet
    discover.record_candidates(conn, _yt(), "UC1", NOW)
    row = conn.execute("SELECT uploads_playlist FROM channels").fetchone()
    assert row["uploads_playlist"] == "UU1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_discover.py -v`
Expected: FAIL with `ImportError: cannot import name 'discover'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/discover.py
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


def _age_minutes(published_at: str, now: datetime) -> float:
    if not published_at:
        return 0.0
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
             seen_at, _age_minutes(u["published_at"], now),
             s.get("comments", 0), s.get("views", 0),
             1 if s.get("comments_enabled", True) else 0),
        )
    conn.commit()
    return [u["video_id"] for u in fresh]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_discover.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/discover.py tests/test_guerrilla_discover.py
git commit -m "feat(guerrilla): uploads-playlist discovery of candidate videos"
```

---

### Task 5: Ranking gates

**Files:**
- Create: `studio/guerrilla/rank.py`
- Test: `tests/test_guerrilla_rank.py`

**Interfaces:**
- Consumes: `watchlist.on_cooldown`
- Produces: `rank.Gates` (dataclass: `max_age_min=90`, `max_comments=40`, `min_median_views=5000`), `rank.evaluate(video, channel, now, gates, comments_enabled=True) -> tuple[bool, str]`, `rank.rank_candidates(conn, now, gates) -> list[sqlite3.Row]`

`evaluate` returns `(True, "")` when the video passes, else `(False, reason)` where reason is one of `too_old`, `too_many_comments`, `channel_too_small`, `comments_disabled`, `channel_cooldown`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_rank.py
from datetime import datetime, timedelta, timezone

from studio.guerrilla import db, discover, rank, watchlist

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
GATES = rank.Gates()


def _video(**kw):
    base = {"age_at_seen_min": 30.0, "comment_count_at_seen": 5}
    base.update(kw)
    return base


def _channel(conn=None, **kw):
    c = db.connect_memory() if conn is None else conn
    watchlist.add(c, "UC1", median_views=kw.get("median_views", 20000))
    if "last_commented_at" in kw:
        watchlist.mark_commented(c, "UC1", kw["last_commented_at"])
    return watchlist.active(c)[0]


def test_fresh_popular_video_passes():
    assert rank.evaluate(_video(), _channel(), NOW, GATES) == (True, "")


def test_old_video_is_rejected():
    ok, why = rank.evaluate(_video(age_at_seen_min=200.0), _channel(), NOW, GATES)
    assert (ok, why) == (False, "too_old")


def test_crowded_video_is_rejected():
    ok, why = rank.evaluate(_video(comment_count_at_seen=90), _channel(), NOW, GATES)
    assert (ok, why) == (False, "too_many_comments")


def test_small_channel_is_rejected():
    ok, why = rank.evaluate(_video(), _channel(median_views=900), NOW, GATES)
    assert (ok, why) == (False, "channel_too_small")


def test_comments_disabled_is_rejected():
    ok, why = rank.evaluate(_video(), _channel(), NOW, GATES, comments_enabled=False)
    assert (ok, why) == (False, "comments_disabled")


def test_channel_on_cooldown_is_rejected():
    recent = (NOW - timedelta(hours=5)).isoformat()
    ok, why = rank.evaluate(_video(), _channel(last_commented_at=recent), NOW, GATES)
    assert (ok, why) == (False, "channel_cooldown")


def test_rank_candidates_rejects_videos_with_comments_disabled():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="P1")
    conn.execute(
        """INSERT INTO videos (video_id, channel_id, age_at_seen_min,
                               comment_count_at_seen, comments_enabled, decision)
           VALUES ('v1', 'UC1', 20.0, 3, 0, 'pending')""")
    conn.commit()
    assert rank.rank_candidates(conn, NOW, GATES) == []
    row = conn.execute("SELECT * FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "skipped_gate"
    assert row["skip_reason"] == "comments_disabled"


def test_rank_candidates_sorts_by_channel_median_views():
    conn = db.connect_memory()
    watchlist.add(conn, "UCsmall", median_views=8000, uploads_playlist="P1")
    watchlist.add(conn, "UCbig", median_views=90000, uploads_playlist="P2")
    for vid, ch in (("v1", "UCsmall"), ("v2", "UCbig")):
        conn.execute(
            """INSERT INTO videos (video_id, channel_id, age_at_seen_min,
                                   comment_count_at_seen, comments_enabled, decision)
               VALUES (?, ?, 20.0, 3, 1, 'pending')""", (vid, ch))
    conn.commit()
    got = rank.rank_candidates(conn, NOW, GATES)
    assert [r["video_id"] for r in got] == ["v2", "v1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_rank.py -v`
Expected: FAIL with `ImportError: cannot import name 'rank'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/rank.py
"""Hard gates plus a simple sort.

Deliberately not a learned score: there is no data to calibrate one on day one.
The gates encode the real constraints — a comment on a 2M-sub channel's video
lands 800th and is invisible, so "biggest channel" is the wrong target. Every
raw feature is recorded in `videos`, so a scoring model or bandit can be trained
later without a backfill.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from studio.guerrilla import watchlist


@dataclass(frozen=True)
class Gates:
    max_age_min: float = 90.0        # be early enough to hold a top slot
    max_comments: int = 40           # past this, a new comment is buried
    min_median_views: int = 5000     # below this there is no audience to reach


def evaluate(video, channel, now: datetime, gates: Gates,
             comments_enabled: bool = True) -> tuple[bool, str]:
    """(passed, reason). reason is '' when passed."""
    if not comments_enabled:
        return False, "comments_disabled"
    if video["age_at_seen_min"] > gates.max_age_min:
        return False, "too_old"
    if video["comment_count_at_seen"] > gates.max_comments:
        return False, "too_many_comments"
    if channel["median_views"] < gates.min_median_views:
        return False, "channel_too_small"
    if watchlist.on_cooldown(channel, now):
        return False, "channel_cooldown"
    return True, ""


def rank_candidates(conn: sqlite3.Connection, now: datetime,
                    gates: Gates | None = None) -> list[sqlite3.Row]:
    """Pending videos that pass every gate, best first. Records rejections."""
    gates = gates or Gates()
    rows = list(conn.execute(
        """SELECT v.*, c.median_views, c.last_commented_at, c.channel_id AS ch_id
           FROM videos v JOIN channels c ON c.channel_id = v.channel_id
           WHERE v.decision = 'pending' AND c.status = 'active'
           ORDER BY c.median_views DESC"""))
    passed = []
    for r in rows:
        ok, why = evaluate(r, r, now, gates, bool(r["comments_enabled"]))
        if ok:
            passed.append(r)
        else:
            conn.execute(
                "UPDATE videos SET decision = 'skipped_gate', skip_reason = ? WHERE video_id = ?",
                (why, r["video_id"]))
    conn.commit()
    return passed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_rank.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/rank.py tests/test_guerrilla_rank.py
git commit -m "feat(guerrilla): hard gates and candidate ranking"
```

---

### Task 6: Topic classification

**Files:**
- Create: `studio/guerrilla/topic.py`
- Test: `tests/test_guerrilla_topic.py`

**Interfaces:**
- Consumes: `studio.providers.llm.complete`, `studio.config.default_provider`
- Produces: `topic.CONFIDENCE_THRESHOLD = 0.7`, `topic.Topic` (pydantic: `topic: str`, `confidence: float`, `summary: str`), `topic.classify(title, description, provider="", complete=None) -> Topic`, `topic.is_clear(t) -> bool`

The `complete` parameter is an injection seam: tests pass a stub, production leaves it `None` and gets `llm.complete`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_topic.py
import pytest

from studio.guerrilla import topic


def _stub(payload):
    def complete(provider, system, user):
        return payload
    return complete


def test_classify_parses_a_clean_verdict():
    t = topic.classify("The Ship of Theseus", "A paradox about identity.",
                       complete=_stub('{"topic": "identity paradox", "confidence": 0.93,'
                                      ' "summary": "Whether a repaired ship stays itself."}'))
    assert t.topic == "identity paradox"
    assert t.confidence == 0.93
    assert topic.is_clear(t) is True


def test_low_confidence_is_not_clear():
    t = topic.classify("vlog #47", "",
                       complete=_stub('{"topic": "unknown", "confidence": 0.2, "summary": ""}'))
    assert topic.is_clear(t) is False


def test_fenced_json_is_tolerated():
    t = topic.classify("T", "d", complete=_stub(
        '```json\n{"topic": "x", "confidence": 0.8, "summary": "s"}\n```'))
    assert t.topic == "x"


def test_unparseable_output_is_treated_as_unclear_not_an_error():
    t = topic.classify("T", "d", complete=_stub("I'm not sure what this video is about."))
    assert t.confidence == 0.0
    assert topic.is_clear(t) is False


def test_llm_exception_is_treated_as_unclear():
    def boom(provider, system, user):
        raise RuntimeError("upstream 500")

    t = topic.classify("T", "d", complete=boom)
    assert topic.is_clear(t) is False


def test_description_is_truncated_before_prompting():
    seen = {}

    def complete(provider, system, user):
        seen["user"] = user
        return '{"topic": "x", "confidence": 0.9, "summary": "s"}'

    topic.classify("T", "z" * 5000, complete=complete)
    assert len(seen["user"]) < 3000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_topic.py -v`
Expected: FAIL with `ImportError: cannot import name 'topic'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/topic.py
"""Decide what a video is actually about, and how sure we are.

The operator's hard rule: if the subject is not clearly understandable from the
title and description, skip the video. A confidently wrong comment is worse than
no comment — it reads as a bot, which is exactly the signal to avoid.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from studio.config import default_provider

CONFIDENCE_THRESHOLD = 0.7
DESC_LIMIT = 1200

SYSTEM = """You classify YouTube videos by subject so a commenter can decide whether they
understand the video well enough to say something relevant.

Judge ONLY from the title and description given. Do not speculate about content you cannot
see. If the title is generic ("vlog #47", "Episode 12", "my thoughts"), if the description is
empty or purely promotional, or if you cannot name a specific subject, report LOW confidence.
Being unsure is a correct and useful answer.

Output ONLY valid JSON:
{"topic": "<a short noun phrase naming the subject>",
 "confidence": <0.0-1.0, how sure you are what this video is about>,
 "summary": "<one sentence a reader of the video would agree with>"}"""

USER_TMPL = """Title: {title}

Description:
{description}"""


class Topic(BaseModel):
    topic: str = ""
    confidence: float = 0.0
    summary: str = ""


def _strip_fence(raw: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return m.group(1).strip() if m else raw.strip()


def classify(title: str, description: str, provider: str = "", complete=None) -> Topic:
    """Classify one video. Any failure yields confidence 0.0 — never raises."""
    if complete is None:
        from studio.providers import llm
        complete = llm.complete
    provider = provider or default_provider("script")
    user = USER_TMPL.format(title=title, description=(description or "")[:DESC_LIMIT])
    try:
        raw = complete(provider, SYSTEM, user)
        return Topic(**json.loads(_strip_fence(raw)))
    except Exception:
        return Topic()


def is_clear(t: Topic) -> bool:
    return bool(t.topic) and t.confidence >= CONFIDENCE_THRESHOLD
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_topic.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/topic.py tests/test_guerrilla_topic.py
git commit -m "feat(guerrilla): topic classification with skip-when-unclear"
```

---

### Task 7: Comment composition

**Files:**
- Create: `studio/guerrilla/compose.py`
- Test: `tests/test_guerrilla_compose.py`

**Interfaces:**
- Consumes: `studio.providers.llm.complete`, `topic.Topic`
- Produces: `compose.STYLE_TAGS = ("provocative_question", "joke", "contrarian_take", "insight")`, `compose.Variant` (pydantic: `text: str`, `style_tag: str`), `compose.variants(title, topic_summary, provider="", n=3, complete=None) -> list[Variant]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_compose.py
from studio.guerrilla import compose

GOOD = ('{"variants": ['
        '{"text": "If you replace every plank, when exactly did it stop being the ship?",'
        ' "style_tag": "provocative_question"},'
        '{"text": "My car has had 3 new engines and I still owe money on the original.",'
        ' "style_tag": "joke"},'
        '{"text": "The paradox dissolves if identity is a process, not an object.",'
        ' "style_tag": "insight"}]}')


def _stub(payload):
    def complete(provider, system, user):
        return payload
    return complete


def test_variants_are_parsed():
    got = compose.variants("The Ship of Theseus", "A paradox about identity.",
                           complete=_stub(GOOD))
    assert len(got) == 3
    assert got[0].style_tag == "provocative_question"
    assert "plank" in got[0].text


def test_unknown_style_tags_are_normalized_to_insight():
    got = compose.variants("T", "s", complete=_stub(
        '{"variants": [{"text": "hi there friend", "style_tag": "shitpost"}]}'))
    assert got[0].style_tag == "insight"


def test_blank_and_overlong_variants_are_dropped():
    got = compose.variants("T", "s", complete=_stub(
        '{"variants": [{"text": "", "style_tag": "joke"},'
        ' {"text": "' + "x" * 400 + '", "style_tag": "joke"},'
        ' {"text": "a real comment", "style_tag": "joke"}]}'))
    assert [v.text for v in got] == ["a real comment"]


def test_unparseable_output_yields_no_variants():
    assert compose.variants("T", "s", complete=_stub("sorry, I can't")) == []


def test_llm_exception_yields_no_variants():
    def boom(provider, system, user):
        raise RuntimeError("upstream 500")

    assert compose.variants("T", "s", complete=boom) == []


def test_prompt_forbids_self_promotion():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        return GOOD

    compose.variants("T", "s", complete=complete)
    assert "never mention" in seen["system"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_compose.py -v`
Expected: FAIL with `ImportError: cannot import name 'compose'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/compose.py
"""Write candidate comments.

The only leverage is indirect: an interesting comment makes a reader click the
commenter's name. So the comment must never mention us. Self-promotion in
comments is the actual bannable line, and it also does not work.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from studio.config import default_provider

STYLE_TAGS = ("provocative_question", "joke", "contrarian_take", "insight")
MAX_LEN = 280  # long comments get collapsed behind "Read more" and lose their pull

SYSTEM = """You write YouTube comments that make strangers curious enough to click the
commenter's name.

HARD RULES:
- NEVER mention yourself, your channel, your videos, or ask anyone to subscribe, follow, watch,
  or check anything out. No links. No handles. Breaking this rule makes the comment worthless.
- The comment must be unmistakably ABOUT THIS SPECIFIC VIDEO. Generic praise ("great video!",
  "underrated channel") is a failure. A reader must be unable to paste it under a different
  video and have it still fit.
- Sound like one specific person with a real opinion, not a brand. No emoji spam, no hashtags,
  no ALL CAPS, no engagement-bait phrasing ("who else...", "drop a like if...").
- Never insult the creator, the audience, or any group. Provocative means intellectually
  provocative — a claim someone would want to argue with, not an offensive one.
- Under 280 characters.

Write {n} DIFFERENT comments, each with a different style_tag from:
- provocative_question: a question the video's own argument leaves dangling
- joke: genuinely funny and specific to the subject, not a pun on the title
- contrarian_take: a defensible disagreement with the video's premise
- insight: a fact or connection the video missed that adds something

Output ONLY valid JSON:
{{"variants": [{{"text": "...", "style_tag": "..."}}]}}"""

USER_TMPL = """Video title: {title}

What the video is about: {summary}"""


class Variant(BaseModel):
    text: str
    style_tag: str


def _strip_fence(raw: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return m.group(1).strip() if m else raw.strip()


def variants(title: str, topic_summary: str, provider: str = "", n: int = 3,
             complete=None) -> list[Variant]:
    """Generate up to `n` candidate comments. Any failure yields []."""
    if complete is None:
        from studio.providers import llm
        complete = llm.complete
    provider = provider or default_provider("script")
    try:
        raw = complete(provider, SYSTEM.format(n=n),
                       USER_TMPL.format(title=title, summary=topic_summary))
        data = json.loads(_strip_fence(raw))
    except Exception:
        return []

    out: list[Variant] = []
    for item in data.get("variants", []):
        text = (item.get("text") or "").strip()
        if not text or len(text) > MAX_LEN:
            continue
        tag = item.get("style_tag", "")
        out.append(Variant(text=text, style_tag=tag if tag in STYLE_TAGS else "insight"))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_compose.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/compose.py tests/test_guerrilla_compose.py
git commit -m "feat(guerrilla): comment variant generation across style tags"
```

---

### Task 8: The critic

**Files:**
- Create: `studio/guerrilla/critic.py`
- Test: `tests/test_guerrilla_critic.py`

**Interfaces:**
- Consumes: `compose.Variant`
- Produces: `critic.CRITERIA = ("on_topic", "provocative_or_funny", "not_generic", "no_self_promo", "not_offensive")`, `critic.AUTO_POST = 4.0`, `critic.QUEUE = 3.0`, `critic.Verdict` (pydantic: `score: float`, `breakdown: dict[str, float]`, `decision: str`), `critic.judge(variant, title, summary, provider="", complete=None) -> Verdict`, `critic.best(variants, title, summary, ...) -> tuple[Variant | None, Verdict | None, int]` returning the winner, its verdict, and its index

`decision` is one of `auto`, `queue`, `skip`. A zero on any criterion forces `skip` regardless of the mean — a single self-promo or offensive hit is disqualifying, not averageable.

**This critic must not reuse `studio/stages/critic.py`.** That one declines every script it has ever seen (see the `studio-critic-ceiling` finding); reusing it would jam the approval queue at 100%.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_critic.py
from studio.guerrilla import compose, critic


def _stub(payload):
    def complete(provider, system, user):
        return payload
    return complete


def _scores(**kw):
    base = dict.fromkeys(critic.CRITERIA, 4.0)
    base.update(kw)
    import json
    return json.dumps({"scores": base})


def test_strong_comment_is_auto_posted():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(on_topic=5.0)))
    assert v.decision == "auto"
    assert v.score > 4.0


def test_middling_comment_is_queued():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(on_topic=3.0, not_generic=3.0,
                                            provocative_or_funny=3.0)))
    assert v.decision == "queue"


def test_weak_comment_is_skipped():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(on_topic=2.0, not_generic=2.0,
                                            provocative_or_funny=2.0)))
    assert v.decision == "skip"


def test_self_promo_zero_forces_skip_despite_high_mean():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(no_self_promo=0.0, on_topic=5.0,
                                            not_generic=5.0, provocative_or_funny=5.0,
                                            not_offensive=5.0)))
    assert v.decision == "skip"


def test_offensive_zero_forces_skip():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(not_offensive=0.0)))
    assert v.decision == "skip"


def test_unparseable_verdict_skips():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub("no idea"))
    assert v.decision == "skip"


def test_best_picks_the_highest_scoring_variant():
    calls = {"n": 0}
    payloads = [_scores(on_topic=2.0, not_generic=2.0, provocative_or_funny=2.0),
                _scores(on_topic=5.0),
                _scores(on_topic=3.0, not_generic=3.0)]

    def complete(provider, system, user):
        p = payloads[calls["n"]]
        calls["n"] += 1
        return p

    vs = [compose.Variant(text=f"t{i}", style_tag="joke") for i in range(3)]
    winner, verdict, idx = critic.best(vs, "T", "s", complete=complete)
    assert idx == 1 and winner.text == "t1" and verdict.decision == "auto"


def test_best_of_empty_list_returns_nothing():
    assert critic.best([], "T", "s", complete=_stub(_scores())) == (None, None, -1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_critic.py -v`
Expected: FAIL with `ImportError: cannot import name 'critic'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/critic.py
"""Score candidate comments before anything reaches YouTube.

Deliberately NOT the `studio/stages/critic.py` content critic — that one is
calibrated to decline nearly everything, which is fine for a $2 video render and
fatal for a gate that must pass ~12 comments a day.

Two criteria are disqualifying rather than averageable: a comment that promotes
us or insults someone is not "below average", it is unpostable.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from studio.config import default_provider
from studio.guerrilla.compose import Variant

CRITERIA = ("on_topic", "provocative_or_funny", "not_generic", "no_self_promo", "not_offensive")
DISQUALIFYING = ("no_self_promo", "not_offensive")
DISQUALIFY_BELOW = 3.0
AUTO_POST = 4.0
QUEUE = 3.0

SYSTEM = """You judge whether a YouTube comment is worth posting under a specific video, from
an account whose only goal is that readers find the comment interesting enough to click the
commenter's name.

Score each criterion 0-5:
- on_topic: does it engage THIS video's actual subject? A comment that would fit under any
  video scores 0-1.
- provocative_or_funny: would a reader want to reply, argue, or laugh? Bland scores low.
- not_generic: is it specific and particular? "Great video", "so underrated", "first" score 0.
- no_self_promo: 5 if it never references the commenter's own channel/videos and contains no
  link or handle. 0 if it does ANY of that.
- not_offensive: 5 if nobody could reasonably take offense. 0 for insults, slurs, or attacks on
  the creator, the audience, or any group.

Output ONLY valid JSON:
{"scores": {"on_topic": 0.0, "provocative_or_funny": 0.0, "not_generic": 0.0,
            "no_self_promo": 0.0, "not_offensive": 0.0}}"""

USER_TMPL = """Video title: {title}
What the video is about: {summary}

The proposed comment:
{text}"""


class Verdict(BaseModel):
    score: float = 0.0
    breakdown: dict[str, float] = {}
    decision: str = "skip"   # auto | queue | skip


def _strip_fence(raw: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return m.group(1).strip() if m else raw.strip()


def _decide(breakdown: dict[str, float]) -> tuple[float, str]:
    mean = sum(breakdown.values()) / len(breakdown)
    if any(breakdown.get(k, 0.0) < DISQUALIFY_BELOW for k in DISQUALIFYING):
        return mean, "skip"
    if mean >= AUTO_POST:
        return mean, "auto"
    if mean >= QUEUE:
        return mean, "queue"
    return mean, "skip"


def judge(variant: Variant, title: str, summary: str, provider: str = "",
          complete=None) -> Verdict:
    """Score one variant. Any failure yields a skip verdict — never raises."""
    if complete is None:
        from studio.providers import llm
        complete = llm.complete
    provider = provider or default_provider("script")
    try:
        raw = complete(provider, SYSTEM,
                       USER_TMPL.format(title=title, summary=summary, text=variant.text))
        scores = json.loads(_strip_fence(raw))["scores"]
        breakdown = {k: float(scores[k]) for k in CRITERIA}
    except Exception:
        return Verdict()
    mean, decision = _decide(breakdown)
    return Verdict(score=round(mean, 2), breakdown=breakdown, decision=decision)


def best(variants: list[Variant], title: str, summary: str, provider: str = "",
         complete=None) -> tuple[Variant | None, Verdict | None, int]:
    """Judge every variant and return the highest scorer with its index."""
    if not variants:
        return None, None, -1
    judged = [(v, judge(v, title, summary, provider, complete)) for v in variants]
    idx = max(range(len(judged)), key=lambda i: judged[i][1].score)
    v, verdict = judged[idx]
    return v, verdict, idx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_critic.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/critic.py tests/test_guerrilla_critic.py
git commit -m "feat(guerrilla): comment critic with disqualifying criteria"
```

---

### Task 9: Rate-discipline rails

**Files:**
- Create: `studio/guerrilla/rails.py`
- Test: `tests/test_guerrilla_rails.py`

**Interfaces:**
- Consumes: nothing (pure)
- Produces: `rails.violates_denylist(text) -> str` (matched rule name, `""` if clean), `rails.shingles(text, k=4) -> set[str]`, `rails.jaccard(a, b) -> float`, `rails.too_similar(text, recent, threshold=0.5) -> bool`, `rails.in_active_window(now, start_hour=9, end_hour=23) -> bool`, `rails.in_blackout(now, publish_times, hours=6) -> bool`, `rails.next_delay_seconds(rng, base_minutes=12, jitter=0.4) -> float`, `rails.recent_texts(conn, limit=200) -> list[str]`

These are the ban defense. They are pure so they can be exhaustively tested without a client, and `post.py` is the only caller.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_rails.py
import random
from datetime import datetime, timezone

import pytest

from studio.guerrilla import rails


@pytest.mark.parametrize("text,rule", [
    ("check out my channel for more", "self_promo"),
    ("I made a video about this: youtube.com/watch?v=abc", "link"),
    ("https://example.com", "link"),
    ("subscribe if you agree", "self_promo"),
    ("watch my video on this", "self_promo"),
    ("PARADOX NOIR covered this", "channel_name"),
    ("🔥🔥🔥🔥 amazing 🔥🔥", "emoji_spam"),
    ("#philosophy #paradox #shorts", "hashtag"),
])
def test_denylist_catches_violations(text, rule):
    assert rails.violates_denylist(text) == rule


def test_clean_comment_passes_denylist():
    assert rails.violates_denylist(
        "If you replace every plank, when did it stop being the ship?") == ""


def test_jaccard_of_identical_text_is_one():
    assert rails.jaccard(rails.shingles("the ship of theseus paradox"),
                         rails.shingles("the ship of theseus paradox")) == 1.0


def test_near_duplicate_is_rejected():
    recent = ["If you replace every plank, when did it stop being the ship?"]
    assert rails.too_similar(
        "If you replace every plank, when did it stop being a ship?", recent) is True


def test_different_comment_is_allowed():
    recent = ["If you replace every plank, when did it stop being the ship?"]
    assert rails.too_similar(
        "Gödel proved arithmetic cannot prove its own consistency.", recent) is False


def test_empty_history_allows_anything():
    assert rails.too_similar("anything at all", []) is False


def test_active_window_excludes_the_small_hours():
    assert rails.in_active_window(datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)) is True
    assert rails.in_active_window(datetime(2026, 7, 18, 4, 0, tzinfo=timezone.utc)) is False
    assert rails.in_active_window(datetime(2026, 7, 18, 23, 30, tzinfo=timezone.utc)) is False


def test_blackout_covers_six_hours_either_side_of_a_publish():
    pub = ["2026-07-18T12:00:00+00:00"]
    assert rails.in_blackout(datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc), pub) is True
    assert rails.in_blackout(datetime(2026, 7, 18, 7, 0, tzinfo=timezone.utc), pub) is True
    assert rails.in_blackout(datetime(2026, 7, 18, 21, 0, tzinfo=timezone.utc), pub) is False


def test_delay_is_jittered_within_bounds_and_never_constant():
    rng = random.Random(7)
    delays = [rails.next_delay_seconds(rng) for _ in range(50)]
    assert all(12 * 60 * 0.6 <= d <= 12 * 60 * 1.4 for d in delays)
    assert len(set(delays)) > 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_rails.py -v`
Expected: FAIL with `ImportError: cannot import name 'rails'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/rails.py
"""Rate discipline and content rails — the ban defense.

Pure predicates, so every rule is exhaustively testable without a network client.
`post.py` is the only caller; nothing reaches YouTube without passing through here.

The deny-list exists because prompts are advisory and code is not. An LLM that
ignores "never self-promote" once per thousand comments still eventually posts
the comment that gets the channel flagged.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone

# Rules are ordered: the first match names the violation.
DENY_RULES: list[tuple[str, re.Pattern]] = [
    ("link", re.compile(r"https?://|www\.|\b\w+\.(com|net|org|io|be|tv|me)\b", re.I)),
    ("channel_name", re.compile(r"paradox\s*noir|parad0xn01r|slope\s*studio", re.I)),
    ("self_promo", re.compile(
        r"\b(check\s+out|subscribe|my\s+channel|my\s+video|watch\s+my|link\s+in\s+bio|"
        r"i\s+made\s+a\s+video|on\s+my\s+page)\b", re.I)),
    ("hashtag", re.compile(r"#\w+")),
    ("emoji_spam", re.compile(r"[\U0001F300-\U0001FAFF☀-➿]{3,}")),
]

SIMILARITY_THRESHOLD = 0.3        # word-shingle path; unrelated text scores 0.0, one-word edits 0.33+
SHORT_TEXT_THRESHOLD = 0.5        # char-gram path for sub-k-word comments, which over-blocks lower
ACTIVE_START_HOUR = 9
ACTIVE_END_HOUR = 23
BLACKOUT_HOURS = 6
BASE_INTERVAL_MIN = 12
JITTER = 0.4


def violates_denylist(text: str) -> str:
    """Name of the first rule the text breaks, or '' if clean."""
    for name, pattern in DENY_RULES:
        if pattern.search(text):
            return name
    return ""


def shingles(text: str, k: int = 4) -> set[str]:
    """Word k-grams — what near-duplicate detection compares."""
    words = re.findall(r"\w+", text.lower())
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def too_similar(text: str, recent: list[str],
                threshold: float = SIMILARITY_THRESHOLD) -> bool:
    """True if the text closely repeats something recently posted.

    Near-duplicate text across many videos is what YouTube's spam filter
    actually matches on — more so than volume.
    """
    s = shingles(text)
    return any(jaccard(s, shingles(prev)) >= threshold for prev in recent)


def in_active_window(now: datetime, start_hour: int = ACTIVE_START_HOUR,
                     end_hour: int = ACTIVE_END_HOUR) -> bool:
    """Comments only during plausible waking hours. 04:00 posting reads as a bot."""
    return start_hour <= now.hour < end_hour


def in_blackout(now: datetime, publish_times: list[str],
                hours: int = BLACKOUT_HOURS) -> bool:
    """True near one of our own publishes.

    Keeps comment-driven visitors separable from upload-driven ones, which is
    what makes the switchback readout interpretable.
    """
    window = timedelta(hours=hours)
    for ts in publish_times:
        if not ts:
            continue
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if abs(now - dt) <= window:
            return True
    return False


def next_delay_seconds(rng, base_minutes: float = BASE_INTERVAL_MIN,
                       jitter: float = JITTER) -> float:
    """Seconds to wait before the next comment. Never a fixed cadence."""
    factor = 1.0 + rng.uniform(-jitter, jitter)
    return base_minutes * 60.0 * factor


def recent_texts(conn: sqlite3.Connection, limit: int = 200) -> list[str]:
    return [r["text"] for r in conn.execute(
        "SELECT text FROM comments ORDER BY posted_at DESC LIMIT ?", (limit,))]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_rails.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/rails.py tests/test_guerrilla_rails.py
git commit -m "feat(guerrilla): pure rate-discipline and content rails"
```

---

### Task 10: Posting

**Files:**
- Create: `studio/guerrilla/post.py`
- Test: `tests/test_guerrilla_post.py`

**Interfaces:**
- Consumes: `rails`, `db.now_iso`, `watchlist.mark_commented`, `FakeYouTube`, `FakeHttpError`
- Produces: `post.PostBlocked` (exception with `.reason`), `post.classify_error(exc) -> str` in `{comments_disabled, forbidden, quota, transient}`, `post.posted_today(conn, now) -> int`, `post.insert(client, video_id, text) -> str`, `post.post_comment(conn, client, video_id, text, style_tag, critic, variant_rank, now, cfg) -> str`

`post_comment` is the chokepoint: it checks the daily cap, active window, blackout, deny-list, and similarity before calling `insert`, then records the comment and stamps the channel's cooldown. It raises `PostBlocked(reason)` rather than posting when any rail fails.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_post.py
from datetime import datetime, timezone

import pytest

from studio.guerrilla import critic, db, post, watchlist
from tests.fixtures.guerrilla.fake_yt import FakeHttpError, FakeYouTube

NOW = datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)
VERDICT = critic.Verdict(score=4.5, breakdown={"on_topic": 5.0}, decision="auto")


def _conn():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000)
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) "
                 "VALUES ('v1', 'UC1', 'pending')")
    conn.commit()
    return conn


def _cfg(**kw):
    base = {"daily_cap": 12, "publish_times": []}
    base.update(kw)
    return base


def test_happy_path_posts_and_records():
    conn, yt = _conn(), FakeYouTube()
    cid = post.post_comment(conn, yt, "v1", "A specific thought about the ship.",
                            "insight", VERDICT, 0, NOW, _cfg())
    assert yt.posted == [("v1", "A specific thought about the ship.")]
    row = conn.execute("SELECT * FROM comments WHERE comment_id = ?", (cid,)).fetchone()
    assert row["style_tag"] == "insight" and row["critic_score"] == 4.5
    assert conn.execute("SELECT decision FROM videos").fetchone()["decision"] == "posted"
    assert watchlist.active(conn)[0]["last_commented_at"] != ""


def test_denylist_violation_blocks_before_the_api_call():
    conn, yt = _conn(), FakeYouTube()
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v1", "check out my channel", "joke",
                          VERDICT, 0, NOW, _cfg())
    assert e.value.reason == "denylist:self_promo"
    assert yt.posted == []


def test_near_duplicate_blocks():
    conn, yt = _conn(), FakeYouTube()
    post.post_comment(conn, yt, "v1", "When exactly did it stop being the ship?",
                      "insight", VERDICT, 0, NOW, _cfg())
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) "
                 "VALUES ('v2', 'UC1', 'pending')")
    conn.commit()
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v2", "When exactly did it stop being a ship?",
                          "insight", VERDICT, 0, NOW, _cfg())
    assert e.value.reason == "near_duplicate"


def test_daily_cap_blocks():
    conn, yt = _conn(), FakeYouTube()
    for i in range(3):
        conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                     "VALUES (?, 'v1', ?, ?)",
                     (f"old{i}", f"text {i}", NOW.isoformat()))
    conn.commit()
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v1", "a brand new distinct thought here",
                          "insight", VERDICT, 0, NOW, _cfg(daily_cap=3))
    assert e.value.reason == "daily_cap"


def test_outside_active_window_blocks():
    conn, yt = _conn(), FakeYouTube()
    night = datetime(2026, 7, 18, 4, 0, tzinfo=timezone.utc)
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v1", "a distinct thought", "insight",
                          VERDICT, 0, night, _cfg())
    assert e.value.reason == "inactive_window"


def test_publish_blackout_blocks():
    conn, yt = _conn(), FakeYouTube()
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v1", "a distinct thought", "insight", VERDICT, 0, NOW,
                          _cfg(publish_times=["2026-07-18T13:00:00+00:00"]))
    assert e.value.reason == "publish_blackout"


@pytest.mark.parametrize("status,reason,expected", [
    (403, "commentsDisabled", "comments_disabled"),
    (403, "forbidden", "forbidden"),
    (403, "quotaExceeded", "quota"),
    (429, "rateLimitExceeded", "quota"),
    (500, "backendError", "transient"),
    (503, "serviceUnavailable", "transient"),
])
def test_error_classification(status, reason, expected):
    assert post.classify_error(FakeHttpError(status, reason)) == expected


def test_api_failure_records_no_comment():
    conn, yt = _conn(), FakeYouTube()
    yt.raise_on_insert = FakeHttpError(403, "commentsDisabled")
    with pytest.raises(FakeHttpError):
        post.post_comment(conn, yt, "v1", "a distinct thought", "insight",
                          VERDICT, 0, NOW, _cfg())
    assert conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_post.py -v`
Expected: FAIL with `ImportError: cannot import name 'post'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/post.py
"""The only module that writes to YouTube.

Every rail is checked here, immediately before the insert, so there is exactly
one place to audit for ban risk. A caller cannot bypass it, because nothing else
calls commentThreads.insert.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from studio.guerrilla import db, rails, watchlist


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
    return "transient"


def posted_today(conn: sqlite3.Connection, now: datetime) -> int:
    day = now.date().isoformat()
    return conn.execute(
        "SELECT COUNT(*) c FROM comments WHERE substr(posted_at, 1, 10) = ?",
        (day,)).fetchone()["c"]


def insert(client, video_id: str, text: str) -> str:
    """Raw commentThreads.insert. 50 quota units."""
    resp = client.commentThreads().insert(part="snippet", body={"snippet": {
        "videoId": video_id,
        "topLevelComment": {"snippet": {"textOriginal": text}},
    }}).execute()
    return resp["id"]


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
    rule = rails.violates_denylist(text)
    if rule:
        raise PostBlocked(f"denylist:{rule}")
    if rails.too_similar(text, rails.recent_texts(conn)):
        raise PostBlocked("near_duplicate")

    video = conn.execute(
        "SELECT channel_id, comment_count_at_seen FROM videos WHERE video_id = ?",
        (video_id,)).fetchone()
    position = video["comment_count_at_seen"] if video else 0

    comment_id = insert(client, video_id, text)  # errors propagate; nothing is recorded

    conn.execute(
        """INSERT INTO comments (comment_id, video_id, text, variant_rank, critic_score,
                                 critic_breakdown, style_tag, posted_at, first_comment,
                                 comment_position_at_post)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (comment_id, video_id, text, variant_rank, verdict.score,
         json.dumps(verdict.breakdown), style_tag, db.now_iso(),
         1 if position == 0 else 0, position))
    conn.execute("UPDATE videos SET decision = 'posted' WHERE video_id = ?", (video_id,))
    conn.commit()
    if video:
        watchlist.mark_commented(conn, video["channel_id"], db.now_iso())
    return comment_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_post.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/post.py tests/test_guerrilla_post.py
git commit -m "feat(guerrilla): posting chokepoint with rails and error classification"
```

---

### Task 11: Tracking and the circuit breaker

**Files:**
- Create: `studio/guerrilla/track.py`
- Test: `tests/test_guerrilla_track.py`

**Interfaces:**
- Consumes: `db.now_iso`, `studio.notify.telegram`, `FakeYouTube`
- Produces: `track.BREAKER_THRESHOLD = 0.85`, `track.BREAKER_WINDOW = 50`, `track.refresh(conn, client, limit=200) -> int`, `track.survival_rate(conn, window=50) -> float`, `track.check_breaker(conn, notify=None) -> bool`

A comment absent from the `commentThreads.list` response has been deleted. This is the shadowban early-warning: mass deletion shows up here long before anything else surfaces it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_track.py
from studio.guerrilla import db, track
from tests.fixtures.guerrilla.fake_yt import FakeYouTube


def _conn(n=3):
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id) VALUES ('UC1')")
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('v1', 'UC1')")
    for i in range(n):
        conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                     "VALUES (?, 'v1', ?, ?)",
                     (f"c{i}", f"text {i}", f"2026-07-1{i}T12:00:00+00:00"))
    conn.commit()
    return conn


def test_refresh_records_metrics():
    conn = _conn(2)
    yt = FakeYouTube(threads={"c0": {"likes": 7, "replies": 2, "hearted": True},
                              "c1": {"likes": 0, "replies": 0}})
    assert track.refresh(conn, yt) == 2
    row = conn.execute(
        "SELECT * FROM comment_metrics WHERE comment_id = 'c0'").fetchone()
    assert row["likes"] == 7 and row["replies"] == 2 and row["hearted"] == 1
    assert row["status"] == "live"


def test_missing_comment_is_recorded_as_deleted():
    conn = _conn(2)
    yt = FakeYouTube(threads={"c0": {"likes": 1}})  # c1 absent
    track.refresh(conn, yt)
    row = conn.execute(
        "SELECT * FROM comment_metrics WHERE comment_id = 'c1'").fetchone()
    assert row["status"] == "deleted"


def test_survival_rate_uses_the_latest_check_per_comment():
    conn = _conn(2)
    track.refresh(conn, FakeYouTube(threads={"c0": {}, "c1": {}}))
    track.refresh(conn, FakeYouTube(threads={"c0": {}}))  # c1 vanished on recheck
    assert track.survival_rate(conn) == 0.5


def test_survival_rate_with_no_data_is_one():
    assert track.survival_rate(db.connect_memory()) == 1.0


def test_breaker_trips_and_notifies_below_threshold():
    conn = _conn(4)
    track.refresh(conn, FakeYouTube(threads={"c0": {}}))  # 1 of 4 alive = 0.25
    sent = []
    assert track.check_breaker(conn, notify=sent.append) is True
    assert "paused" in sent[0].lower()


def test_breaker_holds_when_survival_is_healthy():
    conn = _conn(4)
    track.refresh(conn, FakeYouTube(threads={f"c{i}": {} for i in range(4)}))
    sent = []
    assert track.check_breaker(conn, notify=sent.append) is False
    assert sent == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_track.py -v`
Expected: FAIL with `ImportError: cannot import name 'track'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/track.py
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


def survival_rate(conn: sqlite3.Connection, window: int = BREAKER_WINDOW) -> float:
    """Fraction of the trailing `window` comments still live at their last check."""
    rows = list(conn.execute(
        """SELECT m.status FROM comment_metrics m
           JOIN (SELECT comment_id, MAX(checked_at) AS latest
                 FROM comment_metrics GROUP BY comment_id) l
             ON l.comment_id = m.comment_id AND l.latest = m.checked_at
           JOIN comments c ON c.comment_id = m.comment_id
           ORDER BY c.posted_at DESC LIMIT ?""", (window,)))
    if not rows:
        return 1.0
    live = sum(1 for r in rows if r["status"] == "live")
    return round(live / len(rows), 4)


def check_breaker(conn: sqlite3.Connection, notify=None) -> bool:
    """True if the loop should auto-pause. Sends a Telegram alert when it trips."""
    if notify is None:
        from studio.notify import telegram
        notify = telegram
    rate = survival_rate(conn)
    if rate >= BREAKER_THRESHOLD:
        return False
    notify(f"⚠️ guerrilla: comment survival {rate:.0%} is below "
           f"{BREAKER_THRESHOLD:.0%} — loop paused. Possible shadowban; "
           f"investigate before resuming.")
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_track.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/track.py tests/test_guerrilla_track.py
git commit -m "feat(guerrilla): comment tracking and shadowban circuit breaker"
```

---

### Task 12: Switchback experiment

**Files:**
- Create: `studio/guerrilla/experiment.py`
- Test: `tests/test_guerrilla_experiment.py`

**Interfaces:**
- Consumes: `db`, stdlib `random`, `statistics`
- Produces: `experiment.ON_DAYS = 4`, `experiment.OFF_DAYS = 2`, `experiment.state_for(date, start_date, on_days=4, off_days=2) -> str`, `experiment.record_day(conn, date, subs_gained, views, channel_page_views, comments_posted, state, published_video) -> None`, `experiment.readout(conn, iterations=2000, seed=0) -> dict`

`readout` returns `{"on_days", "off_days", "on_mean", "off_mean", "lift", "ci_low", "ci_high", "verdict"}`. Verdict is `positive`, `negative`, `null`, or `insufficient_data` (fewer than 5 usable days on either side). Confidence interval is a stdlib bootstrap — **do not add scipy**.

Days with `published_video = 1` are excluded from the readout. Our own upload's subscriber spike would otherwise swamp any comment effect.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_experiment.py
from datetime import date

from studio.guerrilla import db, experiment

START = date(2026, 7, 1)


def test_schedule_is_four_on_two_off():
    states = [experiment.state_for(date(2026, 7, d), START) for d in range(1, 13)]
    assert states == ["on"] * 4 + ["off"] * 2 + ["on"] * 4 + ["off"] * 2


def test_day_before_start_is_off():
    assert experiment.state_for(date(2026, 6, 30), START) == "off"


def _seed(conn, on_subs, off_subs, published_days=()):
    d = 1
    for group, values in (("on", on_subs), ("off", off_subs)):
        for v in values:
            iso = f"2026-07-{d:02d}"
            experiment.record_day(conn, iso, subs_gained=v, views=0,
                                  channel_page_views=0, comments_posted=0,
                                  state=group, published_video=iso in published_days)
            d += 1


def test_readout_detects_an_injected_positive_effect():
    conn = db.connect_memory()
    _seed(conn, on_subs=[20, 22, 19, 21, 23, 20], off_subs=[10, 11, 9, 10, 12, 11])
    r = experiment.readout(conn)
    assert r["verdict"] == "positive"
    assert r["lift"] > 8
    assert r["ci_low"] > 0


def test_readout_reports_null_when_there_is_no_effect():
    conn = db.connect_memory()
    _seed(conn, on_subs=[10, 12, 9, 11, 10, 12], off_subs=[11, 10, 12, 9, 11, 10])
    r = experiment.readout(conn)
    assert r["verdict"] == "null"
    assert r["ci_low"] < 0 < r["ci_high"]


def test_publish_days_are_excluded_from_the_readout():
    conn = db.connect_memory()
    _seed(conn, on_subs=[10, 10, 10, 10, 10, 900],
          off_subs=[10, 10, 10, 10, 10, 10],
          published_days=("2026-07-06",))
    r = experiment.readout(conn)
    assert r["on_days"] == 5
    assert r["on_mean"] == 10.0
    assert r["verdict"] == "null"


def test_thin_data_reports_insufficient_not_a_false_signal():
    conn = db.connect_memory()
    _seed(conn, on_subs=[50, 60], off_subs=[1, 2])
    assert experiment.readout(conn)["verdict"] == "insufficient_data"


def test_readout_is_deterministic_for_a_fixed_seed():
    conn = db.connect_memory()
    _seed(conn, on_subs=[20, 22, 19, 21, 23, 20], off_subs=[10, 11, 9, 10, 12, 11])
    assert experiment.readout(conn, seed=7) == experiment.readout(conn, seed=7)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_experiment.py -v`
Expected: FAIL with `ImportError: cannot import name 'experiment'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/experiment.py
"""Switchback: the only design that answers "is this worth running at all?".

Per-comment attribution does not exist — YouTube exposes no referrer that
distinguishes a subscriber who arrived via a comment. So causality has to come
from turning the whole system on and off and comparing.

4 days on / 2 days off. The 2:1 imbalance means the off-state baseline
accumulates at half the rate, so a readable answer takes roughly 8 weeks.

Expect a null. That is a real and useful answer, and this module is built to
report it honestly rather than to find an effect.
"""

from __future__ import annotations

import random
import sqlite3
import statistics
from datetime import date

ON_DAYS = 4
OFF_DAYS = 2
MIN_DAYS_PER_ARM = 20   # below this the percentile bootstrap false-positives ~2x nominal


def state_for(day: date, start: date, on_days: int = ON_DAYS,
              off_days: int = OFF_DAYS) -> str:
    """Which arm a calendar day belongs to."""
    delta = (day - start).days
    if delta < 0:
        return "off"
    return "on" if (delta % (on_days + off_days)) < on_days else "off"


def record_day(conn: sqlite3.Connection, date_iso: str, subs_gained: int = 0,
               views: int = 0, channel_page_views: int = 0, comments_posted: int = 0,
               state: str = "off", published_video: bool = False) -> None:
    conn.execute(
        """INSERT INTO channel_daily (date, subs_gained, views, channel_page_views,
                                      comments_posted, switchback_state, published_video)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
             subs_gained = excluded.subs_gained,
             views = excluded.views,
             channel_page_views = excluded.channel_page_views,
             comments_posted = excluded.comments_posted,
             switchback_state = excluded.switchback_state,
             published_video = excluded.published_video""",
        (date_iso, subs_gained, views, channel_page_views, comments_posted,
         state, 1 if published_video else 0))
    conn.commit()


def _bootstrap_ci(on: list[float], off: list[float], iterations: int,
                  seed: int) -> tuple[float, float]:
    """Percentile bootstrap CI for the difference in means. Stdlib only."""
    rng = random.Random(seed)
    diffs = []
    for _ in range(iterations):
        a = statistics.fmean(rng.choices(on, k=len(on)))
        b = statistics.fmean(rng.choices(off, k=len(off)))
        diffs.append(a - b)
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]
    hi = diffs[int(0.975 * len(diffs)) - 1]
    return round(lo, 3), round(hi, 3)


def readout(conn: sqlite3.Connection, iterations: int = 2000, seed: int = 0) -> dict:
    """Compare subscriber gain on ON days vs OFF days, excluding publish days."""
    rows = list(conn.execute(
        "SELECT switchback_state, subs_gained FROM channel_daily WHERE published_video = 0"))
    on = [float(r["subs_gained"]) for r in rows if r["switchback_state"] == "on"]
    off = [float(r["subs_gained"]) for r in rows if r["switchback_state"] == "off"]

    result = {"on_days": len(on), "off_days": len(off), "on_mean": 0.0, "off_mean": 0.0,
              "lift": 0.0, "ci_low": 0.0, "ci_high": 0.0, "verdict": "insufficient_data"}
    if len(on) < MIN_DAYS_PER_ARM or len(off) < MIN_DAYS_PER_ARM:
        return result

    result["on_mean"] = round(statistics.fmean(on), 3)
    result["off_mean"] = round(statistics.fmean(off), 3)
    result["lift"] = round(result["on_mean"] - result["off_mean"], 3)
    lo, hi = _bootstrap_ci(on, off, iterations, seed)
    result["ci_low"], result["ci_high"] = lo, hi
    if lo > 0:
        result["verdict"] = "positive"
    elif hi < 0:
        result["verdict"] = "negative"
    else:
        result["verdict"] = "null"
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_experiment.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/experiment.py tests/test_guerrilla_experiment.py
git commit -m "feat(guerrilla): switchback schedule and bootstrap readout"
```

---

### Task 13: Effectiveness report

**Files:**
- Create: `studio/guerrilla/report.py`
- Test: `tests/test_guerrilla_report.py`

**Interfaces:**
- Consumes: `track.survival_rate`, `experiment.readout`
- Produces: `report.by_style(conn) -> list[dict]` (keys `style_tag/n/mean_likes/mean_replies/survival`), `report.skip_breakdown(conn) -> list[dict]` (keys `reason/n`), `report.render(conn) -> str` (markdown)

`skip_breakdown` is what tells you the gates are too tight — without it only survivors are ever visible.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_report.py
from studio.guerrilla import db, report


def _conn():
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id) VALUES ('UC1')")
    for vid, decision, reason in [("v1", "posted", ""), ("v2", "posted", ""),
                                  ("v3", "skipped_gate", "too_old"),
                                  ("v4", "skipped_gate", "too_old"),
                                  ("v5", "skipped_topic", "unclear")]:
        conn.execute("INSERT INTO videos (video_id, channel_id, decision, skip_reason) "
                     "VALUES (?, 'UC1', ?, ?)", (vid, decision, reason))
    for cid, vid, tag in [("c1", "v1", "joke"), ("c2", "v2", "insight")]:
        conn.execute("INSERT INTO comments (comment_id, video_id, text, style_tag, posted_at) "
                     "VALUES (?, ?, 'x', ?, '2026-07-18T12:00:00+00:00')", (cid, vid, tag))
    for cid, likes, replies in [("c1", 10, 3), ("c2", 2, 0)]:
        conn.execute("INSERT INTO comment_metrics "
                     "(comment_id, checked_at, likes, replies, status) "
                     "VALUES (?, '2026-07-18T18:00:00+00:00', ?, ?, 'live')",
                     (cid, likes, replies))
    conn.commit()
    return conn


def test_by_style_aggregates_likes_and_replies():
    rows = {r["style_tag"]: r for r in report.by_style(_conn())}
    assert rows["joke"]["n"] == 1
    assert rows["joke"]["mean_likes"] == 10.0
    assert rows["joke"]["mean_replies"] == 3.0
    assert rows["joke"]["survival"] == 1.0


def test_by_style_is_sorted_best_first():
    assert [r["style_tag"] for r in report.by_style(_conn())] == ["joke", "insight"]


def test_skip_breakdown_counts_reasons():
    rows = {r["reason"]: r["n"] for r in report.skip_breakdown(_conn())}
    assert rows == {"too_old": 2, "unclear": 1}


def test_render_produces_markdown_with_every_section():
    md = report.render(_conn())
    assert "# Guerrilla Marketing Report" in md
    assert "## By style tag" in md
    assert "## Why videos were skipped" in md
    assert "## Switchback readout" in md
    assert "joke" in md


def test_render_on_an_empty_db_does_not_crash():
    md = report.render(db.connect_memory())
    assert "# Guerrilla Marketing Report" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_report.py -v`
Expected: FAIL with `ImportError: cannot import name 'report'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/report.py
"""Effectiveness reporting.

The daily loop optimizes what is fast and measurable — likes, replies, survival
by style tag. The switchback section is the honest check on whether any of that
translates into subscribers.
"""

from __future__ import annotations

import sqlite3

from studio.guerrilla import experiment, track

LATEST_METRIC = """
SELECT m.* FROM comment_metrics m
JOIN (SELECT comment_id, MAX(checked_at) AS latest
      FROM comment_metrics GROUP BY comment_id) l
  ON l.comment_id = m.comment_id AND l.latest = m.checked_at
"""


def by_style(conn: sqlite3.Connection) -> list[dict]:
    """Per-style-tag averages, best first. This is what steers composition."""
    rows = list(conn.execute(f"""
        SELECT c.style_tag AS style_tag,
               COUNT(*) AS n,
               AVG(m.likes) AS mean_likes,
               AVG(m.replies) AS mean_replies,
               AVG(CASE WHEN m.status = 'live' THEN 1.0 ELSE 0.0 END) AS survival
        FROM comments c JOIN ({LATEST_METRIC}) m ON m.comment_id = c.comment_id
        GROUP BY c.style_tag"""))
    out = [{"style_tag": r["style_tag"], "n": r["n"],
            "mean_likes": round(r["mean_likes"] or 0.0, 2),
            "mean_replies": round(r["mean_replies"] or 0.0, 2),
            "survival": round(r["survival"] or 0.0, 3)} for r in rows]
    out.sort(key=lambda d: (d["mean_likes"], d["mean_replies"]), reverse=True)
    return out


def skip_breakdown(conn: sqlite3.Connection) -> list[dict]:
    """Why candidates were rejected. Rising counts mean the gates need tuning."""
    rows = list(conn.execute(
        """SELECT skip_reason AS reason, COUNT(*) AS n FROM videos
           WHERE decision LIKE 'skipped%' AND skip_reason != ''
           GROUP BY skip_reason ORDER BY n DESC"""))
    return [{"reason": r["reason"], "n": r["n"]} for r in rows]


def render(conn: sqlite3.Connection) -> str:
    lines = ["# Guerrilla Marketing Report", ""]

    posted = conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"]
    seen = conn.execute("SELECT COUNT(*) c FROM videos").fetchone()["c"]
    lines += [f"Comments posted: **{posted}** across **{seen}** candidate videos seen.",
              f"Comment survival rate: **{track.survival_rate(conn):.1%}**", ""]

    lines += ["## By style tag", ""]
    styles = by_style(conn)
    if styles:
        lines += ["| style | n | mean likes | mean replies | survival |",
                  "|---|---|---|---|---|"]
        lines += [f"| {s['style_tag']} | {s['n']} | {s['mean_likes']} | "
                  f"{s['mean_replies']} | {s['survival']:.0%} |" for s in styles]
    else:
        lines.append("_no tracked comments yet_")
    lines.append("")

    lines += ["## Why videos were skipped", ""]
    skips = skip_breakdown(conn)
    if skips:
        lines += ["| reason | count |", "|---|---|"]
        lines += [f"| {s['reason']} | {s['n']} |" for s in skips]
    else:
        lines.append("_no skips recorded yet_")
    lines.append("")

    r = experiment.readout(conn)
    lines += ["## Switchback readout", "",
              f"- verdict: **{r['verdict']}**",
              f"- ON days: {r['on_days']} (mean {r['on_mean']} subs/day)",
              f"- OFF days: {r['off_days']} (mean {r['off_mean']} subs/day)",
              f"- lift: {r['lift']} subs/day (95% CI {r['ci_low']} to {r['ci_high']})", ""]
    if r["verdict"] == "null":
        lines.append("A null verdict means the comment activity has no detectable effect "
                     "on subscriber gain. That is a legitimate result — consider stopping.")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_report.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/report.py tests/test_guerrilla_report.py
git commit -m "feat(guerrilla): effectiveness report by style tag and switchback"
```

---

### Task 14: The tick

**Files:**
- Create: `studio/guerrilla/loop.py`
- Test: `tests/test_guerrilla_loop.py`

**Interfaces:**
- Consumes: every module above
- Produces: `loop.Config` (dataclass: `daily_cap=12`, `dry_run=False`, `provider=""`, `publish_times: list[str]`, `experiment_start: date | None`), `loop.TickResult` (dataclass: `discovered`, `considered`, `posted`, `queued`, `skipped: dict[str, int]`, `blocked: dict[str, int]`, `paused: bool`), `loop.tick(conn, client, cfg, now, complete=None, notify=None) -> TickResult`

`notify` is threaded through to `track.check_breaker`. It must be injectable: the default resolves to `studio.notify.telegram`, so a test that leaves it unset sends a real message to the operator's chat.

Tick order: breaker check, discover, rank, then per candidate — classify topic, compose, critique, post or queue. Dry-run runs everything except the API insert.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_loop.py
import json
from datetime import date, datetime, timezone

from studio.guerrilla import critic, db, loop, watchlist
from tests.fixtures.guerrilla.fake_yt import FakeYouTube

NOW = datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)


def _silent(msg):
    """Swallow breaker alerts. Without this the suite sends real Telegram messages."""


def _yt():
    return FakeYouTube(
        channels={"UC1": {"uploads_playlist": "UU1", "title": "Deep Thoughts"}},
        playlists={"UU1": [{"video_id": "v1", "title": "The Ship of Theseus",
                            "description": "A paradox about identity.",
                            "published_at": "2026-07-18T13:30:00Z"}]},
        videos={"v1": {"views": 800, "comments": 4, "comments_enabled": True}},
    )


def _conn():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="UU1")
    return conn


def _complete(topic_conf=0.95, scores=None):
    """Stub LLM: answers topic, compose, and critic prompts by sniffing the system text."""
    scores = scores or dict.fromkeys(critic.CRITERIA, 4.5)

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": topic_conf,
                               "summary": "When a repaired ship stops being itself."})
        if "You write YouTube comments" in system:
            return json.dumps({"variants": [
                {"text": "If every plank is replaced, when did it stop being the ship?",
                 "style_tag": "provocative_question"}]})
        return json.dumps({"scores": scores})
    return complete


def test_tick_discovers_and_posts():
    conn, yt = _conn(), _yt()
    r = loop.tick(conn, yt, loop.Config(), NOW, complete=_complete(), notify=_silent)
    assert r.discovered == 1 and r.posted == 1
    assert len(yt.posted) == 1
    assert conn.execute("SELECT decision FROM videos").fetchone()["decision"] == "posted"


def test_unclear_topic_is_skipped_without_composing():
    conn, yt = _conn(), _yt()
    r = loop.tick(conn, yt, loop.Config(), NOW, complete=_complete(topic_conf=0.2), notify=_silent)
    assert r.posted == 0 and r.skipped["skipped_topic"] == 1
    assert yt.posted == []
    assert conn.execute("SELECT decision FROM videos").fetchone()["decision"] == "skipped_topic"


def test_borderline_critic_score_queues_instead_of_posting():
    conn, yt = _conn(), _yt()
    mid = dict.fromkeys(critic.CRITERIA, 4.5)
    mid.update({"on_topic": 3.0, "not_generic": 3.0, "provocative_or_funny": 3.0})
    r = loop.tick(conn, yt, loop.Config(), NOW, complete=_complete(scores=mid), notify=_silent)
    assert r.queued == 1 and r.posted == 0
    assert yt.posted == []
    assert conn.execute("SELECT decision FROM videos").fetchone()["decision"] == "queued"


def test_dry_run_never_calls_the_api():
    conn, yt = _conn(), _yt()
    r = loop.tick(conn, yt, loop.Config(dry_run=True), NOW, complete=_complete(),
                  notify=_silent)
    assert r.posted == 1
    assert yt.posted == []
    assert conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"] == 0


def test_daily_cap_stops_posting_and_is_reported_as_blocked():
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('old', 'UC1')")
    conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                 "VALUES ('old', 'old', 'x', ?)", (NOW.isoformat(),))
    conn.commit()
    r = loop.tick(conn, yt, loop.Config(daily_cap=1), NOW,
                  complete=_complete(), notify=_silent)
    assert r.posted == 0 and r.blocked["daily_cap"] == 1


def test_tripped_breaker_pauses_the_tick_before_discovery():
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('old', 'UC1')")
    for i in range(4):
        conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                     "VALUES (?, 'old', 'x', '2026-07-01T12:00:00+00:00')", (f"c{i}",))
        conn.execute("INSERT INTO comment_metrics (comment_id, checked_at, status) "
                     "VALUES (?, '2026-07-02T12:00:00+00:00', 'deleted')", (f"c{i}",))
    conn.commit()
    r = loop.tick(conn, yt, loop.Config(), NOW, complete=_complete(), notify=_silent)
    assert r.paused is True and r.posted == 0 and r.discovered == 0


def test_experiment_off_day_does_not_post():
    conn, yt = _conn(), _yt()
    cfg = loop.Config(experiment_start=date(2026, 7, 15))  # 15-18 on, 19-20 off
    off_day = datetime(2026, 7, 19, 14, 0, tzinfo=timezone.utc)
    r = loop.tick(conn, yt, cfg, off_day, complete=_complete(), notify=_silent)
    assert r.posted == 0 and r.blocked["switchback_off"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_loop.py -v`
Expected: FAIL with `ImportError: cannot import name 'loop'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/loop.py
"""One tick of the guerrilla loop: discover, rank, classify, compose, judge, post.

Order matters. The breaker is checked first so a suspected shadowban stops the
tick before it can make things worse, and the topic gate runs before composition
so an unclear video costs one LLM call rather than five.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from studio.guerrilla import (compose, critic, discover, experiment, post, rank,
                              topic, track, watchlist)


@dataclass
class Config:
    daily_cap: int = 12
    dry_run: bool = False
    provider: str = ""
    publish_times: list[str] = field(default_factory=list)
    experiment_start: date | None = None
    gates: rank.Gates = field(default_factory=rank.Gates)


@dataclass
class TickResult:
    discovered: int = 0
    considered: int = 0
    posted: int = 0
    queued: int = 0
    skipped: Counter = field(default_factory=Counter)
    blocked: Counter = field(default_factory=Counter)
    paused: bool = False


def _mark(conn: sqlite3.Connection, video_id: str, decision: str, reason: str = "") -> None:
    conn.execute("UPDATE videos SET decision = ?, skip_reason = ? WHERE video_id = ?",
                 (decision, reason, video_id))
    conn.commit()


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
        except Exception:
            watchlist.set_status(conn, ch["channel_id"], "paused")

    for video in rank.rank_candidates(conn, now, cfg.gates):
        r.considered += 1

        t = topic.classify(video["title"], video["description"], cfg.provider, complete)
        conn.execute("UPDATE videos SET topic = ?, topic_confidence = ? WHERE video_id = ?",
                     (t.topic, t.confidence, video["video_id"]))
        conn.commit()
        if not topic.is_clear(t):
            _mark(conn, video["video_id"], "skipped_topic", "unclear")
            r.skipped["skipped_topic"] += 1
            continue

        variants = compose.variants(video["title"], t.summary, cfg.provider,
                                    complete=complete)
        winner, verdict, idx = critic.best(variants, video["title"], t.summary,
                                           cfg.provider, complete)
        if winner is None or verdict.decision == "skip":
            _mark(conn, video["video_id"], "skipped_critic",
                  "no_variants" if winner is None else "low_score")
            r.skipped["skipped_critic"] += 1
            continue

        if verdict.decision == "queue":
            _mark(conn, video["video_id"], "queued", winner.text)
            r.queued += 1
            continue

        if cfg.dry_run:
            r.posted += 1
            continue

        # A near-duplicate block kills only THIS variant, not the video: the composer
        # generated several, and only the winner happened to echo something recent.

        try:
            post.post_comment(conn, client, video["video_id"], winner.text,
                              winner.style_tag, verdict, idx, now,
                              {"daily_cap": cfg.daily_cap,
                               "publish_times": cfg.publish_times})
            r.posted += 1
        except post.PostBlocked as e:
            r.blocked[e.reason] += 1
            if e.reason == "daily_cap":
                break
        except Exception as e:
            kind = post.classify_error(e)
            r.blocked[kind] += 1
            if kind == "comments_disabled":
                _mark(conn, video["video_id"], "skipped_gate", "comments_disabled")
            elif kind in ("forbidden", "quota"):
                break  # hard stop: ban signal or exhausted quota
    return r
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_loop.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/loop.py tests/test_guerrilla_loop.py
git commit -m "feat(guerrilla): tick orchestration with breaker and switchback gating"
```

---

### Task 15: CLI wiring

**Files:**
- Modify: `studio/cli.py` (add sub-app after the `marketing_app` block at line 32-34; commands after the marketing section)
- Test: `tests/test_guerrilla_cli.py`

**Interfaces:**
- Consumes: every module above
- Produces: the `studio guerrilla` command group — `watchlist add|list`, `tick`, `track`, `report`, `queue`, `approve`

`queue` lists videos whose `decision` is `queued` (the pending comment text is held in `skip_reason`); `approve <video_id>` posts it. This keeps the approval loop inside the CLI rather than requiring an interactive Telegram bot.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_cli.py
from typer.testing import CliRunner

from studio.cli import app

runner = CliRunner()


def test_guerrilla_group_is_registered():
    res = runner.invoke(app, ["guerrilla", "--help"])
    assert res.exit_code == 0
    for cmd in ("watchlist", "tick", "track", "report", "queue", "approve"):
        assert cmd in res.stdout


def test_watchlist_add_then_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    add = runner.invoke(app, ["guerrilla", "watchlist", "add", "UC1",
                              "--channel", "test-ch", "--median-views", "20000"])
    assert add.exit_code == 0
    out = runner.invoke(app, ["guerrilla", "watchlist", "list", "--channel", "test-ch"])
    assert out.exit_code == 0 and "UC1" in out.stdout


def test_report_on_a_fresh_db_succeeds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["guerrilla", "report", "--channel", "test-ch"])
    assert res.exit_code == 0
    assert "Guerrilla Marketing Report" in res.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_cli.py -v`
Expected: FAIL — `No such command 'guerrilla'`

- [ ] **Step 3: Write the implementation**

In `studio/cli.py`, immediately after the existing `app.add_typer(marketing_app, name="marketing")` line:

```python
guerrilla_app = typer.Typer(add_completion=False,
                            help="guerrilla-marketing — targeted commenting for indirect reach.")
app.add_typer(guerrilla_app, name="guerrilla")

watchlist_app = typer.Typer(add_completion=False, help="Manage target channels.")
guerrilla_app.add_typer(watchlist_app, name="watchlist")
```

Then append this section at the end of `studio/cli.py`:

```python
# ======================================================= guerrilla-marketing loop

@watchlist_app.command("add")
def guerrilla_watchlist_add(
    channel_id: str = typer.Argument(..., help="Target YouTube channel id (UC...)"),
    channel: str = typer.Option(..., "--channel", help="Our channel token"),
    title: str = typer.Option("", "--title"),
    median_views: int = typer.Option(0, "--median-views"),
    topic_tags: str = typer.Option("", "--tags"),
):
    """Add a target channel to the watchlist."""
    from studio.guerrilla import db as gdb
    from studio.guerrilla import watchlist as gwl

    conn = gdb.connect(channel)
    gwl.add(conn, channel_id, title=title, median_views=median_views,
            topic_tags=topic_tags, added_by="manual")
    console.print(f"[green]added[/] {channel_id} to {channel} watchlist")


@watchlist_app.command("list")
def guerrilla_watchlist_list(channel: str = typer.Option(..., "--channel")):
    """List active target channels."""
    from studio.guerrilla import db as gdb
    from studio.guerrilla import watchlist as gwl

    rows = gwl.active(gdb.connect(channel))
    if not rows:
        console.print("[dim](watchlist empty — guerrilla watchlist add <UC...>)[/]")
        return
    for r in rows:
        console.print(f"{r['channel_id']}  {r['title'] or '(untitled)'}  "
                      f"median_views={r['median_views']}  last={r['last_commented_at'] or '-'}")


@guerrilla_app.command("tick")
def guerrilla_tick(
    channel: str = typer.Option(..., "--channel"),
    daily_cap: int = typer.Option(12, "--cap", min=10, max=25),
    dry_run: bool = typer.Option(False, "--dry-run",
                                 help="Do everything except post. Read the output first."),
    provider: str = typer.Option("", "--provider"),
):
    """Run one discover -> rank -> compose -> gate -> post cycle."""
    from datetime import datetime, timezone

    from studio.guerrilla import client as gclient
    from studio.guerrilla import db as gdb
    from studio.guerrilla import loop as gloop

    conn = gdb.connect(channel)
    cfg = gloop.Config(daily_cap=daily_cap, dry_run=dry_run, provider=provider)
    res = gloop.tick(conn, gclient.build(channel), cfg, datetime.now(timezone.utc))
    if res.paused:
        console.print("[red]PAUSED[/] — circuit breaker tripped, see the Telegram alert")
        raise typer.Exit(1)
    console.print(f"discovered={res.discovered} considered={res.considered} "
                  f"posted={res.posted} queued={res.queued}")
    if res.skipped:
        console.print(f"[dim]skipped: {dict(res.skipped)}[/]")
    if res.blocked:
        console.print(f"[dim]blocked: {dict(res.blocked)}[/]")


@guerrilla_app.command("track")
def guerrilla_track(channel: str = typer.Option(..., "--channel")):
    """Refresh likes/replies/survival for recent comments; check the breaker."""
    from studio.guerrilla import client as gclient
    from studio.guerrilla import db as gdb
    from studio.guerrilla import track as gtrack

    conn = gdb.connect(channel)
    n = gtrack.refresh(conn, gclient.build(channel))
    rate = gtrack.survival_rate(conn)
    console.print(f"checked {n} comments — survival {rate:.1%}")
    if gtrack.check_breaker(conn):
        console.print("[red]breaker tripped — loop should stay paused[/]")
        raise typer.Exit(1)


@guerrilla_app.command("report")
def guerrilla_report(channel: str = typer.Option(..., "--channel"),
                     write: bool = typer.Option(False, "--write")):
    """Effectiveness by style tag, skip reasons, and the switchback readout."""
    from studio import paths
    from studio.guerrilla import db as gdb
    from studio.guerrilla import report as greport

    conn = gdb.connect(channel)
    md = greport.render(conn)
    console.print(md)
    if write:
        out = paths.guerrilla_dir(channel) / "report.md"
        out.write_text(md)
        console.print(f"[green]wrote[/] {out}")


@guerrilla_app.command("queue")
def guerrilla_queue(channel: str = typer.Option(..., "--channel")):
    """Comments awaiting your approval."""
    from studio.guerrilla import db as gdb

    rows = list(gdb.connect(channel).execute(
        "SELECT video_id, title, skip_reason FROM videos WHERE decision = 'queued'"))
    if not rows:
        console.print("[dim](nothing queued)[/]")
        return
    for r in rows:
        console.print(f"[bold]{r['video_id']}[/]  {r['title']}\n  {r['skip_reason']}\n")


@guerrilla_app.command("approve")
def guerrilla_approve(video_id: str = typer.Argument(...),
                      channel: str = typer.Option(..., "--channel")):
    """Post a queued comment."""
    from datetime import datetime, timezone

    from studio.guerrilla import client as gclient
    from studio.guerrilla import critic as gcritic
    from studio.guerrilla import db as gdb
    from studio.guerrilla import post as gpost

    conn = gdb.connect(channel)
    row = conn.execute(
        "SELECT skip_reason FROM videos WHERE video_id = ? AND decision = 'queued'",
        (video_id,)).fetchone()
    if not row:
        console.print(f"[red]{video_id} is not queued[/]")
        raise typer.Exit(1)
    verdict = gcritic.Verdict(score=gcritic.QUEUE, breakdown={}, decision="queue")
    try:
        gpost.post_comment(conn, gclient.build(channel), video_id, row["skip_reason"],
                           "approved", verdict, 0, datetime.now(timezone.utc),
                           {"daily_cap": 25, "publish_times": []})
        console.print("[green]posted[/]")
    except gpost.PostBlocked as e:
        console.print(f"[yellow]blocked:[/] {e.reason}")
        raise typer.Exit(1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_cli.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the whole suite and lint**

Run: `uv run pytest tests/ -q && uv run ruff check studio/guerrilla tests`
Expected: all tests pass, ruff reports no issues

- [ ] **Step 6: Commit**

```bash
git add studio/cli.py tests/test_guerrilla_cli.py
git commit -m "feat(guerrilla): studio guerrilla CLI command group"
```

---

### Task 16: Daily rollup from YouTube Analytics

**Files:**
- Create: `studio/guerrilla/rollup.py`
- Modify: `studio/cli.py` (add `guerrilla rollup`)
- Test: `tests/test_guerrilla_rollup.py`

**Interfaces:**
- Consumes: `experiment.record_day`, `experiment.state_for`, `studio.providers.publish._creds`
- Produces: `rollup.daily_rows(analytics, channel_id, start, end) -> list[dict]` (keys `date/subs_gained/views`), `rollup.run(conn, analytics, channel_id, start, end, experiment_start, publish_dates) -> int`

Without this, `channel_daily` is never populated and Tasks 12 and 13 are dead code — the switchback can produce no verdict. `run` fills one row per day, stamping the switchback arm from `experiment.state_for` and the `published_video` flag from the dates supplied by the caller.

The YouTube Analytics API is a different service (`youtubeAnalytics` v2) from the Data API, and it is queried by date range, not by video. `analytics` is injected so tests use a fake.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guerrilla_rollup.py
from datetime import date

from studio.guerrilla import db, rollup


class FakeAnalytics:
    """Mimics youtubeAnalytics().reports().query(...).execute()."""

    def __init__(self, rows):
        self.rows = rows
        self.last_kwargs = None

    def reports(self):
        return self

    def query(self, **kw):
        self.last_kwargs = kw
        return self

    def execute(self):
        return {"columnHeaders": [{"name": "day"}, {"name": "views"},
                                  {"name": "subscribersGained"}],
                "rows": self.rows}


def test_daily_rows_are_normalized():
    a = FakeAnalytics([["2026-07-01", 500, 12], ["2026-07-02", 400, 8]])
    got = rollup.daily_rows(a, "UCme", date(2026, 7, 1), date(2026, 7, 2))
    assert got == [{"date": "2026-07-01", "views": 500, "subs_gained": 12},
                   {"date": "2026-07-02", "views": 400, "subs_gained": 8}]


def test_query_is_scoped_to_the_channel_and_range():
    a = FakeAnalytics([])
    rollup.daily_rows(a, "UCme", date(2026, 7, 1), date(2026, 7, 2))
    assert a.last_kwargs["ids"] == "channel==UCme"
    assert a.last_kwargs["startDate"] == "2026-07-01"
    assert a.last_kwargs["endDate"] == "2026-07-02"
    assert a.last_kwargs["dimensions"] == "day"


def test_run_stamps_switchback_arm_and_publish_flag():
    conn = db.connect_memory()
    a = FakeAnalytics([["2026-07-01", 500, 12], ["2026-07-05", 400, 8]])
    n = rollup.run(conn, a, "UCme", date(2026, 7, 1), date(2026, 7, 5),
                   experiment_start=date(2026, 7, 1),
                   publish_dates={"2026-07-05"})
    assert n == 2
    rows = {r["date"]: r for r in conn.execute("SELECT * FROM channel_daily")}
    assert rows["2026-07-01"]["switchback_state"] == "on"    # day 0 of a 4-on block
    assert rows["2026-07-05"]["switchback_state"] == "off"   # day 4 -> off
    assert rows["2026-07-05"]["published_video"] == 1
    assert rows["2026-07-01"]["subs_gained"] == 12


def test_run_counts_comments_posted_that_day():
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id) VALUES ('UC1')")
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('v1', 'UC1')")
    for i in range(3):
        conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                     "VALUES (?, 'v1', 'x', '2026-07-01T14:00:00+00:00')", (f"c{i}",))
    conn.commit()
    a = FakeAnalytics([["2026-07-01", 500, 12]])
    rollup.run(conn, a, "UCme", date(2026, 7, 1), date(2026, 7, 1),
               experiment_start=date(2026, 7, 1), publish_dates=set())
    row = conn.execute("SELECT * FROM channel_daily").fetchone()
    assert row["comments_posted"] == 3


def test_run_is_idempotent():
    conn = db.connect_memory()
    a = FakeAnalytics([["2026-07-01", 500, 12]])
    for _ in range(2):
        rollup.run(conn, a, "UCme", date(2026, 7, 1), date(2026, 7, 1),
                   experiment_start=date(2026, 7, 1), publish_dates=set())
    assert conn.execute("SELECT COUNT(*) c FROM channel_daily").fetchone()["c"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guerrilla_rollup.py -v`
Expected: FAIL with `ImportError: cannot import name 'rollup'`

- [ ] **Step 3: Write the implementation**

```python
# studio/guerrilla/rollup.py
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
```

Add to `studio/cli.py`, in the guerrilla section:

```python
@guerrilla_app.command("rollup")
def guerrilla_rollup(
    channel: str = typer.Option(..., "--channel"),
    channel_id: str = typer.Option(..., "--channel-id", help="Our own UC... id"),
    start: str = typer.Option(..., "--start", help="YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", help="YYYY-MM-DD"),
    experiment_start: str = typer.Option(..., "--experiment-start", help="YYYY-MM-DD"),
):
    """Pull daily subs/views into channel_daily so the switchback can be read."""
    from datetime import date as _date

    from studio.guerrilla import db as gdb
    from studio.guerrilla import rollup as grollup
    from studio.marketing import journal as mj

    conn = gdb.connect(channel)
    published = {e.published_at[:10] for e in mj.load(channel).entries
                 if getattr(e, "published_at", "")}
    n = grollup.run(conn, grollup.build(channel), channel_id,
                    _date.fromisoformat(start), _date.fromisoformat(end),
                    _date.fromisoformat(experiment_start), published)
    console.print(f"[green]wrote[/] {n} days into channel_daily")
```

Before writing the `mj.load(channel).entries` line, confirm the accessor name against
`studio/marketing/journal.py` — if the loader or the entry field differs, use whatever that
module actually exposes for published-video timestamps. The intent is fixed (a set of
`YYYY-MM-DD` strings for days we published); the accessor is not.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guerrilla_rollup.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add studio/guerrilla/rollup.py studio/cli.py tests/test_guerrilla_rollup.py
git commit -m "feat(guerrilla): daily analytics rollup feeding the switchback"
```

---

### Task 17: Operator docs and the pre-flight gate

**Files:**
- Create: `docs/guerrilla-marketing.md`
- Modify: `README.md` (add a `guerrilla` line to the command overview)

**Interfaces:**
- Consumes: the full CLI surface
- Produces: no code

This task ships no behavior — it exists because the system's first live post must be preceded by a human reading a dry-run batch, and that gate needs to be written down where the operator will find it.

- [ ] **Step 1: Write the operator doc**

Create `docs/guerrilla-marketing.md` covering, in this order:

1. **What this is and its legal posture** — gray-hat, ToS-adjacent, comments are attributable via the OAuth client id, the main channel carries the risk.
2. **First run checklist:**
   ```bash
   studio guerrilla watchlist add UCxxxx --channel pilot-channel --median-views 20000
   studio guerrilla tick --channel pilot-channel --dry-run --cap 12
   ```
   Read all twelve proposed comments. Ship only after a batch you would be happy to have the channel name attached to. This gate is not optional and not automatable.
3. **Daily operation** — `tick` every 20-40 min via cron, `track` twice daily, `report --write` weekly.
4. **The breaker** — what a Telegram survival alert means, and that the correct response is to stop and investigate, not to lower the threshold.
5. **Reading the report** — style tags steer composition; skip reasons tune the gates; the switchback verdict decides whether the whole thing continues.
6. **Expected outcome, stated plainly** — a null switchback verdict is the most likely result. The system is built to reach that answer cheaply and to be turned off without regret.

- [ ] **Step 2: Add the README line**

In `README.md`'s command overview, add:

```
studio guerrilla   # targeted commenting for indirect reach (see docs/guerrilla-marketing.md)
```

- [ ] **Step 3: Verify the documented commands actually exist**

Run: `uv run studio guerrilla --help`
Expected: lists `watchlist`, `tick`, `track`, `report`, `queue`, `approve`

- [ ] **Step 4: Commit**

```bash
git add docs/guerrilla-marketing.md README.md
git commit -m "docs(guerrilla): operator playbook and pre-flight dry-run gate"
```

---

## Self-Review

**Spec coverage:** Every spec section maps to a task — architecture (2, 15), data model (1), discovery (4), gates (5), topic skip rule (6), composition (7), tiered critic (8), rate rails and deny-list (9), posting and error table (10), breaker (11), switchback (12), effectiveness reporting (13), tick (14), CLI (15), daily rollup feeding the experiment (16),
dry-run gate (17). The spec's weekly search sweep is deliberately **not** implemented — it is listed under future work below, since the watchlist can be seeded manually and the sweep adds a 100-unit quota path with no day-one value.

**Placeholders:** None. Every code step contains complete, runnable code.

**Type consistency:** `critic.Verdict` is constructed in Tasks 8, 14, and 15 with the same three fields. `post.post_comment` has one signature, used identically in Tasks 10, 14, and 15. `rank.Gates` is consumed in Tasks 5 and 14 with matching field names. `discover.record_candidates` returns `list[str]` in Tasks 4 and 14.

**Known rough edge, called out rather than hidden:** queued comment text is stored in `videos.skip_reason`, which is a column doing double duty. It avoids a sixth table for a queue that should rarely hold more than a handful of rows. If the queue becomes a real workflow, promote it to its own table.

## Deferred To Future Work

- Weekly `search.list` sweep proposing new watchlist channels
- Learned ranking score (spec model A) and bandit targeting (model C) — the schema supports both
- Telegram inline approve/reject buttons instead of `guerrilla queue` / `guerrilla approve`
- `channel_page_views` as a supporting signal (Task 16 leaves it at 0; it needs a second
  Analytics query with the `insightTrafficSourceType` dimension)
