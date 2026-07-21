# tests/test_guerrilla_loop.py
import json
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from studio.guerrilla import critic, db, discover, loop, transcript, watchlist
from tests.fixtures.guerrilla.fake_yt import FakeHttpError, FakeYouTube

NOW = datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)

# Every candidate now needs *some* cached transcript to get past the transcript gate and reach
# compose — see `_stub_transcript_fetch` below, which defaults every video to this one so tests
# written before transcript grounding existed don't each need their own setup. The claim at
# 90.0s ("forty-two") exists so tests that want a highlight moment can point `complete`'s
# highlight-prompt stub at real, verifiable transcript text.
DEFAULT_TRANSCRIPT = [
    transcript.Segment(start=0.0, text="Let's talk about the ship of Theseus."),
    transcript.Segment(start=90.0, text="Here's a specific claim: the answer is forty-two."),
    transcript.Segment(start=200.0, text="And that's the paradox in a nutshell."),
]


@pytest.fixture(autouse=True)
def _stub_transcript_fetch(monkeypatch):
    """`loop.tick` now calls `transcript.cached` (network, not LLM) for every candidate before
    the topic gate. Default that to a short canned transcript so every existing test — written
    before transcript grounding existed — still reaches compose without hitting the network or
    needing per-test setup. Tests exercising the no-transcript path re-patch `transcript.fetch`
    again within the test body, via the same `monkeypatch` fixture instance."""
    monkeypatch.setattr(transcript, "fetch", lambda video_id, fetcher=None: list(DEFAULT_TRANSCRIPT))


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


def _complete(topic_conf=0.95, scores=None, citability=4.5):
    """Stub LLM: answers topic, highlight, compose, and critic prompts by sniffing the system
    text. `citability` controls whether the stubbed highlight moment clears `should_cite`."""
    scores = scores or dict.fromkeys(critic.CRITERIA, 4.5)

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": topic_conf,
                               "summary": "When a repaired ship stops being itself."})
        if "comment-worthy moment" in system:
            return json.dumps({"timestamp": 90.0,
                               "quote": "Here's a specific claim: the answer is forty-two.",
                               "why": "a specific, checkable number", "citability": citability})
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
    assert len(r.proposed) == 1
    assert r.proposed[0]["video_id"] == "v1"
    assert r.proposed[0]["text"] == (
        "If every plank is replaced, when did it stop being the ship?")


def test_dry_run_with_three_candidates_evaluates_all_three_and_proposes_three():
    """B1 (dry-run inertness): a dry run never posts, so the `too_soon`-driven
    stop-after-post logic in `tick` — which exists only because a real tick can
    land at most one comment — must never apply to it. All 3 distinct-channel
    candidates from `test_three_eligible_candidates_on_distinct_channels_cost_one_candidates_worth_of_llm`
    must be considered and proposed here, not just the first."""
    conn = db.connect_memory()
    yt = FakeYouTube(
        channels={
            "UC1": {"uploads_playlist": "UU1", "title": "A"},
            "UC2": {"uploads_playlist": "UU2", "title": "B"},
            "UC3": {"uploads_playlist": "UU3", "title": "C"},
        },
        playlists={
            "UU1": [{"video_id": "v1", "title": "The Ship of Theseus",
                     "description": "A paradox about identity.",
                     "published_at": "2026-07-18T13:30:00Z"}],
            "UU2": [{"video_id": "v2", "title": "The Grandfather Paradox",
                     "description": "A paradox about time travel.",
                     "published_at": "2026-07-18T13:20:00Z"}],
            "UU3": [{"video_id": "v3", "title": "The Sorites Paradox",
                     "description": "A paradox about heaps.",
                     "published_at": "2026-07-18T13:10:00Z"}],
        },
        videos={
            "v1": {"views": 800, "comments": 4, "comments_enabled": True},
            "v2": {"views": 900, "comments": 2, "comments_enabled": True},
            "v3": {"views": 700, "comments": 1, "comments_enabled": True},
        },
    )
    watchlist.add(conn, "UC1", median_views=30000, uploads_playlist="UU1")
    watchlist.add(conn, "UC2", median_views=20000, uploads_playlist="UU2")
    watchlist.add(conn, "UC3", median_views=10000, uploads_playlist="UU3")

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "A paradox about the video's own subject."})
        if "You write YouTube comments" in system:
            return json.dumps({"variants": [
                {"text": f"A distinct thought about {user[:20]}", "style_tag": "insight"}]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(dry_run=True), NOW, complete=complete, notify=_silent)
    assert r.considered == 3
    assert r.posted == 3
    assert len(r.proposed) == 3
    assert {p["video_id"] for p in r.proposed} == {"v1", "v2", "v3"}
    assert yt.posted == []  # dry run never calls the API


def test_dry_run_proposal_that_violates_the_denylist_is_blocked_not_proposed():
    """B3: dry-run's pre-flight batch is supposed to show only comments that
    already clear the content rails — otherwise the operator reviews text the
    live path would have rejected outright."""
    conn, yt = _conn(), _yt()

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "When a repaired ship stops being itself."})
        if "You write YouTube comments" in system:
            return json.dumps({"variants": [
                {"text": "Check out my channel for more like this.", "style_tag": "insight"}]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(dry_run=True), NOW, complete=complete, notify=_silent)
    assert r.proposed == []
    assert r.blocked["denylist:self_promo"] == 1
    assert r.posted == 0


def test_try_post_does_not_swallow_a_genuine_programming_bug():
    """Minor fix: `_try_post`'s bare `except Exception` used to classify a
    `KeyError`/`TypeError` bug the same as a real transient API failure and
    silently continue the tick, hiding the defect. A `KeyError` raised from
    inside the post path must propagate instead of being caught and reported
    as `"transient"`."""
    conn, yt = _conn(), _yt()
    yt.raise_on_insert = KeyError("boom")
    with pytest.raises(KeyError):
        loop.tick(conn, yt, loop.Config(), NOW, complete=_complete(), notify=_silent)


def test_daily_cap_stops_posting_and_is_reported_as_blocked():
    """I2 changed *where* the daily cap is enforced: it used to be caught at the
    post-time chokepoint (`post.post_comment` raising `PostBlocked("daily_cap")`
    after `topic`/`compose`/`critic` had already been paid for), which is what
    `r.blocked["daily_cap"]` reflected. Now `rank.rank_candidates` gates the
    candidate out before any LLM call, so it never reaches `_try_post` at all —
    `r.considered` stays 0 and `r.blocked` is never touched for this reason. The
    original assertion (`r.blocked["daily_cap"] == 1`) tested the old, expensive
    mechanism; this asserts the same intent — the tick doesn't exceed the cap —
    against the new, cheaper one."""
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('old', 'UC1')")
    conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                 "VALUES ('old', 'old', 'x', ?)", (NOW.isoformat(),))
    conn.commit()
    r = loop.tick(conn, yt, loop.Config(daily_cap=1), NOW,
                  complete=_complete(), notify=_silent)
    assert r.posted == 0 and r.considered == 0
    assert conn.execute(
        "SELECT decision FROM videos WHERE video_id = 'v1'").fetchone()["decision"] == "pending"


def test_tripped_breaker_pauses_the_tick_before_discovery():
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('old', 'UC1')")
    for i in range(10):  # >= track.MIN_BREAKER_SAMPLE, or the trip is suppressed
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


def test_second_video_from_same_channel_is_never_attempted_in_the_same_tick():
    """B1 part 1 (regression fix): `too_soon` allows at most one successful post
    per tick, so `loop.tick` must stop iterating candidates the instant one
    lands — trying a second candidate afterward, even from a different channel,
    can only pay more LLM calls for a post that rail is guaranteed to
    block. Before that fix, this test (see git history) posted v1, then WENT ON
    to consider v2 — same channel — and asserted `post.post_comment`'s
    `channel_cooldown` chokepoint caught it within the same tick. That specific
    within-a-tick race can no longer happen through `loop.tick`, since nothing
    after a successful post is attempted at all now: v2 stays untouched and
    `pending` for a later tick, and the mock only ever sees the 4 calls
    (topic/highlight/compose/critic — transcript-grounding's Task 5 added the
    highlight call between topic and compose) v1's attempt spent. This stub's
    highlight branch is unhandled deliberately — its wrong-shaped fallback
    response makes `highlight.best_moment` fail closed to `None`, which is
    itself a real, tested code path (`moment=None` degrades compose/critic to
    their pre-grounding behavior) and doesn't change what this test is
    checking: which candidate gets attempted. The chokepoint itself — still
    essential for `guerrilla approve`, which calls `post_comment` directly,
    outside the loop — is covered directly in
    `test_guerrilla_post.test_channel_cooldown_blocks_a_second_direct_post_to_the_same_channel`.
    """
    conn = _conn()
    yt = FakeYouTube(
        channels={"UC1": {"uploads_playlist": "UU1", "title": "Deep Thoughts"}},
        playlists={"UU1": [
            {"video_id": "v1", "title": "The Ship of Theseus",
             "description": "A paradox about identity.",
             "published_at": "2026-07-18T13:30:00Z"},
            {"video_id": "v2", "title": "The Grandfather Paradox",
             "description": "A paradox about time travel.",
             "published_at": "2026-07-18T13:20:00Z"},
        ]},
        videos={
            "v1": {"views": 800, "comments": 4, "comments_enabled": True},
            "v2": {"views": 900, "comments": 2, "comments_enabled": True},
        },
    )
    calls = []

    def complete(provider, system, user):
        calls.append(1)
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "A paradox about the video's own subject."})
        if "You write YouTube comments" in system:
            text = ("If every plank is replaced, when did it stop being the ship?"
                    if "Ship of Theseus" in user else
                    "If your grandfather never grew up, would you exist to ask?")
            return json.dumps({"variants": [{"text": text, "style_tag": "insight"}]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=complete, notify=_silent)
    assert r.posted == 1 and r.considered == 1
    assert r.blocked["channel_cooldown"] == 0
    assert len(yt.posted) == 1
    assert len(calls) == 4  # topic + highlight + compose + critic, spent on v1 only
    row = conn.execute("SELECT decision FROM videos WHERE video_id = 'v2'").fetchone()
    assert row["decision"] == "pending"  # never even considered this tick


def test_near_duplicate_falls_through_to_the_next_best_variant():
    """The critic's #1 pick echoes something already posted; compose gave us a #2
    that doesn't. The tick should post the #2 instead of abandoning the video.

    The prior comment is backdated an hour so the new `too_soon` spacing rail (min
    12 minutes, jittered) doesn't also block the #2 attempt — this test's intent is
    to isolate near-duplicate fallback, not spacing, and both rails would otherwise
    fire simultaneously since the retry happens at the same `now` as the tick."""
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) VALUES ('old', 'UC1', 'posted')")
    conn.execute(
        "INSERT INTO comments (comment_id, video_id, text, posted_at) "
        "VALUES ('old', 'old', 'If every plank is replaced, when did it stop being the ship?', ?)",
        ((NOW - timedelta(hours=1)).isoformat(),))
    conn.commit()

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "When a repaired ship stops being itself."})
        if "You write YouTube comments" in system:
            return json.dumps({"variants": [
                {"text": "If every plank is replaced, when did it stop being the ship?",
                 "style_tag": "provocative_question"},
                {"text": "A ship rebuilt plank by plank still carries the old one's memory.",
                 "style_tag": "insight"},
            ]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=complete, notify=_silent)
    assert r.posted == 1
    assert r.blocked["near_duplicate"] == 1
    assert yt.posted == [
        ("v1", "A ship rebuilt plank by plank still carries the old one's memory.")]
    assert conn.execute(
        "SELECT decision FROM videos WHERE video_id = 'v1'").fetchone()["decision"] == "posted"


def test_repeats_opening_falls_through_to_the_next_best_variant():
    """Mirrors `test_near_duplicate_falls_through_to_the_next_best_variant`: the
    critic's #1 pick shares its first four words with something already posted
    (but not enough overall text to trip `too_similar`), so the tick should post
    the #2 variant instead of abandoning the video."""
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) VALUES ('old', 'UC1', 'posted')")
    conn.execute(
        "INSERT INTO comments (comment_id, video_id, text, style_tag, posted_at) "
        "VALUES ('old', 'old', 'If every plank on this ship gets swapped out eventually, "
        "does it even matter?', 'provocative_question', ?)",
        ((NOW - timedelta(hours=1)).isoformat(),))
    conn.commit()

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "When a repaired ship stops being itself."})
        if "You write YouTube comments" in system:
            return json.dumps({"variants": [
                {"text": "If every plank on this ship gets replaced, is it still the same boat?",
                 "style_tag": "provocative_question"},
                {"text": "A ship rebuilt plank by plank still carries the old one's memory.",
                 "style_tag": "insight"},
            ]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=complete, notify=_silent)
    assert r.posted == 1
    assert r.blocked["repeats_opening"] == 1
    assert yt.posted == [
        ("v1", "A ship rebuilt plank by plank still carries the old one's memory.")]
    assert conn.execute(
        "SELECT decision FROM videos WHERE video_id = 'v1'").fetchone()["decision"] == "posted"


def test_style_overused_falls_through_to_the_next_best_variant():
    """Mirrors `test_near_duplicate_falls_through_to_the_next_best_variant`: two
    prior posts already used `provocative_question`, so the critic's #1 pick
    (also `provocative_question`) trips the style-diversity rail — the tick
    should post the #2 variant (a different style_tag) instead of abandoning
    the video."""
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) VALUES ('old1', 'UC1', 'posted')")
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) VALUES ('old2', 'UC1', 'posted')")
    for cid, text, ts in [
        ("old1", "Every plank on this ship has been swapped out by now.",
         (NOW - timedelta(hours=2)).isoformat()),
        ("old2", "Free will assumptions are baked into this argument from the start.",
         (NOW - timedelta(hours=1)).isoformat()),
    ]:
        conn.execute(
            "INSERT INTO comments (comment_id, video_id, text, style_tag, posted_at) "
            "VALUES (?, ?, ?, 'provocative_question', ?)", (cid, cid, text, ts))
    conn.commit()

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "When a repaired ship stops being itself."})
        if "You write YouTube comments" in system:
            return json.dumps({"variants": [
                {"text": "Consciousness might just be information organizing itself, nothing more.",
                 "style_tag": "provocative_question"},
                {"text": "A ship rebuilt plank by plank still carries the old one's memory.",
                 "style_tag": "insight"},
            ]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=complete, notify=_silent)
    assert r.posted == 1
    assert r.blocked["style_overused"] == 1
    assert yt.posted == [
        ("v1", "A ship rebuilt plank by plank still carries the old one's memory.")]
    assert conn.execute(
        "SELECT decision FROM videos WHERE video_id = 'v1'").fetchone()["decision"] == "posted"


# ------------------------------------------------------------------ I2 part 1: gate before spending

def test_ticking_outside_active_window_costs_zero_llm_calls():
    """5010-minutes-later re-tick style scenario, minus the age: outside the active
    window, the tick must never reach `topic.classify` (or compose/critic) for any
    candidate — that's 3 paid LLM calls per candidate for zero chance of posting."""
    conn, yt = _conn(), _yt()
    calls = []

    def counting_complete(provider, system, user):
        calls.append((provider, system, user))
        return json.dumps({"topic": "identity paradox", "confidence": 0.95, "summary": "x"})

    night = datetime(2026, 7, 18, 4, 0, tzinfo=timezone.utc)
    for _ in range(5):
        r = loop.tick(conn, yt, loop.Config(), night, complete=counting_complete, notify=_silent)
        assert r.posted == 0 and r.considered == 0
    assert calls == []
    assert yt.posted == []


def test_daily_cap_reached_costs_zero_llm_calls_and_video_stays_pending():
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('old', 'UC1')")
    conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                 "VALUES ('old', 'old', 'x', ?)", (NOW.isoformat(),))
    conn.commit()
    calls = []

    def counting_complete(provider, system, user):
        calls.append(1)
        return json.dumps({"topic": "identity paradox", "confidence": 0.95, "summary": "x"})

    r = loop.tick(conn, yt, loop.Config(daily_cap=1), NOW, complete=counting_complete,
                 notify=_silent)
    assert r.posted == 0 and r.considered == 0
    assert calls == []
    row = conn.execute("SELECT decision FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "pending"  # not marked — reconsider once the cap resets


# ------------------------------------------------------------------ B1: at most one post per tick

def test_tick_inside_the_spacing_window_costs_zero_llm_calls():
    """B1 part 2 (regression fix): the `too_soon` spacing rail always requires at
    least 432s (12min jittered -40%) between comments. Without a once-per-tick
    pre-gate in `rank.rank_candidates`, a cron running under ~17 minutes would
    have every candidate pay 3 LLM calls (topic/compose/critic) only to be
    blocked by `post.post_comment`'s real chokepoint. 60s since the last post is
    below even the rail's lowest possible jittered bound, so this must block
    deterministically regardless of the random draw."""
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('old', 'UC1')")
    conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                 "VALUES ('old', 'old', 'x', ?)",
                 ((NOW - timedelta(seconds=60)).isoformat(),))
    conn.commit()
    calls = []

    def counting_complete(provider, system, user):
        calls.append(1)
        return json.dumps({"topic": "identity paradox", "confidence": 0.95, "summary": "x"})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=counting_complete, notify=_silent)
    assert r.posted == 0 and r.considered == 0
    assert calls == []
    assert yt.posted == []
    row = conn.execute("SELECT decision FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "pending"  # time-varying — reconsider once spacing clears


def test_three_eligible_candidates_on_distinct_channels_cost_one_candidates_worth_of_llm():
    """B1 part 1 (regression fix): with 3 eligible candidates on 3 distinct
    channels, the old code paid several LLM calls (topic/compose/critic, plus
    highlight since transcript-grounding's Task 5) PER candidate — a multiple
    of that total — even though `too_soon` guarantees a tick can post at
    most once. The fix must stop after the first successful post, spending LLM
    on exactly one candidate's worth of calls."""
    conn = db.connect_memory()
    yt = FakeYouTube(
        channels={
            "UC1": {"uploads_playlist": "UU1", "title": "A"},
            "UC2": {"uploads_playlist": "UU2", "title": "B"},
            "UC3": {"uploads_playlist": "UU3", "title": "C"},
        },
        playlists={
            "UU1": [{"video_id": "v1", "title": "The Ship of Theseus",
                     "description": "A paradox about identity.",
                     "published_at": "2026-07-18T13:30:00Z"}],
            "UU2": [{"video_id": "v2", "title": "The Grandfather Paradox",
                     "description": "A paradox about time travel.",
                     "published_at": "2026-07-18T13:20:00Z"}],
            "UU3": [{"video_id": "v3", "title": "The Sorites Paradox",
                     "description": "A paradox about heaps.",
                     "published_at": "2026-07-18T13:10:00Z"}],
        },
        videos={
            "v1": {"views": 800, "comments": 4, "comments_enabled": True},
            "v2": {"views": 900, "comments": 2, "comments_enabled": True},
            "v3": {"views": 700, "comments": 1, "comments_enabled": True},
        },
    )
    watchlist.add(conn, "UC1", median_views=30000, uploads_playlist="UU1")
    watchlist.add(conn, "UC2", median_views=20000, uploads_playlist="UU2")
    watchlist.add(conn, "UC3", median_views=10000, uploads_playlist="UU3")

    calls = []
    base_complete = _complete()

    def counting_complete(provider, system, user):
        calls.append(1)
        return base_complete(provider, system, user)

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=counting_complete, notify=_silent)
    assert r.considered == 1
    assert r.posted == 1
    assert len(yt.posted) == 1
    assert len(calls) == 4  # topic + highlight + compose + critic, for the one posted candidate only
    still_pending = {row["video_id"] for row in conn.execute(
        "SELECT video_id FROM videos WHERE decision = 'pending'")}
    assert still_pending == {"v2", "v3"}


# ------------------------------------------------------------------ I2 part 2: mark what is genuinely dead

def test_denylist_blocked_video_is_marked_and_not_reconsidered():
    conn, yt = _conn(), _yt()

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "When a repaired ship stops being itself."})
        if "You write YouTube comments" in system:
            return json.dumps({"variants": [
                {"text": "Check out my channel for more like this.", "style_tag": "insight"}]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=complete, notify=_silent)
    assert r.posted == 0
    assert r.blocked["denylist:self_promo"] == 1
    assert yt.posted == []
    row = conn.execute(
        "SELECT decision, skip_reason FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "skipped_gate"
    assert row["skip_reason"] == "denylist:self_promo"


def test_near_duplicate_that_exhausts_every_variant_marks_the_video():
    """Unlike the fallback case above, when EVERY `auto` variant echoes something
    already posted, compose has nothing left to try — the video must be marked
    so a later tick doesn't re-pay for the same three LLM calls."""
    conn, yt = _conn(), _yt()
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) VALUES ('old', 'UC1', 'posted')")
    conn.execute(
        "INSERT INTO comments (comment_id, video_id, text, posted_at) "
        "VALUES ('old', 'old', 'If every plank is replaced, when did it stop being the ship?', ?)",
        ((NOW - timedelta(hours=1)).isoformat(),))
    conn.commit()

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "When a repaired ship stops being itself."})
        if "You write YouTube comments" in system:
            return json.dumps({"variants": [
                {"text": "If every plank is replaced, when did it stop being the ship?",
                 "style_tag": "provocative_question"}]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=complete, notify=_silent)
    assert r.posted == 0
    assert r.blocked["near_duplicate"] == 1
    assert yt.posted == []
    row = conn.execute(
        "SELECT decision, skip_reason FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "skipped_gate"
    assert row["skip_reason"] == "near_duplicate_exhausted"


# ------------------------------------------------------------------ I5: only pause the watchlist on real dead-channel errors

def test_transient_discovery_error_does_not_pause_the_channel(monkeypatch):
    def boom(conn, client, channel_id, now):
        raise FakeHttpError(500, "backendError")

    monkeypatch.setattr(discover, "record_candidates", boom)
    conn, yt = _conn(), _yt()
    r = loop.tick(conn, yt, loop.Config(), NOW, complete=_complete(), notify=_silent)
    assert watchlist.active(conn) != []
    assert watchlist.active(conn)[0]["status"] == "active"
    assert r.blocked["discover_error:transient"] == 1


def test_404_discovery_error_pauses_the_channel(monkeypatch):
    def boom(conn, client, channel_id, now):
        raise FakeHttpError(404, "channelNotFound")

    monkeypatch.setattr(discover, "record_candidates", boom)
    conn, yt = _conn(), _yt()
    r = loop.tick(conn, yt, loop.Config(), NOW, complete=_complete(), notify=_silent)
    row = conn.execute("SELECT status FROM channels WHERE channel_id = 'UC1'").fetchone()
    assert row["status"] == "paused"
    assert r.blocked["discover_error:not_found"] == 1


# ------------------------------------------------------------------ transcript grounding (Task 5)

def test_video_with_no_cached_transcript_is_skipped_before_any_llm_call(monkeypatch):
    """A caption-less video is common (many Shorts have none) and must cost
    nothing: the transcript fetch is a cached network read, not a model call,
    and it has to run — and be checked — before topic classification, let
    alone highlight/compose/critic, ever gets a chance to spend money."""
    conn, yt = _conn(), _yt()
    monkeypatch.setattr(transcript, "fetch", lambda video_id, fetcher=None: [])
    calls = []

    def counting_complete(provider, system, user):
        calls.append(1)
        return json.dumps({"topic": "identity paradox", "confidence": 0.95, "summary": "x"})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=counting_complete, notify=_silent)
    assert r.posted == 0
    assert r.skipped["skipped_transcript"] == 1
    assert calls == []
    assert yt.posted == []
    row = conn.execute(
        "SELECT decision, skip_reason FROM videos WHERE video_id = 'v1'").fetchone()
    assert row["decision"] == "skipped_transcript"
    assert row["skip_reason"] == "no_transcript"


def test_candidate_with_transcript_reaches_compose_with_moment_and_critic_gets_the_excerpt():
    """With a cached transcript present, the tick should find a highlight
    moment, thread it (and `cite`) into `compose.variants`, and thread a
    non-empty transcript excerpt into `critic.ranked` — closing the review
    finding that `grounded` was inert because nothing ever supplied ground
    truth for the critic to check against."""
    conn, yt = _conn(), _yt()
    captured = {}

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "When a repaired ship stops being itself."})
        if "comment-worthy moment" in system:
            return json.dumps({"timestamp": 90.0,
                               "quote": "Here's a specific claim: the answer is forty-two.",
                               "why": "a specific, checkable number", "citability": 4.8})
        if "You write YouTube comments" in system:
            captured["compose_system"] = system
            captured["compose_user"] = user
            return json.dumps({"variants": [
                {"text": "At 1:30 he claims the answer is forty-two, but that number is "
                         "doing a lot of unearned work.", "style_tag": "insight"}]})
        captured["critic_user"] = user
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    # cite_timestamps=True: this test exercises the citation-allowed path (citability 4.8
    # clears CITE_THRESHOLD), which requires opting in now that citation defaults off.
    r = loop.tick(conn, yt, loop.Config(cite_timestamps=True), NOW, complete=complete,
                 notify=_silent)
    assert r.posted == 1
    # compose saw the real moment: its verbatim quote and stamped timestamp.
    assert "Here's a specific claim: the answer is forty-two." in captured["compose_user"]
    assert "1:30" in captured["compose_user"]
    # citability 4.8 clears CITE_THRESHOLD (4.0), so compose was told it may cite the timestamp.
    assert "DO NOT CITE THE TIMESTAMP" not in captured["compose_system"]
    # critic received a real, non-empty excerpt — the ground truth `grounded` needs to fire.
    assert "Transcript excerpt" in captured["critic_user"]
    assert "forty-two" in captured["critic_user"]


def test_low_citability_moment_yields_cite_false_into_compose():
    conn, yt = _conn(), _yt()
    captured = {}

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "x"})
        if "comment-worthy moment" in system:
            return json.dumps({"timestamp": 90.0,
                               "quote": "Here's a specific claim: the answer is forty-two.",
                               "why": "y", "citability": 1.0})  # below CITE_THRESHOLD
        if "You write YouTube comments" in system:
            captured["system"] = system
            return json.dumps({"variants": [
                {"text": "The forty-two answer feels like a dodge.", "style_tag": "insight"}]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    loop.tick(conn, yt, loop.Config(), NOW, complete=complete, notify=_silent)
    assert "DO NOT CITE THE TIMESTAMP" in captured["system"]


def test_cite_timestamps_defaults_off_even_for_a_high_citability_moment():
    """Timestamp citation is opt-in (default `Config.cite_timestamps=False`): the highlight
    stage's timestamps cluster near the video start regardless of where the quoted content
    actually is, and the "At 0:0X, when he says…" phrasing became a bot-detectable template
    across most comments. So even a moment that clears CITE_THRESHOLD must not be cited unless
    the operator explicitly turns citation on — the moment still drives composition (verbatim
    quote reaches compose), it just can't name a time."""
    conn, yt = _conn(), _yt()
    captured = {}

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "x"})
        if "comment-worthy moment" in system:
            return json.dumps({"timestamp": 90.0,
                               "quote": "Here's a specific claim: the answer is forty-two.",
                               "why": "y", "citability": 4.9})  # well above CITE_THRESHOLD
        if "You write YouTube comments" in system:
            captured["system"] = system
            captured["user"] = user
            return json.dumps({"variants": [
                {"text": "The forty-two answer feels like a dodge.", "style_tag": "insight"}]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    r = loop.tick(conn, yt, loop.Config(), NOW, complete=complete, notify=_silent)
    assert r.posted == 1
    # the moment's substance still reached compose...
    assert "Here's a specific claim: the answer is forty-two." in captured["user"]
    # ...but citation stayed suppressed despite the high-citability moment.
    assert "DO NOT CITE THE TIMESTAMP" in captured["system"]
    assert len(yt.posted) == 1
    posted_text = yt.posted[0][1]
    assert re.search(r"\b\d{1,2}:\d{2}\b", posted_text) is None


def test_high_citability_moment_yields_cite_true_into_compose():
    conn, yt = _conn(), _yt()
    captured = {}

    def complete(provider, system, user):
        if "classify YouTube videos" in system:
            return json.dumps({"topic": "identity paradox", "confidence": 0.95,
                               "summary": "x"})
        if "comment-worthy moment" in system:
            return json.dumps({"timestamp": 90.0,
                               "quote": "Here's a specific claim: the answer is forty-two.",
                               "why": "y", "citability": 4.9})  # above CITE_THRESHOLD
        if "You write YouTube comments" in system:
            captured["system"] = system
            return json.dumps({"variants": [
                {"text": "At 1:30 the forty-two answer feels like a dodge.",
                 "style_tag": "insight"}]})
        return json.dumps({"scores": dict.fromkeys(critic.CRITERIA, 4.5)})

    # cite_timestamps=True: needed to exercise the cite=True path now that it defaults off.
    loop.tick(conn, yt, loop.Config(cite_timestamps=True), NOW, complete=complete, notify=_silent)
    assert "DO NOT CITE THE TIMESTAMP" not in captured["system"]
    assert "CITE THE TIMESTAMP." in captured["system"]
