import json

from studio.guerrilla import compose
from studio.guerrilla.highlight import Moment

GOOD = ('{"variants": ['
        '{"text": "If you replace every plank, when exactly did it stop being the ship?",'
        ' "style_tag": "provocative_question"},'
        '{"text": "My car has had 3 new engines and I still owe money on the original.",'
        ' "style_tag": "joke"},'
        '{"text": "The paradox dissolves if identity is a process, not an object.",'
        ' "style_tag": "insight"}]}')


def _stub(payload):
    def complete(provider, system, user):
        return payload
    return complete


def test_variants_are_parsed():
    got = compose.variants("The Ship of Theseus", "A paradox about identity.",
                           complete=_stub(GOOD))
    assert len(got) == 3
    assert got[0].style_tag == "provocative_question"
    assert "plank" in got[0].text


def test_unknown_style_tags_are_normalized_to_insight():
    got = compose.variants("T", "s", complete=_stub(
        '{"variants": [{"text": "hi there friend", "style_tag": "shitpost"}]}'))
    assert got[0].style_tag == "insight"


def test_blank_and_overlong_variants_are_dropped():
    got = compose.variants("T", "s", complete=_stub(
        '{"variants": [{"text": "", "style_tag": "joke"},'
        ' {"text": "' + "x" * 400 + '", "style_tag": "joke"},'
        ' {"text": "a real comment", "style_tag": "joke"}]}'))
    assert [v.text for v in got] == ["a real comment"]


def test_unparseable_output_yields_no_variants():
    assert compose.variants("T", "s", complete=_stub("sorry, I can't")) == []


def test_llm_exception_yields_no_variants():
    def boom(provider, system, user):
        raise RuntimeError("upstream 500")

    assert compose.variants("T", "s", complete=boom) == []


def test_prompt_forbids_self_promotion():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        return GOOD

    compose.variants("T", "s", complete=complete)
    assert "never mention" in seen["system"].lower()


def test_prompt_forbids_formulaic_openers():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        return GOOD

    compose.variants("T", "s", complete=complete)
    system = seen["system"].lower()
    assert "forbidden" in system
    assert "if ..." in system
    assert "what if" in system
    assert "imagine if" in system
    assert "isn't it interesting that" in system


def test_prompt_bans_hedged_reviewer_register():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        return GOOD

    compose.variants("T", "s", complete=complete)
    system = seen["system"].lower()
    assert "it's fascinating how" in system
    assert "really challenges" in system
    assert "it raises the question" in system
    assert "it makes me wonder" in system
    assert "this really highlights" in system
    # Banning the register alone isn't enough without telling the model not to
    # recap the video's own thesis back at its creator.
    assert "summarizing the video back" in system or "recap" in system


def test_prompt_requires_style_tag_honesty():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        return GOOD

    compose.variants("T", "s", complete=complete)
    system = seen["system"].lower()
    assert "style-tag honesty" in system
    assert "must contain an actual joke" in system
    assert "must actually disagree" in system


def test_system_format_example_block_is_valid_json():
    formatted = compose.SYSTEM.format(n=3)
    marker = "Output ONLY valid JSON:"
    assert marker in formatted
    block = formatted.split(marker, 1)[1].strip()
    data = json.loads(block)
    assert data == {"variants": [{"text": "...", "style_tag": "..."}]}


# ------------------------------------------------------------------ moment grounding


MOMENT = Moment(
    timestamp=753.0,
    quote="the number nobody expected was forty-two",
    why="a specific, checkable claim a stranger could react to without watching",
    citability=4.6,
)


def test_moment_prompt_contains_quote_timestamp_and_why():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        seen["user"] = user
        return GOOD

    compose.variants("T", "s", complete=complete, moment=MOMENT, cite=True)
    prompt = seen["system"] + "\n" + seen["user"]
    assert MOMENT.quote in prompt
    assert MOMENT.why in prompt
    assert "12:33" in prompt  # stamp(753.0) == "12:33"


def test_cite_true_instructs_citing_the_timestamp():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        return GOOD

    compose.variants("T", "s", complete=complete, moment=MOMENT, cite=True)
    system = seen["system"].lower()
    assert "cite the timestamp" in system
    assert "do not cite the timestamp" not in system


def test_cite_false_instructs_not_citing_the_timestamp():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        return GOOD

    compose.variants("T", "s", complete=complete, moment=MOMENT, cite=False)
    system = seen["system"].lower()
    assert "do not cite the timestamp" in system


def test_moment_none_preserves_current_title_and_summary_prompt():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        seen["user"] = user
        return GOOD

    compose.variants("The Ship of Theseus", "A paradox about identity.", complete=complete)
    assert seen["user"] == compose.USER_TMPL.format(
        title="The Ship of Theseus", summary="A paradox about identity.")
    assert "react to one real moment" not in seen["system"].lower()
    assert "cite the timestamp" not in seen["system"].lower()


def test_moment_present_preserves_existing_hard_rules_in_prompt():
    seen = {}

    def complete(provider, system, user):
        seen["system"] = system
        return GOOD

    compose.variants("T", "s", complete=complete, moment=MOMENT, cite=False)
    system = seen["system"].lower()
    assert "never mention" in system
    assert "forbidden" in system
    assert "if ..." in system
    assert "it's fascinating how" in system
    assert "style-tag honesty" in system
