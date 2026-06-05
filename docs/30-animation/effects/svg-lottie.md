# SVG / Lottie vector animation

Programmatic vector paths for **mask reveals, shape morphs, and kinetic typography** as
standalone clips. Status 🔬/🧪. For most vector needs **Manim is the better-integrated path**
([manim-effects.md](manim-effects.md)) since it's already wired — use SVG/Lottie only when you
specifically want SVG/SMIL output or a designer's Lottie JSON.

## drawsvg (MIT) — recommended SVG path

`drawsvg` programmatically builds SVG and renders to **PNG / MP4 / GIF** via Cairo. Supports
both **SMIL** declarative animation (`Animate`, `AnimateMotion`, `AnimateTransform`) and
**frame-based** animation (`frame_animate_video`, spritesheet). MIT-licensed.

```python
import drawsvg as draw
d = draw.Drawing(1080, 1920, origin="center")
circle = draw.Circle(0, 0, 200, fill="teal")
circle.append_anim(draw.Animate("r", "2s", from_or_values="0;200", repeatCount="1"))
d.append(circle)
# d.save_svg(...) or render frames → mp4 (needs system Cairo, not pip-only)
```
Use for mask/clip-path reveals and simple shape morphs. Needs a **system Cairo** install
(like Manim). Add behind a `.[svg]` extra.

## svgwrite (MIT) — declarative SMIL authoring

`svgwrite` gives Python classes for SMIL elements: `Set`, `Animate`, `AnimateColor`,
`AnimateMotion`, `AnimateTransform`. It **writes SVG only** — you still need a renderer
(`cairosvg`/`drawsvg`) to rasterize to frames/MP4. Good for generating animated SVG you then
convert.

## python-lottie — ⚠️ AGPLv3, avoid for commercial

`python-lottie` builds Lottie animations and exports MP4/GIF/SVG/PNG/WebM (video export needs
`cairosvg`+`numpy`+OpenCV). **But it is AGPLv3+ (strong copyleft)** — embedding/distributing it
in a commercial channel pipeline carries source-disclosure obligations. **Avoid** unless you
accept AGPL; prefer drawsvg/svgwrite (MIT) or Manim.

It's still the tool if you have **designer-made Lottie JSON** (from After Effects/LottieFiles)
you want to rasterize — but isolate it (e.g. a separate one-off conversion step), don't bake it
into the shipped pipeline.

## Decision

| need | pick |
|------|------|
| any vector morph / typography / diagram | **Manim** (wired, MIT) — [manim-effects.md](manim-effects.md) |
| SVG/SMIL output or path-precise reveals | **drawsvg** (MIT) |
| rasterize existing Lottie JSON | python-lottie (AGPL — isolate, non-commercial only) |

## Compositing

All render to standalone clips/frames → `normalize` to 1080×1920 and treat like any animator
output, or render transparent and `overlay`. Length-neutral; narration sync unaffected.
