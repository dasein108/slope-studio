# Verified Findings

Output of the deep-research pass: 6 search angles, 29 sources fetched, 128 claims extracted, 25 verified by adversarial 3-vote (need 2/3 to confirm), 19 confirmed, 6 killed, 7 after synthesis. Full run stats in [`sources.md`](sources.md).

Each finding below survived verification. Confidence + vote tally as reported.

---

## F1 — A fully free end-to-end CLI pipeline is buildable (without true AI video) ✅ high
**Vote:** merged 2-0 / 3-0 / 3-0.

OpenRouter free LLM (script → structured JSON of scenes+narration, model swappable in code) + Pollinations.ai (images) + edge-tts (TTS) + faster-whisper (captions) + ffmpeg (stitch). Script can alternatively run on local Ollama (`llama3.1:8b`) or free Groq (`llama-3.1-8b-instant`), avoiding paid Claude/GPT/Gemini.

- OpenRouter `:free` models ~50 req/day; edge-tts no key, 200+ voices; Pollinations no signup; faster-whisper/ffmpeg open-source.
- **Caveats:** Pollinations anonymous tier throttles ~1 req/15s and may watermark (since Mar 2025); edge-tts technically violates Microsoft ToS (stable 3+ yrs).
- **Critical:** the broader claim of a $0 **YouTube-publishing** pipeline with true automation/Pexels was **REFUTED 0-3** — this free stack does **not** include true AI video generation.

Sources: hackaday.io ffmpeg-ai project; github vennittechnologies youtube-automation-workflow; openrouter limits; rany2/edge-tts; pollinations; groq rate-limits.

---

## F2 — Gemini 2.5 Flash Image (Nano Banana): $0.039/img, character-consistent ✅ high
**Vote:** 3-0 (two merged claims).

$30.00 per 1M output tokens; 1290 tokens/image = **$0.039/image** (arithmetic checks). Native support to "place the same character into different environments, showcase a single product from multiple angles, generate consistent brand assets."

- Independent reviews (cybernews, Notebookcheck, DataCamp) confirm consistency is real with "occasional slips." Was top-rated "nano-banana" on LMArena image editing. Pricing still current Feb 2026.

Source: Google developer blog (introducing-gemini-2-5-flash-image). **Primary.**

---

## F3 — Nano Banana 2: up to 14 reference images; 8 models accept ref images ✅ high
**Vote:** 3-0 (two merged claims).

Nano Banana 2 supports **up to 14 reference images**, "character resemblance of up to five characters and fidelity of up to 14 objects," exceptional text rendering, multi-image compositing. The 2026 comparison lists 8 models accepting reference images for character/brand consistency: Nano Banana 2 (14), Seedream 5 Lite (10), Seedream 4.5 (10), Seedream 4 Edit (10), GPT Image 2 (1), Ideogram V3 (1), Grok Imagine (3), Flux Pro Ultra (1).

- Seedream's 10-ref support independently confirmed. Caveat: Google hedges consistency ("may not always get it right").

Sources: melies.co compare; blog.google nano-banana-2; fal.ai nano-banana-2.

---

## F4 — Dec-2025 Video Arena ranking ✅ medium (time-boxed)
**Vote:** 2-1.

As of December 2025, Artificial Analysis Video Arena: **Runway Gen-4.5 #1 (1247 Elo)**, Google Veo 3 #2 (1226), Kling 2.5 Turbo Pro #3 (1225), Veo 3.1 #4 (1220), Luma Ray 3 #5 (1211).

- Corroborated across AICerts, bonega.ai, gaga.art (all trace to Artificial Analysis). Runway Gen-4.5 launched Dec 1 2025 at #1.
- **TIME-SENSITIVE:** already superseded by Seedance 2.0 / Kling 3.0 by Feb-Mar 2026. Treat as a **dated snapshot**, not current.

Sources: aifreeforever.com; aicerts.ai; bonega.ai; gaga.art. (Secondary.)

---

## F5 — Hosted video model characteristics (Veo 3 / Sora 2 / Runway Gen-3) ✅ high
**Vote:** 3-0 (three merged claims).

- **Veo 3 (Google):** ~8s clips, 720p/1080p, 480p Veo-3-Fast mode (YouTube Shorts); Gemini API billing **$0.40/s standard, $0.15/s Fast**; also Vertex AI.
- **Sora 2 (OpenAI):** launched Sep 30 2025 invite-only, free at launch (no app price); up to 1080p; Pro quality via existing $200/mo ChatGPT Pro; per-second API **$0.10-0.50/s** disclosed Oct 7 2025.
- **Runway Gen-3:** up to 10s clips, ~720p, literal "Extend" feature (max ~40s); **10 credits/s** Alpha, **5/s** Turbo.
- Minor nuance: the fast product is "Veo 3 Fast," not "Shorts Fast."

Sources: skywork.ai comparison; Google Developers Blog; techcrunch (Sora app); Runway help docs.

---

## F6 — RunPod self-hosting economics (per-second billing + GPU rates) ✅ high
**Vote:** 3-0 (four merged claims).

Per-second (per-millisecond) billing suits bursty generation. On-demand Secure Cloud: RTX A6000 **$0.49/hr**, RTX 4090 **$0.69/hr**, A100 80GB **$1.39/hr (PCIe) / $1.49 (SXM)**, H100 **$2.89 (PCIe) / $3.19 (NVL) / $3.29 (SXM)**. Community Cloud cheaper (e.g. 4090 ~$0.34/hr).

- Billed per-millisecond ("charged just that minute"), ideal for inference/short loops. 4090 (24GB) & A6000 (48GB) VRAM sufficient for SDXL/FLUX/Wan.
- **Critical:** specific Wan throughput, VRAM, and per-clip cost figures (Spheron blog) were **REFUTED 0-3** — do **not** use for cost-per-clip modeling. See [`refuted.md`](refuted.md).

Sources: runpod.io/pricing (primary, live 2026); docs.runpod.io; runpod h100-sxm; Northflank/Flexprice/Markaicode (corroboration).

---

## F7 — TikTok auto-publish is audit-gated (the hardest constraint) ✅ high
**Vote:** 3-0 (four merged claims).

TikTok Content Posting API, Direct Post flow: `POST /v2/post/publish/video/init/` requires **`video.publish`** scope; sources `PULL_FROM_URL` (server-side) or `FILE_UPLOAD` (device chunks).

- **"All content posted by unaudited clients will be restricted to private viewing mode."**
- **Unaudited clients: up to 5 users / 24h, SELF_ONLY only.** Public attempts → `unaudited_client_can_only_post_to_private_accounts`.
- **Audit takes ~2-4 weeks.** Users can manually flip to public, defeating automation.
- This is the architecture's hardest publish-stage constraint.

Sources: developers.tiktok.com content-posting-api-reference-direct-post; content-sharing-guidelines; postproxy.dev. **Primary** (TikTok official docs).

---

## What verification means here
Each claim was checked by 3 independent adversarial agents instructed to **refute**; a claim survives only with ≥2/3 confirming. 6 claims were killed (see [`refuted.md`](refuted.md)). Confidence reflects source quality (primary > secondary > blog) and vote margin.
