# examples — effect sample renders (polish loop)

Render a sample clip for each animator/effect so you can **eyeball and polish** them before
using in production. Re-run after tweaking an animator to see the change.

```bash
source .venv/bin/activate
python examples/make_examples.py puppet --frames     # one effect, all variants + preview PNGs
python examples/make_examples.py                     # every registered effect
python examples/make_examples.py puppet --src path/to/figure.png --seconds 3
python examples/build_index.py                       # → ./index.html (inline-video gallery)
```

**Gallery:** `python examples/build_index.py` regenerates `./index.html` at the repo root — a
single page with an inline player for every effect/variant, so you can review them all at once.
Open it in a browser. (`index.html` and `examples/out/` are gitignored — local preview built
from the rendered clips.)

- **Output:** `examples/out/<effect>_<variant>.mp4` (+ `_a/_b/_c.png` preview frames with
  `--frames`: start / mid / late, so motion is visible in stills). Watch the mp4:
  `mpv examples/out/puppet_idle.mp4` or open in QuickTime.
- **Source still:** `examples/assets/sample_figure.png` by default — a clear figure on a
  simple background (best for cutout/parallax). Override with `--src`.
- `out/` and `assets/*.png` are gitignored media; this script + README are committed.

## Registered effects (`EFFECTS` in `make_examples.py`)

| effect | variants | notes |
|--------|----------|-------|
| `puppet` | idle · hop · shake · nod | free cutout motion (rembg). shake/nod assume an **upright** figure |
| `atmosphere` | rain · snow · embers · fog | overlay post-pass on a kenburns base |
| `slice` | diag · horizontal | reveal / beheading cut |
| `parallax` | layers | 2.5D depth |
| `motion` | driftright · zoomin | zoompan presets |
| `kinetic` | headline | typographic headline |
| `static` | hold | held still |
| `manim` | sunrise | vector (needs `.[manim]`) |
| `talkinghead` | lipsync | 2D lip-sync (needs `rhubarb`; TTS auto-synthed) |

## Per-effect polish notes (from the review loop)

| effect | verdict | prod note |
|--------|---------|-----------|
| `puppet` idle/hop | ✅ good | breathe + squash/stretch; strong bg blur/desat hides the ghost twin |
| `puppet` shake/nod | ✅ good | assume an **upright** figure (head at top); add `headbottom` to the hint if inverted |
| `puppet` raise/wave (limbs) | ✅ good | the limb `box` must be **TIGHT to the limb** — overlap the torso and you erase a dark patch |
| `atmosphere` rain | ✅ fixed | density boosted 300→900 + higher alpha so it actually reads (was near-invisible) |
| `atmosphere` snow/embers/fog | ✅ ok | snow density bumped too; embers/fog read fine |
| `parallax` | ✅ rebuilt | now TRUE parallax: static sharp subject + REAL background drifts; the subject is **inpainted out** of the bg → no ghost (verified on a frame-filling cat). Best over smooth scenery |
| `blurred-parallax` | ✅ ok | the old soft-backdrop look (blurred panning planes) — for busy backgrounds / dreamy depth |
| `talkinghead` | ✅ good | needs a real face + `mouth_xy` on the mouth (the demo uses the drawn person) |
| `slice` / `motion` / `kinetic` / `static` / `manim` | ✅ ok | render correctly |

## Polish workflow

1. `python examples/make_examples.py <effect> --frames`
2. Watch the mp4 / inspect the preview frames.
3. Tweak the animator in `studio/animate.py` (or its `ffmpeg.py`/`cardgen.py` helpers).
4. Re-run step 1 — repeat until prod-ready.
5. Add new variants by editing the `EFFECTS` dict.
