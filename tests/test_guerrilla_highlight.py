import json

from studio.guerrilla import highlight
from studio.guerrilla.transcript import Segment

MOMENT_JSON = json.dumps({
    "timestamp": 30.0,
    "quote": "something surprising: the number is 42",
    "why": "a specific, checkable claim",
    "citability": 4.6,
})


def _stub(payload):
    def complete(provider, system, user):
        return payload
    return complete


# ------------------------------------------------------------------ single chunk


def test_single_chunk_returns_stubs_moment_parsed():
    segments = [
        Segment(start=0.0, text="hello and welcome"),
        Segment(start=30.0, text="something surprising: the number is 42"),
    ]
    moment = highlight.best_moment(segments, "T", complete=_stub(MOMENT_JSON))
    assert moment is not None
    assert moment.timestamp == 30.0
    assert moment.quote == "something surprising: the number is 42"
    assert moment.why == "a specific, checkable claim"
    assert moment.citability == 4.6


# ------------------------------------------------------------------ multi-chunk chunk-and-rank


def test_multichunk_makes_one_call_per_chunk_and_returns_highest_citability():
    segments = [
        Segment(start=0.0, text="intro filler"),
        Segment(start=120.0, text="ambient stuff"),
        Segment(start=200.0, text="a wild claim two hundred"),
        Segment(start=260.0, text="a numbered claim two sixty"),
        Segment(start=300.0, text="closing filler"),
    ]
    calls = []

    def complete(provider, system, user):
        calls.append(user)
        if "two sixty" in user:
            return json.dumps({
                "timestamp": 260.0, "quote": "a numbered claim two sixty",
                "why": "specific number", "citability": 4.7,
            })
        return json.dumps({
            "timestamp": 200.0, "quote": "a wild claim two hundred",
            "why": "vague", "citability": 1.2,
        })

    moment = highlight.best_moment(segments, "T", complete=complete)
    assert len(calls) == 2
    assert moment is not None
    assert moment.citability == 4.7
    assert moment.timestamp == 260.0
    assert moment.quote == "a numbered claim two sixty"


# ------------------------------------------------------------------ never raises


def test_unparseable_output_yields_none():
    segments = [Segment(start=0.0, text="hi")]
    assert highlight.best_moment(segments, "T", complete=_stub("sorry, I can't")) is None


def test_llm_exception_yields_none():
    segments = [Segment(start=0.0, text="hi")]

    def boom(provider, system, user):
        raise RuntimeError("upstream 500")

    assert highlight.best_moment(segments, "T", complete=boom) is None


def test_empty_transcript_yields_none_without_calling_llm():
    def boom(provider, system, user):
        raise AssertionError("should never be called for an empty transcript")

    assert highlight.best_moment([], "T", complete=boom) is None


def test_provider_resolution_failure_does_not_raise(monkeypatch):
    def raise_error(name):
        raise RuntimeError("provider resolution failed")

    monkeypatch.setattr("studio.guerrilla.highlight.default_provider", raise_error)
    segments = [Segment(start=0.0, text="hi")]
    assert highlight.best_moment(segments, "T") is None


# ------------------------------------------------------------------ should_cite


def test_should_cite_at_exactly_threshold_is_true():
    moment = highlight.Moment(timestamp=1.0, quote="q", why="w", citability=4.0)
    assert highlight.should_cite(moment) is True


def test_should_cite_just_below_threshold_is_false():
    moment = highlight.Moment(timestamp=1.0, quote="q", why="w", citability=3.9)
    assert highlight.should_cite(moment) is False


# ------------------------------------------------------------------ prompt content


def test_system_prompt_demands_verbatim_quote_and_explains_citability():
    system = highlight.SYSTEM.lower()
    assert "verbatim" in system
    assert "citability" in system
    assert "without having watched" in system
    assert "specific number" in system or "surprising claim" in system
