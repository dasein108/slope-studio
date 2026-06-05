# Refuted Claims — Do NOT Rely On These

These 6 claims were **killed** (0-3 vote — all 3 adversarial verifiers refuted) during the research pass. Listed so they aren't accidentally reintroduced. The fact a number appears on a blog does not make it true.

---

## R1 — "Fully free $0/month YouTube automation pipeline with true AI video" ❌ 0-3
The narrow free CLI pipeline survives (see [F1](findings.md#f1--a-fully-free-end-to-end-cli-pipeline-is-buildable-without-true-ai-video--high)), but the broader claim — a $0/month pipeline that includes **true AI video generation** and **real automated public YouTube publishing** using only open/free tools (Ollama/Groq + Edge-TTS + Pexels + FFmpeg + YouTube API) — was refuted. The free stack uses **stock footage / image pans, not AI-generated video**, and free publishing has quota/verification limits.
Source: github vennittechnologies/youtube-automation-workflow.

## R2 — "Veo 3.1 ≈ $0.75/s; fal.ai $0.105-0.21/s" ❌ 0-3
Specific Veo 3.1 pricing refuted. (Verified Veo **3** pricing is $0.40/s std, $0.15/s Fast — see [F5](findings.md#f5--hosted-video-model-characteristics-veo-3--sora-2--runway-gen-3--high).) Do not cite the $0.75/s figure.
Source: aifreeforever.com.

## R3 — "Kling 2.5 sub $6.99-30/mo; fal.ai ~$0.029/s" ❌ 0-3
Specific Kling subscription + per-second figures refuted. Kling is a top-3 Dec-2025 model ([F4](findings.md#f4--dec-2025-video-arena-ranking--medium-time-boxed)) but these prices are unverified. Re-check fal.ai/Kling pricing directly before budgeting.
Source: aifreeforever.com.

## R4 — "Wan 2.1/2.2 14B on H100 SXM5: 480p/5s in ~4 min, 720p/5s in ~10-12 min" ❌ 0-3
Throughput figures refuted. No verified generation-time numbers for self-hosted Wan exist in this research.
Source: spheron.network deploy-wan-2-1 blog.

## R5 — "Self-hosted Wan: ~$0.17-0.21 per 480p/5s clip, ~$0.42-0.50 per 720p/5s clip" ❌ 0-3
Per-clip cost figures refuted. **This is why there is no verified self-hosted cost-per-150s-video** (see [cost-model.md](../10-architecture/cost-model.md) ⚠️). Pilot-measure.
Source: spheron.network.

## R6 — "Wan 14B needs 40-48GB VRAM (FP8) for 480p, 65-80GB for 720p; 1.3B runs 8-12GB/16-20GB" ❌ 0-3
VRAM threshold figures refuted. Do not size GPUs off these. (RunPod GPU *rates* are verified — [F6](findings.md#f6--runpod-self-hosting-economics-per-second-billing--gpu-rates--high) — but the *VRAM-per-model* claims are not.)
Source: spheron.network.

---

## Pattern
All refuted figures are **specific quantitative claims from secondary/blog sources** (Spheron, aifreeforever) — exactly the kind of number that looks authoritative but doesn't survive cross-checking. The self-hosted-Wan economics (R4-R6) collapsing together is the most consequential: it leaves the cheapest *AI-video* tier without a validated cost model. Treat all self-host cost/throughput/VRAM planning as **pilot-measure-first**.
