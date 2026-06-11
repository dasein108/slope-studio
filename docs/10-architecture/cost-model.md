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
2. **Cheaper hosted model** — ltx ($0.04/s ✅ cheapest) / Hailuo / Kling ≪ Veo/Runway/Sora 🔶.
3. **Shorter hook clip** — i2v snaps to a duration grid: ltx 10s = $0.40 → **6s = $0.24** (keep the AI scene ≤6s). ✅
4. **Free motion instead of i2v** — `motion-*` (pan/drift/zoom/pulse) and `kenburns` give real motion at **$0**; reserve i2v for the hook (or none). ✅
5. **Music bed choice** — `fal-stable-audio` = $0.20/video; `local` (vetted reusable packs) / `freesound` (CC0 key) / `synth` = **$0** ✅. sfx is ~$0.002/s on fal and often $0 locally — negligible.
6. **Free TTS** — edge-tts/Kokoro → $0 ✅.
7. **No AI video** — all Ken Burns/stock → $0 ✅ (free tier).

### Whole-video budget (music included)
`--max-cost` caps the **entire** video (images + clips + music). `studio run` reserves the
music-bed cost before the clips stage and **auto-downgrades paid fal music to synth** if it won't
fit (`studio/cli.py` + `audio.expected_music_cost`). Cost ladder for a ~50s short (Nano Banana stills):

| recipe | total |
|--------|-------|
| paid music + 10s ltx hook (pre-budget-fix) | ~$0.78 |
| `--max-cost 0.70` → paid music + 6s ltx hook | **~$0.61** |
| free music + 6s ltx hook | ~$0.41 |
| free music + free `motion-*` only | ~$0.17 |
| all flux-schnell stills + free motion | ~$0.04 |

## LoRA one-time cost (amortized, not per-video)
🔶 ~$1-5 RunPod GPU time to train one FLUX character LoRA (community guides cite ~$1; treat as ballpark). Amortizes across every video using that character → ~$0 per video after.

## Recommendation for accurate budgeting
Instrument the manifest (`cost_usd` per stage — see `studio/manifest.py` and `studio/cli.py`) and run **10 pilot videos per tier** to get *measured* cost-per-video. Do not ship a cost promise off the 🔶 estimates above; the video stage variance is too high and the public figures churn/were refuted.
