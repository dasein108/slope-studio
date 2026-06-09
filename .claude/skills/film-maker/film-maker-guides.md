# film-maker-guides — marvelous animation effects (operator findings)

Companion to [`SKILL.md`](SKILL.md). This is the **quality playbook**: hard-won
recipes for cinematic, anime-grade effects on the free/cheap path, plus the
operator's standing preferences. Read this before authoring scenes for any video
that should look *great* (not just wired). Everything here is free at render time
except the Nano-Banana stills.

> Source of truth for the moving parts: animator code in `studio/animate.py`,
> ffmpeg in `studio/ffmpeg.py`, Pillow in `studio/providers/cardgen.py`. The
> per-effect docs in `docs/30-animation/` are the deep reference; this file is the
> "how to make it look good" layer on top.
>
> **Reaching past the wired animators?** The full research-backed effect catalog —
> rain, snow, fire, fog, sunrise/sunset, water ripple, film grain, glitch, god-rays,
> shape morphs, kinetic typography, and more — is the effects index
> [`docs/30-animation/effects/`](../../../docs/30-animation/effects/README.md), with a
> status tag + recipe + license per effect. This playbook covers the *wired* set
> (`parallax`/`slice`/`kinetic`/`manim`/`motion-*`); the index is where you find
> everything else and how to author or wire it.

---

## 0. Operator's standing preferences (apply by default)

These come from direct feedback — treat as **hard defaults** unless the user says otherwise:

1. **Use lots of motion, cheaply.** Favor `parallax`, `slice`, `kinetic`,
   `motion-drift*`, and honest `static` over plain zoom. A static-*feeling* Short is a
   failure — but a *deliberate* static still is fine (see #5).
1a. **`parallax` = PERSPECTIVE / DEPTH scenery, NOT a big foreground subject.** True 2.5D
   depth is the most premium *free* look in the kit — but it only works on frames with **real
   receding distance**: sky & clouds (far), mountains / hills / a skyline (mid), houses / trees
   / a road / terrain (near). Those planes drift at different speeds and the depth reads.
   - 🚫 **THE HARD NO (operator rule): never use `parallax` on a frame a human, animal, face, or
     one single object DOMINATES (takes most of the space).** A big close subject has no depth
     to reveal and floats as a flat cutout — worse, not better. Big/close subject → `static`,
     `slice`, or `motion-drift*`. A *small* figure inside a wide landscape is fine (it's just
     the nearest plane).
   - **Compose parallax stills as landscapes with clear distance** — foreground, midground,
     horizon — not a portrait of one thing. Write the `visual_prompt` that way.
   - **2 planes (standard, balanced+ default):** a clean `scene_NN_bg.png` plate drifts behind
     held near scenery — two REAL images, **no inpaint, no tear**. `--parallax-plates` (auto on
     balanced/premium).
   - **3 planes (the reach):** author far/mid/near as separate PNGs (sky slow, hills medium,
     foreground near) — `ffmpeg.parallax_drift` takes a per-plane `depth`. For fast soft depth,
     `blurred-parallax` gives a free 2-plane sky-vs-ground.
   - **Aim for 2 clean planes minimum; reach for 3 on the hero/establishing landscape.** Never
     author bare plateless `parallax` expecting depth — with no plate it's only a flat pan
     (still safe, no tear). When in doubt between cheap options, `motion-drift{left,right,up,down}`.
1b. **NO schematic / vector drawings in art or story videos.** `manim` (shapes,
   diagrams, geometric silhouettes) is **only** for informative / educational /
   scientific pieces. In a story/cinematic video, render every beat as a real
   illustration + a free animator — never a vector scene. (See §4.)
2. **Anime / ukiyo-e aesthetic** for narrative/folk-tale content: bake a strong
   `character` style string and reuse it verbatim in every `visual_prompt`.
3. **Captions must always be fully on-frame** in the lower third, never clipped.
4. **Effects must read clearly** — if a vector/manim effect looks abstract or
   "strange", redesign it to be literal and legible (real silhouette, real path,
   real flash), not minimalist lines.
5. **NO `zoom-in`/`zoom-out` (and avoid plain `kenburns`).** The operator finds
   push/pull zoom "epileptic / twitching / still-looking". **A truly static image
   is PREFERABLE to a zoom.** Reach for *lateral* motion (pan/parallax/slice/drift),
   fades, and morphs instead. `motion-pulse` (breathing scale) is also out — too twitchy.
6. **Variety rule: never use the same effect more than 2× per minute.** Vary the
   animator scene-to-scene; be artistic. A row of identical `parallax` (or any one
   look) reads as lazy. Rotate through parallax / slice / kinetic / manim / drift /
   static / fade-morph.
7. **Pacing: no boring scene > 5s. Aim ~3s per scene** (except genuinely dynamic
   ones — a slice reveal, a manim action, a multi-layer parallax can run longer
   because they keep moving). Short, punchy beats. **A scene that holds a frozen
   frame is a bug** (see manim §4).
8. **Fewer transitions, more animation.** Default most cuts to `cut` or a soft
   `fade`; spend the energy on the per-scene *animation*, not on fancy wipes. Use a
   fancy transition only for a real chapter break or reveal. The operator likes
   **fade / morph-cut** over wipes.
9. **Use sound.** Add `sfx` for diegetic moments (sword clash, wind, thunder, crows,
   breath) and a `music` mood for the whole piece — see §11. Atmosphere sells drama.
10. **Atmosphere via art + sound, not twitchy overlays.** Rain / storm / fog / fire /
    falling petals → put them in the **image prompt** (Nano-Banana renders them
    cleanly and still) and in **SFX**. Do NOT use the abandoned ffmpeg rain wash.
11. **Iterate for free first** (stub images) only for *timing*; parallax/anime looks
    only show on real stills — validate by grabbing frames with ffmpeg and viewing them.
12. **Zoom must always FILL the frame — never white/black bars or empty canvas.** Any
    zoom (`kinetic`, `pulse`, ken-burns, `motion-zoom*`) goes **full-image (widest) →
    zoomed-in (tightest)** only; the widest extreme shows the WHOLE image covering the
    frame (scale-to-cover, zoom = 1.0), the tightest a zoomed crop. **Never zoom out past
    1.0** (exposes the empty background). Cover-crop off-aspect stills (increase+crop),
    never letterbox (decrease+pad). `kinetic` headlines sit over the cover-filled still,
    never a blank card. (Enforced in `ffmpeg.kinetic`.)
13. **Continuity: same character / same place every scene.** The doorkeeper must be the
    SAME person across scenes, the gate the SAME gate, an interior the SAME room — like a
    real film, not a new face/door per cut. Style-consistency (the `character` string)
    only fixes *art style*, not *identity*. Fix each recurring subject's **canonical look
    once** (exact face/beard/coat; the gate's exact design; the hall's columns) and paste
    that SAME description verbatim into every scene showing it, and/or pass a
    `--char-ref` still so Nano-Banana holds the identity. Decide the canon up front and
    repeat it — don't re-describe ad hoc each scene.

---

## 0.5 Writing a scenario that PASSES the critic (content, not just motion)

The #1 failure is a beautifully-animated video that says **nothing** — vague narration, no
real fact, no feeling. Effects are polish; **content is the product.** Author the script to
clear the SKILL.md ①.5 critic gate (topic revealed · concrete fact explained · informative AND
interesting · emotional payoff) on the first try:

**Structure — a Short is a tiny story with a spine:**
1. **Hook (0–3s)** — a curiosity gap or a shocking claim that names the stakes. Make a promise
   the body will pay off. ("This trumpet holds a finite cup of paint — but you can never paint
   its surface.")
2. **Turn / build (the middle)** — deliver the actual content: the **one concrete fact / idea /
   event**, *explained* — the what AND the why/how, with a real detail (a name, a number, a
   mechanism, a date, a consequence). This is the part that must teach. Don't gesture ("it
   changed everything") — show the change.
3. **Payoff (last beat)** — resolve the hook and land the **emotion**: the click of a paradox,
   awe at a scale, the injustice of a death, the chill of an implication. End on the feeling.

**The content rules (each maps to a critic criterion):**
- **Answer the title.** If the title teases a question or secret, the body must *reveal* it.
  A viewer who watched only this must come away *knowing the thing*, not just intrigued.
- **One idea, fully landed > five ideas gestured at.** Pick the single most interesting
  fact/turn and actually explain it. Depth beats breadth in 30–40s.
- **Name specifics.** Real names, numbers, places, mechanisms. Specificity *is* credibility and
  *is* interest. "A 20-year-old wrote modern algebra the night before a duel" beats "a young
  genius made discoveries".
- **Decide the emotion per act before writing.** Write the line that *causes* the feeling — a
  stake, a human cost, a reveal, a reversal — don't rely on the visuals to supply it.
- **Cut filler.** Every scene must add information or feeling. If a beat does neither, delete it
  (and let a real beat breathe instead). No "in this video", no throat-clearing intro.
- **Front-load value.** The most interesting thing should arrive fast; retention dies on a slow
  setup (Shorts: ~20–40s, first 3s decide).

**Self-check loop (the operator's critic, run it yourself):** after `studio script`, read
`01_script.json` and write a one-line verdict per criterion. On any fail, name what's missing
(e.g. "criterion 2: claims Cantor 'broke math' but never says HOW — add the diagonal argument
in 1 line") and rewrite that beat, then re-check. Only spend on `visuals` once all four pass.
The proven-winning shapes for this channel: personal-legend genius myth (a person + a paradox +
a cost), a single foundational paradox embodied in one object, an identity/quiz framing on real
archetypes. Flat melancholy, pure shock-horror with no idea, and dry explainers fail the gate.

---

## 1. The effect toolbox (what each is FOR, and the look that works)

| animator | use it for | the recipe that looks good |
|----------|-----------|----------------------------|
| `parallax` | **PERSPECTIVE / depth scenery** — landscapes with distance (mountains, clouds, skyline, houses, road) | **distinct depth planes drift at different speeds** (far slow, near fast) → real 2.5D. 🚫 **NEVER on a frame a human/animal/face/single object DOMINATES** — no depth, floats as a cutout; use `static`/`slice`/`drift` there. §2 |
| `slice` (diag) | a dramatic *reveal* (entrance, a turn) | diagonal cut → halves offset → slide together. Pair with `cut`/`fadeblack`. §3 |
| `slice` (horizontal+flash) | **the violent beat** (a beheading, an impact) | screen splits top/bottom + **red flash**. `motion_hint:"horizontal red flash"`. §3 |
| `manim` | **educational/scientific ONLY** — diagrams, math, graphs, force arrows | NEVER in art/story (schematic look breaks immersion). Use real stills there. §4 |
| `kinetic` | hooks, shouted lines, quotes, the outro | big headline over a *text-free* illustration (never over a `card`). |
| `motion-drift{left,right,up,down}` | establishing / "moving on" beats | gentle LATERAL pan. The only `motion-*` to use. |
| **static** (no animator, or a 2–3s held still) | a calm/severe beat | a strong still is **better than a bad zoom**. Use freely for variety. |

**Banned by operator:** `motion-zoomin` / `motion-zoomout` / `motion-pulse` and a
dominant diet of `kenburns` — all read as twitchy/epileptic/static. Prefer lateral
motion, slice, parallax, fades, and honest static stills.

**RULE — `pulse` and `kinetic` are OFF by default; use only on explicit need.**
`motion-pulse` is twitchy — never use it unless the user explicitly asks. `kinetic`
bakes a big on-screen headline, so use it ONLY where a scene truly needs on-screen
words (hook, shouted line, title/outro card) over a text-free illustration — NOT as
generic motion on ordinary narrated beats (the narration/captions already carry the
words; reach for parallax / slice / drift / static instead).

### Animator decision in one line
> depth landscape (mountains/clouds/houses) → `parallax` (multi-layer) · reveal → `slice` diag · violent hit →
> `slice` horizontal+flash · headline → `kinetic` · drift → `motion-drift*` · calm beat
> → **static**. (`manim` ONLY for educational/scientific videos — never art/story.)
> Rotate them — **max 2× the same per minute.**

> **Atmosphere on top of any of these** (rain, snow, fire, fog, sunrise glow, grain,
> god-rays…): they aren't separate animators — pull them from the effects index. The
> ready-today route is `animator:"manim"` + a paste-ready `manim_code` snippet
> ([`effects/manim-effects.md`](../../../docs/30-animation/effects/manim-effects.md));
> the ffmpeg recipes ([`effects/ffmpeg-recipes.md`](../../../docs/30-animation/effects/ffmpeg-recipes.md))
> are backlog post-passes. **Don't set an unwired effect name in `animator`** — it
> falls back to `kenburns`. Catalog + status legend:
> [`effects/README.md`](../../../docs/30-animation/effects/README.md).

---

## 2. parallax — perspective scenery, depth planes drift (the clean one)

> 🚫 **HARD RULE (operator) — parallax is for PERSPECTIVE / DEPTH scenery, NOT a big
> foreground subject.** Author it on landscapes with real distance — sky & clouds (far),
> mountains / hills / a skyline (mid), houses / trees / a road / terrain (near). Those planes
> drift at different speeds → real 2.5D depth.
> **NEVER use parallax on a frame a human, animal, face, or one single object DOMINATES (takes
> most of the space).** A big close subject has no depth to reveal and floats as a flat cutout —
> it looks worse, not better. Big/close subject → `static`, `slice`, or `motion-drift*`. A
> *small* figure inside a wide landscape is fine — it's just the nearest plane.
> **Now enforced in code — `_parallax` has two modes, and NEVER auto-cuts a subject from a single still:**
> - **no plate (cheap/default)** → a **clean full-image lateral pan** over the vista. Bulletproof; no holes.
> - **plate present (balanced+)** → true layered 2.5D: held near scenery over a **separate
>   `scene_NN_bg.png` background plate** that drifts behind it — two DIFFERENT images, no inpaint
>   hole. Plates from `studio visuals --parallax-plates` (auto on balanced/premium); +1 still/scene.
> The old torn/holed frames came from auto-cutting a subject out of one still — that path is removed.

**Compose the still for depth:** write the `visual_prompt` as a landscape with a clear
foreground → midground → horizon (e.g. "low rocks in front, a valley of houses below, jagged
peaks and drifting clouds beyond"), **not** a portrait of one big thing. The more separable the
distance bands, the better the drift reads.
- `motion_hint:"right"` (default) `|"left"|"up"|"down"` sets drift direction;
- far planes should move slowly, near planes faster — author 2–3 plane PNGs for the hero shot,
  or let the 2-plane plate mode handle the standard case;
- works best where distance bands are distinct (sky / mountains / ground), not a flat wall.

**`blurred-parallax`** = the older **soft-backdrop** look: a *blurred* copy of the still
panned behind the figure. Default = **2-plane** (sky vs ground, opposite directions via
`ffmpeg.parallax_layers`); `motion_hint:"single"` = one heavily-blurred plane. Use it for
**busy backgrounds** where the inpaint would smear, or when you want dreamy depth-of-field.

**Layered (multi-plane) parallax** — far sky +1, nearer clouds +2 — needs the background
split into sub-layers, which can't be auto-extracted from one flat still. `blurred-parallax`
gives a 2-plane approximation today; true multi-plane on the clean path is **backlog** (feed
separate transparent plane PNGs). See [`parallax.md`](../../../docs/30-animation/parallax.md).
Preview: `python examples/make_examples.py parallax` (clean) / `blurred-parallax` (soft).

**Pairing:** needs a landscape with distinct distance bands (a horizon, near/far planes). Flat
stills or big-subject portraits → weak/no depth; use `motion-drift*` or `static` instead.

Tuning: `cardgen.depth_bands` (`seam`, `feather`); `ffmpeg.parallax_layers` (`bw1/bw2`
pan room, `period`, per-layer `gblur`).

---

## 3. slice — the diagonal-cut reveal (NEW)

**What it is:** the still is cut along the top-left→bottom-right diagonal into two
triangles that start **offset apart** (along the cut's perpendicular) over a black
gap, then **slide together** to form the whole image, then hold. A "sword-cut"
reveal. Free.

**Pipeline:** `cardgen.diagonal_halves` (Pillow: two triangle-masked PNGs) →
`ffmpeg.diag_slice` (overlays them converging). Dispatched by `animate._slice`.

**Author it:** set `"animator": "slice"`. `motion_hint` keywords pick the cut:
- (default) **diagonal** reveal — a character's entrance, a reversal.
- `"horizontal"` → **top/bottom split** — THE BEHEADING cut the operator asked for.
- `"vertical"` → left/right split.
- add `"flash"` or `"red"` → a **red flash** pulses at the cut moment.

So the head-cut scene is `animator:"slice"`, `motion_hint:"horizontal red flash"`:
the screen splits in two horizontally and a red flash fires — clean, dramatic, free.
Pair with `transition:"cut"` (the slice IS the moment).

Tuning in `ffmpeg.diag_slice`: `axis`, `red_flash`, `split_dur` (default 0.7s),
`offset` (default 160px). Built from `cardgen.split_halves(axis=…)`.

> This is the operator's answer to "make the cut effect interesting" and "head cut =
> horizontal split + red flash". Use `slice` wherever a hard cut would feel flat.

---

## 4. manim — ONLY for educational/scientific, NEVER for art/story

**Hard rule (operator):** schematic / vector / programmatic drawings (manim shapes,
diagram silhouettes, geometric figures) are **acceptable ONLY in informative,
educational, or scientific videos** — explainers where a diagram IS the content.
**For an art / story / cinematic piece they look wrong and break immersion** — even
a "literal" vector silhouette (a stone-path + a rolling circle-head) reads as a
schematic and must NOT be used. In a story video, render every beat as **real
illustration** (Nano-Banana still) + a free animator (parallax / slice / drift /
static / kinetic). Replace any manim story-beat with a real image + lateral motion.

**Where manim IS right:** a science/how-it-works/math Short — a labelled diagram, a
graph, an equation morph, a force arrow. There, draw it literally and legibly: real
axes/shapes + a clear color cue, authored flush-left (see authoring rules below).

**Anti-example (do NOT repeat):** an early *Diplomacy* (art/story) cut used a manim
"rolling head" (stone-path `Polygon` + a `Circle` head) and a manim blade-glint. The
operator rejected both — "no such visuals at all… acceptable only for informative /
educational / scientific." They were replaced with **real Nano-Banana stills + lateral
motion** (a raised katana on `motion-driftup`; an ominous blood-streaked aftermath on
`motion-driftright`). In a story piece, always do that instead of a vector scene.

**Authoring rules (for the educational/scientific case where manim IS appropriate):**
- Put the **body of `construct()`** in `manim_code`. **Author it FLUSH-LEFT** (no
  leading indentation). `animate._manim` now dedents + re-indents uniformly, so
  flush-left or consistently-indented both work — but flush-left is safest.
- Combine move + spin in ONE animation via chained `.animate`:
  `self.play(sil.animate.move_to([7.5,-3,0]).rotate(-4*PI), run_time=2.3, rate_func=linear)`.
- Use hex colors (`"#c81e1e"`) freely; set `self.camera.background_color`.
- **Match the animation to the scene length, and keep manim scenes SHORT (~3–4s).**
  The clip is fit to narration by **freezing the last frame** — so a 3s animation in
  an 11s scene = 8s of frozen still = "out of animation" (a real operator complaint).
  Either keep continuous motion for the whole scene, or give the scene only ~3–4s of
  narration. Never let manim (or any animator) hold a dead frame for seconds.
- Any error → silent `kenburns` fallback. **Always verify** a manim scene by
  grabbing a frame (see §7); a teal/stub-colored frame means it fell back.

---

## 5. kinetic — headlines that pop

- Pair with a **text-free** illustration (Nano-Banana), never the `card` provider
  (which bakes text → doubled headline).
- The headline sits at ~18% height and slides up + fades in; sentence captions
  burn separately at the bottom — they don't collide.
- Great for the hook (scene 1), shouted lines, and the outro/punchline.

---

## 6. Captions — OFF by default, and clip-proof when on

**Default: captions are OFF.** YouTube/TikTok auto-generate captions from the audio,
and a burned wall of text covers the visuals. Most videos should ship without burned
text. The `narrate` stage still writes `captions.srt` — upload that sidecar to YouTube
for accurate subs without baking pixels.

**Turn them on only when you want text baked in** (e.g. muted-autoplay feeds):
`studio voice <id> --captions burn` or `studio run … --captions burn`.

**When burned, they can't clip** (two past bugs, both fixed):
- `cardgen.caption_strip` uses **fill-width wrap** (chars/line from measured glyph
  width → fewest lines) + font shrink (56→22px) to a **~22%-of-H budget**, then
  **hard-caps** the PNG height at that budget. A 152-char cue → ~5 tidy lines, not 7.
- `ffmpeg.burn_subs` overlays at `H-h-(~0.115*H)` — lower third, clear of the action
  bar. Tight strip + margin ⇒ always on-frame, top and bottom, any aspect.

**Still want captions?** Keep narration sentences punchy (≤ ~16 words) so cues stay
2–3 lines. Tune `max_h` (`0.22*H`) / margin (`0.115*H`) in `cardgen.caption_strip` /
`ffmpeg.burn_subs` if a platform's safe-area differs.

---

## 7. Quality workflow — verify effects by eye, cheaply

Effects (parallax depth, slice, manim, caption placement) can't be trusted from a
log line — **look at frames**:

```bash
# grab a frame at a given second from any clip or the final master
ffmpeg -v error -y -ss <sec> -i runs/<id>/06_final.mp4 -frames:v 1 /tmp/f.png
```
Then open/Read `/tmp/f.png`. To land on the right scene, read narration-driven
timing (cumulative sum of per-scene lengths):
```bash
cat runs/<id>/05_voice/timing.json   # {scene_id: seconds}; cumulative = scene start
```
Checklist per effect:
- **parallax**: bg blurred + moved between t=start and t=end; subject NOT moved; no sharp ghost twin.
- **slice**: mid-converge frame shows the diagonal gap; later frame shows the whole image.
- **manim**: real environment + silhouette visible (NOT a flat stub color = fallback).
- **captions**: full last line visible above the bottom action-bar zone.

---

## 8. Image generation for effects (Nano-Banana)

- **Moderation:** fal blocks overt violence/gore (bound prisoner, severed head,
  rage, blood). **Imply** it — let narration carry the horror, keep visuals
  suggestive (e.g. a stone + a dark rounded shape under moonlight instead of a
  severed head). Rewrite flagged prompts; a 1-color 10 KB PNG in `02_visuals/`
  means that scene was blocked and stubbed.
- **For `parallax`/`slice`:** prompt for ONE clear subject over a distinct bg.
- **For `kinetic`:** prompt a text-free illustration (no baked words).
- **Consistency:** reuse the `character` style string verbatim at the start of
  every `visual_prompt`. Cost: $0.039/still (verified).

---

## 9. Reusable snippets

**Anime dark-folk-tale style string** (`character`):
> `anime cel-shaded art fused with dark ukiyo-e woodblock, muted indigo and ash-grey palette with blood-red accents, dramatic rim light, atmospheric fog, high-contrast silhouettes, painterly, cinematic, 9:16 vertical`

**A scene that reveals a character (slice):**
```json
{"id": 4, "animator": "slice", "transition": "fadeblack",
 "on_screen_text": "THE SAMURAI", "motion_hint": "imposing reveal",
 "visual_prompt": "<style>, a tall composed samurai ... silhouette against pale sky",
 "narration": "..."}
```

**A perspective-depth scenery scene (parallax, planes drift right):**
```json
{"id": 3, "animator": "parallax", "transition": "wipeleft",
 "motion_hint": "slow drift right",
 "visual_prompt": "<style>, wide valley landscape with clear distance: low rocks in the foreground, a town of houses in the midground, jagged peaks and drifting clouds on the horizon — NO big foreground subject",
 "narration": "..."}
```

**The rolling-head manim slash:** copy `manim_code` from scene 9 of
`runs/diplomacy/01_script.json`.

---

## 11. Sound & atmosphere (sfx + music + weather)

Audio is a real stage (`studio audio`, between `stitch` and `voice`; mixed/ducked by
`voice`). It's where most of the "drama" comes from cheaply.

- **Per-scene `sfx`** (scenario `scenes[].sfx`, 0–2 each): `{prompt, at, dur, gain_db}`.
  Add only for clear diegetic moments — `"metallic sword clash"`, `"single thunderclap"`,
  `"howling wind"`, `"sharp gasp"`, `"crows cawing"`, `"heavy rain on wood"`. `at` =
  seconds into the scene; `gain_db` ≈ −6 (subtle) … 0 (prominent).
- **Top-level `music`** = one instrumental MOOD phrase for the whole piece, e.g.
  `"ominous taiko and shakuhachi, slow, tense, cinematic, instrumental"`. Ducked under
  narration automatically.
- **Providers:** `fal-elevenlabs-sfx` ($0.002/s — negligible) + `fal-stable-audio` ($0.20
  flat music) when `FAL_KEY` is set; `freesound` (CC0, needs `FREESOUND_API_KEY`) or `local`
  (packs in `assets/audio/music/`) for **free**; `silence` for $0 drafts. Run
  `studio audio <id> --sfx-provider … --music-provider …`.
- **COST: music is the dominant audio cost ($0.20); sfx is ~free.** `--max-cost` is the
  whole-video budget — `studio run` reserves the music bed and **auto-downgrades paid music
  to free** if it won't fit. To cut the $0.20 without losing music, drop royalty-free tracks
  (Pixabay / YouTube Audio Library / Mixkit) into `assets/audio/music/` and use
  `--music-provider local`. Cheapest "still alive" recipe: free `motion-*` everywhere + one
  ≤6s ltx hook + `local` music ≈ $0.41. See `docs/10-architecture/cost-model.md` for the ladder.
- **Weather/atmosphere = the `atmosphere` field (wired) + ART + SOUND.** Set
  `scene.atmosphere` to `rain|snow|embers|blood|petals|wind|fog` → a free transparent
  particle layer composites over the clip (any animator). It's alpha-`overlay`, so the
  painted art stays intact. See [`atmosphere.md`](../../../docs/30-animation/atmosphere.md).
- **⚠️ Atmosphere is OPT-IN by literal content — default OFF.** Set it ONLY when the
  scene actually depicts that element: snow in an outdoor winter shot, embers for real
  fire, rain in real rain, petals/leaves outdoors among blossom, fog for real mist.
  **Never** add particles to an indoor, portrait, studio, diagram, or neutral scene, and
  never "for mood" or decoration — falling snow in a 1960s office is a bug, not a vibe.
  Most scenes keep `atmosphere: ""`. When you do use it, describe the weather in the
  `visual_prompt` too and add matching SFX (art + overlay + sound sell it together), one
  kind per scene — e.g. `rain` as a throughline, `blood` only on the kill.
- **fx restraint:** pick ONE coherent look for the whole video (e.g. `grain`+`vignette`,
  or `oldfilm`) and apply it consistently — don't sprinkle a different fx on every scene.
  `godrays` needs a real light source; never `chroma`/`glitch` on a calm/realistic piece.

## 12. Pacing & variety checklist (run before rendering)

- [ ] **Scene length:** most scenes ≤ ~5s; calm beats ~3s; only genuinely dynamic
      animators (slice / manim action / multi-layer parallax) run longer.
- [ ] **No frozen holds:** every scene moves for its whole duration, OR is a
      deliberate short static still. No animation that finishes then freezes for seconds.
- [ ] **Variety:** no animator used > 2× in any rolling 60s. Adjacent scenes differ.
- [ ] **No banned motion:** zero `zoomin`/`zoomout`/`pulse`; `kenburns` not dominant.
- [ ] **Transitions sparse:** mostly `cut`/`fade`; a fancy transition only at a real
      chapter break or reveal.
- [ ] **Sound present:** a `music` mood is set; key beats have `sfx`.
- [ ] **Atmosphere in the art:** weather/mood baked into prompts where it fits.
- [ ] **Captions** fit; **effects verified** by frame-grab (§7).

## 13. Poetry / spoken-verse — voice, tone & accents (special case)

Poetry is the one format where **pacing and accent placement ARE the art**. The prose
defaults (fast cuts, 2.6 w/s, busy motion, flat edge voice) fight the verse. Full preset:
[`docs/recipes/poetry.md`](../../../docs/recipes/poetry.md). The operator-critical parts:

**Voice = `openai-tts`, tone = `poetic` (NOT edge, NOT openrouter).**
- `edge` (free) only shifts global rate/pitch — it **cannot place accents** on specific
  words. For verse it sounds flat/wrong. Pay for `openai-tts` here; it earns its keep.
- **OpenRouter is a script-stage (text-LLM) router — it has NO TTS/audio endpoint.** You
  can write the verse with an openrouter LLM, but the *voice* can only be `edge`/`openai-tts`.
- The `poetic` tone (`voices.py` `OPENAI_TONES`) is an instruction-driven prosody: slow,
  pause at every line break / `…` / `—`, stress the key noun-or-verb per line, lift the
  final word. That instruction string is **where accents come from** — edit it, or drop a
  per-scene `tone` override, to re-aim the emphasis.

```bash
studio narrate $RID --provider openai-tts --voice narrator --tone poetic
studio voice   $RID --provider openai-tts                  # captions stay OFF
```

**Placing the right accents (the levers, in order):**
1. **One scene per line or couplet.** The cross-fade *is* the line break; per-scene `tone`
   lets you drop a single stanza to `mystical`/`sad` for a turn.
2. **Punctuation drives breath.** End lines with `.` / `…` / `—` — TTS pauses on terminal
   punctuation. A bare `…` line = a held silent beat (clip holds last frame).
3. **Write ~1.6–2.0 w/s, not 2.6.** A 10s scene = ~16–20 words. Short lines. Slower speech
   auto-lengthens the scene (narration-driven timing), so the visuals breathe with the voice.
4. **Emphasis in the verse itself.** CAPS / spacing / line position steer `gpt-4o-mini-tts`;
   for a hard accent, customise the `poetic` instruction (or add a one-off tone) naming the
   word to stress.

**Visuals match the voice:** calm, drifting — `parallax` (scenery) · `static` (held beats) ·
**no** `slice`/`glitch`/fast `motion-*`/`pulse`. Transitions `fade`/`dissolve`/`fadeblack`
at 0.8–1.2s (long, soft — see recipe). `voice_name`: `narrator` (→ onyx, grave) or `woman`
(→ nova, warm). Captions OFF (a text wall reads as prose, kills the poem). Script is usually
**hand-authored** (`builds/build_<slug>.py`) — the LLM script stage optimises hooks, not verse.

---

## 10. Adding a brand-new effect (pattern)

Mirror `slice`/`parallax`:
1. **Pillow** image transform (if any) → `studio/providers/cardgen.py`.
2. **ffmpeg** compositing → a new function in `studio/ffmpeg.py` (ALL ffmpeg lives here).
3. **Orchestrate** → an `_name` helper + a `name` branch in `animate.render`
   dispatch (`studio/animate.py`). It MUST fall back to `kenburns` on any error.
4. **Document** → a `docs/30-animation/<name>.md`, add to the README matrix and the
   scenario-schema animator list, and note the recipe here.
