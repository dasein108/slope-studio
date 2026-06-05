# Open Questions / Research Gaps

Things the research pass did **not** establish. Resolve these before committing money or a final architecture. Each maps to where it bites in the docs.

## Q1 — Verified cost-per-150s-video per tier ⚠️ high priority
The refutation of the Wan cost figures (R4-R6) left **no validated end-to-end cost model**, especially for the self-hosted GPU path. The question explicitly asked for cost-per-150s estimates.
→ **Action:** instrument the manifest and run 10 pilot videos per tier to *measure* it. See [`../10-architecture/cost-model.md`](../10-architecture/cost-model.md).

## Q2 — Real VRAM + throughput for open video models on RunPod ⚠️
Wan 2.1/2.2, HunyuanVideo, LTX — actual VRAM needs and clips/hour on specific RunPod GPUs. Only refuted figures existed.
→ **Action:** benchmark Wan 2.2 on A100 80GB and RTX 4090 (clip time at 480p/720p, 5s). Decides self-host vs serverless break-even. See [`findings.md`](findings.md).

## Q3 — Orchestration framework choice (no research coverage)
No surviving claim addressed Claude Code skills+workflows vs LangChain vs LangGraph vs plain Python CLI.
→ **Filled by engineering judgment** in [`../10-architecture/orchestration.md`](../10-architecture/orchestration.md) (🔶 not cited): plain CLI substrate → LangGraph when state/branching needed → Claude Code as creative cockpit.

## Q4 — Current TTS + talking-avatar prices/quality
Only edge-tts (free) was verified. ElevenLabs vs OpenAI vs Google vs Kokoro/Chatterbox/F5-TTS pricing/quality, and HeyGen/D-ID/Hedra avatar pricing, are unverified — full comparison tables in [`provider-options.md`](provider-options.md).
→ **Action:** pull current pricing pages for the 2-3 TTS + 1-2 avatar tools you actually shortlist.

## Q5 — YouTube Shorts API publish restrictions vs TikTok
TikTok's audit gate is verified ([F7](findings.md#f7--tiktok-auto-publish-is-audit-gated-the-hardest-constraint--high)). Whether YouTube Data API imposes comparable auto-publish friction (OAuth verification for public-at-scale, quota) is only 🔶 in [`findings.md`](findings.md).
→ **Action:** confirm current `videos.insert` quota cost (~1600 units), daily quota, and OAuth verification requirements for public unattended uploads.

## Q6 — Video model leaderboard is already stale
F4 is a Dec-2025 snapshot; Seedance 2.0 / Kling 3.0 led by Feb-Mar 2026.
→ **Action:** re-check Artificial Analysis Video Arena + fal.ai/Replicate model list at build time. Keep providers behind swappable adapters so this churn is a config change.

## Q7 — Legal/ToS posture
edge-tts violates MS ToS; Pollinations may watermark; Midjourney has no official API (automation ToS risk); third-party TikTok posting resellers carry ToS risk.
→ **Action:** decide commercial vs hobby; for commercial, replace edge-tts (→ Kokoro/OpenAI), avoid Midjourney automation, and pursue the TikTok audit rather than resellers.

---

# Self-improving loop pass (2026-06-05)

From the [`self-improving-loop.md`](self-improving-loop.md) research. A focused **re-run
(2026-06-05, 24/25 confirmed)** resolved the substance of Q8/Q10 and most of Q9; residual gaps
are marked below. Full findings: F-SI6…F-SI11 in [`self-improving-loop.md`](self-improving-loop.md).

## Q8 — Explore/exploit algorithm ✅ RESOLVED + IMPLEMENTED (F-SI6/F-SI7/F-SI8 → T8)
**Built:** `studio/marketing/bandit.py` — warm-started Thompson sampling over theme+tags,
wired into `loop.py` (the autopilot's produce pick), `studio marketing bandit` to inspect.

**Answer:** **drop the fixed 60/40** — it's a wasteful fixed-rate ε≈0.6 policy that over-explores
weak arms. Use a **contextual bandit** (LinUCB / Thompson Sampling) with theme/effect features as
context (12.5% lift over context-free; bigger when data is scarce). **Cold-start:** warm-start
the prior from content features / expert priors, calibrate exploration to the channel's own
incumbent distribution (effective ε 1–3%; +9.5% sim, −21% wasted exploration in production) — but
seed conservatively (misspecified prior → negative transfer). For deep reward models use
**Bootstrap TS / GuideBoot** (O(1)/step). → **Action:** build the bandit in `ideate.py`.
**Residual:** does the lift transfer to the *expensive-pull* regime (each pull = a full video,
not a cheap impression)? What context-feature set carries signal per channel? (see below).

## Q9 — Persistence / memory stack 🟡 PARTLY RESOLVED (F-SI10)
**Answer:** shape the journal as a **structured episodic memory** (5 properties; one
context-tagged row per episode + semantic lesson retrieval — `memory.py` already approximates
this lexically). **Embedded-first SQLite/DuckDB + local vector index**, graduate to
**Postgres+pgvector** at scale. **Residual (still open):** no verified head-to-head benchmarked
SQLite-vs-DuckDB or pgvector-vs-sqlite-vss-vs-LanceDB-vs-Chroma comparison survived — the engine
ranking and the exact scale threshold to graduate remain an engineering inference. Decide before
scaling past ~100 videos. Touches `studio/marketing/journal.py`.

## Q10 — Virality signals + theme/effect attribution ✅ RESOLVED (F-SI9/F-SI11)
**Answer (signals):** log/weight order = **retention/avg-view % → watch time → velocity →
shares/sends → saves → rewatches → comments → subs → likes**; shares/sends weighted 3–5× likes;
watch time is #1. `score.py` today (0.5 velocity / 0.2 retention / 0.2 engagement / 0.1 subs)
**over-weights velocity and buries retention** — re-tune so retention/watch-time leads and
shares/saves are split out from "engagement". (Refuted: "TikTok shares fastest-rising signal" —
don't over-weight raw share count.) **Answer (attribution):** DAG + Pearl ID to choose
confounders (posting time, media type, paid reach, followers) and avoid mediators; combine
observational journal + small targeted experiments; infer with Bayesian mixed-effects + TreeSHAP
over a model featuring **both theme and effect/fx/animator tags**. → **Action:** re-tune
`score.py`; needs analytics to expose shares/saves/avg-view-% (extend `analytics.py`).

## Q11 — Orchestration framework comparison (still uncovered, low urgency)
F-SI5 verified only LangGraph's core checkpointing; the requested comparison against
Temporal/Prefect/Dagster/Airflow/Ray/cron produced no surviving claims (two LangGraph
sub-claims were refuted). Plain Python + the manifest already gives resume, so this is **low
urgency** — but a sourced durability/scheduling/cost comparison is still missing.
→ **Candidate sources:** Temporal/Dagster/LangGraph patterns (kinde), orchestration showdown
(datumlabs), durable-execution agents (vadim.blog). Supersedes/extends [Q3](#q3--orchestration-framework-choice-no-research-coverage).
