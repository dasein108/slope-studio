# Atmosphere overlays (`atmosphere: "rain|snow|embers|blood|petals|wind|fog"`)

A free weather/particle layer composited **on top of the already-rendered clip** —
so it works with ANY animator (parallax, slice, static, kinetic, drift…). Set the
scene field `atmosphere`; the rest is automatic.

> ⚠️ **Use it ONLY when the scene literally depicts that element.** `atmosphere`
> defaults to `""` and the **vast majority of scenes must keep it empty**. Snow only in
> an outdoor winter scene, embers only for real fire, rain only in actual rain,
> petals/leaves only outdoors among blossom, fog only for real mist. **Never** add
> particles to an indoor, portrait, studio, diagram, or neutral scene, and never "for
> mood" or decoration — falling snow in an office (or embers in a tidy room) is a bug,
> not a vibe. When in doubt, leave it empty.

```json
{"id": 1, "animator": "kinetic", "atmosphere": "rain", "visual_prompt": "...", "narration": "..."}
```

## How it works (and why it's clean)

1. `cardgen.particle_layer(kind, …)` draws the effect as **sparse opaque marks on a
   fully TRANSPARENT canvas** (2× frame height, wider than frame) — real alpha, not a
   grey noise field.
2. `ffmpeg.atmosphere(clip, layer, …)` composites it with **`overlay`** (alpha-correct),
   scrolling it vertically and swaying it sideways. Only the particles land on the
   scene — the painted art underneath is untouched.
3. `animate.render` runs this as a post-pass after the animator, recording `+rain`
   (etc.) in the manifest note. Any failure is swallowed — the clip still ships.

> **Why not a screen-blend of ffmpeg `noise`?** That washes the whole frame (tried,
> removed). The transparent-layer + `overlay` route is the fix — see the rain
> before/after in `film-maker-guides.md`.

## Kinds

| kind | look | motion | composite |
|------|------|--------|-----------|
| `rain` | thin blue-white streaks | fast fall, slight sway | overlay |
| `snow` | soft white dots | slow fall, drift | overlay |
| `embers` / `sparks` | glowing orange dots | **rise** | overlay |
| `blood` | sparse red droplets | fall | overlay |
| `petals` / `wind` / `leaves` | drifting petals/leaves | fall + strong sideways sway | overlay |
| `fog` | soft grey haze (blurred) | very slow drift | overlay |

Per-kind speed/rise/sway live in `ffmpeg._ATMO`; density/colour in
`cardgen.particle_layer`. `ffmpeg.atmosphere(..., opacity=)` scales overall strength
(default 0.85 — keep it subtle).

## Use it well

- **Keep it tasteful** (operator rule: simple, not annoying). One kind per scene,
  default opacity. Rain/fog as a throughline; `blood` only on the violent beat;
  `embers` for fire/lantern scenes; `petals` for a melancholy/turning beat.
- **Layer it with the art:** also describe the weather in the `visual_prompt` so the
  still already reads wet/foggy — the overlay then adds live motion on top.
- It's a post-pass, so it stacks on any `animator` (e.g. `parallax` + `rain`).

## Determinism

`particle_layer` is seeded by `scene.id` → same render every time. No `Math.random`.
