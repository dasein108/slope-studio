# Slope Studio — Automated Short-Video Studio (Idea → Published Short)

Research + architecture docs for a full-cycle pipeline that turns a text idea into a finished TikTok / YouTube Short. Each stage is an independent CLI component; the components also chain into one pipeline.

> **▶ New here / just want to run it?** Read [`00-overview/operator-guide.md`](00-overview/operator-guide.md) — the hands-off guide to every skill + feature, with the minimal human steps spelled out.

> **Status:** implemented. The 8-stage pipeline (`studio` CLI) + marketing loop are built and run. These docs cover both the research rationale and the shipped code. Pricing/model rankings are 2025-2026 snapshots and churn monthly — re-verify stages 2-3 before spending.
>
> **▶ Visual map:** [`10-architecture/workflows.md`](10-architecture/workflows.md) — every workflow as a Mermaid diagram (pipeline DAG, run chainer, budget gating, sync path, animator dispatch, marketing loop, OAuth). Module-by-module surface: [`10-architecture/module-map.md`](10-architecture/module-map.md).

## How this is organized

| Dir | Contents |
|-----|----------|
| [`00-overview/`](00-overview/) | **Operator guide (start here)**, pipeline stages end-to-end, glossary |
| [`10-architecture/`](10-architecture/) | **Workflow diagrams**, **module map**, orchestration choices, cost model |
| [`20-research/`](20-research/) | Verified findings, refuted claims, sources, open questions |
| [`30-animation/`](30-animation/) | Per-scene animators + transitions + voice/tone; **`scenario-schema.md`** = authoritative `01_script.json` schema; **[`effects/`](30-animation/effects/README.md)** = full programmatic/vector effect catalog (rain, fire, fog, grain, morphs…) |
| [`40-publishing/`](40-publishing/) | YouTube Shorts auto-publish setup (OAuth) + metadata/SEO |
| [`50-marketing/`](50-marketing/) | The viral growth loop — ideate→deploy→measure→learn journal (`marketing-guru` skill) |

## The 7 stages

1. **Script** — idea → structured scenario JSON (scenes + timings for N seconds, default 150s) + optional voiceover narration text.
2. **Visuals** — generate scene images + a consistent character/avatar (multiple poses/views). Optional LoRA fine-tune for a recurring character.
3. **Video** — turn images/text into short clips (image-to-video, text-to-video) and/or talking-avatar lip-sync clips.
4. **Stitch** — concatenate clips with transitions, normalize resolution/fps/aspect (9:16).
5. **Voiceover** — synthesize narration (TTS), mux audio over video, optional captions + lip-sync.
6. **Save** — render final MP4 to disk with platform-correct encoding.
7. **Publish** *(optional)* — upload to YouTube Shorts (permissive) / TikTok (audit-gated).

See [`00-overview/pipeline-stages.md`](00-overview/pipeline-stages.md) for the full data-flow with artifacts between every stage.

## TL;DR verdict (cheapest accurate stack)

> Full reasoning in [`10-architecture/cost-model.md`](10-architecture/cost-model.md) and the tier table in the repo-root [`CLAUDE.md`](../CLAUDE.md) (free/cheap/balanced/premium).

**Recommended "cheap + accurate" balanced stack (~$0.30–0.80 per 150s video):**
- Script: **Gemini 2.5 Flash** or **GPT-4o-mini / Claude Haiku** (cents) — or free OpenRouter/Groq/Ollama.
- Visuals: **Gemini 2.5 Flash Image (Nano Banana)** — `$0.039/image`, native character consistency *(verified)*.
- Video: **Kling / Hailuo (MiniMax) / Seedance** via [fal.ai](https://fal.ai) or self-hosted **Wan 2.2** on RunPod for volume.
- Stitch: **ffmpeg** (free).
- Voiceover: **edge-tts** (free) for drafts → **ElevenLabs / OpenAI TTS** for quality.
- Talking avatar: **Hedra / HeyGen / D-ID** (SaaS) or self-hosted lip-sync (LatentSync/SadTalker).
- Orchestration: **plain Python CLI + a thin DAG** (or LangGraph if you want state/retries/branching).
- Publish: **YouTube Data API** (works for automation); **TikTok** only `SELF_ONLY` until audit *(verified hard constraint)*.

**Hard constraints to know up front** (verified):
- TikTok auto-publish is **private-only** + **5 users/24h** until you pass a 2-4 week audit. See [`40-publishing/youtube.md`](40-publishing/youtube.md).
- A genuinely **$0 end-to-end pipeline works** — but **without true AI video gen** and without real public auto-publish. See [`20-research/findings.md`](20-research/findings.md).

## Confidence legend used throughout

- ✅ **Verified** — confirmed by the deep-research pass (adversarial 2/3+ vote), cited.
- ⚠️ **Refuted** — a claim that failed verification; do not rely on it. Listed in [`20-research/refuted.md`](20-research/refuted.md).
- 🔶 **Unverified / domain knowledge** — filled from general knowledge to close a research gap; treat as approximate, re-check before spending.
