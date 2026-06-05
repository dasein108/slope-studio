# Effects index — programmatic / vector animation catalog

The **LLM authoring index** for visual effects beyond the base animators. Every effect
here is **free, headless-renderable, and uses no paid AI-video API** — pure `ffmpeg`
filtergraphs, Manim (vector), Python particle libs, GLSL shaders, or SVG/Lottie.

> Backed by a verified deep-research pass — see [`sources.md`](sources.md) for citations
> and confidence. Recipes marked 🧪/🔬 are **authoring backlog**, not yet wired into
> `studio/animate.py`. Read the **status legend** before you set anything in a scene.

## Status legend (READ THIS)

| | Status | How to use it in a scene **today** |
|---|--------|------------------------------------|
| ✅ | **Live** | Set `animator:"<name>"` directly — implemented in `animate.py`. |
| 🧩 | **Manim-authorable now** | Set `animator:"manim"` + paste the `manim_code` snippet. Live via the manim engine, just not a named preset. |
| 🧪 | **Recipe-ready (backlog)** | A drop-in `ffmpeg`/Python recipe exists but **no `animator` is wired yet** — setting a bare name falls back to `kenburns`. Implement first (see [how to add](#adding-an-effect)). |
| 🔬 | **Research-only** | Technique is real but the recipe is unverified or needs heavy deps (GPU/EGL). Validate before building. |

**Do not** put a 🧪/🔬 name in `animator` expecting it to render — `animate.py` returns
`"<name>->kenburns (unknown)"` for anything it doesn't implement. Until wired, reach for
the effect via **Manim (🧩)** or an `ffmpeg` post-pass.

## Compositing modes (how an effect lands on a scene)

| mode | what it does | ffmpeg primitive |
|------|--------------|------------------|
| **overlay-alpha** | particle/vector layer with transparency dropped on the still | `overlay` |
| **screen / add blend** | light-emitting fx (fire, embers, god-rays, lightning) brightens base | `blend=all_mode=screen` / `addition` |
| **displace** | warp the still by a generated map (water ripple, heat haze) | `displace` (x/y map inputs) |
| **color-grade** | recolor/relight the whole frame over time (sunrise, golden hour) | `geq` / `curves` / `colorbalance` / `colortemperature` |
| **standalone** | the effect IS the clip (manim morph, shader, kinetic type) | render → `normalize` |

Particle/shader/SVG layers are best rendered with a **transparent or black background**
then composited: alpha → `overlay`; black light-fx → `blend=screen` (black reads as zero).

## Family A — natural phenomena & particles

| effect | status | engine / recipe | composite | license |
|--------|--------|-----------------|-----------|---------|
| sunrise / sunset / golden-hour | ✅ | `fx:["sunrise"]` / `["sunset"]` (color-grade ramp) | color-grade | FFmpeg ✅ |
| fog / mist / haze | ✅ | `atmosphere:"fog"` (Pillow blurred layer → scroll overlay) · [atmosphere.md](../atmosphere.md) | overlay | FFmpeg+Pillow ✅ |
| rain | ✅ | `atmosphere:"rain"` (Pillow streak layer → scroll overlay) · [atmosphere.md](../atmosphere.md) | overlay | FFmpeg+Pillow ✅ |
| snow | ✅ | `atmosphere:"snow"` · [atmosphere.md](../atmosphere.md) | overlay | FFmpeg+Pillow ✅ |
| sparkles / embers / dust | ✅ | `atmosphere:"embers"`/`"sparks"` (rising glow particles) · [atmosphere.md](../atmosphere.md) | overlay | FFmpeg+Pillow ✅ |
| blood drops / spatter | ✅ | `atmosphere:"blood"` (red droplet layer) · [atmosphere.md](../atmosphere.md) | overlay | FFmpeg+Pillow ✅ |
| falling petals / leaves / wind | ✅ | `atmosphere:"petals"`/`"leaves"`/`"wind"` (drift + sway) · [atmosphere.md](../atmosphere.md) | overlay | FFmpeg+Pillow ✅ |
| fire / flames | 🔬 | GLSL shader (ModernGL) or CC0 asset loop · [shaders](shaders.md#fire) | screen | engine MIT; **shaders: replace NC** ⚠️ |
| water ripple / reflection / caustics | 🔬 | `displace` with `geq` sine map · [ffmpeg](ffmpeg-recipes.md#water); shader for caustics | displace/screen | FFmpeg ✅ |
| wind sway / gusts | 🧩 | Manim mobject sway, or `displace` warp · [manim](manim-effects.md#wind) | standalone/displace | MIT ✅ |
| falling leaves | 🧩 | Manim/`bubbles` particles with rotation · [particles](particles.md) | overlay | MIT ✅ |
| clouds drifting | 🧪 | `motion-driftright` on a cloud still, or `geq` noise pan | standalone | FFmpeg ✅ |
| lightning flash | 🧩 | Manim jagged `Line` + white `Flash`/brightness pulse · [manim](manim-effects.md#lightning) | screen | MIT ✅ |
| stars / aurora | 🔬 | GLSL shader, or Manim dotted field · [shaders](shaders.md) · [manim](manim-effects.md) | screen | engine MIT ✅ |

## Family B — vector motion-graphics

| effect | status | engine / recipe | composite | license |
|--------|--------|-----------------|-----------|---------|
| slice / diagonal reveal | ✅ | `animator:"slice"` · [slice.md](../slice.md) | standalone | FFmpeg ✅ |
| Ken-Burns / drift / zoom / pulse | ✅ | `animator:"kenburns"` / `motion-*` · [motion.md](../motion.md) | standalone | FFmpeg ✅ |
| kinetic headline | ✅ | `animator:"kinetic"` · [kinetic.md](../kinetic.md) | overlay | FFmpeg+Pillow ✅ |
| kinetic typography (typewriter, word-by-word) | 🧩 | Manim `Write`/`AddTextLetterByLetter`/`TypeWithCursor` · [manim](manim-effects.md#typography) | standalone | MIT ✅ |
| shape morph | 🧩 | Manim `Transform`/`TransformMatchingShapes` · [manim](manim-effects.md#morph) | standalone | MIT ✅ |
| equation / formula morph | 🧩 | Manim `TransformMatchingTex` (needs TeX) · [manim](manim-effects.md#morph) | standalone | MIT ✅ |
| mask / shape reveal | 🧩 | Manim clip-path reveal, or SVG `clip-path` · [manim](manim-effects.md) · [svg](svg-lottie.md) | standalone | MIT ✅ |
| transitions (50+ wipes) | ✅ | `transition:"…"` · [transitions.md](../transitions.md) | between clips | FFmpeg ✅ |
| film grain | ✅ | `fx:["grain"]` (temporal noise post-pass) | screen | FFmpeg ✅ |
| vignette | ✅ | `fx:["vignette"]` | color-grade | FFmpeg ✅ |
| chromatic aberration | ✅ | `fx:["chroma"]` (`rgbashift`) | color-grade | FFmpeg ✅ |
| glitch | ✅ | `fx:["glitch"]` (`rgbashift`+`noise`) | standalone | FFmpeg ✅ |
| sunrise / sunset / golden-hour | ✅ | `fx:["sunrise"]` / `["sunset"]` (`colorbalance`+`eq`+`vignette` ramp) | color-grade | FFmpeg ✅ |
| light rays / god-rays | ✅ | `fx:["godrays"]` (radial `geq` shafts + RGB screen) | screen | FFmpeg ✅ |
| flash / impact (explosion, blood hit, fireworks) | ✅ | `fx:["flash-red"]` etc — full-frame colour punch (white/yellow/red/black) that holds then fades back over 0.3–0.8s | overlay | FFmpeg ✅ |
| zoom-blur | 🧪 | `zoompan`+`gblur` blended pulse · [ffmpeg](ffmpeg-recipes.md#zoomblur) | standalone | FFmpeg ✅ |
| bokeh | 🔬 | shader, or blurred bright-point overlay · [shaders](shaders.md) | screen | engine MIT ✅ |

## Family C — avatar / narrator / character motion

| effect | status | engine / recipe | composite | license |
|--------|--------|-----------------|-----------|---------|
| puppet (moving figure, shake/nod head, hop) | ✅ | `animator:"puppet"` — rembg cutout moved over blurred bg · [puppet.md](puppet.md) | standalone (per-frame) | FFmpeg+rembg ✅ |
| per-limb moves (hand up, point, walk) | 🔬 | i2v (cheap short clip) or a future joint schema · [puppet.md](puppet.md) | standalone | fal $ / backlog |
| talking head (2D lip-sync) | ✅ | `animator:"talkinghead"` — Rhubarb visemes → mouth-sprite swap on a static face · [talking-head.md](talking-head.md) | overlay (per-frame) | Rhubarb MIT ✅ |
| amplitude mouth-flap | 🧪 | RMS envelope → 3-shape mouth (no Rhubarb) · [talking-head.md](talking-head.md) | overlay | FFmpeg+Pillow ✅ |
| AI talking-head (photoreal) | 🔬 | Wav2Lip / SadTalker / LatentSync (GPU) · [talking-head.md](talking-head.md) | standalone | ⚠️ **Wav2Lip non-commercial** |

## Engine reference pages

- [`ffmpeg-recipes.md`](ffmpeg-recipes.md) — pure filtergraphs (geq/displace/blend/rgbashift/vignette/noise). **Most build-portable, no extra deps.**
- [`manim-effects.md`](manim-effects.md) — vector morphs + kinetic typography via `manim_code` (**usable today**).
- [`particles.md`](particles.md) — Matplotlib + `bubbles` particle systems → PIL/overlay.
- [`shaders.md`](shaders.md) — GLSL via ModernGL headless (GPU/EGL; licensing caveats).
- [`svg-lottie.md`](svg-lottie.md) — drawsvg/svgwrite (MIT) vs python-lottie (AGPL — avoid).
- [`puppet.md`](puppet.md) — **cutout puppet** (free moving figure: idle/hop/shake/nod head): the wired `puppet` animator.
- [`talking-head.md`](talking-head.md) — **2D lip-sync** (static face, moving mouth): the wired `talkinghead` animator (Rhubarb) + tiers.
- [`sources.md`](sources.md) — citations, confidence, refuted claims, open questions.

## Licensing & build caveats (must-read before shipping)

- **This machine's ffmpeg lacks `drawtext` (no libfreetype) and `subtitles`/`ass`
  (no libass).** So `geq`/`zoompan`/`xfade`/`blend`/`overlay`/`displace`/`noise`/`rgbashift`
  recipes are safe, but **any text must come from Pillow or Manim-Pango**, never ffmpeg
  `drawtext`/`subtitles`. (Same rule as captions — see [`../captions.md`](../captions.md).)
- **Determinism is not free.** Matplotlib rain, GLSL shaders, and any RNG particle effect
  are only reproducible once you **fix the seed** in the plugin. The glsl-to-mp4
  "seed-driven determinism" claim was **refuted** in research — enforce it yourself.
- **python-lottie is AGPLv3+** (strong copyleft) — **avoid embedding/distributing** it in a
  commercial channel pipeline. Prefer drawsvg/svgwrite (MIT).
- **GLSL shaders from glsl-to-mp4 / Shadertoy are CC BY-NC-SA (non-commercial)** even though
  the ModernGL engine is MIT — **replace bundled shaders with original/permissive ones**
  before commercial use.
- **GPU/EGL needed for shaders** — falls back to slow software Mesa on a GPU-less host.
- Safe-for-commercial & permissive: **FFmpeg filters, Manim (MIT), ModernGL (MIT),
  Matplotlib (BSD), bubbles (MIT), drawsvg/svgwrite (MIT).**

## Adding an effect

The mechanical recipe to promote a 🧪 to ✅ (mirrors the existing `slice` animator):

1. **`studio/ffmpeg.py`** — add one filtergraph helper (e.g. `def rain(...)`). All ffmpeg
   shelling stays here.
2. **`studio/animate.py`** — add a name branch in `render()` dispatch (`if a == "rain": …`),
   wrapped by the existing try/except → kenburns fallback (never breaks the pipeline).
3. **`docs/30-animation/scenario-schema.md`** — add the name to the `animator` enum line.
4. **This index** — flip the status to ✅ and link a short `../<name>.md` how-to.
5. Optional deps go in `pyproject.toml` extras (like `.[parallax]`, `.[manim]`); fall back
   to kenburns if the dep/render fails, recording the reason in the manifest note.

For light-emitting / particle effects, prefer **overlay/`blend=screen` as a post-pass** on
the ken-burns clip so the effect composes onto ANY scene without a dedicated branch.
