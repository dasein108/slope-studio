# Python particle systems → PIL / overlay

Pure-Python particle effects (rain, snow, embers, dust, leaves) rendered **headless** to
images, then composited onto the scene still. Status 🧪 — recipes ready, not yet wired into
`animate.py`.

**Determinism:** all of these are RNG-driven — **fix the seed** (`np.random.seed(...)` /
`random.seed(...)`) in the plugin or the effect changes every render. (Research explicitly
**refuted** "determinism for free" — see [`sources.md`](sources.md).)

---

## <a id="rain"></a>Matplotlib rain  (BSD — verified)

The official Matplotlib "rain simulation" gallery example: ~50 scatter points whose size
grows and opacity fades each frame, oldest respawns. Matplotlib is BSD; renders headless via
the **Agg** backend + the ffmpeg writer (no display).

```python
import numpy as np, matplotlib
matplotlib.use("Agg")                       # headless
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

def render_rain(dst, seconds=4, fps=30, n=50, seed=0):
    np.random.seed(seed)                    # determinism
    fig = plt.figure(figsize=(10.8, 19.2), dpi=100); ax = fig.add_axes([0,0,1,1])
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off"); fig.patch.set_facecolor("black")
    drops = np.zeros(n, dtype=[("pos",float,2),("size",float),("alpha",float)])
    drops["pos"] = np.random.uniform(0,1,(n,2)); drops["size"]=np.random.uniform(2,8,n)
    scat = ax.scatter(drops["pos"][:,0], drops["pos"][:,1], s=drops["size"], c="white")
    def update(_):
        drops["pos"][:,1] -= 0.04; drops["alpha"] = np.clip(drops["alpha"]+0.02,0,1)
        off = drops["pos"][:,1] < 0
        drops["pos"][off,1] = 1.0; drops["pos"][off,0] = np.random.uniform(0,1,off.sum())
        scat.set_offsets(drops["pos"]); return scat,
    anim = FuncAnimation(fig, update, frames=int(seconds*fps), interval=1000/fps, blit=True)
    anim.save(dst, writer="ffmpeg", fps=fps, savefig_kwargs={"facecolor":"black"})
```
Output is white rain on black → composite with `blend=all_mode=screen` (black drops out).
See [ffmpeg rain compositing](ffmpeg-recipes.md#rain). Dep: `matplotlib` (add a `.[fx]` extra).

## <a id="snow"></a>bubbles → PIL  (MIT — verified)

`bubbles` is a small MIT particle system whose `ImageEffectRenderer` draws particles directly
onto a **PIL `Image`** — fully headless, frame-by-frame, no pygame window. Best fit for
snow/embers/dust/sparkle layers.

```python
from PIL import Image
from bubbles.renderers.image_effect_renderer import ImageEffectRenderer
from bubbles import ParticleEffect

def render_snow(dst, seconds=4, fps=30, seed=0):
    effect = ParticleEffect.load_from_dict({...})   # configure emitter: white, slow fall, sway
    renderer = ImageEffectRenderer()
    for i in range(int(seconds*fps)):
        effect.update()
        frame = Image.new("RGBA", (1080,1920), (0,0,0,0))
        renderer.render_effect(effect, frame)
        frame.save(f"/tmp/snow/{i:04d}.png")
    # then: ffmpeg -framerate fps -i /tmp/snow/%04d.png snow_layer.mov (RGBA)
```
RGBA frames → composite with `overlay` (alpha preserved). Dep: `bubbles` + `pillow`
(Pillow already a core dep).

> `bubbles` and `lepton` are dormant projects (low maintenance) — fine to use, but pin the
> version and keep the asset-free ffmpeg fallback ([rain/snow streaks](ffmpeg-recipes.md#rain)).

## Leaves, embers, dust

Same `bubbles` pattern with different emitter config: leaves = larger sprites + rotation +
horizontal sway; embers = warm color + upward velocity + `blend=screen`; dust = tiny, slow,
very low opacity. For rotating leaves, Manim is often simpler — see
[manim wind/leaves](manim-effects.md#wind).

## Why not Lepton / pygame?

`lepton` is high-performance but **requires an OpenGL context** and ships only GL/pygame
renderers — none writes an image file directly, so it needs extra headless glue (dummy SDL
driver + `pygame.image.save`). For a strictly headless plugin, **`bubbles` (PIL) and
Matplotlib (Agg) are the clean paths.** GPU particle scale → use a [GLSL shader](shaders.md).

## Compositing summary

| layer output | ffmpeg composite |
|--------------|------------------|
| white-on-black (Matplotlib) | `[base][fx]blend=all_mode=screen:all_opacity=…` |
| RGBA (bubbles PNG/mov) | `[base][fx]overlay` |
| warm embers on black | `blend=all_mode=screen` (add glow) |

Layers are length-neutral overlays → the narration-sync guarantee is unaffected.
