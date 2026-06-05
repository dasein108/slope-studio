# GLSL shaders via ModernGL (headless) — fire, water, fog, aurora, rays

The most powerful family for **procedural natural phenomena** (fire, flowing water/caustics,
fog/smoke, aurora, volumetric god-rays, bokeh, complex glitch). Status 🔬 **research-only** —
real and verified to work, but needs a GPU/EGL host and careful licensing. Treat as a
later-phase plugin, not a default.

## How it works (verified)

ModernGL (MIT) creates a **headless OpenGL context** and runs a `#version 330` fragment
shader per frame on the GPU; raw RGB pixels pipe straight to an `ffmpeg` subprocess — no temp
files, constant memory. Reference implementations: `glsl-to-mp4` (engine MIT) and
`einarf/shadertoy` (run Shadertoy shaders in Python). See [`sources.md`](sources.md).

```python
import moderngl, subprocess, numpy as np
ctx = moderngl.create_context(standalone=True)              # headless; EGL backend on a server
# ... compile a #version 330 fragment shader, set uniforms (iResolution, iTime) ...
ff = subprocess.Popen(["ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24",
                       "-s","1080x1920","-r","30","-i","pipe:",
                       "-c:v","libx264","-crf","18","fx.mp4"], stdin=subprocess.PIPE)
for frame in range(int(seconds*30)):
    # set iTime uniform, vao.render(moderngl.TRIANGLES), read framebuffer:
    ff.stdin.write(fbo.read(components=3))                  # raw RGB bytes
ff.stdin.close(); ff.wait()
```
Headless on a Linux server (no X) uses the EGL backend:
```python
ctx = moderngl.create_context(standalone=True, backend="egl",
                              libgl="libGL.so.1", libegl="libEGL.so.1")
```

## What it's great for

| effect | shader approach | composite |
|--------|-----------------|-----------|
| fire / flames | animated fbm/noise + warm palette ramp | `blend=screen` over still |
| water caustics / ripple / reflection | sine/voronoi displacement + refraction | `displace` or standalone |
| fog / smoke | layered fbm noise scrolling | `blend=screen`, low opacity |
| aurora | banded sine + hue shift on black | `blend=screen` |
| god-rays / volumetric light | radial occlusion blur from a bright point | `blend=screen` |
| bokeh | bright points + circular blur kernel | `blend=screen` |

Render the fx on **black** (so `blend=screen` adds light and the black drops out) or with
alpha for `overlay`.

## ⚠️ Hard caveats (do not skip)

- **Determinism is NOT free** — the "seed-driven determinism" claim for glsl-to-mp4 was
  **refuted** in research. Pin every uniform (especially time stepping and any noise seed) to
  get reproducible output.
- **Licensing:** the **ModernGL engine is MIT**, but **bundled glsl-to-mp4 / Shadertoy shaders
  are CC BY-NC-SA 4.0 (non-commercial, share-alike).** For a commercial channel you **must
  replace bundled shaders with original or permissively-licensed ones.** Write your own
  `#version 330` fire/fog/water shaders, or use CC0/MIT shader sources.
- **GPU/EGL required.** Needs EGL + GL system libraries and ideally a real GPU; on a GPU-less
  host it falls back to software Mesa EGL (much slower). Not viable on every box.
- `einarf/shadertoy` is an inactive proof-of-concept with **no LICENSE file** — lean on
  `moderngl` itself (MIT) as the load-bearing dependency.

## When to choose this vs ffmpeg

Reach for shaders only when an [ffmpeg recipe](ffmpeg-recipes.md) can't get the look (true
volumetric fire, flowing caustics, aurora). For grain/fog/rays/ripple approximations, the
ffmpeg path is cheaper, deterministic, and GPU-free — prefer it. Put any shader behind a
`.[shaders]` extra and fall back to kenburns/ffmpeg if the GPU context fails.
