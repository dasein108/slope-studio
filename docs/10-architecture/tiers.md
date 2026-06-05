# Architecture Tiers — Budget / Balanced / Premium

Three reference stacks sharing the same CLI/manifest/adapters. Switch per-stage via `--tier` or per-stage `--provider`. Costs are 🔶 estimates except where ✅ verified; treat stage-3 (video) numbers as pilot-measure-first.

---

## Budget — "$0 / draft / demo" {#budget}

Goal: working end-to-end short for free. ✅ Research-verified that this works **without true AI video** and without real public auto-publish.

| Stage | Pick | Cost |
|-------|------|------|
| Script | OpenRouter `:free` / Groq `llama-3.1-8b-instant` / Ollama | $0 ✅ |
| Visuals | Pollinations.ai (watermark/throttle ✅) or self-host SDXL | $0 ✅ |
| Video | **No AI video** — ffmpeg Ken Burns on stills, or Pexels stock B-roll | $0 ✅ |
| Stitch | ffmpeg | $0 ✅ |
| Voiceover | edge-tts (ToS-gray ✅) + faster-whisper captions ✅ | $0 ✅ |
| Save | ffmpeg | $0 |
| Publish | YouTube Data API (TikTok self_only only ✅) | $0 |

- **Per-video: ~$0.** **Quality:** static/stock visuals, robotic-ish VO. Fine for high-volume faceless channels, testing the pipeline, slideshow-style explainers.
- **Limits:** rate caps (OpenRouter ~50/day ✅, Pollinations ~1/15s ✅), watermarks, ToS gray (edge-tts ✅). Not the "AI video" product — it's the floor.

---

## Balanced — "cheap + accurate" (recommended default)

Goal: real AI video, consistent character, natural VO, automatable — minimum cost that still looks good.

| Stage | Pick | Cost 🔶 (✅ noted) |
|-------|------|------|
| Script | GPT-4o-mini / Gemini 2.5 Flash | ~$0.005 |
| Visuals | **Nano Banana** $0.039/img ✅, character-consistent ✅ (~6-10 imgs) | ~$0.25-0.40 |
| Video | Kling 2.5 Turbo / Hailuo / Seedance via **fal.ai** (i2v, ~6-10 clips) | ~$0.15-0.50 (dominant) |
| Stitch | ffmpeg | $0 |
| Voiceover | edge-tts (draft) → OpenAI TTS / Kokoro (final) | $0-0.10 |
| Avatar (opt) | Hedra / self-host LatentSync | varies |
| Save | ffmpeg | $0 |
| Publish | YouTube Data API; TikTok self_only ✅ | $0 |

- **Per-video: ~$0.30-0.80** at API rates. Drops to **~$0.05-0.15** if you **self-host video on RunPod at volume** (pilot-measure — sourced cost figures were refuted ⚠️).
- **Quality:** genuinely good shorts with a consistent character. **This is the cheapest-accurate target.**

---

## Premium — "hero / quality-first"

Goal: best achievable quality; cost secondary.

| Stage | Pick | Cost 🔶 (✅ noted) |
|-------|------|------|
| Script | Claude Sonnet/Opus or GPT-4o | ~$0.05-0.20 |
| Visuals | Nano Banana 2 (14 refs ✅) / FLUX Pro Ultra / trained LoRA | ~$0.50-1.50 |
| Video | **Veo 3** ($0.40/s ✅, native audio) / Runway Gen-4.5 (#1 Dec-2025 ✅) / Kling 2.5 Turbo Pro | high — see below |
| Stitch | ffmpeg + designed transitions/overlays | $0 |
| Voiceover | ElevenLabs (best ✅-quality leader) | ~$0.10-0.50 |
| Avatar | HeyGen / Synthesia | per-min SaaS |
| Save | ffmpeg | $0 |
| Publish | YouTube + TikTok (audited app) | audit lead time ✅ |

- **Video cost dominates:** Veo 3 at $0.40/s ✅ → a 150s video of pure Veo footage ≈ **$60** (150 × $0.40). Runway/Kling credit plans similar order. This is why even "premium" uses **short hero clips**, not 150s of continuous top-model footage.
- **Per-video: ~$5-60+** depending on how much premium video you actually generate vs. reuse/extend.

---

## Implemented as (CLI)

Tiers are real presets in `studio/tiers.py`; `studio run --tier <t>` applies them.
Video cost is controlled by `--strategy` (in `studio/stages/clips.py`):

| strategy | behavior | cost |
|----------|----------|------|
| `kenburns` | pan/zoom on every still | $0 |
| `all` | AI i2v on every scene | per-second × full duration |
| `hybrid` | AI only on `--ai-scenes 1,7,15` | per-second × those scenes |
| `auto` | **smart**: spend `--max-cost` on highest-priority scenes, Ken-Burns rest | ≤ max-cost |

`auto` ranks scenes by `Scene.priority` (else hook + outro + every-3rd heuristic) and
greedily animates until the budget is exhausted. `--video-model` picks the fal model
(`ltx` cheapest → `seedance` priciest). `studio estimate <id>` previews the full table;
the clips stage estimates per-second cost up front and **aborts (all/hybrid) or trims
(auto)** so spend never exceeds `--max-cost` (default $3 on `studio run`).

## Cross-tier notes
- **Video is always the cost center.** The lever from $60 → $0.15 is: fewer/shorter premium clips → cheaper hosted models → self-hosted open models at volume → no-AI-video (budget). See [`cost-model.md`](cost-model.md).
- **Mix tiers per video:** premium hook clip + balanced body + budget filler is a common cost-effective pattern.
- **Re-verify stage 2-3 monthly** — rankings/prices churn (Dec-2025 leaderboard already superseded by Feb-Mar 2026 ✅).
