# Manim vector effects — usable TODAY via `manim_code`

Manim (MIT, headless via the Cairo renderer, no display server) is **already wired** as the
`manim` animator. So every effect here is **🧩 live now**: set `animator:"manim"` and paste a
`manim_code` snippet (the body of `construct()`) into the scene. No new code needed.

Deps: `uv pip install -e ".[manim]"`. The Cairo text path needs **no LaTeX**; only
`TransformMatchingTex` (equation morphs) needs a TeX install. Renders 1080×1920 @30fps; the
pipeline fits it to narration length. If manim isn't installed or the code errors, the scene
**falls back to kenburns** (recorded in the manifest note) — the pipeline never breaks.

> Indentation: `manim_code` is auto-dedented and re-indented into `construct()`, so flush-left
> or pre-indented both work (see `animate._manim`). Keep `run_time`s within the scene's seconds.

All classes below are **research-verified** present in Manim Community v0.20.1
(see [`sources.md`](sources.md)).

---

## <a id="typography"></a>Kinetic typography

Pango-rendered `Text` (system fonts, gradients, non-Latin) + dedicated reveal animations:
`Write`, `AddTextLetterByLetter`, `AddTextWordByWord`, `TypeWithCursor`,
`RemoveTextLetterByLetter`, `UntypeWithCursor`, `Unwrite`.

```python
# typewriter headline
t = Text("UNUSUAL KNOWLEDGE", font_size=72, weight=BOLD, gradient=(BLUE, TEAL))
self.play(AddTextLetterByLetter(t, run_time=1.6))
self.wait(0.4)
self.play(Unwrite(t, run_time=1.0))
```
```python
# word-by-word punch-in
t = Text("space is worse\nthan you think", font_size=64, line_spacing=1.1).set_color(WHITE)
self.play(AddTextWordByWord(t, run_time=1.4))
self.wait(0.6)
```
Use for hooks/outros and emphasis beats. (Live `kinetic` animator does a simpler
Pillow-headline slide; Manim gives true per-letter/word control.)

## <a id="morph"></a>Shape & equation morphs

`Transform` (morph A→B), `TransformMatchingShapes` (match submobject shapes),
`TransformMatchingTex` (morph rendered equations — needs TeX).

```python
# shape morph: circle → square → triangle
a = Circle(color=BLUE).scale(2)
self.play(Create(a))
self.play(Transform(a, Square(color=TEAL).scale(2)), run_time=1.0)
self.play(Transform(a, Triangle(color=YELLOW).scale(2)), run_time=1.0)
self.wait(0.3)
```
```python
# equation morph (requires .[manim] + a TeX install)
e1 = MathTex("a^2 + b^2"); e2 = MathTex("c^2")
self.play(Write(e1)); self.wait(0.3)
self.play(TransformMatchingTex(e1, e2), run_time=1.2); self.wait(0.4)
```
Perfect for science/math explainer scenes (the channel niche).

## <a id="lightning"></a>Lightning / energy flash  (screen-friendly on black)

Jagged `Line` chain + a white `Flash`/brightness pulse. Render on the default black bg and
optionally `blend=screen` the clip over a still in a later pass.

```python
import random
random.seed(7)                      # determinism — see the index caveat
pts = [[-1+0.4*random.uniform(-1,1), 4-i, 0] for i in range(8)]
bolt = VMobject(stroke_width=6).set_points_as_corners(pts).set_color(WHITE)
self.play(Create(bolt, run_time=0.18))
self.add(Dot(pts[-1], color=WHITE).scale(3))
self.play(Flash(pts[-1], color=WHITE, flash_radius=1.2, run_time=0.5))
self.play(FadeOut(bolt, run_time=0.3))
```

## <a id="wind"></a>Wind sway / falling leaves / sparkles

Drive mobjects with `Rotate`, `.animate.shift`, and `MoveAlongPath`. Seed any randomness.

```python
# falling leaves: a few rotating shapes drift down with horizontal sway
import random; random.seed(3)
leaves = VGroup(*[Triangle(color=ORANGE).scale(0.2).move_to([random.uniform(-3,3), 5, 0])
                  for _ in range(10)])
self.add(leaves)
anims = [l.animate(run_time=3, rate_func=linear).shift([random.uniform(-1,1), -10, 0]).rotate(PI)
         for l in leaves]
self.play(*anims)
```
```python
# sparkle burst
self.play(*[Flash(p, color=YELLOW, run_time=0.6)
            for p in [[-2,1,0],[1.5,-1,0],[0,2,0]]])
```

---

## Transparent-background compositing (optional)

To lay a Manim effect OVER the scene still instead of using it as a standalone clip, render
with a transparent background and `.mov`/PNG-alpha, then `overlay`:

- Manim flag: `-t`/`--transparent` (outputs `.mov` with alpha) — would require a small
  variant of `animate._manim` that adds `--transparent` and composites via `ffmpeg.overlay`.
  Currently `manim` is standalone-only; this is a 🧪 enhancement (see
  [index → adding an effect](README.md#adding-an-effect)).
- Until then, prefer Manim for full-scene vector moments (morphs, typography, diagrams) and
  the [ffmpeg recipes](ffmpeg-recipes.md) for overlay-style atmospherics (grain, fog, rain).
