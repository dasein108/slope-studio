# Parallax (`animator: "parallax"` and `"blurred-parallax"`)

Depth illusion: **perspective scenery whose distance planes drift at different speeds** (far
slow, near fast) → real 2.5D depth.

> 🚫 **OPERATOR RULE — parallax is for PERSPECTIVE / DEPTH scenery (mountains, clouds, a
> skyline, houses, a road), NOT a big foreground subject.** A frame that a human, animal, face,
> or one single object DOMINATES (takes most of the space) has no depth to reveal and floats as
> a flat cutout — it looks worse, not better. Big/close subject → `static`, `slice`, or
> `motion-drift*`. A *small* figure inside a wide landscape is fine (it's just the nearest
> plane). Compose the still as foreground → midground → horizon, not a portrait of one thing.

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

`animate._parallax` picks the best layer source available, in priority order:

1. **Two real plates (gold).** If a transparent `scene_NN_fg.png` (subject keyed out) AND a
   clean `scene_NN_bg.png` (subject re-rendered out) both exist, it composites those two
   REAL images directly via `ffmpeg.parallax_drift` — **zero inpaint, zero tear**. This is
   the balanced+ default: `studio run` (and `studio visuals --parallax-plates
   --parallax-fg`) generate both plates for every `parallax` scene.
2. **Scenery → SHARP 2-plane depth.** A scene with `image_role:"bg"` (skyline, landscape,
   cosmos — *no* separable subject) is **never** subject-inpainted. It's split into two
   feathered depth bands (`cardgen.depth_bands`) that pan in **opposite directions at
   different speeds** (`ffmpeg.parallax_scenery`) → real visible 2.5D depth, kept crisp.
   This is NOT a flat full-frame pan (that read as plain drift — the old behavior). For the
   *soft/blurred* depth look, ask for `blurred-parallax` explicitly.
3. **Clean cut + auto-inpaint (no plates).** Only when `rembg` finds a **single compact
   subject** (gate `_clean_subject`: rejects thin verticals like minarets, edge-hugging
   masks touching 3+ borders, and fragmented masks). It cuts the subject, erases its hole
   from the background by free blur-diffusion (`_inpaint_subject`), and drifts the filled
   plane behind the static subject.
4. **Last resort → sharp drift.** Anything that fails the gate drifts the whole sharp still
   — never a torn frame or smear column.

Result for a real subject: foreground STAYS, background MOVES, **no ghost twin**. The gate
is what killed the old failure mode — a tall minaret on a busy skyline used to pass as a
"subject", get inpainted, and tear into a smeared vertical seam.

- **`motion_hint`** sets the drift: `right` (default) · `left` · `up` · `down`.
- Drift distance = `depth` (default `0.25` → bg scaled 25% larger; tune in `ffmpeg.parallax_drift`).

```jsonc
{ "id": 3, "animator": "parallax", "motion_hint": "right", "image_role": "hero",
  "visual_prompt": "<style>, a cat in the sky with drifting clouds, one clear subject, 9:16" }
```
Best with a **clear single subject** (person, animal, statue). Pure scenery with no subject
gets the sharp drift instead (or use `blurred-parallax` for soft depth).

## `blurred-parallax` — the soft-backdrop version (was the old `parallax`)

`animate._blurred_parallax`: the background is a **blurred** copy of the still (so the
duplicate subject becomes a soft out-of-focus backdrop), panned behind the sharp cut-out.
- **default = multi-layer:** `cardgen.depth_bands` splits the still into a TOP (sky/far)
  and BOTTOM (ground/near) plane that pan in **opposite** directions (`ffmpeg.parallax_layers`)
  — "sky one way, mountains the other".
- **`motion_hint:"single"`/`"flat"`** = one heavily-blurred plane (`ffmpeg.parallax`).

Use it when the background is busy and the inpaint would smear, or when you *want* the
dreamy anime depth-of-field look. It tolerates any still (the blur hides the ghost).

## Layered parallax — AIM FOR 2–3 PLANES (the quality target)

True multi-plane depth = a foreground + **one or two background planes drifting at different
rates** (the far sky moves +1, nearer hills/clouds move +2, same or opposite direction). The
eye reads the rate difference as distance — it's the most premium *free* look in the kit, so
when a beat deserves depth, **invest in layers instead of a flat single drift.**

**Quality bar:** every `parallax` scene should be **at least 2 clean planes**; reach for **3
on the hero / establishing shot.** All planes must be REAL images (plates), never one torn
still.

- **2 planes (standard, balanced+ default):** static foreground subject + a clean,
  separately-rendered background → `studio visuals --parallax-plates --parallax-fg`. Two real
  images, **no inpaint, no tear**. This is the floor for a quality parallax scene.
- **3 planes (premium reach):** add a **midground** so far/mid/near move at three rates (sky
  slow, hills medium, subject static). Author the extra plane as its own transparent PNG and
  compose it — `ffmpeg.parallax_drift` already takes a per-plane `depth` knob. (Auto-splitting
  one flat still into sky/hills/foreground sub-layers is a **backlog** extension; until it
  lands, hand-author the third plane on the shots that earn it.)
- **Free 2-plane shortcut for scenery:** `blurred-parallax` already drifts a TOP (sky/far) and
  BOTTOM (ground/near) plane in opposite directions — use it when you want soft layered depth
  fast and don't need a sharp keyed subject.

Don't ship a flat single-image drift where a layered parallax was achievable — that's the
difference between "a still that pans" and "a scene with depth".

## Robustness & tuning

- If `rembg` is missing or segmentation fails, `animate.render` falls back to `kenburns`
  (recorded in the manifest note) — the pipeline never breaks.
- Tune `parallax_drift`: `depth` (pan room → drift distance), `direction`. Tune the inpaint:
  `_inpaint_subject` `iters`/`radius` (more = smoother fill, slower).
- Preview both: `python examples/make_examples.py parallax` and `… blurred-parallax`.
