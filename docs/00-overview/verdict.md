# Verdict — Cheapest Accurate Stack

Goal restated: cheapest stack that still produces an *accurate, watchable* 150s short, end-to-end, automatable, decomposed into CLI components.

## The recommendation

Build **balanced tier** as the default, with **budget tier** as a fallback per-stage when quality doesn't matter and **premium tier** swappable in for hero videos. All three share the same CLI/manifest; only `--provider` per stage changes.

### Cheapest *accurate* stack (balanced)

| Stage | Pick | Why | Cost |
|-------|------|-----|------|
| 1 Script | Gemini 2.5 Flash / GPT-4o-mini / Claude Haiku | cheap, strong structured JSON, reliable timing | ~$0.001–0.01 🔶 |
| 2 Visuals | **Gemini 2.5 Flash Image (Nano Banana)** | $0.039/img ✅, native character consistency ✅, up to 14 ref images (NB2) ✅ | ~$0.20–0.40 (5–10 imgs) |
| 3 Video | **Kling / Hailuo(MiniMax) / Seedance via fal.ai**, or self-hosted **Wan 2.2** on RunPod for volume | best quality-per-dollar in i2v; self-host amortizes at scale | ~$0.15–0.50/clip 🔶 → dominant cost |
| 4 Stitch | **ffmpeg** | free, scriptable, deterministic ✅ | $0 |
| 5 Voiceover | **edge-tts** (draft) → **ElevenLabs / OpenAI TTS** (final) | edge-tts free ✅; paid for natural prosody | $0 → ~$0.05–0.30 🔶 |
| 5b Avatar | **Hedra / D-ID / HeyGen** (SaaS) or self-hosted **LatentSync** | only if narrator-on-screen format | varies 🔶 |
| 6 Save | ffmpeg encode | free | $0 |
| 7 Publish | **YouTube Data API** (free quota); TikTok audit-gated | YouTube permits automation; TikTok blocks public until audit ✅ | $0 |

**Estimated all-in: ~$0.30–0.80 per 150s video** at API rates with 6–12 short clips, paid TTS. Drops toward **~$0.05–0.15** if you self-host video (Wan on RunPod) at volume, and to **$0** for drafts (free LLM + Pollinations + edge-tts + stock/Ken-Burns instead of AI video). See [`../10-architecture/cost-model.md`](../10-architecture/cost-model.md).

## Why not cheaper everywhere?

- **Free video gen is the real gap.** ✅ Verified: a $0 pipeline works but *without true AI video* — it falls back to stock footage / image pans (Ken Burns). If "AI clips" is non-negotiable, video is unavoidably the cost center. The cheapest *real* AI video is self-hosted open models (Wan/LTX) on RunPod amortized over many clips, but exact cost-per-clip is **unverified** (the only sourced figures were refuted ⚠️ — see [`../20-research/refuted.md`](../20-research/refuted.md)). Budget a pilot to measure it.
- **edge-tts is free but ToS-gray** ✅ (violates MS ToS, but stable 3+ yrs). For anything commercial use OpenAI TTS / ElevenLabs / a self-hosted open model (Kokoro, Chatterbox, F5-TTS).
- **Nano Banana wins stage 2 outright** ✅ — cheap *and* the character-consistency feature you'd otherwise hack with LoRA. Use LoRA only when you need a *fixed* recurring character at scale or an art style NB can't hold.

## Decision shortcuts

- **"I want it free / a demo":** Budget tier. No AI video, edge-tts, Pollinations, YouTube only. See [`../10-architecture/tiers.md#budget`](../10-architecture/tiers.md).
- **"I want good shorts cheaply, at volume":** Balanced tier + self-host video on RunPod once volume justifies a warm GPU.
- **"Hero content, quality first":** Premium — Veo 3 / Runway Gen-4.5 / Kling 2.5 Turbo, ElevenLabs, HeyGen avatars.
- **"Narrator/character channel":** add the avatar sub-stage (Hedra/HeyGen) + a trained LoRA for a signature character.

## Biggest risks (read before building)

1. **TikTok publishing is audit-gated** ✅ — plan for YouTube-first, or manual TikTok, or a 2-4 week audit.
2. **Model churn** ✅ — stage 2-3 rankings/prices change monthly; keep providers behind a swappable adapter.
3. **No verified self-host cost model** ⚠️ — pilot-measure before committing to RunPod-at-scale claims.
4. **Free-tier fragility** — rate limits (OpenRouter ~50/day, Pollinations ~1/15s), watermarks, ToS gray areas.
