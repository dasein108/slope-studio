# Pipeline Stages — End-to-End Data Flow

The studio is a chain of pure transforms. Each stage reads artifacts from a run directory and
writes new artifacts, so any stage runs standalone or re-runs without redoing the others. This
is what makes "decomposed CLI scripts" and "single pipeline" the same thing.

> This documents the **implemented** pipeline. Visual workflow diagrams:
> [`../10-architecture/workflows.md`](../10-architecture/workflows.md). Per-module surface:
> [`../10-architecture/module-map.md`](../10-architecture/module-map.md).

## The stage order (code truth)

`STAGE_ORDER = ["script", "visuals", "narrate", "clips", "stitch", "audio", "voice", "save"]`

`narrate` (2.5) and `audio` (5b) run only when voice is on. `metadata` (6.5) and `publish` (7)
run only when a publish target is requested. Numbering below matches the conceptual stages.

## Artifact-passing model

A single run lives in one directory, `runs/<id>/`. Stages communicate through files + the
manifest (`project.json`). Exact paths come from `studio/paths.py`:

```
runs/2026-06-03_dragons/
├── project.json            # manifest: config + per-stage provider/cost/latency/done
├── 01_script.json          # scenario: scenes[] (timed) + narration + metadata
├── 02_visuals/
│   ├── scene_01.png        # one keyframe per scene
│   ├── scene_01_bg.png     # optional subject-removed plate (parallax-plates)
│   └── …
├── 03_clips/
│   ├── scene_01.mp4        # one clip per scene (i2v or free animator)
│   └── …
├── 04_stitched.mp4         # clips + transitions, NO audio
├── 05_voice/
│   ├── scenes/scene_01.mp3 # per-scene TTS (narrate stage)
│   ├── timing.json         # {scene_id: seconds} — drives all durations
│   ├── narration.mp3       # combined narration track
│   ├── captions.srt        # aligned captions
│   └── final.mp4           # video + narration + sfx + music + captions muxed
├── 05b_sfx/
│   ├── scene_01_0.mp3      # per-cue sound effect
│   └── placements.json     # [[path, global_start_s, gain_db], …]
├── 05c_music.mp3           # background-music bed
├── 06_final.mp4            # platform-encoded master
├── 06_final.json           # title/description/tags (save → overwritten by metadata)
├── 06_thumb.png            # optional YouTube thumbnail
├── 07_publish.json         # upload receipt (video id, url) if published
├── 08_stats.json           # marketing: views/likes/comments/virality snapshot
└── 08_comments.json        # marketing: fetched comment threads
```

The **manifest** records which provider produced each artifact, its measured `cost_usd` and
`latency_s`, and a done flag — so cost-per-video is measured, not guessed. `studio status <id>`
renders it.

## Stage-by-stage contract

### Stage 1 — Script (`script`)
- **In:** idea string, `N` seconds (default 150), `--voice`, style/tone, aspect.
- **Out:** `01_script.json` — `Script` with timed `scenes[]`. Each scene carries
  `visual_prompt`, `narration`, `on_screen_text`, `motion_hint`, `priority`, `image_role`
  (hero/bg), `animator`, `atmosphere`, `fx`, `transition`, `sfx[]`. Timing sums to N.
- **Provider:** LLM (`openai`/`gemini`/`groq`/`openrouter`/`ollama`) or `stub` (offline split).
- See [`../01-stage-script/`](../01-stage-script/) and
  [`../30-animation/scenario-schema.md`](../30-animation/scenario-schema.md).

### Stage 2 — Visuals (`visuals`)
- **In:** `01_script.json`, optional `--char-ref`.
- **Out:** `02_visuals/scene_NN.png` per scene. Hero scenes use `--provider`; `image_role="bg"`
  scenes use `--cheap-provider`. `--parallax-plates` also writes `scene_NN_bg.png` (subject
  removed) for parallax scenes. Skips existing unless `--force`.
- **Provider:** `fal-nanobanana` (char-ref consistency) / `fal-flux-schnell` / `card` / `stub`.
- See [`../02-stage-visuals/`](../02-stage-visuals/).

### Stage 2.5 — Narrate (`narrate`, voice only)
- **In:** `01_script.json` (per-scene `narration`, `voice_name`, `tone`).
- **Out:** `05_voice/scenes/scene_NN.mp3`, `timing.json` (TTS length + `PAD_S` per scene),
  aligned `captions.srt`. **`timing.json` is the single source of per-scene duration** for
  clips, stitch, and mux — this is what keeps the final length == narration length.
- **Provider:** `edge` (free, sentence-level captions) / `openai-tts`.
- See [`../05-stage-voiceover/`](../05-stage-voiceover/).

### Stage 3 — Clips (`clips`)
- **In:** `01_script.json`, `02_visuals/scene_NN.png`, `05_voice/timing.json` (if present).
- **Out:** `03_clips/scene_NN.mp4`, each normalized to its `timing.json` duration. Skips
  existing unless `--force`.
- **Strategy:** `kenburns` (free) · `all` (AI every scene) · `hybrid` (`--ai-scenes`) · `auto`
  (rank by priority, AI the heroes within `--max-cost`, Ken Burns the rest). Free animators
  dispatch via `animate.render` and fall back to kenburns on error; AI via `fal-i2v` at
  `--model`. **Budget-gated** — aborts pre-flight if `all`/`hybrid` exceeds `--max-cost`.
  Run `studio estimate <id>` first.
- See [`../03-stage-video/`](../03-stage-video/) and [`../30-animation/`](../30-animation/README.md).

### Stage 4 — Stitch (`stitch`)
- **In:** `03_clips/*.mp4`, `05_voice/timing.json` (if present), per-scene `transition`.
- **Out:** `04_stitched.mp4` — single video track, normalized to the aspect canvas, with
  per-scene transitions. `concat_xfade_seq` overlap-compensates so output length = Σ durations.
  No audio. See [`../04-stage-stitch/`](../04-stage-stitch/).

### Stage 5b — Audio (`audio`, voice only)
- **In:** `01_script.json` (`scene.sfx[]`, `Script.music`), `05_voice/timing.json`.
- **Out:** `05b_sfx/scene_*_*.mp3` + `placements.json` (`[path, global_start_s, gain_db]`),
  `05c_music.mp3`. Produces assets only; the voice stage overlays/ducks them. Skips existing
  unless `--force`.
- **Provider:** sfx `fal-elevenlabs-sfx`/`freesound`/`local`/`silence`; music
  `fal-stable-audio`/`freesound`/`local`/`silence`.

### Stage 5 — Voice (`voice`)
- **In:** `04_stitched.mp4`, `05_voice/scenes/*.mp3` (or one-shot TTS fallback), `timing.json`,
  `captions.srt`, `05b_sfx/placements.json`, `05c_music.mp3`.
- **Out:** `05_voice/final.mp4` — video + narration (concatenated per-scene mp3, $0 when
  `narrate` ran) + sfx overlay + ducked music + burned caption PNGs. `mux_audio` holds the
  tail, never truncates. See [`../05-stage-voiceover/`](../05-stage-voiceover/).

### Stage 6 — Save (`save`)
- **In:** `05_voice/final.mp4` (or `04_stitched.mp4` fallback), `01_script.json`.
- **Out:** `06_final.mp4` (platform-correct H.264 master via `encode_master`) + `06_final.json`
  (title/description/hashtags from the script — overwritten by metadata if it runs).
  See [`../06-stage-publish/save.md`](../06-stage-publish/save.md).

### Stage 6.5 — Metadata (`metadata`)
- **In:** `01_script.json`.
- **Out:** `06_final.json` — LLM-polished `title`/`description`/`tags` (YouTube Shorts SEO),
  deterministic script-derived fallback if no LLM. Auto-runs before publish.
  See [`../40-publishing/`](../40-publishing/).

### Stage 7 — Publish (`publish`, optional)
- **In:** `06_final.mp4`, `06_final.json`, `06_thumb.png` (optional).
- **Out:** `07_publish.json` — upload receipt. YouTube via Data API (`videos.insert`); TikTok
  is audit-gated (raises until the app passes review). See [`../06-stage-publish/`](../06-stage-publish/)
  and [`../40-publishing/youtube.md`](../40-publishing/youtube.md).

## Why decomposition matters here

- **Cost control:** stage 3 (video) is ~90% of the cost and time — iterate stages 1–2 (cents)
  without re-rendering video. `studio estimate` + `--max-cost` cap spend before stage 3 runs.
- **Mix-and-match:** swap any stage's provider via `--*-provider` or a `--tier` preset.
- **Caching/resume:** idempotent stages + the manifest give free resume; a failed publish never
  re-runs a paid render. `studio run --run-id <id>` skips `is_done` stages.
- **Parallelism:** scenes are independent in stages 2–3 → fan out N image/video calls.

See [`../10-architecture/cli-component-design.md`](../10-architecture/cli-component-design.md)
for the CLI surface and [`../10-architecture/orchestration.md`](../10-architecture/orchestration.md)
for chaining.
</content>
