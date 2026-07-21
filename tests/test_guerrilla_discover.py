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


def test_record_candidates_persists_comments_disabled():
    conn = db.connect_memory()
    yt = FakeYouTube(
        channels={"UC1": {"uploads_playlist": "UU1", "title": "Deep Thoughts", "subs": 50000}},
        playlists={"UU1": [
            {"video_id": "v1", "title": "The Ship of Theseus",
             "description": "A paradox about identity.",
             "published_at": "2026-07-18T11:30:00Z"},
        ]},
        videos={"v1": {"views": 800, "comments_enabled": False}},
    )
    watchlist.add(conn, "UC1", uploads_playlist="UU1")
    new = discover.record_candidates(conn, yt, "UC1", NOW)
    assert new == ["v1"]
    row = conn.execute("SELECT * FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["comments_enabled"] == 0


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
