# tests/test_guerrilla_track.py
from studio.guerrilla import db, track
from tests.fixtures.guerrilla.fake_yt import FakeYouTube


def _conn(n=3):
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id) VALUES ('UC1')")
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('v1', 'UC1')")
    for i in range(n):
        day = f"2026-08-{i + 1:02d}"  # supports n up to 28 without colliding on month rollover
        conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                     "VALUES (?, 'v1', ?, ?)",
                     (f"c{i}", f"text {i}", f"{day}T12:00:00+00:00"))
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
    conn = _conn(10)
    # 1 of 10 alive = 0.1, well below BREAKER_THRESHOLD, and 10 >= MIN_BREAKER_SAMPLE.
    track.refresh(conn, FakeYouTube(threads={"c0": {}}))
    sent = []
    assert track.check_breaker(conn, notify=sent.append) is True
    assert "paused" in sent[0].lower()


def test_breaker_holds_when_survival_is_healthy():
    conn = _conn(10)
    track.refresh(conn, FakeYouTube(threads={f"c{i}": {} for i in range(10)}))
    sent = []
    assert track.check_breaker(conn, notify=sent.append) is False
    assert sent == []


# ------------------------------------------------------------------ minor fix: minimum sample before tripping

def test_breaker_does_not_trip_on_a_single_deleted_comment_out_of_one_tracked():
    """Without a minimum sample, one comment deleted out of the only comment
    tracked reads as 0% survival and would trip the breaker on noise (a
    commenter deleting their own reply, a moderation-queue race) — halting the
    cron until a manual `guerrilla resume`, not evidence of a shadowban."""
    conn = _conn(1)
    track.refresh(conn, FakeYouTube(threads={}))  # c0 absent -> deleted
    sent = []
    assert track.check_breaker(conn, notify=sent.append) is False
    assert sent == []
    assert track.is_tripped(conn) is False


def test_breaker_still_trips_promptly_on_mass_deletion():
    """The minimum-sample floor must not blunt the breaker's actual job: once
    enough comments exist to judge (>= MIN_BREAKER_SAMPLE), a real mass
    deletion still trips it right away."""
    conn = _conn(track.MIN_BREAKER_SAMPLE)
    # Only c0 survives -> rate well below BREAKER_THRESHOLD.
    track.refresh(conn, FakeYouTube(threads={"c0": {}}))
    sent = []
    assert track.check_breaker(conn, notify=sent.append) is True
    assert track.is_tripped(conn) is True


# ------------------------------------------------------------------ I3: persisted breaker state

def test_breaker_alert_fires_once_across_repeated_calls_while_tripped():
    """Without persistence, every tick re-fires the Telegram alert for as long as
    the survival rate stays low — a 20-40 min alert loop until the operator
    intervenes. The alert must fire once, on the tick that actually trips it."""
    conn = _conn(10)
    track.refresh(conn, FakeYouTube(threads={"c0": {}}))  # 1 of 10 alive = 0.1
    sent = []
    assert track.check_breaker(conn, notify=sent.append) is True
    assert track.check_breaker(conn, notify=sent.append) is True
    assert track.check_breaker(conn, notify=sent.append) is True
    assert len(sent) == 1


def test_is_tripped_reflects_persisted_state():
    conn = _conn(10)
    assert track.is_tripped(conn) is False
    track.refresh(conn, FakeYouTube(threads={"c0": {}}))
    track.check_breaker(conn, notify=lambda *_: None)
    assert track.is_tripped(conn) is True


def test_resume_clears_a_tripped_breaker():
    conn = _conn(10)
    track.refresh(conn, FakeYouTube(threads={"c0": {}}))
    track.check_breaker(conn, notify=lambda *_: None)
    assert track.is_tripped(conn) is True

    track.resume(conn)
    assert track.is_tripped(conn) is False

    # And re-tripping alerts again, since it's a fresh trip.
    sent = []
    assert track.check_breaker(conn, notify=sent.append) is True
    assert len(sent) == 1


def test_resume_is_a_no_op_when_not_tripped():
    conn = _conn(4)
    track.resume(conn)
    assert track.is_tripped(conn) is False


def test_breaker_status_reports_trip_details():
    conn = _conn(10)
    track.refresh(conn, FakeYouTube(threads={"c0": {}}))
    track.check_breaker(conn, notify=lambda *_: None)
    status = track.breaker_status(conn)
    assert status["tripped"] is True
    assert status["rate_at_trip"] == 0.1
    assert status["tripped_at"] != ""
