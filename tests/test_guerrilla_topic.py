from studio.guerrilla import topic


def _stub(payload):
    def complete(provider, system, user):
        return payload
    return complete


def test_classify_parses_a_clean_verdict():
    t = topic.classify("The Ship of Theseus", "A paradox about identity.",
                       complete=_stub('{"topic": "identity paradox", "confidence": 0.93,'
                                      ' "summary": "Whether a repaired ship stays itself."}'))
    assert t.topic == "identity paradox"
    assert t.confidence == 0.93
    assert topic.is_clear(t) is True


def test_low_confidence_is_not_clear():
    t = topic.classify("vlog #47", "",
                       complete=_stub('{"topic": "unknown", "confidence": 0.2, "summary": ""}'))
    assert topic.is_clear(t) is False


def test_fenced_json_is_tolerated():
    t = topic.classify("T", "d", complete=_stub(
        '```json\n{"topic": "x", "confidence": 0.8, "summary": "s"}\n```'))
    assert t.topic == "x"


def test_unparseable_output_is_treated_as_unclear_not_an_error():
    t = topic.classify("T", "d", complete=_stub("I'm not sure what this video is about."))
    assert t.confidence == 0.0
    assert topic.is_clear(t) is False


def test_llm_exception_is_treated_as_unclear():
    def boom(provider, system, user):
        raise RuntimeError("upstream 500")

    t = topic.classify("T", "d", complete=boom)
    assert topic.is_clear(t) is False


def test_description_is_truncated_before_prompting():
    seen = {}

    def complete(provider, system, user):
        seen["user"] = user
        return '{"topic": "x", "confidence": 0.9, "summary": "s"}'

    topic.classify("T", "z" * 5000, complete=complete)
    assert len(seen["user"]) < 3000


def test_provider_resolution_failure_does_not_raise(monkeypatch):
    def raise_error(name):
        raise RuntimeError("provider resolution failed")

    monkeypatch.setattr("studio.guerrilla.topic.default_provider", raise_error)
    t = topic.classify("T", "d")
    assert t.confidence == 0.0
    assert topic.is_clear(t) is False


# ------------------------------------------------------------------ transcript_excerpt (Task 5)


def test_classify_with_excerpt_includes_it_in_the_prompt():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        seen["user"] = user
        return '{"topic": "x", "confidence": 0.9, "summary": "s"}'

    topic.classify("T", "d", complete=complete,
                   transcript_excerpt="[0:00] a very specific spoken claim")
    assert "a very specific spoken claim" in seen["user"]


def test_classify_without_excerpt_is_unchanged():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        seen["user"] = user
        return '{"topic": "x", "confidence": 0.9, "summary": "s"}'

    topic.classify("T", "d", complete=complete)
    assert seen["system"] == topic.SYSTEM
    assert seen["user"] == topic.USER_TMPL.format(title="T", description="d")
    assert "Transcript excerpt" not in seen["user"]
