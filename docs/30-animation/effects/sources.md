# Sources & confidence — effects research

Deep-research pass (2026-06-04): 5 angles, 25 sources fetched, 112 claims extracted, 25
adversarially verified (3-vote, kill on 2/3 refute) → **24 confirmed, 1 refuted**. Confidence
legend matches [`../../README.md`](../../README.md): ✅ verified · ⚠️ refuted · 🔶 domain knowledge.

## ✅ Verified findings

| claim | confidence | source |
|-------|-----------|--------|
| FFmpeg `geq` (per-pixel expr: gradients/displacement/noise), `zoompan` (Ken Burns), `xfade` (50+ named transitions) are free core filters | high (3-0) | [ffmpeg manual](https://ffmpeg.org/ffmpeg-filters.html) |
| Asset-free **film grain** via `geq`+`deflate`+`dilation`+`eq`+`scale`+`blend multiply`+`negate`+`alphamerge`+`overlay` | high (3-0) | [film-grain gist](https://gist.github.com/logiclrd/287140934c12bed1fd4be75e8624c118) |
| **Matplotlib** rain sim (BSD), headless via Agg+ffmpeg writer; deterministic once seeded | high (3-0) | [matplotlib rain](https://matplotlib.org/stable/gallery/animation/rain.html) |
| **bubbles** (MIT) `ImageEffectRenderer` → particles onto a PIL Image, headless | high (3-0) | [jaynewey/bubbles](https://github.com/jaynewey/bubbles) |
| **Lepton** needs an OpenGL context / no direct image output (less headless-friendly than bubbles) | high (3-0 / 2-1) | [lepton docs](https://pythonhosted.org/lepton/) |
| **Manim** (MIT, Cairo headless): `Transform`, `TransformMatchingShapes`, `TransformMatchingTex` morphs | high (3-0) | [manim transform docs](https://docs.manim.community/en/stable/reference/manim.animation.transform.html) |
| **Manim** kinetic typography: Pango `Text` (no LaTeX) + `Write`/`AddTextLetterByLetter`/`AddTextWordByWord`/`TypeWithCursor`/`Unwrite` | high (3-0) | [manim text guide](https://docs.manim.community/en/stable/guides/using_text.html) |
| **GLSL via ModernGL** headless: `create_context(standalone=True[,backend="egl"])`, shader→raw RGB→ffmpeg pipe | high (3-0) | [glsl-to-mp4](https://github.com/nabeel-oz/glsl-to-mp4) · [moderngl headless](https://moderngl.readthedocs.io/en/latest/techniques/headless_ubuntu_18_server.html) |
| glsl-to-mp4 **engine MIT, bundled shaders CC BY-NC-SA** (non-commercial) | high (3-0) | [glsl-to-mp4](https://github.com/nabeel-oz/glsl-to-mp4) |
| **drawsvg** (MIT) SVG→PNG/MP4 (SMIL + frame-based); **svgwrite** (MIT) SMIL classes; **python-lottie AGPLv3+** | high (3-0) | [drawsvg](https://pypi.org/project/drawsvg/) · [svgwrite](https://svgwrite.readthedocs.io/en/latest/svgwrite.html) · [lottie](https://pypi.org/project/lottie/) |

## ⚠️ Refuted

| claim | vote | note |
|-------|------|------|
| glsl-to-mp4 output is deterministic/seed-driven out of the box | 1-2 (killed) | **Determinism must be enforced by the plugin** (fix seeds/uniforms); not guaranteed by the engine. |

## 🔶 Domain knowledge (standard but not separately verified in this pass)

Used in the [ffmpeg recipes](ffmpeg-recipes.md), all standard core filters — **dry-run on this
build before wiring**: `rgbashift` (chromatic aberration/glitch), `vignette`, `displace`
(water/heat warp), `noise`, `gblur`, `blend` modes (`screen`/`average`/`difference`),
`colorbalance`/`eq`/`colortemperature` (sunrise/sunset grade). These were not the subject of a
3-vote claim but are documented FFmpeg filters in the same manual.

## Open questions (from the research, worth a follow-up)

1. Which **permissive/MIT or original GLSL shaders** best reproduce each phenomenon (fire,
   water caustics, fog, aurora, lightning, god-rays, bokeh) — since the verified bundled
   shaders are non-commercial and need replacing?
2. **Per-frame render cost** at 1080×1920 for each path (ffmpeg geq vs Manim Cairo vs ModernGL
   EGL vs Matplotlib vs bubbles) — to decide which are cheap enough to run per-scene at scale.
3. Concrete verified recipes for effects with **no standalone verified claim** yet: clouds
   drifting, falling leaves, wind sway, sunrise/sunset gradients, stars, glitch/datamosh,
   vignette, god-rays — the recipes here are domain-knowledge starting points.
4. Canonical **compositing recipe per library** (bubbles PIL, Manim transparent bg, ModernGL
   framebuffer, Lottie/SVG) — partially answered in [README → compositing](README.md#compositing-modes-how-an-effect-lands-on-a-scene).

## Build constraint (carried from repo CLAUDE.md)

This machine's ffmpeg **lacks `drawtext` (no libfreetype) and `subtitles`/`ass` (no libass)**.
All recipes here avoid those — text comes from Pillow or Manim-Pango. `geq`/`zoompan`/`xfade`/
`blend`/`overlay`/`displace`/`noise`/`rgbashift` are unaffected.
