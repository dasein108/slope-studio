# Open Questions / Research Gaps

Things the research pass did **not** establish. Resolve these before committing money or a final architecture. Each maps to where it bites in the docs.

## Q1 — Verified cost-per-150s-video per tier ⚠️ high priority
The refutation of the Wan cost figures (R4-R6) left **no validated end-to-end cost model**, especially for the self-hosted GPU path. The question explicitly asked for cost-per-150s estimates.
→ **Action:** instrument the manifest and run 10 pilot videos per tier to *measure* it. See [`../10-architecture/cost-model.md`](../10-architecture/cost-model.md).

## Q2 — Real VRAM + throughput for open video models on RunPod ⚠️
Wan 2.1/2.2, HunyuanVideo, LTX — actual VRAM needs and clips/hour on specific RunPod GPUs. Only refuted figures existed.
→ **Action:** benchmark Wan 2.2 on A100 80GB and RTX 4090 (clip time at 480p/720p, 5s). Decides self-host vs serverless break-even. See [`../03-stage-video/`](../03-stage-video/).

## Q3 — Orchestration framework choice (no research coverage)
No surviving claim addressed Claude Code skills+workflows vs LangChain vs LangGraph vs plain Python CLI.
→ **Filled by engineering judgment** in [`../10-architecture/orchestration.md`](../10-architecture/orchestration.md) (🔶 not cited): plain CLI substrate → LangGraph when state/branching needed → Claude Code as creative cockpit.

## Q4 — Current TTS + talking-avatar prices/quality
Only edge-tts (free) was verified. ElevenLabs vs OpenAI vs Google vs Kokoro/Chatterbox/F5-TTS pricing/quality, and HeyGen/D-ID/Hedra avatar pricing, are unverified (🔶 in [`../05-stage-voiceover/`](../05-stage-voiceover/) and [`../03-stage-video/`](../03-stage-video/)).
→ **Action:** pull current pricing pages for the 2-3 TTS + 1-2 avatar tools you actually shortlist.

## Q5 — YouTube Shorts API publish restrictions vs TikTok
TikTok's audit gate is verified ([F7](findings.md#f7--tiktok-auto-publish-is-audit-gated-the-hardest-constraint--high)). Whether YouTube Data API imposes comparable auto-publish friction (OAuth verification for public-at-scale, quota) is only 🔶 in [`../06-stage-publish/`](../06-stage-publish/).
→ **Action:** confirm current `videos.insert` quota cost (~1600 units), daily quota, and OAuth verification requirements for public unattended uploads.

## Q6 — Video model leaderboard is already stale
F4 is a Dec-2025 snapshot; Seedance 2.0 / Kling 3.0 led by Feb-Mar 2026.
→ **Action:** re-check Artificial Analysis Video Arena + fal.ai/Replicate model list at build time. Keep providers behind swappable adapters so this churn is a config change.

## Q7 — Legal/ToS posture
edge-tts violates MS ToS; Pollinations may watermark; Midjourney has no official API (automation ToS risk); third-party TikTok posting resellers carry ToS risk.
→ **Action:** decide commercial vs hobby; for commercial, replace edge-tts (→ Kokoro/OpenAI), avoid Midjourney automation, and pursue the TikTok audit rather than resellers.
