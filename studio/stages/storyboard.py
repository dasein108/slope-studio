"""Stage 1 (story mode) — segment an EXISTING story/audiobook text into scenes.

Unlike `stages/script.py` (idea → invented scenario), this stage takes finished prose
and chunks it into timed, illustratable beats. Narration is the story's own words
(lightly condensed for TTS); `visual_prompt` is only the ACTION + SETTING — character
identity is injected verbatim from character cards at visuals time, so the model here
never rewrites (and never drifts) a character's look.

Each scene is tagged `characters: [...]` from the provided roster; multi-character
scenes are expected and fine. Output is a standard 01_script.json — every later stage
(visuals, narrate, clips, stitch, audio, voice, save) works unchanged.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from studio import artdirect, characters as chars, paths
from studio.models import Scene, Script
from studio.providers import llm

BEAT_S = 18          # target seconds per illustrated beat
MAX_SCENES = 400     # sanity cap for very long books
CHUNK_CHARS = 24000  # per-LLM-call slice of the story: one huge call both times out
                     # and dilutes attention (weak tagging, thin narration); chunked
                     # calls are robust and each beat gets a focused read

SYSTEM = """You are a storyboard artist segmenting finished prose into illustrated beats.

Rules:
- Do NOT invent plot. Narration must be the story's own words, lightly condensed for voiceover.
- Cover the whole text in order; no gaps, no reordering.
- visual_prompt = ONE concrete, filmable moment: the ACTION and SETTING only
  ("pours tea across a rough wooden table at dawn, monastery kitchen"). Never describe a
  known character's face/hair/clothes — identity is injected separately from reference cards.
- PREFER SHOWING PEOPLE over symbols: when a beat narrates something a character does,
  sees, or says, depict THAT CHARACTER in the scene (a figure at a train window, two men
  at a cafe table) — not an abstract metaphor. Use symbolic/scenery beats sparingly,
  for genuinely abstract passages.
- A first-person narrator («я»/"I") IS a known character if the roster marks one as the
  narrator — beats about his own actions depict him, and tag him.
- Stay inside the story's ERA and geography: no objects that don't exist in the story's
  time (check the setting's decade before naming technology).
- characters = which of the KNOWN CHARACTERS (given below) visibly appear in the beat.
  Use their exact names. Empty list for pure scenery/mood beats.
- image_role = "hero" when characters appear, else "bg".
- Keep narration in the story's original language.
- sfx: SPARSE ambient sound only — at most 1 beat in 5 gets a cue, and only where the
  text names a real sound (a train, rain, a bell, a door). One quiet cue per such beat:
  {"prompt": "<the sound>", "at": 0.0, "dur": 3.0, "gain_db": -14}. Most beats: none.
  Never music, never voices, never a sound on a purely visual beat.
Respond ONLY JSON:
{"title": "...", "scenes": [{"id": 1, "start_s": 0, "end_s": 18, "narration": "...",
 "visual_prompt": "...", "characters": ["Name"], "image_role": "hero",
 "sfx": []}, ...]}"""


def _story_chunks(text: str, size: int) -> list[str]:
    """Split into <= ~size-char slices, preferring natural boundaries — recursive
    fallback paragraph → sentence → hard cut (same idea as LangChain's recursive
    splitter, without the dependency: the repo is deliberately framework-free)."""
    def split_by(units: list[str], sep: str) -> list[str]:
        out, cur = [], ""
        for u in units:
            if len(u) > size:                       # unit itself too big → recurse
                if cur:
                    out.append(cur)
                    cur = ""
                if sep == "\n\n":                   # paragraph → sentences
                    out.extend(split_by(re.split(r"(?<=[.!?…])\s+", u), " "))
                else:                               # sentence → hard cut
                    out.extend(u[i:i + size] for i in range(0, len(u), size))
            elif cur and len(cur) + len(sep) + len(u) > size:
                out.append(cur)
                cur = u
            else:
                cur = f"{cur}{sep}{u}" if cur else u
        if cur:
            out.append(cur)
        return out

    return split_by(text.split("\n\n"), "\n\n")


def _chunks(text: str, n: int) -> list[str]:
    """Sentence-aware split into n roughly equal chunks (offline stub path)."""
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    per = max(1, len(sents) // n)
    out = [" ".join(sents[i:i + per]) for i in range(0, len(sents), per)]
    return out[:n] if len(out) > n else out


def _stub(story: str, duration: int, roster: dict) -> tuple[str, list[dict]]:
    """Deterministic keyless segmentation: sentence chunks + substring character tags."""
    n = min(MAX_SCENES, max(1, round(duration / BEAT_S)))
    beats = []
    seg = duration / max(1, len(_chunks(story, n)))
    for i, chunk in enumerate(_chunks(story, n), 1):
        who = chars.match_names(chunk, roster)
        beats.append({"id": i, "start_s": round((i - 1) * seg, 2), "end_s": round(i * seg, 2),
                      "narration": chunk, "visual_prompt": chunk[:180],
                      "characters": who, "image_role": "hero" if who else "bg"})
    return story.strip().split("\n", 1)[0][:80], beats


def _discover_characters(story: str, roster: dict, provider: str) -> list[str]:
    """Names of RECURRING characters in the story that have no card yet. Best-effort:
    any failure returns [] and the storyboard proceeds with the existing roster."""
    try:
        known = list(roster)
        data = json.loads(llm.complete(
            provider,
            "You list the recurring characters of a story (people/beings that appear "
            "in more than one moment and would be drawn in illustrations). Only NAMED "
            "individual persons: skip groups ('professors'), professions ('a musician'), "
            "one-scene extras, and unexpanded initials/single letters.",
            f"Already known (skip these): {known or 'none'}\n\nSTORY:\n{story}\n\n"
            'Respond ONLY JSON: {"characters": ["<name>", ...]} — short canonical '
            "names, lowercase, max 4, most important first; [] if none qualify."))
        out = [n.strip().lower() for n in data.get("characters", []) if n.strip()]
        # skip anything that is a known card under ANY name/alias (e.g. the Cyrillic
        # spelling of an already-carded character) — else we'd build a duplicate card
        # and split one person's identity across two descriptors
        known_needles = {c.name.casefold() for c in roster.values()}
        for c in roster.values():
            known_needles.update(a.casefold() for a in c.aliases)
        fresh = [n for n in out if len(n) > 2
                 and not any(n in k or k in n for k in known_needles)]
        # deterministic recurrence check: a drawable character's NAME appears
        # capitalized repeatedly; this kills pronouns the LLM sneaks in ("никто"
        # capitalizes only at sentence starts) and one-mention historical figures
        fresh = [n for n in fresh if story.count(n.capitalize()) >= 3]
        return fresh[:4]
    except Exception:
        return []


def run(run_dir: Path, story_text: str, duration: int, aspect: str, style: str,
        provider: str, voice_name: str = "narrator", tone: str = "neutral",
        roster_root: Path | None = None, discover: bool = True) -> tuple[Script, float]:
    """story text -> 01_script.json with character-tagged scenes.

    `discover` (LLM mode only): characters found in the story that have NO card get a
    text-derived card first — the whole story is analyzed once for their physical
    characteristics (inventing committed specifics where the prose is silent), so
    their look is locked BEFORE the first frame renders and stays constant after."""
    t0 = time.time()
    roster = chars.roster(roster_root) if roster_root else {}
    if discover and provider != "stub" and roster_root:
        for name in _discover_characters(story_text, roster, provider):
            if name not in roster:
                roster[name] = chars.build_card_from_text(roster_root, name, story_text,
                                                          provider=provider)
    known = ", ".join(f"{c.name} (aliases: {', '.join(c.aliases) or '-'})"
                      for c in roster.values()) or "none"

    if provider == "stub":
        title, beats = _stub(story_text, duration, roster)
    else:
        parts = _story_chunks(story_text, CHUNK_CHARS)
        n_total = min(MAX_SCENES, max(1, round(duration / BEAT_S)))
        title, beats = "", []
        for pi, part in enumerate(parts):
            share = len(part) / max(1, len(story_text))
            n = max(2, round(n_total * share))
            user = (f"KNOWN CHARACTERS: {known}\n"
                    f"This is PART {pi + 1}/{len(parts)} of the text (cover ONLY this part).\n"
                    f"TARGET: ~{n} beats for this part, ~{BEAT_S}s per beat.\n"
                    f"STYLE (global, do not restate per scene): {style or 'painterly, cinematic'}\n\n"
                    f"STORY:\n{part}")
            data = json.loads(llm.complete(provider, SYSTEM, user))
            title = title or data.get("title", "story")
            beats.extend(data["scenes"])
        # renumber + retime sequentially (narrate later refits exact timings to TTS)
        seg = duration / max(1, len(beats))
        for i, b in enumerate(beats, 1):
            b["id"], b["start_s"], b["end_s"] = i, round((i - 1) * seg, 2), round(i * seg, 2)

    # canonicalize + backstop character tags. LLM tags are unreliable (wrong-language
    # spellings, missed mentions), so: map any name/alias the LLM used back to the
    # canonical card name, then UNION with deterministic text matching on the beat's
    # own words (card aliases can hold language stems, e.g. "успенск", to survive
    # inflected forms). The union only ADDS known characters — never invents.
    alias_to_name = {}
    for c in roster.values():
        alias_to_name[c.name.casefold()] = c.name
        for a in c.aliases:
            alias_to_name[a.casefold()] = c.name
    scenes = []
    for b in beats:
        tags = []
        for raw in b.get("characters", []):
            hit = alias_to_name.get(str(raw).casefold())
            if not hit:  # try substring against aliases (inflections, initials)
                hit = next((n for a, n in alias_to_name.items()
                            if len(a) > 3 and a in str(raw).casefold()), None)
            if hit and hit not in tags:
                tags.append(hit)
        for hit in chars.match_names(f"{b.get('narration','')} {b.get('visual_prompt','')}",
                                     roster):
            if hit not in tags:
                tags.append(hit)
        b["characters"] = tags
        if tags:
            b["image_role"] = "hero"
        scenes.append(Scene.model_validate(b))

    script = Script(topic=title, duration_s=duration, aspect=aspect, voice=True,
                    voice_name=voice_name, tone=tone, style=style, scenes=scenes,
                    title=title)
    artdirect.decorate(script)
    paths.script_json(run_dir).write_text(script.model_dump_json(indent=2))
    return script, round(time.time() - t0, 2)
