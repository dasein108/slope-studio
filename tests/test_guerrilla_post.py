# tests/test_guerrilla_post.py
import json
import random
from datetime import datetime, timedelta, timezone

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
    # v2 lives on a different channel (UC2) so this test isolates near-duplicate
    # detection from the per-channel cooldown rail: two posts to the SAME channel
    # would now legitimately be blocked by `channel_cooldown` (72h) regardless of
    # text similarity, which would make this test pass for the wrong reason.
    conn, yt = _conn(), FakeYouTube()
    watchlist.add(conn, "UC2", median_views=20000)
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) "
                 "VALUES ('v2', 'UC2', 'pending')")
    conn.commit()
    post.post_comment(conn, yt, "v1", "When exactly did it stop being the ship?",
                      "insight", VERDICT, 0, NOW, _cfg())
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v2", "When exactly did it stop being a ship?",
                          "insight", VERDICT, 0, NOW, _cfg())
    assert e.value.reason == "near_duplicate"


def _seed_transcript(conn, video_id, duration, segments):
    conn.execute(
        "INSERT INTO transcripts (video_id, fetched_at, duration, segments) VALUES (?, ?, ?, ?)",
        (video_id, "2026-07-18T00:00:00+00:00", duration,
         json.dumps([[start, text] for start, text in segments])))
    conn.commit()


def test_bad_timestamp_blocks_a_citation_with_no_matching_segment():
    """Task 4: `post.post_comment` is the one chokepoint everything reaches, so
    the timestamp-verification rail has to be checked here too, not just in the
    dry-run preview — this is the safety task's actual enforcement point."""
    conn, yt = _conn(), FakeYouTube()
    _seed_transcript(conn, "v1", 600.0, [(0.0, "intro"), (590.0, "closing thought")])
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v1", "Great point around 5:00 about ships.",
                          "insight", VERDICT, 0, NOW, _cfg())
    assert e.value.reason == "bad_timestamp"
    assert yt.posted == []
    assert conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"] == 0


def test_bad_timestamp_blocks_a_citation_beyond_the_video_duration():
    conn, yt = _conn(), FakeYouTube()
    _seed_transcript(conn, "v1", 120.0, [(0.0, "intro"), (100.0, "outro")])
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v1", "This reminds me of the point at 5:00.",
                          "insight", VERDICT, 0, NOW, _cfg())
    assert e.value.reason == "bad_timestamp"


def test_matching_timestamp_citation_is_not_blocked():
    conn, yt = _conn(), FakeYouTube()
    _seed_transcript(conn, "v1", 600.0, [(0.0, "intro"), (300.0, "the actual key point")])
    cid = post.post_comment(conn, yt, "v1", "Great point at 5:00.",
                            "insight", VERDICT, 0, NOW, _cfg())
    assert cid is not None
    assert yt.posted == [("v1", "Great point at 5:00.")]


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


def test_too_soon_blocks_then_succeeds_after_the_jittered_interval():
    """Rails §Rate Discipline: minimum 12 minutes between comments, jittered ±40%.
    Uses a different channel for the second post so `channel_cooldown` (72h) can't
    be the thing doing the blocking — this test isolates the spacing rail."""
    conn, yt = _conn(), FakeYouTube()
    watchlist.add(conn, "UC2", median_views=20000)
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) "
                 "VALUES ('v2', 'UC2', 'pending')")
    conn.commit()
    rng = random.Random(42)
    cfg = _cfg(rng=rng)

    post.post_comment(conn, yt, "v1", "A specific thought about the ship.",
                      "insight", VERDICT, 0, NOW, cfg)

    soon = NOW + timedelta(seconds=60)  # below even the lowest jittered bound (432s)
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v2", "A wholly unrelated remark about time travel.",
                          "insight", VERDICT, 0, soon, cfg)
    assert e.value.reason == "too_soon"

    later = NOW + timedelta(minutes=20)  # above even the highest jittered bound (1008s)
    cid = post.post_comment(conn, yt, "v2", "A wholly unrelated remark about time travel.",
                            "insight", VERDICT, 0, later, cfg)
    assert cid is not None
    assert len(yt.posted) == 2


def test_first_ever_comment_is_never_blocked_as_too_soon():
    conn, yt = _conn(), FakeYouTube()
    post.post_comment(conn, yt, "v1", "A specific thought about the ship.",
                      "insight", VERDICT, 0, NOW, _cfg(rng=random.Random(1)))
    assert len(yt.posted) == 1


def test_api_failure_records_no_comment():
    conn, yt = _conn(), FakeYouTube()
    yt.raise_on_insert = FakeHttpError(403, "commentsDisabled")
    with pytest.raises(FakeHttpError):
        post.post_comment(conn, yt, "v1", "a distinct thought", "insight",
                          VERDICT, 0, NOW, _cfg())
    assert conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"] == 0


# ------------------------------------------------------------------ I4: SSL ghost-success read-back

def test_transient_failure_after_the_comment_landed_is_recorded_not_lost():
    """The SSL-ghost-success trap: `insert` reaches YouTube, the comment is written,
    and only the response read raises. A blind retry would double-post — the fix
    reads back the video's recent threads and, finding our text AND our own
    authorship there, records it like a normal successful post instead of losing
    track of it. `our_channel_id` must match what `insert()` tags new comments
    with (`yt.our_channel_id`), the way a real caller would resolve its own
    identity, or the authorship check can never confirm the match."""
    conn, yt = _conn(), FakeYouTube()
    yt.raise_after_insert = FakeHttpError(500, "backendError")
    cid = post.post_comment(conn, yt, "v1", "A specific thought about the ship.",
                            "insight", VERDICT, 0, NOW,
                            _cfg(our_channel_id=yt.our_channel_id))
    assert cid is not None
    assert yt.posted == [("v1", "A specific thought about the ship.")]  # landed exactly once
    row = conn.execute("SELECT * FROM comments WHERE comment_id = ?", (cid,)).fetchone()
    assert row["text"] == "A specific thought about the ship."
    assert conn.execute("SELECT decision FROM videos").fetchone()["decision"] == "posted"


def test_ghost_post_readback_does_not_claim_a_different_authors_comment():
    """B2: a 503 that never actually wrote our comment, on a video that already
    carries a byte-identical comment from a DIFFERENT author. Text-only matching
    would misattribute that stranger's comment as ours and start tracking them
    for survival — poisoning the circuit breaker and the style-tag report with
    data that was never ours. Author identity must gate the match, so the
    original error must still propagate and nothing gets recorded."""
    conn, yt = _conn(), FakeYouTube(
        seed_threads={"v1": [{"text": "A specific thought about the ship.",
                              "author_channel_id": "UC_STRANGER"}]},
    )
    yt.raise_on_insert = FakeHttpError(503, "serviceUnavailable")  # never reaches the write
    with pytest.raises(FakeHttpError):
        post.post_comment(conn, yt, "v1", "A specific thought about the ship.",
                          "insight", VERDICT, 0, NOW,
                          _cfg(our_channel_id=yt.our_channel_id))
    assert conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"] == 0
    assert yt.posted == []


def test_channel_cooldown_blocks_a_second_direct_post_to_the_same_channel():
    """Direct unit coverage of the chokepoint `post_comment` re-checks itself
    (see its `channel_cooldown` comment): `guerrilla approve` can call
    `post_comment` more than once for the same channel across separate
    invocations (e.g. two queued videos approved back to back), so the
    re-check must fire regardless of any caller's own snapshot."""
    conn, yt = _conn(), FakeYouTube()
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) "
                 "VALUES ('v2', 'UC1', 'pending')")
    conn.commit()
    post.post_comment(conn, yt, "v1", "A specific thought about the ship.",
                      "insight", VERDICT, 0, NOW, _cfg())
    later = NOW + timedelta(minutes=20)  # clears `too_soon`, but not the 72h channel cooldown
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v2", "A wholly unrelated remark about time travel.",
                          "insight", VERDICT, 0, later, _cfg())
    assert e.value.reason == "channel_cooldown"


def test_transient_failure_that_never_landed_propagates_and_records_nothing():
    conn, yt = _conn(), FakeYouTube()
    yt.raise_on_insert = FakeHttpError(500, "backendError")  # never reaches the write
    with pytest.raises(FakeHttpError):
        post.post_comment(conn, yt, "v1", "a distinct thought here", "insight",
                          VERDICT, 0, NOW, _cfg())
    assert conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"] == 0
    assert yt.posted == []


def test_repeats_opening_blocks():
    """Same content-similarity floor `test_near_duplicate_blocks` uses (different
    channels so `channel_cooldown` can't be the thing doing the blocking), but this
    time the two comments share only their first four words, not enough overall
    text to trip `too_similar`'s jaccard check — the template-monoculture pattern
    `repeats_opening` exists to catch instead."""
    conn, yt = _conn(), FakeYouTube()
    watchlist.add(conn, "UC2", median_views=20000)
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) "
                 "VALUES ('v2', 'UC2', 'pending')")
    conn.commit()
    post.post_comment(conn, yt, "v1",
                      "If communication is the most important skill, how do we address this?",
                      "provocative_question", VERDICT, 0, NOW, _cfg())
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v2",
                          "If communication is the bedrock of every relationship we have.",
                          "insight", VERDICT, 0, NOW, _cfg())
    assert e.value.reason == "repeats_opening"
    assert yt.posted == [
        ("v1", "If communication is the most important skill, how do we address this?")]


def test_style_overused_blocks():
    """`style_overused`'s default `limit=2` needs two PRIOR posts of the same
    style_tag already on record before a third trips it, so this seeds two
    `provocative_question` posts (distinct channels and openings so neither
    `channel_cooldown`, `too_soon`, `near_duplicate`, nor `repeats_opening` is
    what ends up doing the blocking) and checks that a third of the same style
    is refused."""
    conn, yt = _conn(), FakeYouTube()
    watchlist.add(conn, "UC2", median_views=20000)
    watchlist.add(conn, "UC3", median_views=20000)
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) "
                 "VALUES ('v2', 'UC2', 'pending')")
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) "
                 "VALUES ('v3', 'UC3', 'pending')")
    conn.commit()
    post.post_comment(conn, yt, "v1", "Every plank on this ship has been swapped out by now.",
                      "provocative_question", VERDICT, 0, NOW, _cfg())
    later = NOW + timedelta(minutes=20)
    post.post_comment(conn, yt, "v2",
                      "Free will assumptions are baked into this argument from the start.",
                      "provocative_question", VERDICT, 0, later, _cfg())
    even_later = NOW + timedelta(minutes=40)
    with pytest.raises(post.PostBlocked) as e:
        post.post_comment(conn, yt, "v3",
                          "Consciousness might just be information organizing itself, nothing more.",
                          "provocative_question", VERDICT, 0, even_later, _cfg())
    assert e.value.reason == "style_overused"
    assert len(yt.posted) == 2


def test_forbidden_failure_does_not_trigger_a_readback():
    """Read-back is only for `transient` errors — a 403 forbidden is the ban
    signal itself and must propagate untouched, not be reinterpreted via a
    videoId lookup that happens to find some other comment."""
    conn, yt = _conn(), FakeYouTube()
    yt.raise_on_insert = FakeHttpError(403, "forbidden")
    with pytest.raises(FakeHttpError):
        post.post_comment(conn, yt, "v1", "a distinct thought here", "insight",
                          VERDICT, 0, NOW, _cfg())
    assert conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"] == 0
