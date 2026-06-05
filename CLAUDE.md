# CLAUDE.md — Slope Studio

Guidance for Claude Code working in this repo. Read this first.

## What this is

An **automated short-video studio**: text idea → finished vertical Short (TikTok / YouTube Shorts). A 7-stage pipeline where **each stage is an independent CLI subcommand** and they also chain via `studio run`. Current scope = **faceless scene videos**, **balanced** cost/quality tier, **YouTube-first** publishing, **plain Python CLI** orchestration.

Deep research + architecture rationale lives in [`docs/`](docs/) — start at `docs/README.md`. Don't duplicate it here; link to it. The **hands-off operator guide** (how to use both skills + every feature with minimal human effort) is [`docs/00-overview/operator-guide.md`](docs/00-overview/operator-guide.md).

## The 7 stages (data flows through `runs/<id>/`)

| # | Stage | CLI | Input → Output |
|---|-------|-----|----------------|
| 1 | Script | `studio script` | idea → `01_script.json` (timed scenes + narration) |
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
                    + `marketing` sub-app: ideate|link|measure|learn|journal|report
                      + helpers add|backlog|recall|strategy|budget|bandit
                      + autonomous tick|autopilot
  config.py         env-key detection → default_provider(stage); free fallbacks
  models.py         Scene, Script (pydantic) + timing validation
  manifest.py       Manifest/StageRecord — project.json read/write, cost rollup
  paths.py          canonical runs/<id>/ artifact paths
  canvas.py         live render W×H; set_from_aspect(aspect) at each rendering stage →
                    every ffmpeg/cardgen/image helper defaults w,h to it. 9:16 vertical
                    (default) | 16:9 landscape/classic YouTube | 1:1 | 4:5 | 4:3 | 21:9
  ffmpeg.py         ALL ffmpeg shelling: normalize/ken_burns/motion/still/kinetic/parallax/
                    parallax_layers/diag_slice/atmosphere/concat_xfade_seq/mux/burn/encode
  animate.py        free animators dispatch: kenburns|motion-*|kinetic|parallax|blurred-parallax|slice|static|puppet|talkinghead|manim
                    parallax = static subject + REAL bg drift (subject inpainted out); blurred-parallax = old blurred panning planes
                    + atmosphere overlay post-pass (rain|snow|embers|blood|petals|leaves|wind|fog)
                    + fx look post-pass (Scene.fx): grain|vignette|chroma|glitch|sunrise|sunset|godrays|flash[-white|-yellow|-red|-black]
                    puppet = rembg cutout figure motion (idle/hop/shake/nod head)
                    talkinghead = Rhubarb 2D lip-sync (mouth sprites on a static face)
  tiers.py          tier presets (free/cheap/balanced/premium) → providers + strategy
  stages/<stage>.py one pure function per stage (incl. narrate.py)
  providers/
    base.py         GenResult(path, cost_usd, latency_s, provider, note)
    llm.py          script: stub|ollama|groq|openrouter|openai|gemini
    image.py        visuals: card(Pillow)|stub|pollinations|fal-nanobanana
    cardgen.py      Pillow: card images, caption strips, kinetic headlines
    video.py        clips AI: fal-i2v (kling/ltx/wan/hailuo/seedance) + FAL_MODELS prices
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
| cheap | Nano Banana | kenburns (pan/zoom) | **~$0.59** | budget hero stills |
| balanced | Nano Banana | **auto** AI within `--max-cost` | **= max-cost** | best per dollar |
| premium | Nano Banana | AI every scene | $6–10+ | quality first |

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
- Don't hardcode secrets; read via `config.env()`. `.env`, `runs/`, `token.json`, `client_secret*.json` are gitignored.
- Commit only when the user asks.
- **All per-video build scripts live in `builds/`** (e.g. `builds/build_before_the_law.py`, `builds/build_first_sorrow.py`). These are one-off generators that author a `runs/<id>/01_script.json` by hand — they are NOT part of the `studio` package and shouldn't sit at repo root. Keeping them in `builds/` keeps the root clean, makes the back-catalog of authored videos discoverable in one place, and separates throwaway authoring scripts from the reusable pipeline code. Run them from repo root so their relative `runs/<id>/` output paths resolve (`python builds/build_first_sorrow.py`).

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
- **`parallax`/`manim` need optional extras** (`.[parallax]`, `.[manim]`); both fall back to `kenburns` (recorded in the manifest note) if missing/failing — pipeline never breaks. `slice` needs no extra.
- **`parallax` = static sharp subject + REAL background drifting** — the subject is **inpainted out** of the background (`animate._inpaint_subject`, free blur-diffusion, no OpenCV) so the drifting plane has **no ghost twin**. Direction from `motion_hint` (`right`/`left`/`up`/`down`). Best over smooth scenery. **`blurred-parallax`** = the old soft look (blurred panning planes, `gblur` hides the ghost) — for busy backgrounds. See `docs/30-animation/parallax.md`.
- **`manim_code` must be authored flush-left** (or consistently indented); `animate._manim` dedents+reindents, but mixed indentation breaks it. Make vector effects **literal** (real path/silhouette/flash), not abstract lines. See `docs/30-animation/manim.md`.
- **Captions are OFF by default** — YouTube/TikTok auto-generate them and a burned wall of text covers the visuals. `narrate` still writes `captions.srt` (upload as a sidecar). Opt in with `--captions burn`. When burned, `cardgen.caption_strip` is **fill-width wrapped (fewest lines) + font-shrunk to a ~22%-of-H budget + hard height-capped**, overlaid at `H-h-(~0.115*H)`, so the block can NEVER clip top or bottom in any aspect. (Past bug: long 150-char sentence cues rendered at near-full font across 7 lines and overflowed.) See `docs/30-animation/captions.md`.
- **fal/Nano-Banana blocks overt violence/gore** (bound prisoner, severed head, blood) → returns no media → that scene stubs (1-color 10 KB PNG). Imply violence symbolically; let narration carry it. Rewrite flagged prompts and re-`--force` visuals.
- **The quality playbook is `.claude/skills/film-maker/film-maker-guides.md`** — read it (and operator preferences) before authoring scenes for a video that must look great.
- TikTok auto-publish is **private-only until a 2–4 week app audit** (verified) — `publish.py` tiktok raises with that explanation by design.

## Roadmap (follow-up tasks)

Avatar narrator format · mixed avatar+B-roll · RunPod self-host video cost pilot · commercial-safe TTS · TikTok audit. See `docs/20-research/open-questions.md`.
