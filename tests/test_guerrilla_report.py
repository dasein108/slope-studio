from studio.guerrilla import db, report, track


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


def test_skip_breakdown_counts_missing_transcripts():
    """`loop.tick` marks a caption-less video `skipped_transcript` / `no_transcript`
    (Task 5) — the operator needs this broken out same as any other skip reason,
    to see how many candidates are lost to missing captions."""
    conn = _conn()
    conn.execute("INSERT INTO videos (video_id, channel_id, decision, skip_reason) "
                 "VALUES ('v6', 'UC1', 'skipped_transcript', 'no_transcript')")
    conn.commit()
    rows = {r["reason"]: r["n"] for r in report.skip_breakdown(conn)}
    assert rows["no_transcript"] == 1
    md = report.render(conn)
    assert "no_transcript" in md


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


def test_render_surfaces_contaminated_days_when_present():
    """A null verdict caused by comments having leaked onto OFF days must not read
    the same as a genuine null — the operator needs to know the readout is unreliable
    before concluding the bot has no effect."""
    conn = _conn()
    conn.execute(
        "INSERT INTO channel_daily (date, subs_gained, switchback_state, comments_posted, "
        "published_video) VALUES ('2026-08-01', 3, 'off', 4, 0)")
    conn.commit()
    md = report.render(conn)
    assert "1 OFF day(s) had comments posted" in md
    assert "unreliable" in md.lower()


def test_render_omits_contamination_warning_when_clean():
    md = report.render(_conn())
    assert "OFF day(s) had comments posted" not in md


# ------------------------------------------------------------------ Must-fix minor: survival rate on empty data

def test_render_shows_na_survival_when_nothing_is_tracked():
    """`track.survival_rate` returns 1.0 on an empty database by contract (the
    breaker needs "no evidence of a problem", not a crash) — but printing that
    as 100.0% in the operator-facing report reads as "the channel is safe" when
    really nothing has ever been checked."""
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id) VALUES ('UC1')")
    conn.execute("INSERT INTO videos (video_id, channel_id, decision) VALUES ('v1', 'UC1', 'posted')")
    conn.execute("INSERT INTO comments (comment_id, video_id, text, posted_at) "
                 "VALUES ('c1', 'v1', 'x', '2026-07-18T12:00:00+00:00')")
    conn.commit()
    md = report.render(conn)
    assert "n/a (no tracked comments)" in md
    assert "100.0%" not in md


def test_render_shows_a_real_percentage_once_comments_are_tracked():
    md = report.render(_conn())
    assert "n/a" not in md


# ------------------------------------------------------------------ I3: breaker state surfaced in the report

def test_render_shows_a_tripped_breaker():
    conn = _conn()
    track.trip_breaker(conn, 0.42)
    md = report.render(conn)
    assert "TRIPPED" in md
    assert "42%" in md


def test_render_omits_the_breaker_section_when_healthy():
    md = report.render(_conn())
    assert "TRIPPED" not in md
