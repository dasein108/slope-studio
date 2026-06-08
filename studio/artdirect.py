"""Art-direction pass — assign per-scene visual effects (animator / atmosphere / fx /
transition).

Hybrid policy:
  1. The script LLM is asked (in stages/script.py) to pick effects from a documented menu.
  2. This pass VALIDATES those picks (unknown names → dropped) and FILLS any gaps with
     content + position heuristics.

So a scene the model left bare — or the whole offline `stub` script, which has no LLM —
still gets purposeful, varied motion instead of every scene falling back to `kenburns`.
The whole reason this exists: the effect library was large but nothing *selected* from it,
so only kenburns ever shipped. Keep it tasteful: vary animators, use atmosphere/fx only
when the content calls for it, never kinetic-spam.
"""

from __future__ import annotations

from studio.models import Scene, Script

# canonical valid names (mirror studio/models.py + animate.py + ffmpeg.post_fx)
ANIMATORS = {
    "kenburns", "static", "kinetic", "parallax", "blurred-parallax", "slice",
    "puppet", "talkinghead", "manim",
    "motion-driftleft", "motion-driftright", "motion-driftup", "motion-driftdown",
    "motion-zoomin", "motion-zoomout", "motion-pulse",
}
ATMOS = {"rain", "snow", "embers", "blood", "petals", "leaves", "wind", "fog"}
FX = {"grain", "vignette", "chroma", "glitch", "sunrise", "sunset", "godrays", "oldfilm",
      "flash-white", "flash-yellow", "flash-red", "flash-black"}
TRANSITIONS = {"cut", "fade", "fadeblack", "wipeleft", "dissolve", "slideup",
               "smoothright", "circleopen", "pixelize", "radial"}

# content keyword -> (atmosphere, [fx]). First match wins; tuned for tasteful, obvious fits.
_MOOD: list[tuple[tuple[str, ...], str, list[str]]] = [
    (("duel", "battle", "war", "fight", "clash", "gun", "shot", "blood", "wound", "kill",
      "stab", "blade", "sword"), "embers", ["flash-red"]),
    (("fire", "burn", "flame", "ember", "explosion", "blast", "forge", "inferno"),
     "embers", ["grain"]),
    (("rain", "storm", "tears", "weep", "wept", "grief", "mourn", "funeral", "sorrow",
      "cry", "drown"), "rain", ["vignette"]),
    (("snow", "winter", "cold", "ice", "frost", "blizzard"), "snow", []),
    (("fog", "mist", "ghost", "eerie", "haunt", "dream", "vision", "mystery"), "fog", []),
    (("petal", "blossom", "flower", "spring", "cherry"), "petals", []),
    (("leaf", "leaves", "autumn", "forest", "wood"), "leaves", []),
    (("ancient", "history", "centur", "1800", "1900", "memory", "past", "old days",
      "long ago", "vintage", "archive"), "", ["oldfilm"]),
    (("divine", "holy", "heaven", "god ", "goddess", "sacred", "miracle", "ray of light",
      "sunbeam", "glow"), "", ["godrays"]),
    (("dawn", "sunrise", "morning", "hope", "new day"), "", ["sunrise"]),
    (("sunset", "dusk", "evening", "twilight"), "", ["sunset"]),
    (("night", "dark", "shadow", "midnight", "void", "abyss"), "", ["vignette"]),
    (("glitch", "digital", "data", "code", "cyber", "hack", "signal"), "", ["glitch"]),
]

# rotation for body scenes — varied motion that includes true-depth parallax periodically.
_BODY_CYCLE = ["motion-driftright", "parallax", "kenburns", "motion-driftleft",
               "motion-zoomin", "parallax", "motion-driftup", "kenburns"]
_DIRS = ("left", "right", "up", "down")


def _has_direction(hint: str) -> bool:
    h = (hint or "").lower()
    return any(d in h for d in _DIRS)


def _is_scenery(sc: Scene) -> bool:
    """A background/establishing shot (no recurring character) — best for parallax depth."""
    return (sc.image_role or "").lower() == "bg"


# atmosphere -> the literal keywords that justify it (derived from _MOOD, plus its own
# name). An atmosphere only survives if the scene text actually contains one of these —
# this is what stops gratuitous snow/rain/embers landing on scenes that don't call for it.
_ATMO_KEYS: dict[str, set[str]] = {}
for _keys, _atmo, _ in _MOOD:
    if _atmo:
        _ATMO_KEYS.setdefault(_atmo, set()).update(_keys)
for _a in ATMOS:
    _ATMO_KEYS.setdefault(_a, set()).add(_a)


def _atmo_justified(atmo: str, text: str) -> bool:
    """True only if the scene text literally references this atmosphere's content."""
    return any(k in text for k in _ATMO_KEYS.get(atmo, {atmo}))


def _mood(text: str) -> tuple[str, list[str]]:
    for keys, atmo, fx in _MOOD:
        if any(k in text for k in keys):
            return atmo, fx
    return "", []


def decorate(script: Script) -> Script:
    """Validate LLM-chosen effects and fill gaps heuristically. Mutates + returns script."""
    scenes = script.scenes
    n = len(scenes)
    body_i = 0
    for i, sc in enumerate(scenes):
        text = f"{sc.visual_prompt} {sc.narration} {sc.on_screen_text}".lower()

        # 1) validate whatever the model (or a hand author) already set
        sc.animator = sc.animator if sc.animator in ANIMATORS else ""
        # atmosphere survives only if it's valid AND the scene literally calls for it —
        # the model loves to sprinkle embers/snow/rain on scenes that don't need them.
        sc.atmosphere = (sc.atmosphere if sc.atmosphere in ATMOS
                         and _atmo_justified(sc.atmosphere, text) else "")
        sc.fx = [f for f in (sc.fx or []) if f in FX][:2]
        sc.transition = sc.transition if sc.transition in TRANSITIONS else ""

        # 2) fill animator if unset — position first, then scenery, then a varied cycle
        if not sc.animator:
            if i == 0 and sc.on_screen_text.strip():
                sc.animator = "kinetic"                      # hook headline
            elif i >= n - 1:
                sc.animator = "static"                       # let the outro/CTA settle
            elif _is_scenery(sc):
                sc.animator = "parallax"
            else:
                sc.animator = _BODY_CYCLE[body_i % len(_BODY_CYCLE)]
                body_i += 1
        # give parallax a drift direction if none was hinted (else it defaults right)
        if sc.animator == "parallax" and not _has_direction(sc.motion_hint):
            sc.motion_hint = "pan left" if i % 2 else "pan right"

        # 3) atmosphere + fx from content mood (only where the author left them empty)
        atmo, fx = _mood(text)
        if not sc.atmosphere and atmo:
            sc.atmosphere = atmo
        if not sc.fx and fx:
            sc.fx = fx

        # 4) transitions — gentle variety; keep the very first a clean fade-in
        if not sc.transition:
            sc.transition = "fade" if i == 0 else ("dissolve" if i % 4 == 0 else "")

    _apply_taste_caps(scenes)
    _diversify_duplicate_prompts(scenes)
    return script


# distinct framings appended to repeated visual_prompts so identical text doesn't render
# as identical frames (the model often reuses one portrait for every hero scene).
_FRAMINGS = ["wide establishing shot", "extreme close-up", "low-angle dramatic shot",
             "profile view", "seen from behind", "over-the-shoulder framing",
             "high-angle shot", "dramatic three-quarter angle"]


def _diversify_duplicate_prompts(scenes: list[Scene]) -> None:
    """When >1 scene shares an identical visual_prompt, append a distinct framing cue to
    each repeat (the first occurrence is left as authored) so they render as varied shots
    instead of the same image N times."""
    seen: dict[str, int] = {}
    for sc in scenes:
        vp = (sc.visual_prompt or "").strip()
        if not vp:
            continue
        key = vp.lower()
        k = seen.get(key, 0)
        if k > 0:
            sc.visual_prompt = f"{vp}, {_FRAMINGS[(k - 1) % len(_FRAMINGS)]}"
        seen[key] = k + 1


def _apply_taste_caps(scenes: list[Scene]) -> None:
    """Stop effects from blanketing every scene (monotone = the slop look). A `flash` is an
    IMPACT punch → keep at most one. A single atmosphere covering ~all scenes gets thinned to
    alternating scenes so it reads as accent, not wallpaper."""
    n = len(scenes)
    # flash: keep only the first scene that has one
    seen_flash = False
    for sc in scenes:
        flashes = [f for f in sc.fx if f.startswith("flash")]
        if flashes and not seen_flash:
            seen_flash = True
        elif flashes:
            sc.fx = [f for f in sc.fx if not f.startswith("flash")]
    # atmosphere: if one type is on > ~60% of scenes, thin it to every other scene
    if n >= 4:
        from collections import Counter
        counts = Counter(sc.atmosphere for sc in scenes if sc.atmosphere)
        for atmo, c in counts.items():
            if c > max(2, round(n * 0.6)):
                kept = 0
                for i, sc in enumerate(scenes):
                    if sc.atmosphere == atmo:
                        if i % 2:                 # drop it on every other occurrence
                            sc.atmosphere = ""
                        else:
                            kept += 1
