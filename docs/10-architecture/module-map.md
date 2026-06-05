# Module Map — every part of `studio/`

What each module is, its public surface, and where it sits in the pipeline. Mirrors the
code in `studio/`; pair with [`workflows.md`](workflows.md) (diagram 10 is the dependency
graph) and the [CLI surface](cli-component-design.md).

> One job per module. Stages are pure functions (read artifacts → write artifacts →
> return `GenResult`). Providers are swappable backends. Everything ffmpeg goes through
> `ffmpeg.py`; every cost is measured, not guessed.

---

## Top-level orchestration

### `cli.py` — the Typer app
Every subcommand + the `run` chainer + `status` + the `marketing` sub-app.

`STAGE_ORDER = ["script", "visuals", "narrate", "clips", "stitch", "audio", "voice", "save"]`

| Command | Purpose |
|---------|---------|
| `init idea [--duration --aspect --voice --style --tier --run-id]` | Create run dir + manifest |
| `script run_id [--provider]` | Stage 1 — idea → timed scenario |
| `visuals run_id [--provider --cheap-provider --char-ref --force --parallax-plates]` | Stage 2 — keyframe per scene (hero vs bg split) |
| `narrate run_id [--provider --voice --tone]` | Stage 2.5 — per-scene TTS + `timing.json` + captions |
| `clips run_id [--strategy --model --ai-scenes --max-cost --force]` | Stage 3 — video clips, budget-gated |
| `stitch run_id [--transition --transition-s]` | Stage 4 — glue clips with transitions |
| `audio run_id [--sfx-provider --music-provider --force]` | Stage 5b — sfx + music bed |
| `voice run_id [--provider --voice-name --captions --music]` | Stage 5 — mux narration+sfx+music+captions |
| `save run_id` | Stage 6 — encode platform master + metadata sidecar |
| `metadata run_id [--provider]` | Stage 6.5 — LLM SEO title/description/tags |
| `estimate run_id [--budget]` | Price stage-3 video per model before spending |
| `status run_id` | Render manifest: stages done, provider, cost, latency |
| `thumbnail run_id [--at --title --author --hook]` | YouTube preview → `06_thumb.png` |
| `publish run_id [--target --privacy --channel]` | Stage 7 — upload (youtube; tiktok audit-gated) |
| `yt-channel [--channel]` | Authorize + print bound YouTube channel |
| `run idea [many flags]` | Full pipeline idea → master (± publish), with resume |
| `marketing ideate\|link\|measure\|learn\|journal\|report` | Growth-loop sub-app |

`run` applies a `--tier` preset, then walks `STAGE_ORDER` (sliced `--from-stage`…`--to-stage`),
skipping `is_done` stages on resume. `narrate`/`audio` run only with `--with-voice`; clips get
`cap = max_cost − cost-so-far`; `metadata`+`publish` run only with `--publish-to`.

### `config.py` — key detection → default provider
`default_provider(stage)` returns a provider name based on which keys are in `.env`, else a
free fallback. Chains: script `OPENAI→GEMINI→GROQ→OPENROUTER→OLLAMA→stub`; visuals
`FAL_KEY→card`; clips `FAL_KEY→kenburns`; voice `OPENAI_API_KEY→edge`; sfx
`FAL_KEY→FREESOUND→local`; music `FAL_KEY→local`. Read secrets via `config.env()`.

### `tiers.py` — bulk provider presets
`preset(tier)` → dict of stage→provider. `DEFAULT_MODEL_BY_TIER` picks the i2v model.

| tier | script | image (hero) | image_cheap (bg) | video | strategy | voice | sfx | music | i2v model |
|------|--------|--------------|------------------|-------|----------|-------|-----|-------|-----------|
| free | stub | card | card | kenburns | kenburns | edge | silence | silence | kling |
| cheap | stub | fal-flux-schnell | fal-flux-schnell | kenburns | kenburns | edge | local | local | kling |
| balanced | stub | fal-nanobanana | fal-flux-schnell | fal-i2v | auto | edge | fal-elevenlabs-sfx | fal-stable-audio | ltx |
| premium | stub | fal-nanobanana | fal-flux-schnell | fal-i2v | all | openai-tts | fal-elevenlabs-sfx | fal-stable-audio | kling |

> Note: `cheap` uses **fal-flux-schnell** (~$0.006/img) for stills — the code dict, not the
> "Nano Banana" wording in the module docstring, is authoritative.

### `manifest.py` — `project.json`
`Manifest(id, idea, duration_s, aspect, voice, style, tier, stages: dict[str, StageRecord])`.
`StageRecord(done, provider, cost_usd, latency_s, n, note)`. `total_cost_usd` sums all stages
(cost rollup). `record(stage, **kw)`, `is_done(stage)`, load/save to `runs/<id>/project.json`.

### `paths.py` — canonical artifact paths
Single source of truth for `runs/<id>/` filenames. Key: `01_script.json`,
`02_visuals/scene_NN.png` (+`_bg.png`), `03_clips/scene_NN.mp4`, `04_stitched.mp4`,
`05_voice/{scenes/scene_NN.mp3, timing.json, narration.mp3, captions.srt, final.mp4}`,
`05b_sfx/{scene_*.mp3, placements.json}`, `05c_music.mp3`, `06_final.mp4`, `06_final.json`,
`06_thumb.png`, `07_publish.json`, `08_stats.json`, `08_comments.json`. Marketing:
`runs/_marketing/<channel>/{journal.json, journal.md, report.md}`. Assets: `assets/audio/{sfx,music}/`,
`assets/mouths/<set>/*.png`.

### `models.py` — pydantic schema
- **`Scene`**: `id, start_s, end_s, visual_prompt, narration, on_screen_text, motion_hint,
  priority, image_role, transition, transition_dur, tone, animator, atmosphere, fx[],
  manim_code, mouth_set, mouth_xy[], limbs[], sfx[]`; `.duration_s` property.
- **`Script`**: `topic, duration_s, aspect, voice, voice_name, tone, style, character, music,
  scenes[], title, description, hashtags[]`; `.validate_timing()` → list of problems.
- **`SoundCue`**: `prompt, at, dur, gain_db`. **`Limb`**: `box, pivot, move, amp, period, phase`.

Authoritative `01_script.json` schema: [`../30-animation/scenario-schema.md`](../30-animation/scenario-schema.md).

### `canvas.py` — live render dimensions
Global `W, H` (default `1080×1920`, 9:16). `set_from_aspect(aspect)` mutates them; every
ffmpeg/cardgen/image helper defaults to `canvas.W/H`. Supported: `16:9`(1920×1080),
`9:16`(1080×1920), `1:1`(1080×1080), `4:5`(1080×1350), `4:3`(1440×1080), `21:9`(2560×1080).
Unknown → 9:16.

---

## Stages (`studio/stages/`) — one pure function each

| Module | Reads | Writes | Provider(s) | Idempotent |
|--------|-------|--------|-------------|------------|
| `script.py` | (idea args) | `01_script.json` | llm / stub | overwrite |
| `visuals.py` | `01_script.json` | `02_visuals/scene_NN.png` (+`_bg.png` if parallax-plates) | image / cheap split by `image_role` | skip-if-exists, `--force` |
| `narrate.py` | `01_script.json` | per-scene mp3, `timing.json`, `captions.srt` | tts (edge/openai) | one-shot |
| `clips.py` | script, visuals, `timing.json` | `03_clips/scene_NN.mp4` | fal-i2v / animate | skip-if-exists, `--force`, budget-gated |
| `stitch.py` | script, clips, `timing.json` | `04_stitched.mp4` (no audio) | ffmpeg | always regen |
| `audio.py` | script, `timing.json` | `05b_sfx/*`, `placements.json`, `05c_music.mp3` | sfx + music providers | skip-if-exists, `--force` |
| `voice.py` | stitched, scene mp3, captions, placements, music | `05_voice/final.mp4` | tts (fallback), ffmpeg | always regen |
| `save.py` | `final.mp4`/`stitched.mp4`, script | `06_final.mp4`, `06_final.json` | ffmpeg | always regen |
| `metadata.py` | `01_script.json` | `06_final.json` (overwrites) | llm / deterministic fallback | always regen |
| `publish.py` | `06_final.mp4`, `06_final.json`, `06_thumb.png?` | `07_publish.json` | youtube / tiktok | always attempt |

Key behaviors: `narrate` derives `timing.json` (TTS length + `PAD_S`) — the single source of
per-scene duration for the rest of the pipeline. `clips` ranks scenes by
`_effective_priority` under `auto`, aborts pre-flight if `all`/`hybrid` estimate exceeds
`--max-cost`. `voice` concatenates pre-synthesized scene mp3 (free) when `narrate` ran, else
one-shot TTS; overlays sfx + ducks music + burns caption PNGs. `metadata` LLM-polishes
title/description/tags, falls back to script-derived; auto-runs before publish.

---

## Providers (`studio/providers/`) — swappable backends

All return `GenResult(path, cost_usd, latency_s, provider, note)` (`base.py`).

### `llm.py` — script generation
`complete(provider, system, user) → str` (JSON). Providers: `stub`, `ollama` (llama3.1:8b),
`groq` (llama-3.1-8b-instant), `openrouter` (free llama-3.1-8b), `openai` (gpt-4o-mini),
`gemini` (gemini-2.5-flash). All JSON-mode, temp 0.8.

### `image.py` — visuals
`generate(provider, prompt, dst, refs, aspect, w, h, headline, index) → GenResult`.
`card` (Pillow gradient+text, $0), `stub` (solid color, $0), `pollinations` (paywalled/broken),
`fal-nanobanana` (Gemini 2.5 Flash Image, char-ref consistency, **$0.039/img**),
`fal-flux-schnell` (FLUX schnell, no char-ref, **~$0.006/img**).

### `video.py` — clips (AI)
`generate(provider, image, prompt, seconds, dst, model) → GenResult`;
`estimate_cost(provider, model, seconds)`. `kenburns` (free) or `fal-i2v`. `FAL_MODELS`
(per-second, verified 2026-06-04): `kling` $0.07/s (billing-confirmed), `ltx` $0.04/s,
`hailuo` $0.045/s, `wan` $0.16/s, `seedance` $0.30/s. Most cap 5–10s/clip → clip is fit to
scene length downstream.

### `tts.py` — voice
`synth(provider, text, mp3, srt, voice_name, tone)` and
`synth_scene(provider, text, mp3, voice_name, tone) → cues`. `edge` (free, sentence-level
captions via `SubMaker`), `openai-tts` (gpt-4o-mini-tts, ~$0.015/1k chars, no captions).

### `audio.py` — sfx + music
`generate_sfx(provider, prompt, seconds, dst)`, `generate_music(provider, prompt, seconds, dst)`.
SFX: `fal-elevenlabs-sfx` ($0.002/s, ≤30s), `freesound` (CC0, free), `local` (asset packs),
`silence`. Music: `fal-stable-audio` ($0.20 flat, ≤~3min), `freesound` (CC0), `local`, `silence`.

### `cardgen.py` — Pillow offline image utilities ($0, no network/GPU)
`render` (scene card), `caption_strip` (auto-shrink caption PNG for `burn_subs`),
`split_halves` (slice animator), `depth_bands` (parallax layers), `particle_layer`
(rain/snow/embers/… atmosphere), `mouth_sprite_image` (talkinghead fallback), `headline_png`
(kinetic overlay), `thumbnail` (1280×720 YouTube preview). 6-pair cycling palette.

### `publish.py` — upload + OAuth
`publish(...)` dispatch → `_youtube()` (`videos.insert` + thumbnail, category 22) or tiktok
(`NotImplementedError`, audit-gated). `_creds(channel, scopes)` reads/refreshes/creates
`token_<channel>.json`; `channel_info()`. Scopes: `youtube.upload` + `youtube.readonly`.

### `analytics.py` — post-publish metrics
`video_stats` (Data API: views/likes/comments/age), `retention` + `subs_gained` (Analytics
API, best-effort), `comments`, `recent_uploads`, `video_id_from_url`. Reuses the publish
OAuth token, adding `yt-analytics.readonly`.

---

## Media engine

### `animate.py` — free animator dispatch
`render(animator, ...)` branches: `static`/`none`/`hold`, `kenburns`(default), `motion-*`,
`kinetic`, `parallax` (sharp subject + inpainted bg drift), `blurred-parallax`, `slice`,
`puppet`/`cutout`, `talkinghead` (Rhubarb lip-sync), `manim`, unknown→kenburns. Post-passes:
`Scene.atmosphere` (particle overlay) then `Scene.fx`
(grain/vignette/chroma/glitch/sunrise/sunset/godrays/flash-*). Any failure → kenburns
fallback (recorded in manifest note). Diagram: [`workflows.md` §6](workflows.md).

### `ffmpeg.py` — ALL ffmpeg shelling
Never shell ffmpeg elsewhere. Functions: `probe_duration`, `grab_frame`, `normalize`,
`to_wav`, `frames_to_video`, `silence`, `placeholder_image`, `ken_burns`, `still`, `motion`,
`concat_xfade_seq`, `kinetic`, `parallax`, `parallax_drift`, `diag_slice`, `parallax_layers`,
`atmosphere`, `post_fx`, `concat`, `concat_xfade`, `pad_audio`, `concat_audio`, `mux_audio`,
`loudnorm`, `duck_music`, `overlay_sfx`, `burn_subs`, `encode_master`. Constants: `TRANSITIONS`
(27 xfade types), `_MOTION`, `_ATMO`. This build lacks `drawtext`/`subtitles` — captions are
overlaid Pillow PNGs.

### `voices.py` — semantic voice → TTS settings
`resolve(provider, voice_name, tone)`. `EDGE_VOICES` (woman=Aria, man=Guy, narrator=Ryan-GB,
cartoon=Ana) + `EDGE_TONES` (rate/pitch per neutral/serious/mystical/friendly/sad/excited).
`OPENAI_VOICES` (nova/onyx/onyx/fable) + `OPENAI_TONES` (instruction strings). Defaults
woman/neutral/edge.

---

## Marketing (`studio/marketing/`) — growth loop

### `journal.py` — the bet ledger
`Entry` (id `jNNNN`, idea/hook/assumption/goal/theme/tags, status planned→deployed→measured,
run_id/video_id/url, metrics/virality/percentile/outcome/learnings). `Metrics` (views, likes,
comments, retention, subs_gained, age_days, velocity, engagement). `Strategy` (niche,
current_direction, winning/losing_patterns, next_seeds). `Journal` (channel,
bootstrap_target=10, strategy, entries; `in_cold_start`, `deployed_count`, `measured()`).
Stored `runs/_marketing/<channel>/journal.{json,md}`.

### `score.py` — virality math
`virality(m) = 0.5·log10(velocity+1) + 0.2·(retention/100) + 0.2·min(engagement·20,1) +
0.1·min(subs_conv·50,1)`. `derive` (velocity, engagement), `relativize` (→percentile),
`outcome` (win ≥75, loss ≤25, neutral; cold-start while <10 deployed).

### `ideate.py` — next bet
`generate(j, provider, n, signals, niche) → list[dict]`. Cold-start = maximize diversity;
optimizing = exploit winners + reserve exploration. Feeds on strategy + web-search signals +
last-30 tried (no-repeat). Deterministic fallback without an LLM key.

### `learn.py` — reflect
`reflect(j, provider) → str`. Sorts measured entries by virality, LLM extracts
winning/losing patterns + new `current_direction` + `next_seeds` + per-entry learnings;
updates `j.strategy` in place. Heuristic fallback (top/bottom quartile) without an LLM.

Loop reference: [`../50-marketing/`](../50-marketing/README.md). Diagram: [`workflows.md` §7](workflows.md).
</content>
