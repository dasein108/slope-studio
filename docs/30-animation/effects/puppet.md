# Puppet — free cutout animation (moving figure, shake head)

Naive "paper-puppet" motion of an **illustrated figure**, free and deterministic — the
South Park / Monty Python trick. `rembg` cuts the figure out of the still; we move it over a
blurred copy of the same still (so the static "ghost twin" recedes). **Wired** as
`animator:"puppet"`.

This fills the gap between camera-only animators (kenburns/parallax move the *frame*, not the
figure) and paid i2v: a drawn character that actually **bobs, sways, hops, or shakes its
head** — at $0.

## Modes (picked from `motion_hint` keywords)

| `motion_hint` contains | mode | what moves |
|------------------------|------|-----------|
| *(default / "idle"/"sway")* | **idle** | whole figure: gentle bob + sway + tilt + breathe — keeps a character alive |
| "hop" / "jump" / "bounce" | **hop** | whole figure bounces up & down with squash/stretch |
| "shake" / "no" | **shake** | the **head region** swings left-right around the neck (shaking head "no") |
| "nod" / "yes" | **nod** | the head region bobs + tilts (nodding "yes") |
| + "headbottom" / "inverted" | *(modifier)* | head is at the BOTTOM of the figure (upside-down subject) — flips the split |

The head/body split is automatic: the figure's alpha bounding box → neck ≈ 42% from the head
end (top by default; bottom with the `headbottom`/`inverted` hint). The head rotates around
the neck pivot, the body stays put. The background is the still, **heavily blurred +
desaturated + darkened**, so the static "ghost twin" recedes and the sharp cutout pops.

```jsonc
{ "id": 4, "animator": "puppet", "motion_hint": "shake head, annoyed",
  "visual_prompt": "<character>, a man standing, facing camera, simple background" }
```

## What it's good for / not

- ✅ **moving figure** (idle life), **head shake / nod**, **hop** — on any still with a
  separable subject.
- ✅ **Per-limb moves** (hand up, wave, point) — via the `limbs` field (below).
- ✅ Works best with a **clear figure on a simple background** (rembg cuts cleanly), like
  `parallax`. Flat/busy art → weak cutout.
- ↔ For complex full-body action (walk, run) use **i2v** (cheap on a short hero clip:
  `--ai-scenes N --model ltx`, ~$0.20/5s) — it animates from the still + a prompt, no rigging.

## Per-limb articulation — `limbs`

Rotate a limb region around a joint (arm around the shoulder = "hand goes up" / "wave").
Each `Scene.limbs[*]` is a joint, **all coords as fractions of the frame (0-1)**:

```jsonc
"limbs": [
  { "box": [0.353, 0.32, 0.422, 0.60],  // TIGHT bounds of just the arm
    "pivot": [0.388, 0.34],             // the joint (shoulder) to rotate around
    "move": "raise",                    // raise|point (ramp & hold) · wave|swing (oscillate)
    "amp": 120,                         // degrees, signed (+ccw, -cw)
    "period": 0.8,                      // seconds: ramp time (raise) or cycle (wave)
    "phase": 0.0 }                      // desync multiple limbs
]
```
- **`box` must be TIGHT to the limb** — if it overlaps the torso, that strip is erased from
  the body and shows as a dark patch. Eyeball the still and bound just the arm.
- `move`: **raise**/**point** = smooth ramp 0→`amp` then hold (hand goes up & stays);
  **wave**/**swing** = oscillate ±`amp` (waving). Sign of `amp` flips direction — preview and
  adjust.
- Multiple limbs animate together; use `phase` to offset them.
- The body is static while limbs move (the limb regions are erased from it so they don't
  ghost). Preview: `python examples/make_examples.py puppet` → `puppet_raise.mp4`, `puppet_wave.mp4`.

## How it works (code)

`animate._puppet` + `ffmpeg.frames_to_video`:
1. `rembg` removes the background → transparent figure cutout.
2. Background = the still, Gaussian-blurred + darkened (hides the cut hole / ghost twin).
3. Per frame, transform the cutout (or just the head region) by a sine function of time and
   composite onto the background (Pillow `alpha_composite`).
4. Frames → silent mp4. Deterministic (no RNG). Voice/SFX added later as usual.

Dep: the parallax extra — `uv pip install -e ".[parallax]"` (provides `rembg`). If it's
missing or the cutout fails, the scene **falls back to kenburns** (manifest note) — never
breaks.

## Compare

| want | use |
|------|-----|
| frame/camera motion (pan, zoom, depth) | `kenburns` / `motion-*` / `parallax` |
| **drawn figure moves itself** (idle, hop, shake/nod head) | **`puppet`** (this, free) |
| limb-level / complex action (hand up, walk) | **i2v** (`--ai-scenes`, ~$0.20/5s) — [cost-model](../../10-architecture/cost-model.md) |
| objects/shapes/sun rising | `manim` (free, vector) |
| lip-sync narration on a face | `talkinghead` ([talking-head.md](talking-head.md)) |

## Preview / polish

Render samples to eyeball + tune:
```bash
python examples/make_examples.py puppet --frames   # → examples/out/puppet_{idle,hop,shake,nod}.mp4
```
See [`examples/README.md`](../../../examples/README.md).

## Status

✅ **Live** — `animator:"puppet"` (idle / hop / shake / nod; `headbottom` modifier). Per-limb
pivots = backlog. See [README → adding an effect](README.md#adding-an-effect).
