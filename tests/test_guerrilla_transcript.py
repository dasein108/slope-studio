from studio.guerrilla import db, transcript


def _conn():
    conn = db.connect_memory()
    conn.execute("INSERT INTO channels (channel_id) VALUES ('UC1')")
    conn.execute("INSERT INTO videos (video_id, channel_id) VALUES ('v1', 'UC1')")
    conn.commit()
    return conn


class _AttrSnippet:
    """Stand-in for the current library's FetchedTranscriptSnippet."""

    def __init__(self, start, text):
        self.start = start
        self.text = text


# ------------------------------------------------------------------ normalization


def test_fetch_normalizes_attribute_style_snippets():
    def fetcher(video_id):
        return [_AttrSnippet(0.0, "hello"), _AttrSnippet(2.5, "world")]

    segments = transcript.fetch("v1", fetcher=fetcher)
    assert segments == [
        transcript.Segment(start=0.0, text="hello"),
        transcript.Segment(start=2.5, text="world"),
    ]


def test_fetch_normalizes_dict_style_snippets():
    def fetcher(video_id):
        return [{"start": 0.0, "text": "hello"}, {"start": 2.5, "text": "world"}]

    segments = transcript.fetch("v1", fetcher=fetcher)
    assert segments == [
        transcript.Segment(start=0.0, text="hello"),
        transcript.Segment(start=2.5, text="world"),
    ]


# ------------------------------------------------------------------ fetch never raises


def test_fetch_returns_empty_list_on_fetcher_exception():
    def fetcher(video_id):
        raise RuntimeError("no captions available")

    assert transcript.fetch("v1", fetcher=fetcher) == []


# ------------------------------------------------------------------ cached


def test_cached_fetches_once_then_reads_from_db():
    conn = _conn()
    calls = []

    def fetcher(video_id):
        calls.append(video_id)
        return [{"start": 0.0, "text": "hi"}]

    first = transcript.cached(conn, "v1", fetcher=fetcher)
    second = transcript.cached(conn, "v1", fetcher=fetcher)

    assert first == [transcript.Segment(start=0.0, text="hi")]
    assert second == first
    assert calls == ["v1"]


def test_cached_stores_empty_result_and_does_not_refetch():
    conn = _conn()
    calls = []

    def fetcher(video_id):
        calls.append(video_id)
        return []

    first = transcript.cached(conn, "v1", fetcher=fetcher)
    second = transcript.cached(conn, "v1", fetcher=fetcher)

    assert first == []
    assert second == []
    assert calls == ["v1"]

    row = conn.execute("SELECT * FROM transcripts WHERE video_id = 'v1'").fetchone()
    assert row is not None
    assert row["segments"] == "[]"


# ------------------------------------------------------------------ stamp


def test_stamp_at_zero_seconds():
    assert transcript.stamp(0) == "0:00"


def test_stamp_under_an_hour():
    assert transcript.stamp(63) == "1:03"


def test_stamp_at_and_past_an_hour():
    assert transcript.stamp(3723) == "1:02:03"


# ------------------------------------------------------------------ at


def test_at_returns_nearby_text_and_excludes_far_segments():
    segments = [
        transcript.Segment(start=0.0, text="intro"),
        transcript.Segment(start=100.0, text="near before"),
        transcript.Segment(start=110.0, text="on target"),
        transcript.Segment(start=120.0, text="near after"),
        transcript.Segment(start=300.0, text="far away"),
    ]
    result = transcript.at(segments, 110.0, window=15.0)
    assert "near before" in result
    assert "on target" in result
    assert "near after" in result
    assert "far away" not in result
    assert "intro" not in result


# ------------------------------------------------------------------ as_prompt


def test_as_prompt_formats_lines():
    segments = [
        transcript.Segment(start=0.0, text="hello"),
        transcript.Segment(start=63.0, text="world"),
    ]
    assert transcript.as_prompt(segments) == "[0:00] hello\n[1:03] world"


def test_as_prompt_respects_start_and_end_range():
    segments = [
        transcript.Segment(start=0.0, text="too early"),
        transcript.Segment(start=50.0, text="in range"),
        transcript.Segment(start=200.0, text="too late"),
    ]
    result = transcript.as_prompt(segments, start=10.0, end=100.0)
    assert result == "[0:50] in range"


# ------------------------------------------------------------------ duration


def test_duration_is_last_segment_start():
    segments = [transcript.Segment(start=0.0, text="a"), transcript.Segment(start=42.0, text="b")]
    assert transcript.duration(segments) == 42.0


def test_duration_of_empty_list_is_zero():
    assert transcript.duration([]) == 0.0
