# Parallax (`animator: "parallax"` and `"blurred-parallax"`)

Depth illusion: a **static sharp foreground subject** in front of a **moving background**.
Two flavours:

| animator | background | use |
|----------|-----------|-----|
| **`parallax`** (default) | the REAL background, subject **removed** (inpainted), **drifts sharply** | clean "PNG figure + moving scenery" — no ghost |
| **`blurred-parallax`** | a **blurred** copy of the still, panned (1 or 2 planes) | when the background can't be cleanly recovered; blur hides the ghost twin |

Free at render time; needs the `parallax` extra. Install:
```bash
uv pip install -e ".[parallax]"     # rembg + onnxruntime (first run caches u2net ~176MB)
```

## `parallax` — TRUE parallax (the clean one)

`animate._parallax`:
1. `rembg.remove(still)` → the **sharp cut-out subject** (transparent background), held
   **static and centered** — it never moves.
2. **The subject is erased from the background** by a free blur-diffusion inpaint
   (`_inpaint_subject`: repeatedly blur, restamp the known pixels → the subject hole fills
   with the surrounding colours). On smooth backgrounds (sky, clouds, walls) this is
   invisible; on busy backgrounds it's approximate.
3. `ffmpeg.parallax_drift` scales that clean background slightly larger and **drifts it
   steadily** behind the static foreground.

Result: foreground STAYS, background MOVES — like `motion-driftright` happening *only* to
the scenery, with the subject pinned in front. **No ghost twin** (the subject isn't in the
background any more).

- **`motion_hint`** sets the drift: `right` (default) · `left` · `up` · `down`.
- Drift distance = `depth` (default `0.25` → bg scaled 25% larger; tune in `ffmpeg.parallax_drift`).

```jsonc
{ "id": 3, "animator": "parallax", "motion_hint": "right",
  "visual_prompt": "<style>, a cat in the sky with drifting clouds, one clear subject, 9:16" }
```
Best with a **clear subject over a smooth/separable background** (sky, gradient, soft
scenery) — that's where the inpaint is seamless.

## `blurred-parallax` — the soft-backdrop version (was the old `parallax`)

`animate._blurred_parallax`: the background is a **blurred** copy of the still (so the
duplicate subject becomes a soft out-of-focus backdrop), panned behind the sharp cut-out.
- **default = multi-layer:** `cardgen.depth_bands` splits the still into a TOP (sky/far)
  and BOTTOM (ground/near) plane that pan in **opposite** directions (`ffmpeg.parallax_layers`)
  — "sky one way, mountains the other".
- **`motion_hint:"single"`/`"flat"`** = one heavily-blurred plane (`ffmpeg.parallax`).

Use it when the background is busy and the inpaint would smear, or when you *want* the
dreamy anime depth-of-field look. It tolerates any still (the blur hides the ghost).

## Layered parallax (the "two backgrounds" idea)

True multi-plane depth = a foreground + **several background planes drifting at different
rates** (the far sky moves +1, nearer clouds move +2, same or opposite direction). The eye
reads the rate difference as distance.

- `blurred-parallax` already does a **2-plane** version (sky vs ground, opposite directions).
- For the **clean** `parallax`, full multi-plane needs the background separated into sub-layers
  (sky / clouds / hills), which can't be done automatically from one flat still. **To get it
  today:** supply those planes as separate transparent PNGs and compose them — a documented
  **backlog** extension (`parallax_drift` already takes a `depth` knob per plane). Until then,
  single-plane `parallax` (foreground static + one clean drifting background) covers most needs.

## Robustness & tuning

- If `rembg` is missing or segmentation fails, `animate.render` falls back to `kenburns`
  (recorded in the manifest note) — the pipeline never breaks.
- Tune `parallax_drift`: `depth` (pan room → drift distance), `direction`. Tune the inpaint:
  `_inpaint_subject` `iters`/`radius` (more = smoother fill, slower).
- Preview both: `python examples/make_examples.py parallax` and `… blurred-parallax`.
