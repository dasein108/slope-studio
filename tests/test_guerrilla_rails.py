import random
from datetime import datetime, timedelta, timezone

import pytest

from studio.guerrilla import db, rails, transcript, watchlist


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


@pytest.mark.parametrize("text,rule", [
    ("bit.ly/xyz check this out", "link"),
    ("find me at example dot com", "link"),
    ("🔥 great point 🔥 really 🔥 got me 🔥", "emoji_spam"),
    ("follow for more content like this", "self_promo"),
    ("smash that like button if you agree", "self_promo"),
    ("drop a like if this made sense", "self_promo"),
    ("new video every week on this topic", "self_promo"),
    ("dm me if you want to talk more", "self_promo"),
    ("comment below what you think", "self_promo"),
    ("you should check it out sometime", "self_promo"),
    ("Starship Pilot covered this exact idea", "channel_name"),
    ("P.O.L.S. did a video on this", "channel_name"),
    ("p4rad0x n01r talked about this too", "channel_name"),
    ("parad0x  noir mentioned this last week", "channel_name"),
])
def test_denylist_catches_widened_evasions(text, rule):
    assert rails.violates_denylist(text) == rule


def test_clean_comment_passes_denylist():
    assert rails.violates_denylist(
        "If you replace every plank, when did it stop being the ship?") == ""


@pytest.mark.parametrize("text,rule", [
    ("P.O.L.S. did a video on this", "channel_name"),
    ("POLS did a video on this", "channel_name"),
    ("PARADOX   NOIR with odd spacing", "channel_name"),
])
def test_denylist_channel_alias_still_catches_genuine_forms(text, rule):
    assert rails.violates_denylist(text) == rule


@pytest.mark.parametrize("text", [
    "Polska has a rich philosophical tradition too.",
    "I really enjoy polish cuisine.",
    "the polls results from yesterday were surprising",
])
def test_denylist_channel_alias_does_not_match_mid_word(text):
    """The bare P.O.L.S. alias has no letters left to anchor on once dots
    are optional, so without word boundaries it matches inside ordinary
    words like "Polska", "polish", and "polls"."""
    assert rails.violates_denylist(text) == ""


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


@pytest.mark.parametrize("text,recent", [
    ("mind blown genuinely", ["mind blown honestly"]),
    ("this really hits different", ["this hits different"]),
])
def test_short_comment_near_duplicate_is_rejected(text, recent):
    """A one-word edit on a short comment must not defeat duplicate detection."""
    assert rails.too_similar(text, recent) is True


def test_long_comment_genuinely_different_is_still_allowed():
    """Guard against the short-text fallback over-matching unrelated long text."""
    recent = ["If you replace every plank, when did it stop being the ship?"]
    assert rails.too_similar(
        "Gödel proved arithmetic cannot prove its own consistency, "
        "which is a very different kind of paradox entirely.", recent) is False


@pytest.mark.parametrize("text,recent", [
    # Real one-word-edit comment pairs measured off the word-shingle path
    # (more than k=4 words each). Under the old single 0.5 threshold these
    # all scored below the bar and were NOT blocked; that's the fail-open
    # this rail exists to close.
    ("When exactly did it stop being a ship?",
     ["When exactly did it stop being the ship?"]),  # jaccard 0.429
    ("If you replace every plank, when did it stop being a ship?",
     ["If you replace every plank, when did it stop being the ship?"]),  # jaccard 0.636
    ("I think that this is the clearest explanation",
     ["I think that this is the best explanation"]),  # jaccard 0.429
    ("The paradox dissolves when identity is a process, not an object.",
     ["The paradox dissolves if identity is a process, not an object."]),  # jaccard 0.333
])
def test_one_word_edit_word_shingle_pairs_are_rejected(text, recent):
    """Measured against real comment pairs: one-word edits of the same
    comment score 0.333-0.636 jaccard on the word-shingle path, all above
    the 0.3 threshold and with a wide margin over genuinely unrelated text
    (0.0). The 0.5 threshold missed every one of these."""
    assert rails.too_similar(text, recent) is True


def test_unrelated_long_comments_score_zero_and_are_allowed():
    """Regression guard against over-blocking: genuinely unrelated long
    comments measure 0.0 jaccard, nowhere near the 0.3 word-shingle
    threshold."""
    recent = ["If you replace every plank, when did it stop being the ship?"]
    assert rails.jaccard(
        rails.shingles("Gödel proved arithmetic cannot prove its own consistency."),
        rails.shingles(recent[0])) == 0.0
    assert rails.too_similar(
        "Gödel proved arithmetic cannot prove its own consistency.", recent) is False


def test_short_text_path_keeps_the_higher_threshold():
    """A sub-k-word pair that scores between the two thresholds (0.417,
    here) must NOT be flagged: the character-gram fallback path stays at
    0.5, not the 0.3 word-shingle threshold, because it already over-blocks
    at 0.5 on short antonym pairs and dropping it further would be worse."""
    text, recent = "great work", ["great job"]
    score = rails.jaccard(rails.shingles(text), rails.shingles(recent[0]))
    assert 0.3 <= score < 0.5
    assert rails.too_similar(text, recent) is False


@pytest.mark.parametrize("text,recent", [
    ("makes sense", ["makes no sense"]),
    ("i agree completely", ["i disagree completely"]),
    ("this is helpful", ["this is unhelpful"]),
    ("expected this outcome", ["unexpected this outcome"]),
    ("i like this", ["i dislike this"]),
    ("totally agree here", ["totally disagree here"]),
])
def test_short_negation_is_not_a_near_duplicate(text, recent):
    """A negation flips meaning; the char-gram fallback must not treat it
    as a near-duplicate just because the footprint barely moved."""
    assert rails.too_similar(text, recent) is False


def test_active_window_excludes_the_small_hours():
    assert rails.in_active_window(datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)) is True
    assert rails.in_active_window(datetime(2026, 7, 18, 4, 0, tzinfo=timezone.utc)) is False
    assert rails.in_active_window(datetime(2026, 7, 18, 23, 30, tzinfo=timezone.utc)) is False


def test_blackout_covers_six_hours_either_side_of_a_publish():
    pub = ["2026-07-18T12:00:00+00:00"]
    assert rails.in_blackout(datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc), pub) is True
    assert rails.in_blackout(datetime(2026, 7, 18, 7, 0, tzinfo=timezone.utc), pub) is True
    assert rails.in_blackout(datetime(2026, 7, 18, 21, 0, tzinfo=timezone.utc), pub) is False


def test_active_window_is_timezone_normalized():
    """The same real instant must verdict the same regardless of the tzinfo
    the caller happened to attach — e.g. `datetime.now().astimezone()`."""
    instant_utc = datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)
    instant_plus10 = instant_utc.astimezone(timezone(timedelta(hours=10)))
    instant_naive = instant_utc.replace(tzinfo=None)

    verdicts = {rails.in_active_window(instant_utc),
                rails.in_active_window(instant_plus10),
                rails.in_active_window(instant_naive)}
    assert verdicts == {True}


def test_blackout_accepts_naive_now_without_raising():
    pub = ["2026-07-18T12:00:00+00:00"]
    naive_now = datetime(2026, 7, 18, 15, 0)
    assert rails.in_blackout(naive_now, pub) is True


def test_delay_is_jittered_within_bounds_and_never_constant():
    rng = random.Random(7)
    delays = [rails.next_delay_seconds(rng) for _ in range(50)]
    assert all(12 * 60 * 0.6 <= d <= 12 * 60 * 1.4 for d in delays)
    assert len(set(delays)) > 40


# ------------------------------------------------------------------ template-monoculture rails

@pytest.mark.parametrize("text,recent", [
    ("If communication is the most important skill, how do we address this?",
     ["If communication is the true glue holding civilization together, this proves it."]),
    ("if Christ changed human consciousness forever, what does that mean?",
     ["If Christ changed human history in ways we still feel today."]),
])
def test_repeats_opening_catches_shared_four_word_opener(text, recent):
    assert rails.repeats_opening(text, recent) is True


def test_repeats_opening_is_case_and_punctuation_insensitive():
    assert rails.repeats_opening(
        "IF, communication is the most important skill...",
        ["if communication is the most important skill of all"]) is True


@pytest.mark.parametrize("text,recent", [
    ("Bertrand Russell walks into a bar and orders a drink.",
     ["If archetypes shape our reality, do we ever truly have free will?"]),
    ("Quantum entanglement links particles no matter the distance.",
     ["If quantum entanglement can link particles across distances, what does that imply?"]),
])
def test_repeats_opening_passes_genuinely_different_openings(text, recent):
    assert rails.repeats_opening(text, recent) is False


def test_repeats_opening_empty_history_allows_anything():
    assert rails.repeats_opening("If this opens the same way", []) is False


def test_style_overused_fires_at_the_limit_inside_the_window():
    recent_styles = ["provocative_question", "insight", "provocative_question", "joke", "insight"]
    assert rails.style_overused("provocative_question", recent_styles) is True


def test_style_overused_does_not_fire_below_the_limit():
    recent_styles = ["provocative_question", "insight", "joke", "insight", "contrarian_take"]
    assert rails.style_overused("provocative_question", recent_styles) is False


def test_style_overused_ignores_entries_outside_the_window():
    # Two prior "joke"s exist, but both fall outside a window of 3.
    recent_styles = ["insight", "contrarian_take", "provocative_question", "joke", "joke"]
    assert rails.style_overused("joke", recent_styles, limit=2, window=3) is False


# ------------------------------------------------------------------ bad_timestamp (transcript-grounding, Task 4)

def _segments(*pairs):
    return [transcript.Segment(start=start, text=text) for start, text in pairs]


def test_bad_timestamp_beyond_duration_is_rejected():
    segments = _segments((0.0, "intro"), (100.0, "closing thought"))
    assert rails.bad_timestamp("check the point around 5:00", segments) != ""


def test_bad_timestamp_matching_a_real_segment_is_clean():
    segments = _segments((0.0, "intro"), (300.0, "the actual key point"))
    assert rails.bad_timestamp("great point at 5:00", segments) == ""


def test_bad_timestamp_no_matching_segment_within_tolerance_is_rejected():
    """Within the video's duration, but nothing in the transcript is anywhere
    near the cited moment — an unverifiable citation, rejected the same as an
    out-of-range one."""
    segments = _segments((0.0, "intro"), (590.0, "closing thought"))
    assert rails.bad_timestamp("great point around 5:00", segments) != ""


def test_bad_timestamp_no_citation_is_always_clean():
    segments = _segments((0.0, "intro"))
    assert rails.bad_timestamp("no timestamp mentioned here at all", segments) == ""


def test_bad_timestamp_no_citation_is_clean_even_with_no_transcript():
    assert rails.bad_timestamp("no timestamp mentioned here at all", []) == ""


def test_bad_timestamp_fails_closed_with_no_transcript():
    """A video with no cached transcript (`segments == []`) must reject any
    cited timestamp — an unverifiable citation is treated as unsafe, not as a
    free pass."""
    assert rails.bad_timestamp("check the point around 5:00", []) != ""


def test_bad_timestamp_understands_hour_minute_second_format():
    segments = _segments((0.0, "intro"), (3723.0, "the hour-plus mark"))
    assert rails.bad_timestamp("right around 1:02:03", segments) == ""
    assert rails.bad_timestamp("right around 2:02:03", segments) != ""


def test_bad_timestamp_does_not_misfire_on_aspect_ratios():
    segments = _segments((0.0, "intro"), (100.0, "shot in 16:9 aspect ratio, love it"))
    assert rails.bad_timestamp("shot in 16:9 aspect ratio, love it", segments) == ""


def test_bad_timestamp_does_not_flag_time_of_day():
    """"12:30 pm" has the same M:SS shape as a video timestamp but means a clock
    time, not a moment in the video. Without the am/pm exclusion this would be
    extracted as a citation and rejected as unverifiable against a transcript
    that (correctly) has nothing at 12:30 (750s) in."""
    assert rails.bad_timestamp("let's meet at 12:30 pm to talk about this", []) == ""
    assert rails.bad_timestamp("call me at 9:15am tomorrow", []) == ""
    assert rails.bad_timestamp("around 1:02:03 a.m. is when I usually watch these", []) == ""


def test_bad_timestamp_still_flags_a_genuine_video_timestamp_near_am_pm_text():
    """The am/pm exclusion must be narrow: a real video-timestamp citation that
    merely appears near unrelated am/pm text elsewhere in the comment still
    gets checked."""
    segments = _segments((0.0, "intro"), (100.0, "closing thought"))
    assert rails.bad_timestamp("posted this at 9am but the good bit is at 5:00", segments) != ""


def test_recent_styles_returns_newest_first():
    conn = db.connect_memory()
    watchlist.add(conn, "UC1", median_views=20000)
    for i, (cid, tag, ts) in enumerate([
        ("c1", "joke", "2026-07-18T10:00:00+00:00"),
        ("c2", "insight", "2026-07-18T11:00:00+00:00"),
        ("c3", "provocative_question", "2026-07-18T12:00:00+00:00"),
    ]):
        conn.execute(
            "INSERT INTO videos (video_id, channel_id) VALUES (?, 'UC1')", (f"v{i}",))
        conn.execute(
            "INSERT INTO comments (comment_id, video_id, text, style_tag, posted_at) "
            "VALUES (?, ?, 'x', ?, ?)", (cid, f"v{i}", tag, ts))
    conn.commit()
    assert rails.recent_styles(conn) == ["provocative_question", "insight", "joke"]
