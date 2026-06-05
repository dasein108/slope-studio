# Slope Studio

Automated short-video studio: **idea → published Short**. Faceless MVP, balanced tier, YouTube-first, plain Python CLI.

Each of the 7 stages is an independent `studio` subcommand; `studio run` chains them with resume. Every paid stage has a **free fallback**, so the full pipeline runs end-to-end with **zero API keys** (degraded quality), then you swap real providers in via `--provider`.

**▶ Want the hands-off, minimal-effort way to run everything?** Read the
[operator guide](docs/00-overview/operator-guide.md) — every skill + feature, and the
exact human steps, in one page.

Full research + architecture: see [`docs/`](docs/) (start at [`docs/README.md`](docs/README.md)).

## Install

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[fal]"        # add ,youtube for publishing
cp .env.example .env              # fill FAL_KEY etc (all optional)
```
Requires `ffmpeg` + `ffprobe` on PATH.

## Quickstart (free path, no keys)

```bash
# full pipeline, offline stub script + pollinations + ken-burns + edge-tts
studio run "why octopuses are basically aliens" --duration 30 \
  --script-provider stub --image-provider pollinations \
  --video-provider kenburns --voice-provider edge
```

## Pick a tier (the cost knob)

`--tier` sets all providers + video strategy; `--max-cost` (default $3) caps spend.
AI video is billed **per second** — run `studio estimate <id>` before stage 3.

```bash
studio estimate <run-id> --budget 3                 # preview video cost per model

# cheap: Nano Banana stills + free Ken-Burns motion (~$0.59 / 150s)
studio run "the chemistry of humor" --duration 150 --tier cheap

# balanced: stills + SMART AI video filling the budget on the best scenes
studio run "the chemistry of humor" --duration 150 --tier balanced --video-model ltx --max-cost 3

# premium: AI on every scene (uncap with --max-cost 0)
studio run "topic" --duration 60 --tier premium --max-cost 0
```

| tier | images | video | ~cost / 150s |
|------|--------|-------|--------------|
| free | offline stub | kenburns | $0 |
| cheap | Nano Banana | kenburns (pan/zoom) | ~$0.59 |
| balanced | Nano Banana | **auto** AI within `--max-cost` | = max-cost |
| premium | Nano Banana | AI every scene | $6–10+ |

Video `--strategy`: `kenburns` · `all` · `hybrid` (`--ai-scenes 1,7,15`) · `auto` (smart fill).

## Per-stage (decomposed)

```bash
RID=$(studio init "octopuses are aliens" --duration 150)
studio script  $RID
studio visuals $RID --provider fal-nanobanana
studio clips   $RID --provider fal-i2v --model kling
studio stitch  $RID --transition fade
studio voice   $RID --provider edge --captions burn
studio save    $RID
studio publish $RID --target youtube --privacy public
studio status  $RID
```

Artifacts live in `runs/<id>/` (see [`docs/00-overview/pipeline-stages.md`](docs/00-overview/pipeline-stages.md)). Stages are idempotent: re-running skips existing output (use `--force` on visuals/clips to regenerate).

## Providers

| Stage | Options | Free fallback |
|-------|---------|---------------|
| script | openai · gemini · groq · openrouter · ollama · **stub** | stub (offline) |
| visuals | **fal-nanobanana** ($0.039/img) · pollinations · **stub** | stub (offline) |
| clips | strategy: kenburns(free) · auto · hybrid · all; model: ltx · **kling** · wan · hailuo · seedance | kenburns |
| voice | openai-tts · **edge** | edge |
| publish | youtube · tiktok (stub: audit-gated) | — |

**Cost reality:** AI video is per-second (kling $0.07/s → 150s ≈ $10.50; ltx ≈ $6).
No hosted AI-video model fits $2–3 for 150s — use `kenburns` (free) or `auto`/`hybrid`
to animate only hero scenes within budget. See `docs/10-architecture/cost-model.md`.

## Grow the channel (viral loop)

Producing a Short is half the job; growing a channel is the other half. The
**`marketing-guru`** workflow runs a closed feedback loop — **ideate → deploy → measure
→ learn** — backed by a per-channel journal, so each video is a falsifiable bet and the
next idea is steered by what actually went viral *for your channel*.

```bash
studio marketing ideate  --channel pols --provider gpt-4o-mini --n 3   # record viral bets
#   → deploy each with: studio run "<idea>" --publish-to youtube --channel pols
studio marketing link    j0001 <run-id> --channel pols                 # bind run → bet
studio marketing measure --channel pols                                # virality vs portfolio
studio marketing learn   --channel pols --provider gpt-4o-mini         # update strategy
studio marketing journal --channel pols                                # see the ledger
```

First **10 videos are exploration** (no baseline yet); after that the loop ranks winners
vs losers and exploits. Stats/comments use the readonly scope publishing already grants;
retention is best-effort (one optional re-auth). Full guide:
[`docs/50-marketing/`](docs/50-marketing/) + the `marketing-guru` skill.

## Status & roadmap

MVP = faceless scene videos. Follow-ups tracked: avatar narrator, mixed avatar+B-roll, RunPod self-host cost pilot, commercial TTS, TikTok audit. See [`docs/20-research/open-questions.md`](docs/20-research/open-questions.md).
