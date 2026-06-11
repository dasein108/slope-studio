---
name: sound-designer
description: The audio counterpart to art-direction for the Slope Studio pipeline — design and PRODUCE all the sound a video needs. Use when a video feels silent/flat, when adding a music bed + sound effects, when the clip maker (visuals/clips) has produced scenes that need atmosphere, or whenever asked to do sound design, score, add sfx/music, or make a Short "feel produced". Prefers FREE tools (ffmpeg synth music + the local CC0 sfx library); falls back to paid (fal) only when free can't cover and budget allows.
---

# sound-designer — produce all the sound the clip maker requested

A silent Short feels dead. Visual motion is only half of "not slop"; **sound builds the rest of
the scene in the viewer's head** — a gust of wind, a low cello, a distant bell, and the still
becomes a place. You are the audio half of art-direction: the clip maker (script + visuals)
hands you scenes; you decide and produce the **music bed + per-scene sfx** for them, as cheaply
as possible.

## The flow: request → produce

1. **Read the run.** `runs/<id>/01_script.json` — each `Scene` has `narration`, `visual_prompt`,
   mood/`tone`, and possibly existing `sfx` cues; the top-level `Script.music` is the bed mood.
   Eyeball the visuals if useful (`runs/<id>/02_visuals/*.png`).
2. **Design per scene + the bed.** Decide:
   - `Script.music` — ONE coherent mood string for the whole video (not per-scene).
   - per-scene `Scene.sfx` — a list of `{prompt, at, dur, gain_db}` cues, only where the scene
     literally depicts a sound source.
3. **Write it into `01_script.json`** (edit the `music` field + each scene's `sfx` list).
4. **Produce** by running the audio stage, then re-muxing voice:
   ```bash
   studio audio <id> --music-provider synth --sfx-provider local   # FREE: drone bed + CC0/synth sfx
   studio voice <id>                                                # ducks music under narration
   studio save  <id>
   ```

## Provider ladder — free first

| layer | free (default) | paid fallback (only if needed + budget) |
|-------|----------------|------------------------------------------|
| **music bed** | `--music-provider synth` — ffmpeg drone, $0, generated from the `music` mood (cosmic/dread → deep minor; mournful → soft mid; folk/ancient → brighter major) | `fal-stable-audio` ($0.20 flat) for a real melodic track |
| **sfx** | `--sfx-provider local` — keyword-matches the cue against `assets/audio/sfx/` (synth starter + any CC0 you fetched) | `fal-elevenlabs-sfx` (~$0.002/s) for a specific real sound |

- **Stage the library once:** `python scripts/fetch_sfx.py` (synth starter always; richer
  **Freesound CC0** recordings if `FREESOUND_API_KEY` is set). Add your own CC0 files to
  `assets/audio/sfx/` with **keyword-rich filenames** — `local` matches a cue by filename overlap.
- The synth bed and synth sfx are **$0 and on-brand** for the channel's cosmic/mystical tone —
  prefer them; reach for fal only when a scene truly needs a specific real sound.
- **Cheap-tier / budget videos: FREE providers ONLY** — `--music-provider synth` +
  `--sfx-provider local`, never paid fal, no matter how good a fal sound would be. (`studio run
  --tier cheap` already pins this; honor it when driving by hand and on a tight `--max-cost`.)

## Taste rules (what separates produced from slop)

- **Sound = atmosphere, not decoration.** Add a cue only where the scene depicts its source
  (wind on a vista, a sword on a clash, a hum in space). Empty/abstract scenes → music only.
- **Don't over-cue.** ≤1–2 sfx per scene; most beats need none. A wall of sfx reads as noise.
  Never add a cue that points to nothing on screen, and never sprinkle sfx as generic "energy."
  **A wrong or pointless sound is worse than silence** — restraint reads as produced.
- **Voice always wins.** The bed is ducked to **−24 dB** under narration (sidechain, automatic in
  `studio voice`). Set sfx `gain_db` low (−10 to −3) so they sit *under* the voice, never over it.
- **One bed per video.** A single coherent `music` mood; don't switch genres mid-Short.
- **Match the beat:** `at` = seconds into the scene the sound should hit (e.g. a sword clash at
  the cut), `dur` ≈ how long, both small.

## Authoring `sfx` cues (schema)

Each scene's `sfx` is a list of `SoundCue`:
```jsonc
"sfx": [
  { "prompt": "deep impact boom on the cut", "at": 0.0, "dur": 1.0, "gain_db": -4 },
  { "prompt": "low cosmic hum under the reveal", "at": 0.5, "dur": 4.0, "gain_db": -12 }
]
```
With `--sfx-provider local`, `prompt` keywords are matched against the library filenames
(synth starter covers: whoosh · rumble/tension · sparkle/shimmer · impact/boom · cosmic-hum).

## Quick recipes

- **Cosmic/physics piece:** `music: "deep cosmic drone, awe and dread, sparse"` →
  `synth` gives a deep minor drone; add a `cosmic-hum` sfx under the reveal, an `impact` on a
  hard cut. All $0.
- **Tragic/historical:** `music: "slow mournful strings, tragic"` → softer mid drone; sparse
  sfx (a distant bell, wind) from the CC0 lib.
- **Make an existing run feel produced (no re-render):** edit `music` + add a couple `sfx`, then
  `studio audio <id> --music-provider synth --sfx-provider local && studio voice <id> && studio save <id>`.

This is the **film-maker**'s sound half — see `.claude/skills/film-maker/` for the visual side
(`art-direction`), and `studio/providers/audio.py` for the renderer.
