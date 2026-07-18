"""Stage 2 — one keyframe image per scene (consistent character via prompt/refs)."""

from __future__ import annotations

import re
from pathlib import Path

from studio import canvas, paths
from studio.models import Script
from studio.providers import image
from studio.providers.base import GenResult


# Aspect-ratio token (e.g. "9:16", "16:9") that the script LLM sometimes bakes into a
# scene's visual_prompt despite instructions not to. Prompt-literal image models
# (fal-flux-schnell, pollinations) render it as on-screen text → QA Gate-2 rejects.
# Aspect already lives in `script.aspect` (sent as an API param), so it must never reach
# the image prompt. Strip every occurrence plus any trailing/leading separators.
_ASPECT_TOKEN = re.compile(r"\s*,?\s*\b\d{1,2}:\d{1,2}\b")


def _strip_aspect_token(prompt: str) -> str:
    """Remove any aspect-ratio token (digits:digits) from an image prompt."""
    cleaned = _ASPECT_TOKEN.sub("", prompt)
    return re.sub(r"\s+", " ", cleaned).strip(" ,")


PLATE_SUFFIX = (
    ". BACKGROUND PLATE — render the EXACT same scene, setting, composition and lighting "
    "but with every person, figure, character and main foreground subject COMPLETELY "
    "REMOVED: empty architecture and scenery only, no people anywhere, a clean uninhabited "
    "background"
)

FG_SUFFIX = (
    ". FOREGROUND SUBJECT PLATE — render ONLY the main subject/character, full body, centered, "
    "isolated on a PLAIN FLAT solid pale-grey background with NOTHING else in frame (no scenery, "
    "no props, no shadow), even studio lighting — composed to be cleanly cut out."
)


def _key_foreground(path: Path) -> bool:
    """Cut the (flat-bg) subject to transparency with rembg. Returns True on success; on any
    failure the plate is removed so parallax falls back to cutting the main still."""
    try:
        from rembg import remove
        from PIL import Image
        remove(Image.open(path).convert("RGBA")).save(path)
        return True
    except Exception:
        path.unlink(missing_ok=True)
        return False


def _scene_char_setup(scene, roster: dict, char_root: Path) -> tuple[str, list[Path]]:
    """Identity preamble + ordered anchor refs for a character-tagged scene.
    Pure function (unit-tested): cards are looked up by scene.characters, capped at
    the model's reference limit, and the SAME canonical anchors are returned for
    every scene — anchor stability is the anti-drift contract."""
    from studio import characters as chars
    cards, ref_cards, refs = [], [], []
    for name in scene.characters[:chars.MAX_SCENE_REFS]:
        card = roster.get(name)
        if not card:
            continue
        cards.append(card)
        anchors = chars.anchor_refs(card, char_root)
        if anchors:
            ref_cards.append(card)
            refs.append(anchors[0])   # exactly one anchor per character, always the same
        # no anchors → text-derived card: locked descriptor IS the anchor
    if not cards:
        return "", []
    return chars.scene_identity_block(cards, with_refs=ref_cards), refs


def _verify_character(img: Path, cards: list) -> str:
    """Drift gate: vision-check the rendered frame against each card's locked
    descriptor. Returns "" when consistent, else concrete fix notes for ONE retry.
    Any failure (no key, bad JSON) returns "" — the gate never blocks offline runs."""
    import json as _json
    try:
        from studio.providers import llm
        want = "; ".join(f"{c.name}: {c.descriptor}" for c in cards if c.descriptor)
        if not want:
            return ""
        d = _json.loads(llm.vision_json(
            img,
            "You verify character consistency between an illustration and locked descriptors.",
            f"Expected characters: {want}\nDoes each match the figure(s) in the image? "
            'Respond ONLY JSON: {"match": true|false, "fixes": "<what to correct, or empty>"}'))
        return "" if d.get("match", True) else str(d.get("fixes", ""))[:300]
    except Exception:
        return ""


def run(run_dir: Path, provider: str, char_ref: Path | None = None,
        force: bool = False, cheap_provider: str = "", parallax_plates: bool = False,
        parallax_fg: bool = False, characters_root: Path | None = None,
        verify_chars: bool = True) -> GenResult:
    """Generate one keyframe per scene. With `cheap_provider`, scenes flagged
    `image_role="bg"` (backgrounds/overlays) use the cheaper model, while
    `hero`/default scenes (character/main person) use the quality `provider` — and
    only those get the character reference (cheap models ignore it anyway).

    `parallax_plates` (balanced+ tiers): for every `animator:"parallax"` scene also
    generate a SEPARATE background plate (subject removed) → true layered parallax with
    genuinely different fg/bg images (no torn frame, no inpaint hole). +1 image/scene."""
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    canvas.set_from_aspect(script.aspect)
    paths.visuals_dir(run_dir).mkdir(parents=True, exist_ok=True)
    refs = [char_ref] if char_ref else None
    ch_roster: dict = {}
    if characters_root and any(s.characters for s in script.scenes):
        from studio import characters as chars
        ch_roster = chars.roster(characters_root)

    total_cost, total_latency = 0.0, 0.0
    counts: dict[str, int] = {}
    for idx, scene in enumerate(script.scenes):
        dst = paths.scene_image(run_dir, scene.id)
        # character-tagged scenes → quality model + that scene's card anchors;
        # backgrounds/overlays → cheap model (no char ref); else quality + global ref.
        identity, ch_refs = ("", [])
        if scene.characters and ch_roster:
            identity, ch_refs = _scene_char_setup(scene, ch_roster, characters_root)
        if identity:
            # never the cheap model for a character scene — even a text-only identity
            # needs the reference-capable model to hold a constant look
            prov, use_refs = provider, (ch_refs or None)
        elif scene.image_role == "bg" and cheap_provider:
            prov, use_refs = cheap_provider, None
        else:
            prov, use_refs = provider, refs
        # reinforce consistency: prepend the reusable character string.
        # strip any leaked aspect-ratio token so prompt-literal models don't render it.
        prompt = _strip_aspect_token(scene.visual_prompt)
        if identity:
            prompt = f"{identity} Scene: {prompt}"
        elif script.character and script.character not in prompt:
            prompt = f"{script.character}. {prompt}"
        if characters_root is not None and not scene.on_screen_text:
            # the model sometimes renders the prompt itself as a garbled overlay
            # caption. Ban OVERLAYS only — text that belongs to objects in the
            # scene (newspaper headlines, shop signs, a chalkboard) is welcome.
            prompt += (" No overlay text: no captions, subtitles, watermarks, or "
                       "floating labels. Text printed on objects inside the scene "
                       "(newspapers, signs, books) is fine.")
        if not (dst.exists() and not force):
            res = image.generate(prov, prompt, dst, refs=use_refs, aspect=script.aspect,
                                 headline=scene.on_screen_text, index=idx)
            total_cost += res.cost_usd
            total_latency += res.latency_s
            counts[prov] = counts.get(prov, 0) + 1
            # drift gate: one vision check + at most one corrected regeneration
            # (text-derived identities are verified too — the descriptor is checkable)
            if identity and verify_chars:
                fixes = _verify_character(dst, [ch_roster[n] for n in scene.characters
                                                if n in ch_roster])
                if fixes:
                    res = image.generate(prov, f"{prompt} CORRECTIONS: {fixes}", dst,
                                         refs=use_refs, aspect=script.aspect,
                                         headline=scene.on_screen_text, index=idx)
                    total_cost += res.cost_usd
                    total_latency += res.latency_s
                    counts[f"{prov}+retry"] = counts.get(f"{prov}+retry", 0) + 1
        is_parallax = (scene.animator or "").strip() == "parallax"
        # layered-parallax background plate (subject removed) — balanced+ only.
        if parallax_plates and is_parallax:
            bgdst = paths.scene_image_bg(run_dir, scene.id)
            if not (bgdst.exists() and not force):
                res2 = image.generate(prov, prompt + PLATE_SUFFIX, bgdst, refs=None,
                                      aspect=script.aspect, index=idx)
                total_cost += res2.cost_usd
                total_latency += res2.latency_s
                counts[f"{prov}+plate"] = counts.get(f"{prov}+plate", 0) + 1
        # Route 1: separate FOREGROUND plate — subject on a flat bg, keyed to transparency
        # (cleaner cutout than rembg-ing the busy still; uses the char ref to match the scene).
        if parallax_fg and is_parallax:
            fgdst = paths.scene_image_fg(run_dir, scene.id)
            if not (fgdst.exists() and not force):
                res3 = image.generate(prov, prompt + FG_SUFFIX, fgdst, refs=use_refs,
                                      aspect=script.aspect, index=idx)
                total_cost += res3.cost_usd
                total_latency += res3.latency_s
                if _key_foreground(fgdst):
                    counts[f"{prov}+fg"] = counts.get(f"{prov}+fg", 0) + 1
    n = sum(counts.values())
    mix = ", ".join(f"{v}×{k}" for k, v in counts.items()) or "0"
    return GenResult(path=paths.visuals_dir(run_dir), cost_usd=round(total_cost, 4),
                     latency_s=round(total_latency, 2),
                     provider="+".join(counts) or provider, note=f"{n} images ({mix})")
