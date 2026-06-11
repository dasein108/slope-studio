# Sound layer + sound-designer role — design

**Date:** 2026-06-10 · **Status:** approved (brainstorming) → implementing

## Problem
Videos ship with empty/silent music (the `local` music pack is empty → silence) and ad-hoc
sfx. There's no dedicated taste layer for sound — the script-LLM jots per-scene `sfx` cues +
a `Script.music` mood and the `audio` stage renders them. We want: (a) a free music bed that
always works, (b) a reusable free SFX library, (c) a "sound-designer" role that produces all
the sound a clip needs.

## Decision
**A `sound-designer` skill (agent-driven) + two free tools it uses.** Mirrors the
"thinking = agent, CLI = I/O" pattern (like marketing-guru / the art-director). No new pipeline
stage — the existing `audio` stage renders; the skill authors the plan.

## Components

### 1. `synth` music provider (free, ffmpeg)
- `ffmpeg.synth_drone(dst, seconds, root_hz=55, brightness=0.5, minor=True)`: detuned
  oscillators (root + fifth + octave) + slow tremolo LFO + lowpass (brightness) + faint
  filtered noise texture + `aecho` (space) + long `afade` in/out. Pure ffmpeg → $0, generative.
- `audio.generate_music("synth", prompt, seconds, dst)`: map mood words → `(root_hz, brightness,
  minor)` (cosmic/dread/dark → ~55 Hz, dark, minor; mournful → mid, soft; wry/light → brighter,
  major). `expected_music_cost("synth") == 0`. Selectable `--music-provider synth`.

### 2. CC0 SFX library (`assets/audio/sfx/`, gitignored → fetched)
- `scripts/fetch_sfx.py`: pull curated **Kenney CC0** (impact/whoosh/UI/sci-fi-space) + a few
  **freesound CC0** ambiences (wind, fire, cosmic hum), named descriptively so
  `audio._local_pick` keyword-matches a scene's `sfx` cue. `assets/audio/CREDITS.md` records CC0
  provenance. Enables `--sfx-provider local`.

### 3. `sound-designer` skill (`.claude/skills/sound-designer/`)
- The audio counterpart to the art-director. Input: a run's scenes. Output: per-scene `sfx`
  (what / `at` / `dur` / `gain_db`) + `Script.music` mood written into `01_script.json`, then it
  runs the `audio` stage. **Prefers free tools** (synth music, local CC0 sfx); falls back to fal
  only for what they can't cover. Taste rules: sound = atmosphere, don't over-cue, voice-forward
  ducking, match the beat. Frames the flow as "the clip maker requests, the sound-designer
  produces."

### 4. Docs/instructions
- CLAUDE.md: `synth` in the provider map; `sound-designer` skill; `assets/audio/` lib; **Sound
  designer = LLM/agent role**; a sound gotcha. film-maker-guides.md: sound-design section +
  skill pointer. A `docs/` sound reference. scenario-schema clarifies `sfx`/`music` if needed.

### 5. Bonus (minimal)
- A thin `artdirect.py` heuristic to set a default `music` mood headless so `studio run` gets a
  baseline bed (real taste lives in the skill).

## Scope guard (YAGNI)
No new pipeline stage. One music bed per video (not per-scene). No paid layers by default.
SFX library is fetched, not committed.

## Build order
tools (1 → 2) → skill (3) → docs (4) → bonus (5).
