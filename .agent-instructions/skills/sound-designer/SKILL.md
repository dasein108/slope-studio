---
name: sound-designer
description: The audio counterpart to art-direction for the Slope Studio pipeline — design and PRODUCE all the sound a video needs. Use when a video feels silent/flat, when adding music + sound effects, when the clip maker (visuals/clips) has produced scenes that need atmosphere, or whenever asked to do sound design, score, add sfx/music, or make a Short "feel produced". Use license-safe audio: paid/generated providers we control, synthetic ffmpeg audio, CC0/public-domain Freesound, or local assets with explicit reusable rights. Never use copyrighted music, CC-BY/attribution-required tracks, CC-BY-NC/non-commercial audio, platform-restricted music, or unclear community audio. Do not use the same drone bed for every video; use music as arrangement and accents around story moments.
---

# sound-designer — produce all the sound the clip maker requested

A silent Short feels dead. Visual motion is only half of "not slop"; **sound builds the rest of
the scene in the viewer's head** — a gust of wind, a low cello, a distant bell, and the still
becomes a place. You are the audio half of art-direction: the clip maker (script + visuals)
hands you scenes; you decide and produce the **music arrangement + per-scene sfx** for them, as cheaply
as possible.

## The flow: request → produce

1. **Read the run.** `runs/<id>/01_script.json` — each `Scene` has `narration`, `visual_prompt`,
   mood/`tone`, and possibly existing `sfx` cues; the top-level `Script.music` is the bed/arrangement mood.
   Eyeball the visuals if useful (`runs/<id>/02_visuals/*.png`).
2. **Inspect the available library before choosing.**
   ```bash
   find assets/audio/music assets/audio/sfx -maxdepth 1 -type f 2>/dev/null | sort
   sed -n '1,220p' assets/audio/CREDITS.md 2>/dev/null
   ```
   If fal is available and budget allows, prefer paid/generated fal audio for quality. If using
   community/library audio, only use local files with explicit reusable rights or Freesound
   CC0/public-domain beds (`scripts/fetch_music.py`). Fall back to `synth` when nothing fits.
3. **Design per scene + the music.** Decide:
   - `Script.music` — ONE coherent mood/arrangement phrase for the whole video (not per-scene).
     Include movement when useful: "fade in slowly", "swell at the reveal", "drop to near silence
     after the quote", "soft outro". The renderer currently creates one bed, so use this phrase to
     shape the bed and use SFX cues for precise accents.
   - per-scene `Scene.sfx` — a list of `{prompt, at, dur, gain_db}` cues, only where the scene
     literally depicts a sound source or where a small musical accent supports a real story beat.
     Accent cues should usually be **0.2-2.0s**; **5.0s is the hard maximum** unless the scene
     visibly needs ambience (wind/rain/crowd). Long bells, drones, rumbles, and ambiences are not
     accents.
4. **Write it into `01_script.json`** (edit the `music` field + each scene's `sfx` list).
5. **Produce** by running the audio stage, then re-muxing voice:
   ```bash
   studio audio <id> --music-provider local --sfx-provider local   # best if a suitable local/Freesound bed exists
   # fallback: studio audio <id> --music-provider synth --sfx-provider local
   studio voice <id>                                                # ducks music under narration
   studio save  <id>
   ```

## Provider ladder — license-safe first

| layer | preferred quality source | fallback |
|-------|----------------|------------------------------------------|
| **music bed** | `--music-provider fal-stable-audio` when budget allows; `local` for vetted reusable tracks; `freesound` for CC0/public-domain API search | `synth` for ffmpeg-generated beds, then `silence` |
| **sfx** | `--sfx-provider fal-elevenlabs-sfx` when budget allows; `local` for vetted reusable cues; `freesound` for CC0/public-domain API search | `local` synth starter or `silence` |

- **Stage the libraries once:** `python scripts/fetch_sfx.py` for SFX and
  `python scripts/fetch_music.py --query "<mood>"` for CC0/public-domain music. Add your own
  CC0/public-domain/open files to `assets/audio/{sfx,music}/` with keyword-rich filenames —
  `local` matches by filename overlap. Do not add copyrighted, CC-BY/attribution-required,
  CC-BY-NC/non-commercial, platform-restricted, or unclear-license audio.
- **Priority:** suitable quality paid/generated fal or vetted local/Freesound music first;
  `synth` second as a reliable fallback. The synth provider is **$0**, but it is not a universal
  default. Use silence when a line needs air.
- **Cheap-tier / budget videos:** use `--music-provider local|freesound|synth`
  + `--sfx-provider local|freesound` unless budget explicitly allows fal audio.

## Selection checklist

Before rendering, explicitly check:

- **Story fit:** Does the bed match the actual subject, period, emotion, and pace? Tanpura/lyre
  can fit philosophy, mysticism, ancient material, or meditative science; it is wrong for comic,
  urgent, modern, or hard-news pieces unless used ironically on purpose.
- **Moment fit:** Identify the 1-3 moments that deserve accents: hook, reveal, quote, reversal,
  death, joke, awe beat, or final payoff. If there is no real beat, do not add an accent.
- **Audio quality:** Reject beds with harsh starts, clipped peaks, distracting hiss, sudden edits,
  spoken words, recognizable copyrighted music, or loops that jump.
- **Edges:** The mixer fades music in/out, but still choose sources with natural starts/tails.
  If a cue itself has sharp edges, use a softer cue or lower gain.
- **License:** use paid/generated providers we control, synthetic audio, CC0/public-domain, or
  local assets with explicit reusable rights. Reject copyrighted music, CC-BY/attribution-required,
  CC-BY-NC/non-commercial, platform-restricted, and unclear-license music/SFX.
- **Voice clarity:** After `studio voice`, listen to the first 10 seconds, one middle reveal, and
  the ending. If words fight the music, rerun with a quieter bed or fewer accents.

## Taste rules (what separates produced from slop)

- **Sound = atmosphere, not decoration.** Add a cue only where the scene depicts its source
  (wind on a vista, a sword on a clash, a hum in space). Empty/abstract scenes → music only.
- **Music is arrangement, not wallpaper.** Do not place the same continuous drone under every
  video. Decide where music should enter, thin out, swell, or disappear. Name those movements in
  `Script.music` even if the current renderer approximates them with one bed.
- **Use accents for story turns.** At a reveal, quote, death, realization, joke, or emotional
  payoff, add one small cue: `low swell into the reveal`, `soft bell after the quote`,
  `short dark hit on the cut`, `brief shimmer under the answer`. Put these in `Scene.sfx` with
  a precise `at`, short `dur`, and low `gain_db` so they support the voice rather than announce
  themselves.
- **Accents are short.** For non-diegetic punctuation, use 0.2-2.0s. Never let a bell, chime,
  rumble, drone, or ambience ring for a whole scene unless it is intentionally the scene's
  environment. If a cue needs more than 5s, it is probably music/ambience, not `Scene.sfx`.
- **Fade in/out deliberately.** Prefer beds that fade in at the opening and fade out at the end.
  The mixer fades music at the composition edges, but still choose tracks with smooth starts,
  stable middles, and clean tails. For mid-video breath, use a quieter/shorter accent instead of
  forcing continuous music through every scene. Reject tracks with sharp attacks, sudden cuts,
  noisy endings, or obvious loops that break the video composition.
- **Don't over-cue.** ≤1–2 sfx per scene; most beats need none. A wall of sfx reads as noise.
  Never add a cue that points to nothing on screen, and never sprinkle sfx as generic "energy."
  **A wrong or pointless sound is worse than silence** — restraint reads as produced.
- **Do not repeat an SFX family inside 30 seconds.** One impact, ratchet/click, shimmer,
  whoosh, or rumble is enough for that window. Choose silence or a genuinely different
  diegetic sound for the next beat. The audio stage enforces this cooldown as a backstop.
- **Voice always wins.** The bed is ducked to **−22.5 dB** under narration (sidechain, automatic in
  `studio voice`). Set sfx `gain_db` low (−10 to −3) so they sit *under* the voice, never over it.
- **One bed per video, not one sound for all videos.** A single coherent `music` mood per video;
  do not switch genres mid-Short, and do not reuse a generic drone when the story asks for warmth,
  irony, tragedy, awe, or silence.
- **Match the beat:** `at` = seconds into the scene the sound should hit (e.g. a sword clash at
  the cut), `dur` ≈ how long, both small. Keep accent `dur` ≤2s by default and ≤5s always.

## Authoring `sfx` cues (schema)

Each scene's `sfx` is a list of `SoundCue`:
```jsonc
"sfx": [
  { "prompt": "deep impact boom on the cut", "at": 0.0, "dur": 0.7, "gain_db": -8 },
  { "prompt": "brief digital shimmer under the reveal", "at": 0.5, "dur": 1.2, "gain_db": -12 }
]
```
With `--sfx-provider local`, `prompt` keywords are matched against the library filenames
(synth starter covers: whoosh · rumble/tension · sparkle/shimmer · impact/boom · cosmic-hum).
Use file-keyword words deliberately; unknown prompts should not be allowed to pick arbitrary long
library files.

## Quick recipes

- **Cosmic/physics piece:** `music: "dark cosmic bed, fade in slowly, swell under the paradox,
  sparse outro"` → add one `cosmic-hum` or `low swell` cue under the reveal, an `impact` only on
  a real hard cut. All $0 with synth/local.
- **Tragic/historical:** `music: "slow mournful minor bed, thin under narration, fade out after
  the final line"` → sparse sfx (distant bell, wind, low hit) only at pictured or emotional beats.
- **Philosophy/classical:** first try a suitable Freesound/local bed such as tanpura, lyre,
  oud, or soft ancient ambience; if none fits, use
  `music: "gentle ancient plucked pulse, warm and wry, soft fade-in, leave space after the quote"`.
  Use one bell/pluck accent after the key quote; do not use a cosmic drone.
- **No-music choice:** if the narration is intimate or the quote needs weight, set a very sparse
  `music` mood or use `silence` and rely on one accent cue. Silence can be the produced choice.
- **Make an existing run feel produced (no re-render):** edit `music` + add a couple `sfx`, then
  `studio audio <id> --music-provider local --sfx-provider local && studio voice <id> && studio save <id>`.
  If no suitable local/Freesound bed exists, rerun the audio stage with `--music-provider synth`.

This is the **film-maker**'s sound half — see `.agent-instructions/skills/film-maker/` for the visual side
(`art-direction`), and `studio/providers/audio.py` for the renderer.
