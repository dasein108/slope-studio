---
name: film-maker
description: >
  Operator playbook for the Slope Studio short-video pipeline. Use when the user
  wants to produce, generate, render, run, debug, observe, or publish a short
  vertical video (TikTok / YouTube Shorts) from an idea — or to run/inspect any
  single stage (script, visuals, clips, stitch, voice, save, publish). Covers the
  `studio` CLI end-to-end: provider choice, cost control, artifact inspection, and
  troubleshooting.
---

# film-maker — Slope Studio operator guide

You are driving `studio`, a 7-stage CLI that turns a text idea into a finished
vertical Short. This skill tells you exactly how to run and observe each stage.

## 0. Environment check (do this first)

```bash
cd /Users/dasein/dev/slope-studio
source .venv/bin/activate 2>/dev/null || { uv venv && source .venv/bin/activate && uv pip install -e ".[fal]"; }
command -v ffmpeg ffprobe >/dev/null || echo "MISSING ffmpeg — install it"
studio --help        # confirm the CLI is importable
```

Keys live in `.env` (gitignored). `studio` auto-detects them and picks providers;
`FAL_KEY` unlocks Nano Banana images + AI video. No keys → it still runs on the
free/offline path (`stub` script, `stub` images, `kenburns` video, `edge` voice).

## 1. The pipeline at a glance

```
script → visuals → narrate → clips → stitch → audio → voice → save → [publish]
  ①         ②         ②.5      ③       ④       ④.5      ⑤      ⑥        ⑦
```
Each stage reads/writes `runs/<id>/`. The manifest `project.json` records provider,
cost, latency, done-flag per stage. Stages are idempotent (skip if output exists;
`--force` to redo visuals/clips). **`audio` ④.5** generates sfx + a music bed between
stitch and voice; the voice stage mixes them in (music ducked under narration). Sound
is a cheap, big quality lever — see guides §11.

**`narrate`** (stage ②.5, runs when `voice` is on) TTS-synthesizes each scene first,
so every clip lasts exactly as long as its narration → the final length follows the
speech (~target ±30s), perfectly synced, no truncation. It writes `05_voice/scenes/*.mp3`,
`05_voice/timing.json`, and the aligned `05_voice/captions.srt`.

> **Silent held beats** — a scene with **empty `narration`** is NOT dropped: `narrate`
> emits silence for the scene's planned `duration_s` (start→end) and holds the clip that
> long. Use this for wordless cinematic interludes (atmosphere skies, a held glow) that
> stretch a short text to a longer runtime — keep them moving (parallax/drift) and let the
> `music` bed carry them so they read as breathing room, not dead air.

## 1.5 Orientation / aspect ratio — vertical OR classic landscape

The pipeline renders **whatever aspect the scenario asks for**. Set it once and every
stage (visuals, animators, transitions, captions, master) adapts — driven by
`studio/canvas.py` (`set_from_aspect` → `W×H`); helpers default their `w,h` to that canvas.

| `aspect` | pixels | use |
|----------|--------|-----|
| `9:16` (default) | 1080×1920 | vertical Shorts / TikTok |
| `16:9` | 1920×1080 | **classic / landscape YouTube** |
| `1:1` · `4:5` · `4:3` · `21:9` | square / portrait / TV / ultrawide | other placements |

```bash
studio run "topic" --aspect 16:9 --duration 600   # classic landscape YouTube video
studio init "topic" --aspect 16:9                  # then drive stages; aspect lives in 01_script.json
```
- A hand-authored `01_script.json` just sets `"aspect": "16:9"` (top level) — stages read it.
- **Captions stay on-frame in any aspect** (`burn_subs` margin + `caption_strip` width/height
  scale with the canvas; landscape wraps wider so text fills the frame, never clipped).
- **Compose prompts for the orientation**: for `16:9`, write WIDE horizontal framings (vistas,
  lateral staging, subject offset left/right) and put `16:9 widescreen` in the `character`
  style string; for `9:16`, vertical framings.
- ⚠️ Length note: a 9:16 ≤180s upload is a *Short*; anything longer (or any 16:9) is a regular
  YouTube **video**, not a Short. Long landscape readings are fine — just not "Shorts".

## 2. Produce a whole video (one command) — pick a TIER

`--tier free|cheap|balanced|premium` sets all providers + video strategy. Override any
stage with a flag. `--max-cost` (default $3) caps spend; clips trims/aborts to fit.

```bash
# cheap: real Nano Banana stills + free Ken-Burns motion (~$0.59 / 150s)
studio run "the chemistry of humor" --duration 150 --tier cheap

# balanced: stills + SMART AI video filling $3 on the best scenes
studio run "the chemistry of humor" --duration 150 --tier balanced --video-model ltx --max-cost 3

# free: fully offline draft, no spend, no AI
studio run "topic" --duration 30 --tier free

# premium: AI on every scene (expensive — uncap with --max-cost 0)
studio run "topic" --duration 60 --tier premium --max-cost 0

# explicit per-scene control overrides the tier:
studio run "topic" --tier cheap --ai-scenes 1,8,15 --video-model kling --max-cost 3
```
- `--max-cost N` (default 3) — clips estimates per-second cost and **aborts/trims before spending**.
- `--publish-to youtube --privacy public` to upload at the end.
- `--from-stage` / `--to-stage` to run a slice (e.g. `--from-stage visuals --to-stage stitch`).
- `--run-id NAME` reuses/resumes a run; without it a timestamped id is created.

**Always report the run id + `studio status <id>` after producing.**

## 3. Run & observe ONE stage at a time

Create a run, then drive stages individually — the normal mode when iterating or debugging:

```bash
RID=$(studio init "octopuses are aliens" --duration 60 | awk '{print $2}')
# (or: studio init ... --run-id myrun  → then RID=myrun)
```

### ① script
```bash
studio script $RID --provider stub        # or groq|openrouter|ollama|openai|gemini
cat runs/$RID/01_script.json | jq '.scenes | length, .scenes[0]'   # inspect scenes/timing
```
Check: scenes tile [0, duration] with no gaps; each ≤8s; narration present if voice.
Timing warnings print to stderr.

### ② visuals
```bash
studio visuals $RID --provider fal-nanobanana   # or stub (offline) | pollinations
ls runs/$RID/02_visuals/                          # one PNG per scene
# pass a character reference for consistency:
studio visuals $RID --provider fal-nanobanana --char-ref path/to/face.png --force
```
Observe: open the PNGs; verify the character looks consistent across scenes.

### ③ clips  ⚠️ COST CENTER — always `studio estimate` first
AI video is billed **per second** (kling $0.07/s → 150s = $10.50). Pick a strategy:
```bash
studio estimate $RID --budget 3                         # preview cost per model + what fits
studio clips $RID --strategy kenburns                   # FREE pan/zoom on stills ($0)
studio clips $RID --strategy auto --model ltx --max-cost 3   # SMART: fill AI within $3
studio clips $RID --strategy hybrid --ai-scenes 1,8,15  # only these scenes get AI
studio clips $RID --strategy all --model kling --max-cost 0  # AI every scene (0 = no cap)
for f in runs/$RID/03_clips/*.mp4; do ffprobe -v error -show_entries format=duration -of csv=p=0 "$f"; done
```
- `--model` (all PER-SECOND, verified 2026-06-04): `ltx` (cheapest ~$0.04/s @1080p → 5s ≈ $0.20) · `hailuo` (~$0.045/s) · `kling` (default $0.07/s) · `wan` (~$0.16/s → 6s ≈ $0.80) · `seedance` (~$0.30/s, premium).
- The stage **aborts/trims before spending** if the estimate exceeds `--max-cost`.
- Each clip normalized to 1080x1920/30fps; fal i2v clamps to 5/10s.
- To bias `auto`, set `"priority": N` on important scenes in `01_script.json`.

### ④ stitch
```bash
studio stitch $RID --transition fade --transition-s 0.4   # fade|cut|wipeleft|dissolve|...
ffprobe -v error -show_entries format=duration -of csv=p=0 runs/$RID/04_stitched.mp4
```

### ⑤ voice
```bash
studio voice $RID --provider edge          # captions OFF by default (YouTube auto-generates)
#   add a music bed:  --music beds/lofi.mp3
#   only bake in text for muted-autoplay feeds:  --captions burn
mpv runs/$RID/05_voice/final.mp4   # or open in QuickTime; check VO sync (+ captions if burned)
```
Captions are **off by default** — `narrate` still writes `captions.srt`, so upload that as a
YouTube sidecar instead of burning a text wall over the visuals. See guides §6.

### ⑥ save
```bash
studio save $RID
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height \
  -of default=noprint_wrappers=1 runs/$RID/06_final.mp4   # expect h264 1080x1920 + aac
```

### ⑥.5 metadata + ⑦ publish (optional)
```bash
studio metadata $RID                                  # SEO title/desc/tags → 06_final.json (auto-runs before publish)
# YouTube: one-time OAuth setup (client_secret.json) — see docs/40-publishing/youtube.md
uv pip install -e ".[youtube]"
studio publish $RID --target youtube --privacy public # receipt → 07_publish.json
# or in one go: studio run "..." --publish-to youtube --privacy public
# TikTok is audit-gated → tiktok target raises (private-only until audited)
```
Full setup + quota/constraints: [`docs/40-publishing/youtube.md`](../../../docs/40-publishing/youtube.md).

### ⑥.7 thumbnail / preview (REQUIRED for landscape uploads)

> ⚠️ **RULE — every normal (non-vertical, i.e. `16:9`/landscape) video MUST get a
> generated preview/thumbnail before YouTube upload.** It's a *balanced* composition
> with a **hook** (a curiosity-gap line or the most striking frame), and **if the piece
> has an Author/Name** (e.g. *Franz Kafka* — *Before the Law*) **that author + title MUST
> appear on the thumbnail.** `publish` auto-attaches `06_thumb.png` if present, so make
> it first. (Vertical Shorts don't need one — YouTube auto-picks a Shorts cover.)

```bash
studio thumbnail $RID --at 6                     # hero frame @6s + auto title/author → 06_thumb.png
studio thumbnail $RID --title "BEFORE THE LAW" --author "Franz Kafka" \
                      --hook "a door made only for you"   # override any field
# then publish — the thumbnail is set on the upload automatically:
studio publish $RID --target youtube --privacy unlisted --channel <name>
```
- Title/author auto-derive from the scenario `topic`/`title` (e.g. "… — Franz Kafka",
  "… by Kafka"); override with `--title/--author`. `--hook` is the curiosity line.
- Free (Pillow): `cardgen.thumbnail` cover-crops the frame, adds a scrim, yellow accent,
  author-in-yellow + big white title, optional hook. 1280×720.
- Custom thumbnails need a **verified** YouTube channel; if the account isn't verified the
  upload still succeeds, the thumbnail is just skipped.

## 3.5 Animation & transitions (per-scene, free)

> **Authoring for QUALITY?** Read [`film-maker-guides.md`](film-maker-guides.md) —
> the marvelous-effects playbook (parallax depth, the `slice` reveal, literal manim
> moments, caption safety, operator preferences). Use it whenever a video should
> look *great*, not just be wired.

Each scene in `01_script.json` controls its own look — set by the script author/LLM:
- `animator`: `kenburns` (default) · `motion-driftright|driftleft|driftup|driftdown|zoomin|zoomout|pulse` · `kinetic` · `parallax` · `blurred-parallax` · `slice` · `static` · `puppet` · `talkinghead` · `manim`
- `transition` (into the scene): `cut` (default) · `fade` · `wipeleft/right/up/down` · `slide*` · `circleopen/close` · `dissolve` · `radial` · `zoomin` …
- `transition_dur`: seconds (default 0.4) · `manim_code`: vector animation body for `animator:"manim"`

Transitions are overlap-compensated → video stays synced to narration (no drift).
`animator` applies to FREE scenes; AI scenes use `fal-i2v` (paid). Mix freely.

> ⚠️ **RULE — `parallax` has TWO modes; it NEVER cuts a subject out of a single still.**
> The old auto rembg-cut-out (subject frozen in the middle, background inpainted + drifted)
> produced **torn frames and a moving "hole" around the centre** on subjectless stills — so
> it's gone. Now:
> - **Default (cheap / no plate):** `parallax` = a **clean full-image lateral pan** (a camera
>   move over the whole still). Always safe, never holes/tears. For architecture/vista/crowd
>   beats this is exactly right (or just use `motion-drift*`/`static`).
> - **Layered 2.5D (balanced+):** `studio run --tier balanced|premium` (or `studio visuals
>   --parallax-plates`) generates a **separate background plate** (`scene_NN_bg.png`, the same
>   scene with the subject removed) for each parallax scene. Then the subject is cut from the
>   main still and held static while the **plate drifts behind it** — two genuinely DIFFERENT
>   images, so real depth with **no inpaint hole**. +1 paid still per parallax scene.
> Either way: author `parallax` on scenes that have a clear separable subject; the foreground
> and background are always different images, never the same still cut against itself.

> ⚠️ **RULE — `pulse` and `kinetic` are OFF by default; use only on explicit need.**
> - `motion-pulse` (breathing zoom) reads as twitchy/epileptic — **never** reach for it
>   unless the user explicitly asks (same family as the banned `zoomin`/`zoomout`).
> - `kinetic` bakes a big on-screen HEADLINE — use it **only** when a scene genuinely needs
>   on-screen words (the hook, a shouted line, a title/outro card), and only over a
>   *text-free* illustration (never a `card`, which doubles the text). For ordinary
>   narrated/story beats use `parallax` / `slice` / `motion-drift*` / `static` instead —
>   the spoken line (and captions, if on) already carries the words. Don't sprinkle
>   `kinetic` as generic motion.

> ⚠️ **RULE — any zoom effect (`kinetic`, `pulse`, ken-burns, `motion-zoom*`) must keep
> the image FILLING the frame at all times — never reveal white / black bars / empty
> canvas.** Bound the zoom so it only ever goes from **full image (widest) → zoomed-in
> (tightest)**, never wider than the full image:
> - widest extreme = the **whole image covers the frame** (scale-to-cover, zoom = 1.0);
> - tightest extreme = a zoomed-in crop; **never zoom OUT past 1.0** (that exposes the
>   background = white/empty).
> - A `kinetic` headline always sits **over the cover-filled still**, never on a blank
>   card. If a still doesn't match the aspect, it's **cover-cropped (increase+crop)**, not
>   letterboxed (decrease+pad) — padding shows empty bars. (Enforced in `ffmpeg.kinetic`.)

> ⚠️ **RULE — keep RECURRING characters & settings visually CONSISTENT across scenes.**
> Same-style is not enough: the doorkeeper must look like the **same person** every scene,
> the gate the **same gate**, an interior the **same room** — as in real continuity, not a
> new face/door each cut. The `character` style string only fixes the *art style*. For
> *subject identity*:
> - Decide each recurring entity's **canonical look once** (the doorkeeper's exact face,
>   beard, fur coat; the gate's exact shape/material; the hall's columns) and paste that
>   **same detailed description verbatim** into every scene that shows it.
> - And/or pass a **`--char-ref <image.png>`** to `studio visuals` (Nano-Banana `edit`
>   model holds the reference identity); reuse one scene's good render as the ref.
> - Author the scenario so each subject has a fixed description block reused across scenes,
>   not a fresh ad-hoc description per scene.

**Extra effects catalog (rain, snow, fire, fog, sunrise/sunset, water, film grain,
glitch, god-rays, shape morphs, kinetic typography…):** the bullet above lists what's
**wired**. The full research-backed library is the effects index
[`docs/30-animation/effects/`](../../../docs/30-animation/effects/README.md), status-tagged:
- ✅ live (set `animator:"…"`); 🧩 author today via `animator:"manim"` + `manim_code`
  (morphs, kinetic typography, lightning, leaves — paste-ready snippets in
  [`effects/manim-effects.md`](../../../docs/30-animation/effects/manim-effects.md));
- 🧪 recipe-backlog (drop-in ffmpeg filtergraphs in
  [`effects/ffmpeg-recipes.md`](../../../docs/30-animation/effects/ffmpeg-recipes.md));
  🔬 research-only ([`shaders.md`](../../../docs/30-animation/effects/shaders.md) /
  [`particles.md`](../../../docs/30-animation/effects/particles.md)).
- ⚠️ **Never set a 🧪/🔬 name in `animator`** — unknown names fall back to `kenburns`. Reach
  those via Manim or an ffmpeg post-pass; to wire one, follow
  [effects → adding an effect](../../../docs/30-animation/effects/README.md#adding-an-effect).

**Voice & tone:** Script `voice_name` (man|woman|cartoon|narrator) + `tone`
(neutral|serious|mystical|friendly|sad|excited); per-scene `tone` overrides. CLI:
`--voice man --tone mystical`. edge approximates tone (rate/pitch, free); openai-tts
gives real tone. See [`voices.md`](../../../docs/30-animation/voices.md).

Full references (read before authoring scenes or adding presets):
- Schema: [`docs/30-animation/scenario-schema.md`](../../../docs/30-animation/scenario-schema.md)
- Index + decision matrix: [`docs/30-animation/README.md`](../../../docs/30-animation/README.md)
- **Effects index (full catalog):** [`docs/30-animation/effects/README.md`](../../../docs/30-animation/effects/README.md)
- [`transitions.md`](../../../docs/30-animation/transitions.md) · [`motion.md`](../../../docs/30-animation/motion.md) · [`kinetic.md`](../../../docs/30-animation/kinetic.md) · [`parallax.md`](../../../docs/30-animation/parallax.md) · [`slice.md`](../../../docs/30-animation/slice.md) · [`manim.md`](../../../docs/30-animation/manim.md)

Deps: `parallax` → `uv pip install -e ".[parallax]"`; `manim` → `".[manim]"`. Both
fall back to `kenburns` (recorded in the manifest note) if a dep/render fails.

## 4. Observe the whole run

```bash
studio status $RID                 # table: stage / done / provider / cost / latency / note
cat runs/$RID/project.json | jq .  # raw manifest incl total_cost_usd
find runs/$RID -type f | sort      # every artifact produced
```

## 5. Cost control

- Stage 3 (video) dominates cost. Iterate cheaply on ① ② (cents) before rendering ③.
- Nano Banana image = **$0.039** (verified). fal i2v per-clip is an **estimate** in the
  manifest — confirm against fal.ai's current pricing; refine after a pilot.
- Use `--max-cost` on `studio run`. Use `kenburns` + `stub` to dry-run wiring for $0.
- A 150s video ≈ 19–30 scenes by default; lower `--duration` while iterating.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `402 Payment Required` on visuals | Pollinations paywalls anonymous. Use `--image-provider stub` or `fal-nanobanana`. |
| `No such filter: 'drawtext'`/`subtitles` | This ffmpeg lacks libfreetype AND libass. Caption burn overlays **Pillow PNG strips** (`burn_subs`→`caption_strip`); never switch to `subtitles=`/`drawtext`. Stub/`card` images avoid drawtext too. |
| `missing FAL_KEY` | Add it to `.env`. Or use free providers (`stub`/`kenburns`). |
| script JSON parse error | Free LLMs sometimes break JSON. Retry, or `--script-provider stub`. |
| clips too short / trimmed | i2v caps at 5/10s; long scenes need splitting in stage 1. |
| output shorter than expected | Fixed via `apad` in mux; if recurring, check narration vs video length. |
| TikTok publish raises | By design — audit-gated. Default to `--privacy self_only` or use YouTube. |

## 7. After producing

Always: print the **run id**, the **`studio status`** table (providers + total cost),
the **master path** (`runs/<id>/06_final.mp4`), and offer to publish or iterate a stage.
For deeper rationale (model comparisons, pricing, tiers) point to `docs/`.
