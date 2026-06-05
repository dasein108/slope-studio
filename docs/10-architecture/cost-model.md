# Cost Model — Per-150s-Video Estimates

> ⚠️ **Important gap:** the deep-research pass **refuted** the only sourced self-hosted video cost/throughput figures (Spheron Wan blog, 0-3 — see [`../20-research/refuted.md`](../20-research/refuted.md)) and several hosted prices (Veo 3.1, Kling subs). So there is **no fully verified end-to-end cost-per-150s number**. Below mixes ✅ verified unit prices with 🔶 estimates and clearly flags which is which. **Pilot-measure stage 3 before committing.**

## ⚡ MEASURED fal i2v prices (from this project's own billing, Jun 2026)

**The single most important lesson: hosted AI video is billed PER SECOND of output.**
A 150s video costs the same whether you make 15×10s or 30×5s clips. Confirmed real prices:

| fal model | real price | 150s of AI video |
|-----------|-----------|------------------|
| kling 2.5 turbo pro | **$0.07/s** (confirmed: $0.70 per 10s clip) | **$10.50** |
| LTX-2 Fast (720p) | ~$0.04/s | ~$6.00 |
| Kling V3 std | ~$0.084/s | ~$12.6 |
| Seedance | ~$0.30/s | ~$45 |
| Hailuo 2.3 | ~$0.49/video (flat) | depends on clip count |
| Wan Pro | ~$0.16/video (flat) | depends on clip count |
| Nano Banana still | $0.039/img | ~$0.59 for 15 stills |

**Implication: no hosted AI-video model produces 150s for $2-3.** For that budget use
`kenburns` (free pan/zoom on the Nano Banana stills, total ≈ $0.59) or a **hybrid** —
AI-animate a few hero scenes, Ken-Burns the rest. `studio estimate <id>` prints this
table per run; `studio run` defaults to `--max-cost 3` and aborts pre-flight.

> Earlier this doc carried a flat ~$0.05/clip placeholder — that was WRONG (per-second,
> not per-clip). Corrected from real billing data. This closes research gap Q1 for kling.

## Verified unit prices (✅)
- Nano Banana image: **$0.039/img** ✅
- Veo 3 video: **$0.40/s** standard, **$0.15/s** Fast ✅
- Sora 2 API: **$0.10-0.50/s** ✅
- Runway Gen-3: 10 credits/s (Alpha), 5/s (Turbo) ✅
- RunPod on-demand: RTX 4090 **$0.69/hr**, A6000 **$0.49/hr**, A100 80GB **$1.39-1.49/hr**, H100 **$2.89-3.29/hr** ✅ (Community Cloud cheaper, e.g. 4090 ~$0.34/hr)
- edge-tts, Pollinations, ffmpeg, faster-whisper, YouTube API quota: **$0** ✅

## Structural assumption
A 150s short ≈ **8-15 scenes**, each a 5-10s clip. Most cost = (images) + (video clips) + (TTS). Stitch/save/captions ≈ free.

## Tier estimates (per 150s video)

### Budget — ~$0 ✅
No AI video (Ken Burns/stock), free LLM, Pollinations, edge-tts. Verified workable ✅. Quality: slideshow/stock.

### Balanced — ~$0.30-0.80 (API) 🔶
- Script: ~$0.005 (GPT-4o-mini) 🔶
- Visuals: 8 imgs × $0.039 = **$0.31** ✅ unit price
- Video: 8 clips × ~$0.02-0.06/clip via fal.ai (Kling/Hailuo/Seedance) = **$0.15-0.50** 🔶 (re-check fal pricing)
- TTS: ~150s narration; OpenAI TTS ~$0.02-0.06 🔶, or $0 with edge-tts/Kokoro
- **Total: ~$0.30-0.80** 🔶 (video estimate is the soft number)

### Balanced + self-host video on RunPod — ~$0.05-0.20 🔶 (UNVERIFIED)
- The pitch: rent a GPU per-second ✅, run Wan 2.2, amortize over many clips.
- Worked example **with assumed throughput** (⚠️ assumption, not verified — the real figures were refuted): *if* an A100 80GB ($1.39/hr ✅ = $0.000386/s) renders a 5s clip in ~3 min (180s) → ~$0.069/clip → 8 clips ≈ **$0.56** + images/TTS. *If* it renders in ~60s → ~$0.023/clip → 8 ≈ $0.18. **Throughput is the unknown that decides everything → measure it in a pilot.**
- Self-host only beats serverless APIs **above a break-even volume** (warm GPU vs idle cost + cold starts). For low/bursty volume, **fal.ai/Replicate per-call is cheaper and simpler.**

### Premium — ~$5-60+ 🔶
- Pure Veo 3: 150s × $0.40/s = **$60** ✅ math. Nobody does 150s of continuous top-model video — use short hero clips.
- Realistic premium: ~20-40s of Veo/Runway hero footage ($8-16) + balanced body + ElevenLabs VO ($0.10-0.50) → **~$10-20**.

## The cost levers (high → low)
1. **Less premium video time** — short hero clips, reuse, Extend features (Runway →40s ✅) instead of fresh gen.
2. **Cheaper hosted model** — Kling/Hailuo/Seedance ≪ Veo/Runway/Sora per second 🔶.
3. **Self-host open models** — Wan/LTX on RunPod at volume 🔶 (measure first ⚠️).
4. **No AI video** — Ken Burns/stock → $0 ✅ (budget tier).
5. **Free TTS** — edge-tts/Kokoro → $0 ✅.

## LoRA one-time cost (amortized, not per-video)
🔶 ~$1-5 RunPod GPU time to train one FLUX character LoRA (community guides cite ~$1; treat as ballpark). Amortizes across every video using that character → ~$0 per video after.

## Recommendation for accurate budgeting
Instrument the manifest (`cost_usd` per stage — see [`cli-component-design.md`](cli-component-design.md)) and run **10 pilot videos per tier** to get *measured* cost-per-video. Do not ship a cost promise off the 🔶 estimates above; the video stage variance is too high and the public figures churn/were refuted.
