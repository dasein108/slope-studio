# FFmpeg effect recipes (asset-free, build-portable)

Pure filtergraphs — no extra Python deps, no GPU. The most portable effects path. Each
recipe is a `-filter_complex` you wrap in a `studio/ffmpeg.py` helper (all ffmpeg shelling
lives there). Most run as a **post-pass on the ken-burns clip**, so they compose onto any
scene without a dedicated animator branch.

**Verification:** `geq`, `zoompan`, `xfade`, and the film-grain recipe are research-verified
(see [`sources.md`](sources.md)). `rgbashift`/`vignette`/`displace`/`noise`/`gblur`/`blend`
are standard core filters (domain knowledge) — **dry-run once on this build** before wiring
(this machine's ffmpeg is missing only `drawtext`/`libass`, not these).

Conventions below: `IN` = input still or clip, `S=1080x1920`, `D` = seconds, `FPS=30`.

---

## <a id="sunrise"></a>Sunrise / sunset / golden-hour  🧪 color-grade

Ramp a warm tint + brightness across the clip. Cleanest with `colorbalance`+`eq` animated
by time (`t`), or a `geq` warm-gradient overlay. No assets.

```bash
# warm up over the clip: shadows→amber, lift midtones, gentle vignette
-i IN -vf "format=rgb24,
  colorbalance=rs=0.1:gs=0.02:bs=-0.12:rm=0.15:bm=-0.1,
  eq=brightness='0.02+0.06*t/D':saturation='1.0+0.25*t/D',
  vignette=PI/5" -t D
```
Sunset = invert the time ramp (warm→cool) or run `t→(D-t)`. For a literal sun-glow, add a
radial warm gradient via `geq` (see [god-rays](#godrays)) blended `screen`.
Helper: `def golden_hour(src, dst, seconds, direction="sunrise")`.

## <a id="fog"></a>Fog / mist / haze  🧪 screen

Animate a low-frequency noise veil, blur it heavily, and `screen`-blend (lightens) over the
base — drifting it sideways reads as moving mist.

```bash
-i IN -filter_complex "
  color=c=white:s=1080x1920:r=30:d=D[w];
  [w]geq=lum='128+80*sin((X+T*40)/120)*cos((Y-T*25)/160)':cb=128:cr=128,
     gblur=sigma=60,format=gray[veil];
  [0:v][veil]blend=all_mode=screen:all_opacity=0.35" -t D
```
Lower `all_opacity` for thin haze. Helper: `def fog(src, dst, seconds, density=0.35)`.

## <a id="grain"></a>Film grain / dust / sparkle  🧪 screen — VERIFIED recipe

Research-verified asset-free grain: random noise at scale, shaped, then composited. Source:
the "ultimate film grain" gist (see [`sources.md`](sources.md)).

```bash
# generate grain then screen it over the base
-i IN -filter_complex "
  color=black:s=1080x1920:r=30:d=D,
    geq=lum_expr='random(1)*256':cb=128:cr=128,
    deflate=threshold0=15,dilation=threshold0=10,eq=contrast=3,
    scale=1080:1920[g];
  [0:v][g]blend=all_mode=screen:all_opacity=0.12" -t D
```
- **Sparkle/embers:** raise `eq=contrast`, lower opacity, tint the grain warm (`colorbalance`)
  and add a slow upward drift (`crop` pan) before blending `screen`.
- **Dust motes:** same grain, very low opacity, large `dilation`, slow drift.
- The simple alternative is `noise=alls=18:allf=t` straight on the clip (TV-static grain).

Helper: `def grain(src, dst, seconds, opacity=0.12, warm=False)`.

## <a id="vignette"></a>Vignette  🧪 color-grade

```bash
-i IN -vf "vignette=angle=PI/5" -t D          # static
-i IN -vf "vignette='PI/5+0.1*sin(2*PI*t/4)'" -t D   # breathing
```
Pairs with grain for a cinematic look. Helper: `def vignette(src, dst, seconds, amount=...)`.

## <a id="chroma"></a>Chromatic aberration  🧪 color-grade

Shift the R/B channels apart with `rgbashift` — subtle = filmic, strong = glitch.

```bash
-i IN -vf "rgbashift=rh=6:bh=-6" -t D                 # static split
-i IN -vf "rgbashift=rh='6*sin(2*PI*t/2)':bh='-6*sin(2*PI*t/2)'" -t D  # pulsing
```
Helper: `def chroma_shift(src, dst, seconds, px=6)`.

## <a id="glitch"></a>Glitch / datamosh  🧪 standalone

Combine channel shift + bursty noise + frame-blend stutter, gated to short bursts with
`enable='between(t,…)'`.

```bash
-i IN -vf "
  rgbashift=rh='if(lt(mod(t,1.5),0.12),14,0)':bh='if(lt(mod(t,1.5),0.12),-14,0)',
  noise=alls='if(lt(mod(t,1.5),0.12),40,0)':allf=t" -t D
```
Add `tblend=all_mode=difference` on a split for a heavier mosh. Helper: `def glitch(...)`.

## <a id="flash"></a>Flash / impact  ✅ overlay — `fx:["flash-…"]`

A full-frame **colour punch** that hits fast (~0.05s), holds, then fades back to normal over
a 0.3–0.8s delay. For explosions, a blood hit, fireworks, a hard cut, a "rage" beat. Wired as
`fx:["flash-white"|"flash-yellow"|"flash-red"|"flash-black"]` (bare `flash` = white).
**white/black** = quick punch; **red/yellow** hold longer (a brief palette shift) then revert.

```bash
# overlay a colour layer whose alpha rises fast, holds, then fades out
-i IN -filter_complex "
  color=c=#d11414:s=1080x1920:r=30:d=D[c];
  [c]format=rgba,fade=t=in:st=0.08:d=0.05:alpha=1,
     fade=t=out:st=0.45:d=0.75:alpha=1,colorchannelmixer=aa=0.62[fl];
  [0:v][fl]overlay=0:0" -t D
```
Pair with art/SFX for the moment: `atmosphere:"blood"` + `fx:["flash-red"]` + a `sfx` impact,
or `atmosphere:"embers"` + `fx:["flash-yellow"]` for fireworks. Tune peak alpha / hold / fade
per colour in `ffmpeg.post_fx`.

## <a id="godrays"></a>Light rays / god-rays  🔬 screen

Build a radial/striped bright beam with `geq` and `screen`-blend it; animate the angle for
moving shafts. Approximate (volumetric rays really want a shader — see [shaders.md](shaders.md)).

```bash
-i IN -filter_complex "
  color=black:s=1080x1920:r=30:d=D,
    geq=lum='200*pow(max(0,cos(atan2(Y-200,X-540)-0.6+0.05*sin(T)))\,8)':cb=128:cr=128,
    gblur=sigma=30[rays];
  [0:v][rays]blend=all_mode=screen:all_opacity=0.5" -t D
```
Tune the ray origin `(540,200)` and exponent. Helper: `def god_rays(src, dst, seconds)`.

## <a id="zoomblur"></a>Zoom-blur  🧪 standalone

Blend a sharp frame with a zoomed+blurred copy, pulsing the mix — a punch-in feel.

```bash
-i IN -filter_complex "
  [0:v]split[a][b];
  [b]scale=1188:2112,crop=1080:1920,gblur=sigma=18[bz];
  [a][bz]blend=all_mode=average:all_opacity='0.6*abs(sin(2*PI*t/2))'" -t D
```
Helper: `def zoom_blur(src, dst, seconds)`.

## <a id="water"></a>Water ripple / heat haze  🔬 displace

Warp the still by sine X/Y displacement maps (`displace` needs two map inputs). Animating
the map phase makes the surface shimmer; mask to the lower half for a "reflection".

```bash
-i IN -filter_complex "
  color=gray:s=1080x1920:r=30:d=D,geq=lum='128+18*sin((Y+T*60)/22)':cb=128:cr=128[xmap];
  color=gray:s=1080x1920:r=30:d=D,geq=lum='128+18*sin((X+T*45)/26)':cb=128:cr=128[ymap];
  [0:v][xmap][ymap]displace=edge=smear" -t D
```
For a reflection, vertically flip + ripple only `crop` of the bottom third, then `vstack`.
Caustics/realistic water want a GLSL shader. Helper: `def water_ripple(src, dst, seconds)`.

## <a id="rain"></a><a id="snow"></a>Rain / snow  🧪 overlay/screen

Two routes:
1. **Particle layer** (best look) — render with Matplotlib/`bubbles` ([particles.md](particles.md))
   to a transparent/black PNG sequence or webm, then composite:
   ```bash
   -i IN -i rain_layer.mov -filter_complex "[0:v][1:v]blend=all_mode=screen" -t D   # white rain on black
   -i IN -i snow_layer.mov -filter_complex "[0:v][1:v]overlay" -t D                  # RGBA snow
   ```
2. **Asset-free streaks** — drifting high-contrast noise, motion-blurred along the fall axis:
   ```bash
   -i IN -filter_complex "
     color=black:s=1080x1920:r=30:d=D,
       geq=lum_expr='random(1)*256':cb=128:cr=128,
       eq=contrast=8,scale=1080:2400,crop=1080:1920:0:'mod(t*900,480)',
       gblur=sigmaX=0.4:sigmaY=8[rain];
     [0:v][rain]blend=all_mode=screen:all_opacity=0.25" -t D
   ```
   Snow = round dots (less vertical blur, slower `t*` drift, slight horizontal sway via the
   crop `x`). Helper: `def precip(src, dst, seconds, kind="rain")`.

---

### Why a post-pass beats a per-effect animator

`overlay`/`blend=screen` of a generated or asset layer composes onto **any** scene clip
(kenburns, motion, even an AI clip) without a new dispatch branch. Consider a single
`Scene.effects: ["grain","fog"]` field (post-passes applied in order after `animate.render`)
rather than one `animator` per effect — see the index's [adding-an-effect](README.md#adding-an-effect)
note. Keep each post-pass loudness/length-neutral; the narration-sync guarantee is unaffected
because these don't change clip duration.
