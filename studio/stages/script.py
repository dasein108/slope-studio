"""Stage 1 — idea -> timed scenario JSON (+ optional narration)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from studio import artdirect, paths
from studio.models import Scene, Script
from studio.providers import llm

SYSTEM = """You are a short-form video scriptwriter. Output ONLY valid JSON matching
the requested schema. Scenes must tile [0, duration_s] with no gaps or overlaps and
the last scene must end exactly at duration_s. Each scene is 4-8 seconds. Reuse the
SAME character description verbatim inside every visual_prompt for consistency.
Narration must fit the scene length at ~2.7 words/second.

IMAGE ROLE (controls cost — a cheap model is used for non-character scenes):
- Set scene "image_role":"hero" when the scene FEATURES the main character / a person /
  the recurring subject (needs the quality model + consistency).
- Set "image_role":"bg" for backgrounds, establishing shots, objects, textures, maps,
  abstract or overlay visuals with NO recurring character (cheap model is fine).
- If unsure, omit it. Mark only the genuinely character-driven scenes as "hero" so most
  scenes fall back to the cheaper model.

AUDIO DESIGN (commercial-safe; the pipeline generates these):
- "music": ONE short instrumental-mood phrase for the whole video (genre + energy +
  instruments), e.g. "tense cinematic battle drums, instrumental". Use "" for none.
- Per-scene "sfx": 0-2 short one-shot effects that match the on-screen action ONLY when
  there is a clear diegetic moment (a sword clash, a whoosh, a door slam, a breath).
  Each: {"prompt": vivid sound description, "at": seconds INTO the scene to trigger,
  "dur": 0.5-3 length, "gain_db": loudness vs voice (-6 quiet .. 0 prominent)}.
  Most scenes need NO sfx — leave the list empty rather than inventing noise.

ART DIRECTION (free motion + looks — pick per scene from these menus; a heuristic pass
fills anything you omit, so only set what clearly fits, and VARY it across scenes):
- "animator" (how the still moves, all free):
  kenburns (gentle pan/zoom, safe default) · motion-driftleft/driftright/driftup/driftdown
  (lateral drift) · motion-zoomin/zoomout · parallax (BEST for scenery/landscapes with a
  clear subject — foreground stays, background drifts for real depth) · kinetic (slides a
  big on-screen HEADLINE — use ONLY on the opening hook or a scene built around short text)
  · slice (a split-and-slide reveal at a hard cut) · static (a held shot — good for an
  outro/CTA). Spread these out; don't repeat one animator every scene.
- "atmosphere" (a weather/particle overlay): rain · snow · embers · blood · petals ·
  leaves · wind · fog. **DEFAULT IS "" (none). Set it ONLY when the scene literally
  depicts that element** — snow only if it's an outdoor winter/snow scene, embers only
  for actual fire, rain only in real rain, petals/leaves only outdoors among blossom/trees,
  fog only for real mist. NEVER add particles to an indoor, portrait, studio, diagram, or
  neutral scene, and NEVER for "mood" or decoration. Falling snow in an office is a bug.
  The vast majority of scenes MUST have atmosphere "".
- "fx" (0-2 colour/look post-passes, used sparingly and consistently): grain · vignette ·
  oldfilm (vintage film) · godrays (warm light shafts — only with a real light source) ·
  sunrise · sunset · chroma · glitch · flash-white/yellow/red/black (a brief impact punch
  for an action/violence beat). Pick ONE coherent look for the whole video and apply it
  consistently; don't sprinkle different fx per scene. Default to none unless it serves the
  look. Never use chroma/glitch on a calm/period/realistic piece.
- "transition" (into this scene): cut · fade · dissolve · wipeleft · slideup · circleopen.
  Omit to let the pipeline choose."""

USER_TMPL = """Idea: {idea}
Total duration: {duration} seconds. Aspect: {aspect}. Voiceover: {voice}.
Style/tone: {style}

Return JSON:
{{
  "topic": "...",
  "character": "one reusable character/subject description string",
  "music": "instrumental mood phrase for the whole video, or \\"\\" for none",
  "title": "catchy title with #Shorts",
  "description": "youtube description",
  "hashtags": ["#shorts", "..."],
  "scenes": [
    {{"id":1,"start_s":0,"end_s":6,"visual_prompt":"<character desc> ... , 9:16",
      "narration":"...","on_screen_text":"SHORT HOOK","motion_hint":"slow push-in",
      "image_role":"hero","animator":"kinetic","atmosphere":"","fx":["vignette"],
      "transition":"fade",
      "sfx":[{{"prompt":"metallic sword unsheathing, sharp","at":0.5,"dur":1.2,"gain_db":-3}}]}}
  ]
}}"""


def run(run_dir: Path, idea: str, duration: int, aspect: str, voice: bool,
        style: str, provider: str) -> tuple[Script, float, float]:
    t0 = time.time()
    if provider == "stub":
        script = _stub(idea, duration, aspect, voice, style)
    else:
        raw = llm.complete(provider, SYSTEM, USER_TMPL.format(
            idea=idea, duration=duration, aspect=aspect,
            voice="yes" if voice else "no", style=style or "engaging, fast-paced"))
        data = json.loads(raw)
        data.setdefault("duration_s", duration)
        data.setdefault("aspect", aspect)
        data["voice"] = voice
        script = Script.model_validate(data)

    artdirect.decorate(script)   # validate LLM effect picks + fill gaps (hybrid art direction)
    paths.script_json(run_dir).write_text(script.model_dump_json(indent=2))
    return script, round(time.time() - t0, 2), 0.0  # cost ~0 for script


def _stub(idea: str, duration: int, aspect: str, voice: bool, style: str) -> Script:
    """Deterministic offline split so the pipeline runs with zero API keys."""
    n = max(1, round(duration / 6))
    seg = duration / n
    char = f"a clean flat-illustration scene about: {idea}"
    scenes = []
    for i in range(n):
        scenes.append(Scene(
            id=i + 1, start_s=round(i * seg, 3), end_s=round((i + 1) * seg, 3),
            visual_prompt=f"{char}, part {i + 1} of {n}, vibrant, {aspect}",
            narration=f"{idea} — point {i + 1}." if voice else "",
            on_screen_text=f"{i + 1}", motion_hint="slow push-in"))
    scenes[-1].end_s = float(duration)
    return Script(topic=idea, duration_s=duration, aspect=aspect, voice=voice,
                  style=style, character=char, scenes=scenes,
                  title=f"{idea} #Shorts", description=idea,
                  hashtags=["#shorts"])
