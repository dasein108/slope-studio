import json

from studio.guerrilla import compose, critic


def _stub(payload):
    def complete(provider, system, user):
        return payload
    return complete


def _scores(**kw):
    base = dict.fromkeys(critic.CRITERIA, 4.0)
    base.update(kw)
    return json.dumps({"scores": base})


def test_strong_comment_is_auto_posted():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(on_topic=5.0)))
    assert v.decision == "auto"
    assert v.score > 4.0


def test_middling_comment_is_queued():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(on_topic=3.0, not_generic=3.0,
                                            provocative_or_funny=3.0)))
    assert v.decision == "queue"


def test_weak_comment_is_skipped():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(on_topic=2.0, not_generic=2.0,
                                            provocative_or_funny=2.0)))
    assert v.decision == "skip"


def test_self_promo_zero_forces_skip_despite_high_mean():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(no_self_promo=0.0, on_topic=5.0,
                                            not_generic=5.0, provocative_or_funny=5.0,
                                            not_offensive=5.0)))
    assert v.decision == "skip"


def test_offensive_zero_forces_skip():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(not_offensive=0.0)))
    assert v.decision == "skip"


def test_unparseable_verdict_skips():
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub("no idea"))
    assert v.decision == "skip"


def test_best_picks_the_highest_scoring_variant():
    calls = {"n": 0}
    payloads = [_scores(on_topic=2.0, not_generic=2.0, provocative_or_funny=2.0),
                _scores(on_topic=5.0),
                _scores(on_topic=3.0, not_generic=3.0)]

    def complete(provider, system, user):
        p = payloads[calls["n"]]
        calls["n"] += 1
        return p

    vs = [compose.Variant(text=f"t{i}", style_tag="joke") for i in range(3)]
    winner, verdict, idx = critic.best(vs, "T", "s", complete=complete)
    assert idx == 1 and winner.text == "t1" and verdict.decision == "auto"


def test_best_of_empty_list_returns_nothing():
    assert critic.best([], "T", "s", complete=_stub(_scores())) == (None, None, -1)


# ------------------------------------------------------------------ grounded (transcript-grounding, Task 4)

def test_fabricated_claim_scores_grounded_zero_and_skips_despite_high_mean():
    """A comment that invents a specific the transcript excerpt does not support
    must be unpostable regardless of how well it scores on everything else — the
    same treatment `no_self_promo`/`not_offensive` get."""
    v = critic.judge(
        compose.Variant(text="This reminds me of Flight 32.", style_tag="insight"), "T", "s",
        complete=_stub(_scores(grounded=0.0, on_topic=5.0, provocative_or_funny=5.0,
                               not_generic=5.0)),
        transcript_excerpt="[0:05] The video never mentions any flight or aviation incident.")
    assert v.decision == "skip"
    assert v.breakdown["grounded"] == 0.0


def test_grounded_comment_with_excerpt_can_still_auto_post():
    v = critic.judge(
        compose.Variant(text="A fair reaction to the point made.", style_tag="insight"), "T", "s",
        complete=_stub(_scores(grounded=5.0, on_topic=5.0)),
        transcript_excerpt="[0:05] The actual point the comment reacts to.")
    assert v.decision == "auto"
    assert v.breakdown["grounded"] == 5.0


def test_empty_excerpt_never_disqualifies_on_grounded():
    """With no transcript excerpt, `grounded` must never gate the decision —
    even when a stubbed response (as if a caller stitched one together oddly)
    claims a 0 for it, the empty-excerpt path never reads that key at all."""
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(grounded=0.0, on_topic=5.0)),
                     transcript_excerpt="")
    assert v.decision == "auto"
    assert "grounded" not in v.breakdown


def test_empty_excerpt_leaves_existing_five_criterion_behavior_unchanged():
    """Explicit regression guard for the plan's backward-compatibility bar: an
    empty `transcript_excerpt` (the default, and every pre-Task-4 call site)
    must reproduce exactly the pre-`grounded` scoring behavior."""
    v = critic.judge(compose.Variant(text="t", style_tag="joke"), "T", "s",
                     complete=_stub(_scores(on_topic=5.0)))
    assert v.decision == "auto"
    assert v.score > 4.0
    assert set(v.breakdown) == set(critic.UNGROUNDED_CRITERIA)
