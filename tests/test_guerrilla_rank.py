from datetime import datetime, timedelta, timezone

from studio.guerrilla import db, rank, watchlist

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)  # noon UTC — inside the active window
GATES = rank.Gates()


def _video(**kw):
    # `age_at_seen_min` only sets the default `published_at` (age gating now runs
    # off `published_at` vs `now`, per I1 — the stored snapshot is recorded but no
    # longer gated on). Pass `published_at` explicitly to decouple the two.
    age_min = kw.pop("age_at_seen_min", 30.0)
    base = {"age_at_seen_min": age_min,
            "published_at": (NOW - timedelta(minutes=age_min)).isoformat(),
            "comment_count_at_seen": 5}
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


def test_empty_published_at_is_rejected():
    """Minor fix: an unknown publish time must fail CLOSED (too old), not open
    (age zero) — the latter would let a video with a blank timestamp pass the
    age gate forever."""
    ok, why = rank.evaluate(_video(published_at=""), _channel(), NOW, GATES)
    assert (ok, why) == (False, "too_old")


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
            """INSERT INTO videos (video_id, channel_id, published_at, age_at_seen_min,
                                   comment_count_at_seen, comments_enabled, decision)
               VALUES (?, ?, ?, 20.0, 3, 1, 'pending')""", (vid, ch, NOW.isoformat()))
    conn.commit()
    got = rank.rank_candidates(conn, NOW, GATES)
    assert [r["video_id"] for r in got] == ["v2", "v1"]


# ------------------------------------------------------------------ I1: current age, not the frozen snapshot

def test_video_with_small_stored_snapshot_but_stale_real_age_is_rejected():
    """A video discovered at a normal age, left `pending` for days (e.g. blocked by
    the inactive-window rail), must be judged on its CURRENT age — not the
    `age_at_seen_min` recorded once at discovery, which stays small forever."""
    stale_published = (NOW - timedelta(days=3, minutes=30)).isoformat()
    video = _video(age_at_seen_min=30.0, published_at=stale_published)  # stored: fresh
    ok, why = rank.evaluate(video, _channel(), NOW, GATES)
    assert (ok, why) == (False, "too_old")


def test_video_with_stale_stored_snapshot_but_fresh_real_age_passes():
    """The inverse: a large stored snapshot must not block a video whose real
    age (from `published_at`) is actually within the gate."""
    fresh_published = (NOW - timedelta(minutes=10)).isoformat()
    video = _video(age_at_seen_min=5000.0, published_at=fresh_published)  # stored: ancient
    assert rank.evaluate(video, _channel(), NOW, GATES) == (True, "")


# ------------------------------------------------------------------ I2 part 1: gate before spending, don't mark

def test_inactive_window_is_rejected_without_being_marked():
    night = datetime(2026, 7, 18, 4, 0, tzinfo=timezone.utc)
    ok, why = rank.evaluate(_video(), _channel(), night, GATES)
    assert (ok, why) == (False, "inactive_window")


def test_daily_cap_reached_is_rejected_without_being_marked():
    ok, why = rank.evaluate(_video(), _channel(), NOW, GATES, daily_posted=12, daily_cap=12)
    assert (ok, why) == (False, "daily_cap")


def test_daily_cap_none_disables_the_check():
    """Callers that don't care about the daily cap (e.g. isolated unit tests of
    the other gates) aren't forced to thread one through."""
    ok, why = rank.evaluate(_video(), _channel(), NOW, GATES, daily_posted=999, daily_cap=None)
    assert (ok, why) == (True, "")


def test_rank_candidates_leaves_inactive_window_videos_pending():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="P1")
    conn.execute(
        """INSERT INTO videos (video_id, channel_id, published_at,
                               comment_count_at_seen, comments_enabled, decision)
           VALUES ('v1', 'UC1', ?, 3, 1, 'pending')""", (NOW.isoformat(),))
    conn.commit()
    night = datetime(2026, 7, 18, 4, 0, tzinfo=timezone.utc)
    assert rank.rank_candidates(conn, night, GATES) == []
    row = conn.execute("SELECT * FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "pending"  # not skipped_gate — reconsider once the window opens
    assert row["skip_reason"] == ""


def test_rank_candidates_leaves_daily_cap_videos_pending():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="P1")
    conn.execute(
        """INSERT INTO videos (video_id, channel_id, published_at,
                               comment_count_at_seen, comments_enabled, decision)
           VALUES ('v1', 'UC1', ?, 3, 1, 'pending')""", (NOW.isoformat(),))
    conn.commit()
    assert rank.rank_candidates(conn, NOW, GATES, daily_cap=0) == []
    row = conn.execute("SELECT * FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "pending"
    assert row["skip_reason"] == ""


# ------------------------------------------------------------------ I2 deferred item: inactive channels

def test_rank_candidates_marks_pending_videos_of_a_paused_channel():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="P1")
    conn.execute(
        """INSERT INTO videos (video_id, channel_id, published_at,
                               comment_count_at_seen, comments_enabled, decision)
           VALUES ('v1', 'UC1', ?, 3, 1, 'pending')""", (NOW.isoformat(),))
    conn.commit()
    watchlist.set_status(conn, "UC1", "paused")
    assert rank.rank_candidates(conn, NOW, GATES) == []
    row = conn.execute("SELECT * FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "skipped_gate"
    assert row["skip_reason"] == "channel_inactive"


# ------------------------------------------------------------------ B1 part 3: cooldown is time-varying

def test_rank_candidates_leaves_channel_cooldown_videos_pending():
    """Minor fix: `rank.evaluate` and `_try_post` must agree that
    `channel_cooldown` is time-varying (it clears in 72h on its own) — marking
    it `skipped_gate` here would permanently retire a video `_try_post` treats
    as merely postponed."""
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="P1")
    watchlist.mark_commented(conn, "UC1", (NOW - timedelta(hours=5)).isoformat())
    conn.execute(
        """INSERT INTO videos (video_id, channel_id, published_at,
                               comment_count_at_seen, comments_enabled, decision)
           VALUES ('v1', 'UC1', ?, 3, 1, 'pending')""", (NOW.isoformat(),))
    conn.commit()
    assert rank.rank_candidates(conn, NOW, GATES) == []
    row = conn.execute("SELECT * FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "pending"
    assert row["skip_reason"] == ""


# ------------------------------------------------------------------ B1 part 2: once-per-tick spacing pre-gate

def test_rank_candidates_returns_nothing_inside_the_spacing_window():
    """60s since the last post is below even the rail's lowest possible
    jittered bound (432s), so this blocks deterministically."""
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="P1")
    conn.execute(
        """INSERT INTO videos (video_id, channel_id, published_at,
                               comment_count_at_seen, comments_enabled, decision)
           VALUES ('v1', 'UC1', ?, 3, 1, 'pending')""", (NOW.isoformat(),))
    conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                 "VALUES ('c0', 'v1', 'x', ?)", ((NOW - timedelta(seconds=60)).isoformat(),))
    conn.commit()
    assert rank.rank_candidates(conn, NOW, GATES) == []
    row = conn.execute("SELECT * FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "pending"  # time-varying — reconsider once spacing clears
    assert row["skip_reason"] == ""


def test_rank_candidates_ignores_the_spacing_window_in_a_dry_run():
    """B1 (dry-run inertness): a dry run never posts, so `too_soon` — which only
    exists to space out real posts — must never gate what a dry run evaluates.
    Without `dry_run=True` this returns [] for the same reason as
    `test_rank_candidates_returns_nothing_inside_the_spacing_window`."""
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="P1")
    conn.execute(
        """INSERT INTO videos (video_id, channel_id, published_at,
                               comment_count_at_seen, comments_enabled, decision)
           VALUES ('v1', 'UC1', ?, 3, 1, 'pending')""", (NOW.isoformat(),))
    conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                 "VALUES ('c0', 'v1', 'x', ?)", ((NOW - timedelta(seconds=60)).isoformat(),))
    conn.commit()
    got = rank.rank_candidates(conn, NOW, GATES, dry_run=True)
    assert [r["video_id"] for r in got] == ["v1"]


def test_rank_candidates_proceeds_once_the_spacing_window_has_elapsed():
    """20 minutes since the last post is above even the rail's highest possible
    jittered bound (1008s ≈ 16.8min), so this passes deterministically."""
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000, uploads_playlist="P1")
    conn.execute(
        """INSERT INTO videos (video_id, channel_id, published_at,
                               comment_count_at_seen, comments_enabled, decision)
           VALUES ('v1', 'UC1', ?, 3, 1, 'pending')""", (NOW.isoformat(),))
    conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                 "VALUES ('c0', 'v1', 'x', ?)", ((NOW - timedelta(minutes=20)).isoformat(),))
    conn.commit()
    got = rank.rank_candidates(conn, NOW, GATES)
    assert [r["video_id"] for r in got] == ["v1"]
