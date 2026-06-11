# Sound layer + sound-designer role — design

**Date:** 2026-06-10 · **Status:** implemented, then evolved

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
- `ffmpeg.synth_drone`, `ffmpeg.synth_plucked_bed`, and `ffmpeg.synth_major_pad` generate
  simple $0 beds with built-in fade-in/fade-out.
- `audio.generate_music("synth", prompt, seconds, dst)`: map mood words to distinct recipes
  (cosmic/dread/dark → dark drone; mournful → soft minor bed; ancient/folk/lyre → plucked pulse;
  bright/hopeful → major pad). `expected_music_cost("synth") == 0`. Selectable
  `--music-provider synth`.
- Current taste rule: `synth` is a tool, not a blanket default. Do not put the same continuous
  drone under every video; choose a bed per story, use silence/breathing room where stronger, and
  use per-scene SFX cues as musical accents for reveals, turns, quotes, and emotional payoff.
- Current licensing rule: audio must be paid/generated provider output we control, synthetic,
  CC0/public-domain, or vetted local assets with explicit reusable rights. No CC-BY/
  attribution-required tracks, CC-BY-NC/non-commercial audio, copyrighted music,
  platform-restricted music/SFX, or unclear community audio.

### 2. CC0 SFX library (`assets/audio/sfx/`, gitignored → fetched)
- `scripts/fetch_sfx.py`: pull curated **Kenney CC0** (impact/whoosh/UI/sci-fi-space) + a few
  **freesound CC0** ambiences (wind, fire, cosmic hum), named descriptively so
  `audio._local_pick` keyword-matches a scene's `sfx` cue. `assets/audio/CREDITS.md` records CC0
  provenance. Enables `--sfx-provider local`.

### 3. `sound-designer` skill (`.claude/skills/sound-designer/`)
- The audio counterpart to the art-director. Input: a run's scenes. Output: per-scene `sfx`
  (what / `at` / `dur` / `gain_db`) + `Script.music` mood written into `01_script.json`, then it
  runs the `audio` stage. Uses license-safe tools only (fal generated audio when budget allows,
  synth/local/freesound music, local/freesound CC0 sfx).
  Taste rules: music = arrangement, not
  wallpaper; don't over-cue; voice-forward ducking; match the beat; add accents at story turns.
  Frames the flow as "the clip maker requests, the sound-designer produces."

### 4. Docs/instructions
- CLAUDE.md: `synth` in the provider map; `sound-designer` skill; `assets/audio/` lib; **Sound
  designer = LLM/agent role**; a sound gotcha. film-maker-guides.md: sound-design section +
  skill pointer. A `docs/` sound reference. scenario-schema clarifies `sfx`/`music` if needed.

### 5. Bonus (minimal)
- A thin `artdirect.py` heuristic to set a default `music` mood headless so `studio run` gets a
  baseline bed (real taste lives in the skill).

## Scope guard (YAGNI)
No new pipeline stage. One music bed per video (not per-scene); precise moment accents are handled
as `Scene.sfx` cues until true per-scene music arrangement exists. Avoid copyrighted, attribution-
required, non-commercial, platform-restricted, or unclear-license audio layers.
SFX library is fetched, not committed.

## Build order
tools (1 → 2) → skill (3) → docs (4) → bonus (5).
