# Stage 3 — Video (Clips from Scenes / Avatar / Both)

The cost + quality center of the whole studio. Three sub-modes:

- **A. Scene clips** — animate each keyframe (image-to-video) or generate from text (text-to-video).
- **B. Avatar clips** — drive a character face to speak the narration (talking-avatar / lip-sync).
- **C. Both** — avatar composited over generated scene backgrounds.

## Key reality: clips are short
Most models generate **5-10s** per call. A 150s video = many clips. Long beats are handled by **Extend** features (Runway up to ~40s ✅) or by chaining/last-frame-continuation. Plan stage 1 scenes around the cap.

## Hosted video model options (price / features / speed / quality)

> ✅ verified facts noted. ⚠️ several specific prices were **refuted** — see [`../20-research/refuted.md`](../20-research/refuted.md). 🔶 = approximate, re-verify before spending.

| Model | Clip len / res | API price 🔶 (✅ noted) | Quality | Notes |
|-------|---------------|---------|---------|-------|
| **Runway Gen-4.5 / Gen-4** | 5-10s, 720p+ | credits 🔶 | top-tier | **#1 Video Arena Dec-2025 (1247 Elo)** ✅ — snapshot, churns ✅ |
| **Google Veo 3 / 3.1** | **~8s** ✅, 720p/1080p (480p Fast) ✅ | **$0.40/s std, $0.15/s Fast** ✅ (Gemini API) | top-tier, native audio | #2 Dec-2025 ✅; Veo 3.1 ~$0.75/s claim **refuted** ⚠️ |
| **Kling 2.5 Turbo Pro** | 5-10s, up to 1080p | 🔶 (subscription claims refuted ⚠️) | top-tier | **#3 Dec-2025 (1225)** ✅; excellent i2v value |
| **Luma Ray 3 / Dream Machine** | 5-10s | 🔶 credits | high | #5 Dec-2025 (1211) ✅; good motion |
| **Hailuo / MiniMax** | 6-10s | 🔶 cheap | high | strong price/quality for i2v |
| **Seedance (ByteDance)** | 5-10s | 🔶 cheap | high | Seedance 2.0 led by Feb-Mar 2026 ✅ (leaderboard turned over) |
| **Pika** | 3-10s | 🔶 sub/credits | good | fast, stylized, effects |
| **OpenAI Sora 2** | seconds, up to **1080p** ✅ | **$0.10-0.50/s** API (Oct 7 2025) ✅; Pro via $200/mo ChatGPT Pro ✅ | top-tier, audio | invite-gated at launch ✅ |
| **Runway Gen-3** | **up to 10s** ✅, **720p** ✅, Extend→**40s** ✅ | 10 cr/s Alpha, 5 Turbo ✅ | high | older but documented + cheap Turbo |

## Open-source video models (self-host on RunPod)

> ⚠️ The only sourced VRAM/throughput/cost-per-clip figures (Spheron blog) were **refuted 0-3** — do **not** cite them. Pilot-measure your own numbers. Below is qualitative 🔶.

| Model | Notes 🔶 |
|-------|-------|
| **Wan 2.1 / 2.2** (Alibaba) | leading open i2v/t2v; 14B (quality) + smaller variants; runs on 24-48GB+ GPUs depending on res/quant. Best open default. |
| **HunyuanVideo** (Tencent) | high quality t2v, larger VRAM appetite; LoRA ecosystem growing. |
| **LTX-Video** (Lightricks) | fast/lightweight, real-time-ish on smaller GPUs; lower fidelity than Wan/Hunyuan. |
| **CogVideoX** | older, modest VRAM, decent i2v. |
| **Mochi 1** (Genmo) | strong open t2v, heavy VRAM. |

Self-host economics: ✅ RunPod per-second billing (RTX 4090 $0.69/hr, A6000 $0.49/hr, A100 80GB $1.39-1.49/hr, H100 $2.89-3.29/hr; Community Cloud cheaper, e.g. 4090 ~$0.34/hr). Self-host wins **at volume** (warm GPU amortizes), loses for bursty/low volume (cold starts, idle cost) vs serverless APIs. See [`../10-architecture/cost-model.md`](../10-architecture/cost-model.md).

**Serverless middle ground:** [fal.ai](https://fal.ai) / [Replicate](https://replicate.com) host Wan/Kling/Hailuo/Seedance/LTX behind pay-per-call APIs — no infra, per-second-ish billing, the pragmatic default before committing to self-host.

## Talking-avatar / lip-sync options (sub-mode B)

> 🔶 prices approximate. Research verified a HeyGen-vs-Hedra comparison exists but not current prices — re-check.

| Tool | Type | Notes 🔶 |
|------|------|-------|
| **HeyGen** | SaaS | best polished talking avatars; API; credit/sub pricing; commercial-friendly |
| **D-ID** | SaaS | photo→talking-head API; per-minute pricing; fast |
| **Hedra** (Character-3) | SaaS | expressive character video from image+audio; strong emotion |
| **Synthesia** | SaaS | enterprise avatars, pricey |
| **LatentSync** (open) | self-host | SOTA open lip-sync; run on RunPod |
| **SadTalker / Wav2Lip / MuseTalk** (open) | self-host | cheaper/older; Wav2Lip robust but low-res; MuseTalk realtime |

Pipeline for avatars: stage 2 character face → stage 5 TTS narration → drive face with audio here → composite. Lip-sync needs the audio first, so for avatar mode **stage 5 (TTS) runs before/with stage 3**.

## Recommendation
- **Default (balanced):** Kling 2.5 Turbo or Hailuo/Seedance via **fal.ai** for i2v of stage-2 keyframes — best quality/$ without infra.
- **Volume:** self-host **Wan 2.2** on RunPod once you exceed ~the break-even (pilot-measure cost/clip first ⚠️).
- **Premium/hero:** Veo 3 (native audio, $0.40/s ✅) or Runway Gen-4.5.
- **Free/draft:** skip true AI video — Ken Burns pan/zoom on stage-2 stills via ffmpeg, or stock (Pexels). ✅ This is the verified $0 path.
- **Narrator channel:** Hedra/HeyGen avatar (or self-host LatentSync) lip-synced to stage-5 audio.

## CLI
```
# image-to-video per scene
studio clips --visuals runs/<id>/02_visuals/ --mode i2v \
  --provider fal:kling-2.5 --max-clip-s 8 --out runs/<id>/03_clips/

# talking avatar (needs audio from stage 5 first)
studio clips --mode avatar --face runs/<id>/02_visuals/character/ref_front.png \
  --audio runs/<id>/05_voice/narration.mp3 --provider hedra --out runs/<id>/03_clips/

# self-hosted Wan on RunPod
studio clips --mode i2v --provider runpod:wan2.2 --gpu a100-80gb --out ...
```
