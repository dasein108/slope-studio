"""Character cards + storyboard tagging + per-scene ref selection (all keyless paths)."""

from __future__ import annotations

from pathlib import Path

from studio import characters as chars
from studio.models import Scene, Script
from studio.stages import storyboard
from studio.stages.visuals import _scene_char_setup


def _mk_char(root: Path, name: str, n_imgs: int = 2, aliases: list[str] | None = None):
    d = root / name
    d.mkdir(parents=True)
    for i in range(n_imgs):
        (d / f"ref{i}.png").write_bytes(b"\x89PNG\r\n\x1a\n fake")
    card = chars.CharacterCard(
        name=name, aliases=aliases or [], descriptor=f"locked look of {name}",
        canonical_refs=["ref0.png"], source_images=n_imgs)
    chars.card_path(root, name).write_text(card.model_dump_json())
    return card


def test_stub_card_builds_without_vision_key(tmp_path, monkeypatch):
    # no LLM available → _analyze_one returns None → stub card, first image anchor
    monkeypatch.setattr(chars, "_analyze_one", lambda img: None)
    d = tmp_path / "gurdjieff"
    d.mkdir()
    (d / "b.png").write_bytes(b"x")
    (d / "a.jpg").write_bytes(b"x")
    card = chars.build_card(tmp_path, "gurdjieff")
    assert card.canonical_refs == ["a.jpg"]          # deterministic: sorted first
    assert "gurdjieff" in card.descriptor
    assert chars.card_path(tmp_path, "gurdjieff").exists()


def test_roster_and_alias_matching(tmp_path):
    _mk_char(tmp_path, "gurdjieff", aliases=["G.I. Gurdjieff", "Georgi"])
    _mk_char(tmp_path, "ouspensky")
    r = chars.roster(tmp_path)
    assert set(r) == {"gurdjieff", "ouspensky"}
    hit = chars.match_names("Then Georgi poured the tea while ouspensky waited.", r)
    assert set(hit) == {"gurdjieff", "ouspensky"}


def test_storyboard_stub_tags_characters(tmp_path):
    _mk_char(tmp_path, "gurdjieff")
    run = tmp_path / "run"
    run.mkdir()
    story = ("Gurdjieff arrived at the monastery before dawn. The mountains were silent. "
             "He spoke to no one for three days. Then gurdjieff began to teach.")
    script, _ = storyboard.run(run, story, duration=54, aspect="16:9", style="noir",
                               provider="stub", roster_root=tmp_path)
    assert script.scenes, "no beats"
    assert script.aspect == "16:9"
    tagged = [s for s in script.scenes if s.characters]
    assert tagged and all(s.characters == ["gurdjieff"] for s in tagged)
    assert all(s.image_role == "hero" for s in tagged)
    # full coverage in order, no invented text
    assert "monastery" in " ".join(s.narration for s in script.scenes)


def test_scene_char_setup_stable_anchors_and_cap(tmp_path):
    for n in ("a", "b", "c", "d"):
        _mk_char(tmp_path, n)
    r = chars.roster(tmp_path)
    sc = Scene(id=1, start_s=0, end_s=10, visual_prompt="x",
               characters=["a", "b", "c", "d", "ghost"])
    identity, refs = _scene_char_setup(sc, r, tmp_path)
    assert len(refs) == chars.MAX_SCENE_REFS            # capped at model ref limit
    assert refs[0] == tmp_path / "a" / "ref0.png"       # same anchor every call
    _, refs2 = _scene_char_setup(sc, r, tmp_path)
    assert refs == refs2                                 # deterministic = drift-safe
    assert "Reference image 1 shows a" in identity
    assert "EXACTLY" in identity


def test_scene_without_cards_falls_through(tmp_path):
    sc = Scene(id=1, start_s=0, end_s=10, visual_prompt="x", characters=["nobody"])
    identity, refs = _scene_char_setup(sc, {}, tmp_path)
    assert identity == "" and refs == []


def _mk_text_char(root: Path, name: str, descriptor: str):
    d = root / name
    d.mkdir(parents=True)
    card = chars.CharacterCard(name=name, descriptor=descriptor, canonical_refs=[])
    chars.card_path(root, name).write_text(card.model_dump_json())
    return card


def test_text_card_keyless_build_is_stable(tmp_path, monkeypatch):
    # no LLM key → descriptor still constant + card persisted (never blocks)
    import studio.providers.llm as llm
    monkeypatch.setattr(llm, "complete",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no key")))
    card = chars.build_card_from_text(tmp_path, "the abbot", "story text")
    assert card.canonical_refs == []
    assert "the abbot" in card.descriptor
    assert "text-derived" in card.note
    assert chars.card_path(tmp_path, "the abbot").exists()


def test_text_card_llm_locks_descriptor(tmp_path, monkeypatch):
    import studio.providers.llm as llm
    monkeypatch.setattr(llm, "complete", lambda p, s, u:
                        '{"descriptor": "a gaunt monk in his seventies, white beard to the '
                        'chest, grey wool habit, walnut cane", "aliases": ["the old monk"]}')
    card = chars.build_card_from_text(tmp_path, "the abbot", "…")
    assert "white beard" in card.descriptor
    assert card.aliases == ["the old monk"]


def test_mixed_scene_image_and_text_identity(tmp_path):
    # gurdjieff has an image anchor; the abbot is text-derived (no refs)
    _mk_char(tmp_path, "gurdjieff")
    _mk_text_char(tmp_path, "abbot", "a gaunt monk, white beard, grey habit")
    r = chars.roster(tmp_path)
    sc = Scene(id=1, start_s=0, end_s=10, visual_prompt="tea at dawn",
               characters=["gurdjieff", "abbot"])
    identity, refs = _scene_char_setup(sc, r, tmp_path)
    assert len(refs) == 1                                   # only the image-backed card
    assert "Reference image 1 shows gurdjieff" in identity
    assert "abbot (no reference image" in identity          # text identity still injected
    assert "white beard" in identity


def test_text_only_scene_gets_identity_without_refs(tmp_path):
    _mk_text_char(tmp_path, "abbot", "a gaunt monk, white beard, grey habit")
    sc = Scene(id=1, start_s=0, end_s=10, visual_prompt="x", characters=["abbot"])
    identity, refs = _scene_char_setup(sc, chars.roster(tmp_path), tmp_path)
    assert refs == []
    assert identity and "IDENTICALLY" in identity


def test_story_chunks_respect_boundaries_and_size():
    from studio.stages.storyboard import _story_chunks
    # paragraphs pack up to the limit, never split mid-paragraph when avoidable
    text = "\n\n".join(f"Абзац {i}. " + "слово " * 50 for i in range(12))
    chunks = _story_chunks(text, 1200)
    assert all(len(c) <= 1200 for c in chunks)
    assert "".join(c.replace("\n\n", "") for c in chunks).count("Абзац") == 12
    # an oversized single paragraph falls back to sentence splits, then hard cuts
    giant = "Первое предложение. " * 200
    chunks = _story_chunks(giant, 500)
    assert all(len(c) <= 500 for c in chunks)
    assert sum(c.count("предложение") for c in chunks) == 200


def test_scene_spans_char_mapping():
    from studio.stages.narrate import _scene_spans
    # 3 scenes; word cues drift from .split() tokenization — mapping is char-based
    texts = ["один два три", "четыре пять", "шесть"]
    cues, t = [], 0.0
    for w in "один два три четыре пять шесть".split():
        cues.append((t, t + 0.4, w)); t += 0.5
    durs = _scene_spans(texts, cues, total=3.0)
    assert len(durs) == 3
    assert abs(sum(durs) - 3.0) < 0.01           # durations sum to the audio length
    assert durs[0] > durs[2]                      # 3 words > 1 word
