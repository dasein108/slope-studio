# Recipe — Quality Poetry Video

How to produce a **poetry / spoken-verse Short** that actually feels like poetry: unhurried
delivery, breathing room between lines, imagery that drifts rather than cuts, and sound that
sits *under* the words. This is a tuned preset on top of the standard 7-stage pipeline — every
knob below already exists; this page is the opinionated combination.

> Poetry is the hardest format for an automated studio because pacing **is** the art. The
> defaults (fast cuts, 2.6 words/s, busy motion) fight the verse. Slow everything down.

---

## TL;DR preset

| Knob | Poetry value | Why |
|------|--------------|-----|
| Voice provider | **`openai-tts`** (`gpt-4o-mini-tts`) | Real instruction-driven prosody; edge only fakes tone with rate/pitch. |
| `voice_name` | `narrator` (→ onyx) or `woman` (→ nova) | Grave or warm; both read verse well. |
| `tone` | `mystical` or `sad` | Slow, hushed, deliberate. |
| `animator` | `parallax` (scenery) · `static` (portraits/still beats) · `kinetic` (a single line of text) | Calm, drifting motion. **Never** `slice`, `glitch`, fast `motion-*`. |
| `atmosphere` | `fog` · `petals` · `snow` · `embers` (sparingly) | One mood layer, thin. |
| `fx` | `grain` + `vignette` (and maybe `godrays`/`oldfilm`) | Filmic, soft. Avoid `flash`, `chroma`, `glitch`. |
| `transition` | `dissolve` / `fade` / `fadeblack`, `transition_dur` **0.8–1.2** | Long, soft cross-fades — no hard cuts. |
| `music` | one instrumental mood phrase, ducked | Bed under the voice, never competes. |
| Captions | **off** (default) | A wall of text covers the imagery; let the voice carry. Ship `captions.srt` as a sidecar. |
| Pacing | ~**1.6–2.0 words/sec** + line-end pauses | Slower than the 2.6 w/s prose default. |

---

## 1. Pacing is the whole game

The pipeline is **narration-driven**: `narrate` measures each scene's TTS length and sets the
clip to match (`timing.json`), so **slower speech automatically makes longer, calmer scenes** —
you don't fight the timer, you slow the voice and the visuals follow.

Two levers:

1. **Slow tone.** `mystical` / `sad` already lower the rate. With `openai-tts` you get real
   slowing via instructions (see §2).
2. **Pauses inside `narration`.** Write the verse with explicit beats so the TTS breathes:
   - End lines with `.` / `…` / `—` — TTS pauses on terminal punctuation.
   - Put each line (or couplet) on its own visual scene so the cross-fade *is* the line break.
   - A bare `…` line, or a short scene with empty/near-empty narration, becomes a held silent
     beat (the clip holds its last frame — see "silent interludes" in the long-form playbook).

Budget roughly **one scene per line or couplet**, 5–10s each. `duration_s` only sets the scene
*count* (≈duration/6); real length follows narration, so err toward more, shorter scenes for
finer control over imagery and breath.

> Word-rate math: the schema assumes ~2.6 w/s. For poetry aim **~1.6–2.0 w/s**, i.e. a 10s
> scene = ~16–20 words, not 26. Keep lines short.

---

## 2. Voice — `openai-tts`, custom instructions

`edge` (free) only approximates tone with rate+pitch. For real verse delivery use
**`openai-tts`** and, ideally, add a poetry-specific instruction.

Quick path (existing tones):

```bash
studio voice <id> --voice-provider openai-tts   # uses Script voice_name + tone
```

Better path — add a dedicated poetry tone in `studio/voices.py`:

```python
# OPENAI_TONES
"poetic": (
    "Read this as poetry. Slow, deliberate pace. Pause at every line break and let "
    "each image land. Warm, intimate, unhurried — as if reading aloud to one person. "
    "Never rush; let silence do work."
),
```

Then set `"tone": "poetic"` in the scenario. (`edge` has no equivalent — it would only shift
pitch — so poetry is the case where paying for TTS earns its keep. A future ElevenLabs provider
would be the top tier; tracked under the "commercial-safe TTS" follow-up.)

Per-scene `tone` overrides the Script tone, so you can drop one stanza to `mystical` for a turn.

---

## 3. Visuals — drift, don't cut

Goal: imagery that moves like a slow breath. Pick `animator` by scene content:

- **`parallax`** — landscapes, skies, water, scenery. Static sharp subject + real background
  drift (subject inpainted out, no ghost twin). The signature poetry look. Direction from
  `motion_hint` (`left`/`right`/`up`/`down`). Needs `.[parallax]`; falls back to `kenburns`.
- **`static`** — portraits, objects, a held emotional beat. Pair with `atmosphere`/`fx` so it
  isn't dead-still.
- **`kinetic`** — *one* scene showing a single printed line of verse. Pair with a
  `fal-nanobanana` illustration, **not** a `card` image (a card already bakes text → double
  render). Use at most once or twice.
- **`motion-driftup` / `driftdown`** — gentle vertical drift for a rising/falling line.

**Avoid** for poetry: `slice` (violent reveal), fast `motion-zoom/pulse`, `puppet`,
`talkinghead`, `manim` (reads as a schematic, never art). Keep Ken Burns moves *slow* if used.

### Image prompts
Put the recurring look in `character` (e.g. `"painterly muted watercolor, soft grain, film
still, 16:9"`) and prepend it verbatim to every `visual_prompt` for a consistent series. Use
`image_role: "hero"` for the one or two key frames (quality model + char ref), `"bg"` for
scenery (≈4× cheaper). Lean abstract/atmospheric — fog, light, texture — over literal.

---

## 4. Atmosphere & fx — one mood layer, thin

Post-passes composite on any animator (`atmosphere` first, then `fx` in order):

- **Atmosphere (pick at most one):** `fog` (dreamy), `petals`/`leaves` (lyrical), `snow` (cold,
  still), `embers` (warm, elegiac), `rain` (melancholy). Keep it thin — taste caps in
  `artdirect.py` already discourage a thick blanket on every scene; don't override that.
- **fx (filmic stack):** `grain` + `vignette` as a base. Add `godrays` for a sunlit beat,
  `sunrise`/`sunset` for a turn, `oldfilm` for a memory/archival feel. **Avoid** `flash`,
  `chroma`, `glitch` — they break the spell.

One look per scene. Restraint > stacking.

---

## 5. Transitions — long, soft

Hard `cut` is the enemy. Use cross-fades and make them slow:

```jsonc
"transition": "dissolve",     // or "fade" / "fadeblack" for a stanza break
"transition_dur": 1.0          // 0.8–1.2s; the line-break beat
```

`fadeblack` between stanzas = a longer breath / section break. The first scene's transition is
ignored. Timing is overlap-compensated (`concat_xfade_seq`), so long fades won't desync audio.

---

## 6. Music — instrumental bed, ducked

Set top-level `music` to a single instrumental mood phrase (e.g. `"sparse ambient piano, warm
reverb, slow"`). It's generated by the `audio` stage and **sidechain-ducked under narration**
(`duck_music`, default −24 dB, voice-forward). Raise/lower `music_db` to taste — for poetry keep
it low so it never competes with the words. `""` = silence, which is a legitimate, often
*better* choice for spoken verse. Skip `sfx` almost entirely (poetry rarely wants a sword clash).

Budget note: a paid bed (`fal-stable-audio`) is $0.20; free `local`/`freesound` is $0. `studio
run` reserves the bed cost before clips, and a too-tight `--max-cost` auto-downgrades music to
free `local`. For a clean poetry bed, paid is worth it if the budget allows.

---

## 7. Captions — off

Leave captions **off** (the default). A burned wall of text covers the imagery and reads as
prose, killing the poem. YouTube/TikTok auto-generate captions anyway, and `narrate` still
writes `captions.srt` — upload it as a sidecar.

If you *must* burn (e.g. one signature line on screen), prefer `kinetic` `on_screen_text` for a
single line over full burned captions, or `--captions burn` knowing the strip is fill-width
wrapped + height-capped so it can't clip.

---

## Aspect ratio

- **16:9** for cinematic, "literary" poetry on YouTube (matches the operator's long-form noir
  work). Set `"aspect": "16:9"`.
- **9:16** for TikTok / Shorts. Either works — every stage adapts via `canvas.py`.

---

## End-to-end example (per-stage, paid TTS + free visuals draft)

```bash
# 1. New run (idea drives the script if you use studio script; here we hand-author below)
RID=$(studio init "the sea remembers — a short poem" --duration 60)

# ... author runs/$RID/01_script.json by hand (recommended for poetry — see builds/) ...

studio visuals  $RID --image-provider fal-nanobanana
studio narrate  $RID --voice-provider openai-tts --voice narrator --tone poetic
studio clips    $RID --video-strategy kenburns        # parallax/static are free
studio stitch   $RID
studio voice    $RID --voice-provider openai-tts       # captions stay off
studio save     $RID
studio status   $RID
```

For poetry the **script is usually hand-authored** (the LLM script stage optimizes for hooks and
retention, not verse). Write a `builds/build_<slug>.py` that emits `runs/<id>/01_script.json`
directly — one scene per line/couplet, with the presets above. Keep build scripts in `builds/`,
never at repo root. See [`builds/README.md`](../../builds/README.md).

---

## Scenario skeleton (hand-authored)

```jsonc
{
  "topic": "the sea remembers",
  "duration_s": 60,
  "aspect": "16:9",
  "voice": true,
  "voice_name": "narrator",
  "tone": "poetic",
  "style": "elegiac, intimate, slow",
  "character": "painterly muted watercolor seascape, soft film grain, 16:9, cohesive palette",
  "music": "sparse ambient piano, warm reverb, slow, instrumental",
  "scenes": [
    {
      "id": 1, "start_s": 0, "end_s": 10,
      "visual_prompt": "painterly muted watercolor seascape, soft film grain, 16:9, cohesive palette — grey tide pulling back over wet sand at dawn",
      "narration": "The sea remembers every name… it never learned to speak.",
      "on_screen_text": "",
      "animator": "parallax", "motion_hint": "left",
      "atmosphere": "fog", "fx": ["grain", "vignette"],
      "transition": "fade", "transition_dur": 1.0,
      "image_role": "hero", "tone": "poetic"
    },
    {
      "id": 2, "start_s": 10, "end_s": 20,
      "visual_prompt": "painterly muted watercolor seascape, soft film grain, 16:9, cohesive palette — a single gull suspended over a pale horizon",
      "narration": "It keeps them folded in the dark… beneath the weight of going.",
      "on_screen_text": "",
      "animator": "static",
      "atmosphere": "", "fx": ["grain", "vignette", "godrays"],
      "transition": "dissolve", "transition_dur": 1.2,
      "image_role": "bg", "tone": "poetic"
    }
  ],
  "title": "The Sea Remembers — a poem",
  "description": "A short poem.",
  "hashtags": ["#poetry", "#spokenword"]
}
```

---

## Checklist before rendering

- [ ] TTS is `openai-tts` with a `poetic`/`mystical`/`sad` tone (not flat edge).
- [ ] `narration` written as verse with line-end punctuation for natural pauses (~1.6–2.0 w/s).
- [ ] Animators are calm: `parallax` / `static` / one `kinetic`. No `slice`/`glitch`/fast motion.
- [ ] Transitions are `fade`/`dissolve`/`fadeblack` at **0.8–1.2s**.
- [ ] At most one `atmosphere` per scene; `fx` is the soft `grain`+`vignette` stack.
- [ ] Music bed is low / ducked, or silence. No stray `sfx`.
- [ ] Captions off (sidecar `captions.srt` only).
- [ ] `character` prepended to every `visual_prompt` for a consistent look.
- [ ] Eyeball the first frames (`--frames`) before paying for clips.

---

## See also

- [`docs/30-animation/voices.md`](../30-animation/voices.md) — voice & tone registry.
- [`docs/30-animation/parallax.md`](../30-animation/parallax.md) — the signature poetry motion.
- [`docs/30-animation/atmosphere.md`](../30-animation/atmosphere.md) · [`fx recipes`](../30-animation/effects/README.md).
- [`docs/30-animation/transitions.md`](../30-animation/transitions.md) — cross-fade reference.
- [`docs/30-animation/captions.md`](../30-animation/captions.md) — why off by default.
- [`docs/30-animation/scenario-schema.md`](../30-animation/scenario-schema.md) — authoritative field list.
- [`builds/README.md`](../../builds/README.md) — where hand-authored build scripts live.
