# Animation & Transitions

Free, context-driven motion + transitions, controlled per-scene from the scenario
JSON. No paid video models. Choose the right tool per scene; the pipeline keeps
everything synced to the narration.

## Guides

- [`scenario-schema.md`](scenario-schema.md) — **authoritative `01_script.json` schema** (read this to author scenes correctly)
- [`transitions.md`](transitions.md) — per-scene transition vocabulary + when to use each
- [`motion.md`](motion.md) — `motion-*` presets (pan/zoom/drift/pulse) on a still
- [`kinetic.md`](kinetic.md) — kinetic-typography (animated headline over a background)
- [`parallax.md`](parallax.md) — 2.5D depth: `parallax` = static sharp subject + REAL bg drift (subject inpainted out); `blurred-parallax` = older blurred-panning-planes look
- [`slice.md`](slice.md) — diagonal-cut reveal (two halves offset, then slide together)
- [`effects/puppet.md`](effects/puppet.md) — `puppet`: free cutout animation (drawn figure bobs/hops/shakes head; rembg over a blurred bg)
- [`effects/talking-head.md`](effects/talking-head.md) — `talkinghead`: 2D lip-sync (static face, mouth moves with narration via Rhubarb)
- [`manim.md`](manim.md) — true vector animation (Flash-style) via Manim code per scene
- [`effects/`](effects/README.md) — **effects index**: the full catalog of free programmatic/vector effects (rain, snow, fire, fog, sunrise, water, grain, glitch, god-rays, morphs, kinetic type…), each with status, technique, recipe, and license
- [`captions.md`](captions.md) — burned sentence captions (tight-fit, safe-area placement)
- [`voices.md`](voices.md) — narrator voice (man/woman/cartoon/narrator) + tone (mystical/serious/friendly/sad/…)

## Per-scene fields (set in each scene of `01_script.json`)

| field | example | effect |
|-------|---------|--------|
| `animator` | `"kinetic"` | how the free clip is made (default `kenburns`) |
| `transition` | `"wipeleft"` | transition INTO this scene (default `cut`) |
| `transition_dur` | `0.5` | seconds for that transition (default 0.4) |
| `manim_code` | `"…"` | Manim `construct()` body (only for `animator:"manim"`) |
| `motion_hint` | `"slow push-in"` | free-text hint (used as i2v prompt; informs preset choice) |
| `priority` | `3` | hero weight for `auto` AI-video budgeting |

## Animator decision matrix

| animator | deps | best for | look |
|----------|------|----------|------|
| `kenburns` | none | any still, default | gentle pan/zoom |
| `motion-driftright/left/up/down` | none | directional emphasis, "next…" | parallax-ish pan |
| `motion-zoomin` / `motion-zoomout` | none | reveal / pull-back | push/pull |
| `motion-pulse` | none | energy, beats | breathing scale |
| `kinetic` | Pillow (bundled) | text-free backgrounds (illustrations) | motion-graphics headline |
| `parallax` | `pip install .[parallax]` | a clear subject over smooth scenery | TRUE parallax: static sharp subject, REAL background drifts (subject inpainted out → no ghost). [parallax.md](parallax.md) |
| `blurred-parallax` | `pip install .[parallax]` | busy bg / dreamy depth | static subject over a BLURRED panning bg (1–2 planes). [parallax.md](parallax.md) |
| `slice` | none | reveal / entrance / **beheading** | diagonal, or horizontal/vertical split (+ optional red flash) |
| `static` | none | calm/severe beat | a true held still, NO motion (better than a twitchy zoom) |
| `puppet` | `pip install .[parallax]` (rembg) | a drawn figure that should MOVE (idle, hop, shake/nod head) | cutout puppet over blurred bg — the figure itself moves, free. [effects/puppet.md](effects/puppet.md) |
| `talkinghead` | `rhubarb` binary | a narrating face / avatar | static face + mouth lip-syncs the narration (2D viseme swap). [effects/talking-head.md](effects/talking-head.md) |
| `manim` | `pip install .[manim]` | **educational/scientific ONLY** — diagrams, math, graphs | vector animation (Flash). NOT for art/story (schematic look breaks immersion) |
| `fal-i2v` | `FAL_KEY` ($) | true AI motion (paid, per-second) | real video |

`animator` applies to **free** scenes. AI scenes (via `--strategy all/auto/hybrid`)
use `fal-i2v` instead. Mix freely: most scenes `kenburns`/`motion-*`, a few diagram
scenes `manim`, hero scene `fal-i2v`. See [`../10-architecture/cost-model.md`](../10-architecture/cost-model.md).

**Want more (rain, fire, fog, sunrise, water, grain, glitch, god-rays, morphs, kinetic
type)?** The above are the **wired** animators; the [`effects/`](effects/README.md) index
catalogs the full research-backed effect library. Some are usable today (via `manim_code`),
others are documented recipes on the backlog — **read the status legend there before setting
an unlisted `animator`** (unknown names fall back to `kenburns`).

## Pairing rules (important)

- **`kinetic` needs a text-free background.** The `card` image provider bakes the
  headline into the image, so `kinetic` over a card double-renders the text. Pair
  `kinetic` with `fal-nanobanana` illustrations (or a future plain-card variant).
- **`parallax` needs a separable subject.** Flat/abstract images give weak depth.
- **`manim` ignores the still** — it renders its own vector scene. Use for diagrams.

## Sync guarantee

Transitions are **overlap-compensated** in `ffmpeg.concat_xfade_seq`: each non-last
clip is pre-extended by its transition duration so the stitched video length ==
sum of clip durations == narration length. No drift, no truncation. (Verified:
stitched within ~0.02s of narration.) See [`transitions.md`](transitions.md#sync).
