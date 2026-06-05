# Diagonal slice reveal (`animator: "slice"`)

A dramatic "sword-cut" reveal: the still is cut along the top-left→bottom-right
diagonal into two triangles that start **offset apart** (along the cut's
perpendicular, over a black gap), then **slide together** to form the whole image,
then hold. Free (Pillow + ffmpeg), $0. The operator's preferred replacement for a
flat hard cut.

## How it works

- `cardgen.split_halves(src, out_a, out_b, axis=…)` — Pillow masks the still into two
  complementary PNGs. `axis`: `diag` (upper-right / lower-left triangles),
  `horizontal` (top / bottom), `vertical` (left / right). (`ImageOps.fit` covers the
  1080×1920 frame first.)
- `ffmpeg.diag_slice(half_a, half_b, dst, seconds, axis=…, red_flash=…)` — overlays
  both over a dark base, offset apart along the cut's perpendicular, converging to
  `(0,0)` over `split_dur`, then static. `red_flash=True` pulses a red full-frame
  layer at the cut.
- Orchestrated by `animate._slice`, which reads `motion_hint`.

## Author it

`motion_hint` keywords pick the variant:
- *(default)* **diagonal reveal** — a character's entrance, a reversal.
- `"horizontal"` → **top/bottom split** — the beheading / a hard impact.
- `"vertical"` → left/right split.
- `"flash"` or `"red"` → add a **red flash** at the cut.

```json
// dramatic reveal
{"id": 4, "animator": "slice", "transition": "fadeblack",
 "motion_hint": "imposing reveal",
 "visual_prompt": "<style>, a tall composed samurai, silhouette against pale sky, 9:16"}

// the beheading — screen splits horizontally + red flash
{"id": 9, "animator": "slice", "transition": "cut",
 "motion_hint": "horizontal red flash",
 "visual_prompt": "<style>, extreme close-up of a stern face, deep red background"}
```

Pair with `transition:"cut"`/`"fadeblack"`; the slice IS the moment.

## Tuning

`ffmpeg.diag_slice`: `axis`, `red_flash`, `split_dur` (converge time, default 0.7s),
`offset` (how far apart the halves start, default 160px). Bigger offset / longer
split = more dramatic. Masks live in `cardgen.split_halves`.

## Robustness

Any failure (Pillow/ffmpeg) → `animate.render` falls back to `kenburns`. Pipeline
never breaks.
