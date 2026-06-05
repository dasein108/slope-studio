# Manim vector animation (`animator: "manim"`)

True programmatic vector animation — the closest thing to old-school Flash, and ideal
for diagrams, math, schematics, and explainer graphics. Free at render time (CPU);
needs the `manim` extra. Implemented in `animate._manim`.

## Install

```bash
uv pip install -e ".[manim]"     # manim community edition
# system deps (usually present on macOS via Homebrew): cairo, pango, ffmpeg
```
Verify: `manim --version`.

## How it works

`animate._manim` wraps your code in a `Scene`:

```python
from manim import *
class StudioScene(Scene):
    def construct(self):
        <your manim_code, indented 8 spaces>
```

then renders `manim render -qm --format mp4 --fps 30 --resolution 1080,1920`. The
output mp4 is copied to the scene clip and fit to the narration length in `clips`
(hold/trim). The still image is **ignored** — manim draws its own scene.

## Authoring `manim_code` (per scene)

Put the **body of `construct()`** in the scene's `manim_code` field. Rules:
- It runs inside `from manim import *` (so `Text`, `Circle`, `Arrow`, `self.play`, etc. are available).
- **Indentation: author FLUSH-LEFT** (no leading whitespace). `animate._manim`
  dedents any common indent and re-indents uniformly to the `construct()` body
  level, so flush-left or consistently-indented both work — but mixed indentation
  (flush-left first line + indented rest) is the one thing to avoid. Flush-left is
  safest. (This used to cause silent `kenburns` fallbacks; now normalized.)
- Combine motion + spin in ONE animation via chained `.animate`, e.g.
  `self.play(sil.animate.move_to([7.5,-3,0]).rotate(-4*PI), run_time=2.3, rate_func=linear)`.
- Keep total animation roughly the scene length (it's fit afterward, but matching avoids long holds).
- Use a dark or transparent background (default Manim bg is near-black) — design captions/headline around it.
- **Make effects LITERAL, not abstract.** A minimalist "two lines + a dot" reads as
  strange. Draw the real environment + a real silhouette + a punchy color cue.

### Example — the "rolling head" slash (literal vector action)

A perspective **stone path** (trapezoid `Polygon` + grey `Ellipse` stones), a quick
**red flash** (`Rectangle`, opacity 0→0.6→0), then a **head silhouette** (`Circle`
+ topknot, dark fill / red stroke) that **rolls across the screen**
(`.animate.move_to(...).rotate(-4*PI)`). Copy the full `manim_code` from scene 9 of
`runs/diplomacy/01_script.json`.

### Example — hyperbolic triangle (angles < 180°)

```json
{
  "id": 7, "animator": "manim", "transition": "circleopen", "transition_dur": 0.6,
  "on_screen_text": "ANGLES < 180°",
  "narration": "On a saddle, a triangle's angles add up to less than 180 degrees.",
  "visual_prompt": "(ignored by manim)",
  "manim_code": "tri = Polygon([-2,-1,0],[2,-1,0],[0,2,0], color=TEAL)\n        self.play(Create(tri), run_time=1.2)\n        label = MathTex(r\"\\alpha+\\beta+\\gamma < 180^\\circ\", font_size=60).next_to(tri, DOWN)\n        self.play(Write(label), run_time=1.2)\n        self.play(tri.animate.set_fill(TEAL, opacity=0.3))\n        self.wait(0.8)"
}
```

### Default (no `manim_code`)

If `manim_code` is empty, a built-in template animates `on_screen_text` as a title
plus a moving dot — fine as a placeholder, but author real `manim_code` for value.

## When to use

- Geometry / math / physics explainers (perfect for the Lobachevsky theme).
- Flowcharts, graphs, number lines, equations, step-by-step diagrams.
- A few diagram scenes mixed with `kenburns`/`kinetic` illustration scenes.

## Robustness & performance

- Any failure (manim missing, code error, no mp4) → `animate.render` falls back to
  `kenburns` and records `manim->kenburns (fallback: …)` in the manifest. Pipeline never breaks.
- Render is CPU-bound and slower than other animators (seconds–minutes per scene at
  `-qm`). Use `-ql` for drafts by editing `animate._manim` if needed.
- LLM workflow: an LLM can generate `manim_code` per scene from `visual_prompt`/
  `narration` — instruct it to emit only the `construct()` body following the rules above.

## Tuning

Edit `animate._manim`: quality flag (`-qm`/`-ql`), resolution, fps, timeout, or the
`_MANIM_TEMPLATE` / `_MANIM_DEFAULT`.
