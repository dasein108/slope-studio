# CLAUDE.md — Slope Studio

Guidance for Claude Code working in this repo. Read this first.

## What this is

An **automated short-video studio**: text idea → finished vertical Short (TikTok / YouTube Shorts). A 7-stage pipeline where **each stage is an independent CLI subcommand** and they also chain via `studio run`. Current scope = **faceless scene videos**, **balanced** cost/quality tier, **YouTube-first** publishing, **plain Python CLI** orchestration.

Deep research + architecture rationale lives in [`docs/`](docs/) — start at `docs/README.md`. Don't duplicate it here; link to it. The **hands-off operator guide** (how to use both skills + every feature with minimal human effort) is [`docs/00-overview/operator-guide.md`](docs/00-overview/operator-guide.md).

## The 7 stages (data flows through `runs/<id>/`)

| # | Stage | CLI | Input → Output |
|---|-------|-----|----------------|
| 1 | Script | `studio script` | idea → `01_script.json` (timed scenes + narration) |
| 1.5 | Critic | `studio critic` | scenario → `01_critic.json` (CONTENT gate: topic revealed · fact explained · informative+interesting · emotion). `studio run` loops script↔critic to rework weak scripts before spending. LLM, ~free. |
| 2 | Visuals | `studio visuals` | script → `02_visuals/scene_NN.png` |
| 2.5 | Narrate | `studio narrate` | per-scene TTS → `05_voice/scenes/*.mp3` + `timing.json` + aligned `captions.srt` (runs when `voice` on; drives clip lengths) |
| 3 | Clips | `studio clips` | images → `03_clips/scene_NN.mp4` (animator or i2v) |
| 4 | Stitch | `studio stitch` | clips → `04_stitched.mp4` (transitions, no audio) |
| 5 | Voice | `studio voice` | narration → `05_voice/final.mp4` (TTS muxed; captions **off** by default — `--captions burn` to bake in) |
| 6 | Save | `studio save` | → `06_final.mp4` (platform master) + `06_final.json` meta |
| 6.5 | Metadata | `studio metadata` | SEO-polish title/description/tags → `06_final.json` (LLM, fallback to script). Auto-runs before publish. |
| 7 | Publish | `studio publish` | master → YouTube (TikTok audit-gated). Setup: [`docs/40-publishing/youtube.md`](docs/40-publishing/youtube.md) |

`project.json` is the manifest: per-stage provider, cost, latency, done-flag. `studio status <id>` renders it. Stages are **idempotent** — re-running skips existing output (`--force` on visuals/clips to regenerate).

The **`film-maker` skill** (`.claude/skills/film-maker/`) is the operator playbook — invoke it when asked to produce, run, debug, or observe a video. It documents every stage's commands, providers, and how to inspect artifacts.

The **`marketing-guru` skill** (`.claude/skills/marketing-guru/`) is the growth half: a closed, **self-improving ideate→deploy→measure→learn** loop that picks *what* to make and judges how viral it was. It's backed by a per-channel **journal** (`runs/_marketing/<channel>/journal.json`) and the `studio marketing` CLI sub-app. The loop is decomposed into **per-step lego-block skills** any agent can use alone — `marketing-ideate` (generate bets) · `marketing-deploy` (produce+publish+link) · `marketing-measure-learn` (score virality, then reflect into strategy) — plus **`marketing-autopilot`** (the hands-off scheduled driver, handling the 48–72h measurement-maturation wait). The umbrella **`marketing-guru`** also owns the thin read/pick/report helpers (journal state, backlog pick per the shipped bandit / 60-40 fallback, growth brief) and links the canonical memory model. The **thinking is agent-driven; the CLI commands are I/O helpers.** Deep reference + memory model: [`docs/50-marketing/`](docs/50-marketing/) (start at `README.md`, then `memory.md`, the canonical memory reference); why this shape: [`docs/20-research/self-improving-loop.md`](docs/20-research/self-improving-loop.md). Its **channel-setup lego-block** is the **`youtube-branding` skill** (`.claude/skills/youtube-branding/`) — `studio brand <spec.json>` generates a full brand kit (banner, avatar, transparent video-watermark logo, keywords, description) into `runs/_brand/<slug>/`.

## Architecture map (where code lives)

```
studio/
  cli.py            typer app — every subcommand + `run` chainer + `status`
                    + `critic` (content gate) + `_script_with_critic` (bounded script↔critic
                      rework loop wired into `run`; --critic on|off|strict, --critic-retries)
                    + `marketing` sub-app: ideate|link|measure|learn|journal|report
                      + helpers add|backlog|recall|strategy|budget|bandit
                      + autonomous tick|autopilot
  config.py         env-key detection → default_provider(stage); free fallbacks
  models.py         Scene, Script (pydantic) + timing validation + CriticVerdict/CriterionScore (1.5 gate)
  manifest.py       Manifest/StageRecord — project.json read/write, cost rollup
  paths.py          canonical runs/<id>/ artifact paths
  canvas.py         live render W×H; set_from_aspect(aspect) at each rendering stage →
                    every ffmpeg/cardgen/image helper defaults w,h to it. 9:16 vertical
                    (default) | 16:9 landscape/classic YouTube | 1:1 | 4:5 | 4:3 | 21:9
  ffmpeg.py         ALL ffmpeg shelling: normalize/ken_burns/motion/still/kinetic/parallax/
                    parallax_layers/diag_slice/atmosphere/concat_xfade_seq/mux/burn/encode
  animate.py        free animators dispatch: kenburns|motion-*|kinetic|parallax|blurred-parallax|slice|static|puppet|talkinghead|manim
                    parallax = PERSPECTIVE/DEPTH scenery (mountains/clouds/houses) — depth planes drift; NOT for big foreground subjects (human/animal/single object dominating → floats as cutout; use static/slice/drift). Two real plates (near + bg) when present, else clean full-frame pan (no tear). blurred-parallax = old blurred panning planes
                    + atmosphere overlay post-pass (rain|snow|embers|blood|petals|leaves|wind|fog)
                    + fx look post-pass (Scene.fx): grain|vignette|chroma|glitch|sunrise|sunset|godrays|oldfilm|flash[-white|-yellow|-red|-black]
                    puppet = rembg cutout figure motion (idle/hop/shake/nod head)
                    talkinghead = Rhubarb 2D lip-sync (mouth sprites on a static face)
  tiers.py          tier presets (free/cheap/balanced/premium) → providers + strategy
  artdirect.py      HYBRID effect selection: validates the script LLM's per-scene effect
                    picks (animator/atmosphere/fx/transition) + fills gaps with content/
                    position heuristics (hook→kinetic, scenery→parallax, mood keywords→
                    atmosphere/fx) + taste caps (flash once; thin blanket atmosphere). This
                    is what makes the effect library actually get USED (not just kenburns) —
                    runs in stages/script.py for BOTH the LLM and offline stub paths.
  stages/<stage>.py one pure function per stage (incl. narrate.py + critic.py — the 1.5
                    content gate: LLM scores the scenario → CriticVerdict; NOT in STAGE_ORDER
                    (it's a script sub-step, looped by cli._script_with_critic))
  providers/
    base.py         GenResult(path, cost_usd, latency_s, provider, note)
    llm.py          script: stub|ollama|groq|openrouter|openai|gemini
    image.py        visuals: card(Pillow)|stub|pollinations|fal-nanobanana
    cardgen.py      Pillow: card images, caption strips, kinetic headlines
    video.py        clips AI: fal-i2v (kling/ltx/wan/hailuo/seedance) + FAL_MODELS prices
                    + local-i2v (FREE, local ComfyUI on MPS) → comfy_local.py
    comfy_local.py  local-i2v backend: patches workflows/*.json (wan-local|ltx-local),
                    submits to a running ComfyUI server, polls, pulls the mp4. SLOW
                    (minutes/clip), DRAFT-tier. `python -m studio.providers.comfy_local` to test.
    tts.py          voice: edge (SubMaker captions)|openai-tts; synth_scene for narrate
  voices.py         semantic voice (man/woman/cartoon/narrator) + tone -> TTS settings
    publish.py      youtube | tiktok(stub, audit-gated); _creds(channel, scopes) OAuth
    analytics.py    YouTube stats/comments (Data API) + retention/subs (Analytics API,
                    best-effort) — reuses the publish OAuth token
  marketing/        viral growth loop (marketing-guru skill)
    journal.py      Entry/Strategy/Journal/BudgetConfig/LoopConfig — per-channel ledger (json+md)
                    Entry holds production telemetry (cost/duration/animators/fx/model) too (T3)
    score.py        virality composite + portfolio percentile + win/loss verdict
    ideate.py       LLM: next bet from learned strategy + recall + web-search trend signals
    learn.py        LLM: reflect on measured bets → update strategy + next seeds
    memory.py       episodic recall — rank measured bets by relevance to a query (lexical)
    telemetry.py    T3: extract cost/duration/effects/model from a run manifest → Entry
    loop.py         T1 engine: plan(journal, now) → the one DUE action (measure|learn|
                    ideate|produce|idle); deferred-measurement state machine
    bandit.py       T8: warm-started Thompson sampling over theme+tags → next bet to produce
    brand.py        channel brand kit (banner/avatar/transparent logo + keywords/
                    description) from a spec → runs/_brand/<slug>/ (youtube-branding
                    skill; `studio brand`). Text-free art + Pillow safe-area wordmark
```

**Marketing / growth loop** = a self-improving `ideate→deploy→measure→learn` cycle, journal at
`runs/_marketing/<channel>/`. Cold-start (first 10 videos) explores; then exploits via a
warm-started Thompson bandit over theme+tags (T8). `film-maker` produces, `marketing-guru`
decides what & judges virality. **Memory:** long-term `Strategy` + episodic `Entry[]` ledger +
relevance `recall` (`memory.py`); each Entry also records its production telemetry (T3). **Budget:**
per-video or per-minute cap (`studio marketing budget`) → sizes each render's `--max-cost` (T4).
**Autonomous:** `studio marketing tick`/`autopilot` + the `marketing-autopilot` skill run the
whole loop on a schedule, handling the 48–72h measurement-maturation wait (`loop.py`, T1).
Full reference: [`docs/50-marketing/`](docs/50-marketing/) (loop `README.md` + memory `memory.md`).

**Animation/transitions** are per-scene, free, context-driven — full reference in
[`docs/30-animation/`](docs/30-animation/) (start at `README.md`; `scenario-schema.md`
is the authoritative `01_script.json` schema). Scene fields: `animator`, `transition`,
`transition_dur`, `manim_code`, `mouth_set`/`mouth_xy` (talkinghead). Wired animators:
`kenburns`·`motion-*`·`kinetic`·`parallax`·`blurred-parallax`·`slice`·`static`·`puppet`·`talkinghead`·`manim`
(unknown names → kenburns fallback). The full research-backed effect catalog
(rain, fire, fog, sunrise, water, grain, glitch, god-rays, morphs, kinetic type — ffmpeg
recipes / Manim snippets / GLSL / particles, each status-tagged + licensed) is
[`docs/30-animation/effects/`](docs/30-animation/effects/README.md). Don't inline that detail
here — link to the guides.

**Adding a provider** = one function in the relevant `providers/*.py` + a name branch; no pipeline change. **Adding a stage** = a `stages/*.py` function + a `cli.py` command + entry in `STAGE_ORDER`.

**Adding (or changing) an animator/effect — REQUIRED workflow (do all four):**
1. **Implement** — a name branch in `studio/animate.py` (+ any filtergraph in `studio/ffmpeg.py`, Pillow in `cardgen.py`), with a graceful fallback to `kenburns` on failure.
2. **Document + describe** — a page under `docs/30-animation/` (or `docs/30-animation/effects/`), and update the animator enum in `docs/30-animation/scenario-schema.md`, the decision matrix in `docs/30-animation/README.md`, this file's animator list, and `.claude/skills/film-maker/film-maker-guides.md` if it affects authoring.
3. **Generate a demo** — add a variant to the `EFFECTS` registry in `examples/make_examples.py` and render it: `python examples/make_examples.py <effect> --frames`. Eyeball it; polish before calling it done.
4. **Rebuild the gallery** — `python examples/build_index.py` → regenerates `./index.html` (the single-page inline-video gallery of every effect; gitignored, built from `examples/out/`). Open it to review all effects in one place.

## Running

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[fal]"          # add ,youtube to publish
# .env holds FAL_KEY (gitignored)

# free/offline smoke test (no keys, no network except edge-tts):
studio run "topic" --duration 12 \
  --script-provider stub --image-provider stub \
  --video-provider kenburns --voice-provider edge

# real balanced run (fal images+video; script on free LLM or stub):
studio run "topic" --duration 150 \
  --script-provider stub --image-provider fal-nanobanana \
  --video-provider fal-i2v --video-model kling --voice-provider edge

# per-stage + observe:
RID=$(studio init "topic" --duration 60)
studio script $RID && studio visuals $RID && studio status $RID
```

## Tiers & video strategy (the cost knobs)

`studio run --tier free|cheap|balanced|premium` sets every stage's provider via
`studio/tiers.py`; any `--*-provider` / `--video-strategy` / `--video-model` flag
overrides the preset.

| tier | images | video | ~cost / 150s | use |
|------|--------|-------|--------------|-----|
| free | stub (offline) | kenburns | **$0** | wiring/draft |
| cheap | **FLUX schnell** (all scenes) | kenburns (pan/zoom) | **~$0.15** | budget stills, no char consistency |
| balanced | **Nano Banana** hero **+ FLUX** bg | **auto** AI within `--max-cost` | **= max-cost** | best per dollar |
| premium | **Nano Banana** hero **+ FLUX** bg | AI every scene | $6–10+ | quality first |

**Images per tier** (`tiers.py`): `cheap` renders **every** scene on FLUX schnell (~$0.006/img, no character-reference consistency). `balanced`/`premium` split by `Scene.image_role`: **hero/character** scenes → Nano Banana (quality + char-ref); **`bg`** (backgrounds/overlays) → FLUX schnell (`visuals.py` `cheap_provider`). Override either with `--image-provider` / `--image-cheap-provider`.

Video `--strategy`: `kenburns` (free) · `all` (AI every scene) · `hybrid`
(`--ai-scenes 1,7,15`) · `auto` (smart: spend the budget on highest-priority scenes,
Ken-Burns the rest). Priority = `Scene.priority` else a hero heuristic (hook + outro +
spread). `--video-model` picks the fal model (ltx cheapest, kling default, etc).
Always `studio estimate <id>` first; clips **trims/aborts** to respect `--max-cost`.

## Provider defaults (config.default_provider)

Chosen by which keys are present in `.env`, else free fallback:
- script: openai→gemini→groq→openrouter→ollama→**stub** (offline split)
- visuals: fal-nanobanana (if `FAL_KEY`) → **stub** (offline color frame)
- clips: fal-i2v (if `FAL_KEY`) → **kenburns** (ffmpeg pan/zoom, free)
- voice: openai-tts (if `OPENAI_API_KEY`) → **edge** (free)

## Conventions

- Python ≥3.11, `ruff` line-length 120. Run `uvx ruff check studio/` before finishing.
- Type hints everywhere; `from __future__ import annotations` at top.
- **All ffmpeg goes through `studio/ffmpeg.py`** — never shell ffmpeg elsewhere.
- Every provider returns `GenResult` with real `cost_usd`/`latency_s` → manifest = measured cost, not guessed.
- **Costs are PER-SECOND for AI video** — a 150s kling video ≈ $10.50 no matter how clips are split. Real fal prices live in `video.FAL_MODELS` (verified 2026-06-04; kling $0.07/s CONFIRMED from billing; ltx ~$0.04/s @1080p; seedance ~$0.30/s; hailuo ~$0.045/s; wan ~$0.16/s — wan/hailuo are PER-SECOND, not flat: a wan 6s clip ≈ $0.80). Nano Banana stills = $0.039/img (verified). Always run `studio estimate <id>` before stage 3; `studio run` defaults to `--max-cost 3` and the clips stage **aborts pre-flight** if the estimate exceeds it. Cheapest real options for a tight budget: `kenburns` (free, pan/zoom on stills) or hybrid `--ai-scenes`.
- **`--max-cost` is the WHOLE-video budget (images + clips + music).** `studio run` reserves the music-bed cost (`audio.expected_music_cost`: `fal-stable-audio` = $0.20, all free providers = $0) BEFORE the clips stage, so clips can't eat the room music needs; if a paid bed still won't fit what's left, music **auto-downgrades to `local`** (free; silence if no packs) with a note. Cost ladder for a ~50s short (Nano Banana stills): paid music + 10s ltx ≈ $0.78 → music-in-budget caps it to **~$0.61** (6s hook + bed) at `--max-cost 0.70` → free music + 6s ltx ≈ $0.41 → free music + free `motion-*` only ≈ $0.17. **Biggest levers: the music bed ($0.20 → free `local`/`freesound`) and hook clip length (10s $0.40 → 6s $0.24, or free `motion-*`).** sfx is ~$0.002/s — negligible, not reserved.
- Don't hardcode secrets; read via `config.env()`. `.env`, `runs/`, `token.json`, `client_secret*.json` are gitignored.
- Commit only when the user asks.
- **Per-video build scripts MUST live in `builds/`, never at repo root.** Any `build_*.py` (one-off generators that author a `runs/<id>/01_script.json` by hand) goes in `builds/build_<slug>.py`. They are NOT part of the `studio` package — keeping them out of root keeps it clean and makes the back-catalog of authored videos discoverable in one place. **When creating a new one, write it straight into `builds/`; if you ever find a `build_*.py` at repo root, move it into `builds/` (it's a mistake).** Run them from repo root so their relative `runs/<id>/` output paths resolve: `python builds/build_<slug>.py`. See [`builds/README.md`](builds/README.md).

## Known gotchas (learned, still true)

- **`studio run <idea> --run-id <id>` RE-SCRIPTS from the positional idea argument, NOT the manifest.** `--run-id` only selects the directory; the script stage runs on whatever idea string you pass. Resuming a run with a placeholder (e.g. `studio run "ignored" --run-id …`) makes "ignored" the topic and silently discards the real idea. **To resume/continue an existing run, use the per-stage commands** (`studio script <id>`, `studio visuals <id>`, `studio clips <id>` …) — those read the idea from `project.json`. Only pass an idea to `studio run` for a brand-new run.
- **`--script-provider stub` is the OFFLINE WIRING generator, not a content generator.** It emits placeholder narration (`"{idea} — point N"`) and prompts (`"...part i of n, vibrant"`). NEVER run the paid `visuals`/`clips` stages downstream of a `stub` script — you'll pay to render meaningless filler. If `config.default_provider("script")` is `stub` (no LLM key set), STOP and add a free key (Groq/Gemini/OpenRouter) first. **Always read `01_script.json` and confirm the narration is real before spending.**
- **Pollinations anonymous tier now returns 402** (paywalled) — that's why `stub` is the keyless visuals default, not pollinations.
- **This machine's ffmpeg lacks BOTH `drawtext` (no libfreetype) AND `subtitles`/`ass` (no libass).** So captions are burned by overlaying **Pillow-rendered PNG strips** via the `overlay` filter (`ffmpeg.burn_subs` → `cardgen.caption_strip`). Don't switch to `subtitles=`/`drawtext` — they'll fail on this build. Free images use the Pillow `card` provider (also avoids drawtext).
- **edge-tts 7.x emits `SentenceBoundary`, not `WordBoundary`** — captions are built with `edge_tts.SubMaker().feed()/get_srt()` (sentence-level). Watch for `*Boundary` generically, not just WordBoundary.
- Most i2v models cap at **5–10s/clip** — `video.py` snaps the fal request to each model's accepted duration grid via `_clip_dur(model, seconds)` (default 5/10; **ltx-2 needs even integers and is sent as an int, capped at 10s = $0.40/clip**). Longer scenes hold the last frame via `normalize(target_dur=…)`. NOTE: ltx silently 400s on a string duration or one off its grid — keep new models in `_DUR_GRID`/`FAL_MODELS`, never hardcode `"5"`/`"10"`.
- **Music bed is ducked under narration** (`ffmpeg.duck_music`, sidechain). Default bed level is **−24 dB** (voice-forward); raise/lower `music_db` to taste. The non-ducked `mux_audio` path uses a flat `volume=0.15` for music.
- **Audio/video sync is narration-driven.** `narrate` sets per-scene clip durations = TTS length (`timing.json`); `clips`/`stitch` honor them; `concat_xfade_seq` overlap-compensates transitions; `mux_audio` never truncates (holds last frame + tail). Net: video length == narration (±tail), no drift. Don't reintroduce `-shortest`-style trimming.
- **`kinetic` over a `card` image double-renders the headline** (card bakes text). Pair `kinetic` with `fal-nanobanana` illustrations. See `docs/30-animation/kinetic.md`.
- **`local-i2v` = FREE local video gen via ComfyUI** (`studio clips --video-provider local-i2v --model wan-local|ltx-local`, or `studio run --video-provider local-i2v`). Needs a running ComfyUI server (default `http://127.0.0.1:8188`) + bf16 models on disk. **Use bf16, NOT fp8 — fp8 is broken on Metal/MPS.** It's a DRAFT tier: minutes per clip. `auto` strategy caps local AI scenes at `local_max_clips=6` (free per-clip cost would otherwise pick every scene → hours); `all` is uncapped (explicit). Clips capped 5s; render res = canvas aspect at longest-side 832 (`video._local_dims`). Workflow templates in `providers/workflows/*.json`; model filenames auto-filled from the live `/object_info`. ⚠️ 32 GB RAM is tight for Wan 5B fp16 + umt5 fp16 (~22 GB) — close other apps or it OOMs/swaps.
- **`parallax`/`manim` need optional extras** (`.[parallax]`, `.[manim]`); both fall back to `kenburns` (recorded in the manifest note) if missing/failing — pipeline never breaks. `slice` needs no extra.
- **`parallax` = PERSPECTIVE / DEPTH scenery (mountains, clouds, houses, skyline) — depth planes drift at different speeds.** 🚫 **Do NOT author it on a frame a human / animal / face / single object DOMINATES** (takes most of the space): a big close subject has no depth to reveal and floats as a flat cutout — use `static` / `slice` / `motion-drift*` there. A *small* figure inside a wide landscape is fine (it's the nearest plane). Compose the still as foreground→midground→horizon, not a portrait. Layer-source priority (`animate._parallax`): (1) **two real plates** — held near scenery over a clean `_bg.png` plate → composited directly, **no inpaint, no tear** (balanced+ default; `studio visuals --parallax-plates`); else (2) a **clean full-frame pan** over the vista (never subject-inpainted — that's what used to tear a skyline into a smeared seam). Direction from `motion_hint` (`right`/`left`/`up`/`down`). **Quality bar: aim for LAYERED depth — ≥2 clean planes; reach for 3 (hand-author far/mid/near PNGs; `parallax_drift` takes a per-plane `depth`) on the hero/establishing landscape.** **`blurred-parallax`** = the old soft look (blurred panning planes) — its 2-plane sky/ground mode is a free layered-depth shortcut for scenery. See `docs/30-animation/parallax.md`.
- **`manim_code` must be authored flush-left** (or consistently indented); `animate._manim` dedents+reindents, but mixed indentation breaks it. Make vector effects **literal** (real path/silhouette/flash), not abstract lines. See `docs/30-animation/manim.md`.
- **Captions are OFF by default** — YouTube/TikTok auto-generate them and a burned wall of text covers the visuals. `narrate` still writes `captions.srt` (upload as a sidecar). Opt in with `--captions burn`. When burned, `cardgen.caption_strip` is **fill-width wrapped (fewest lines) + font-shrunk to a ~22%-of-H budget + hard height-capped**, overlaid at `H-h-(~0.115*H)`, so the block can NEVER clip top or bottom in any aspect. (Past bug: long 150-char sentence cues rendered at near-full font across 7 lines and overflowed.) See `docs/30-animation/captions.md`.
- **fal/Nano-Banana blocks overt violence/gore** (bound prisoner, severed head, blood) → returns no media → that scene stubs (1-color 10 KB PNG). Imply violence symbolically; let narration carry it. Rewrite flagged prompts and re-`--force` visuals.
- **The quality playbook is `.claude/skills/film-maker/film-maker-guides.md`** — read it (and operator preferences) before authoring scenes for a video that must look great.
- TikTok auto-publish is **private-only until a 2–4 week app audit** (verified) — `publish.py` tiktok raises with that explanation by design.

## Roadmap (follow-up tasks)

Avatar narrator format · mixed avatar+B-roll · RunPod self-host video cost pilot · commercial-safe TTS · TikTok audit. See `docs/20-research/open-questions.md`.
