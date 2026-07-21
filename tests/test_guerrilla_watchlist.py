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


# ------------------------------------------------------------------ I5: visibility and recovery for paused channels

def test_all_channels_includes_paused_ones_that_active_hides():
    conn = _conn()
    watchlist.add(conn, "UC1")
    watchlist.add(conn, "UC2")
    watchlist.set_status(conn, "UC2", "paused")
    assert watchlist.active(conn) == [] or {r["channel_id"] for r in watchlist.active(conn)} == {"UC1"}
    ids = {r["channel_id"] for r in watchlist.all_channels(conn)}
    assert ids == {"UC1", "UC2"}


def test_all_channels_lists_active_before_paused():
    conn = _conn()
    watchlist.add(conn, "UC1")
    watchlist.set_status(conn, "UC1", "paused")
    watchlist.add(conn, "UC2")
    rows = watchlist.all_channels(conn)
    assert [r["channel_id"] for r in rows] == ["UC2", "UC1"]


def test_resuming_via_set_status_makes_the_channel_active_again():
    conn = _conn()
    watchlist.add(conn, "UC1")
    watchlist.set_status(conn, "UC1", "paused")
    assert watchlist.active(conn) == []
    watchlist.set_status(conn, "UC1", "active")
    assert [r["channel_id"] for r in watchlist.active(conn)] == ["UC1"]
