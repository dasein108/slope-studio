# Self-Improving Agent Loop — Research Findings

Output of a dedicated deep-research pass (2026-06-05) on **how to build a self-improving,
persistent feedback loop** for an autonomous short-form-video studio. 5 search angles, 24
sources fetched, 116 claims extracted, 25 verified by adversarial 3-vote, **12 confirmed**.

This is the research backing for the marketing growth loop (`studio/marketing/`,
[`../50-marketing/`](../50-marketing/README.md)). The headline result: **the loop you already
built is the pattern the literature endorses** — the work ahead is upgrading the journal from
append-only to retrieval-based episodic memory.

> **Coverage.** The first pass verified only **angles 1–2** (loop architecture, orchestration);
> angles 3–5 crashed in verification (verifier-subagent fault, **not** refutation). A **focused
> re-run (2026-06-05, 24/25 claims confirmed)** then resolved all three — see the **"Re-run
> findings" section below** (F-SI6…F-SI11). The original-pass findings (F-SI1…F-SI5) follow first.

---

## F-SI1 — Build it as a training-free, in-context reflective loop ✅ high
**Vote:** 4 papers, unanimous (3-0 / 2-0 on constituent claims).

The agent reflects on each video's outcome, distills reusable lessons/heuristics, stores them
in a **persistent memory buffer**, and retrieves them on the next cycle — improving **without
retraining the base model**. Four primary papers converge on this exact shape:

- **Reflexion** — reinforces agents "not by updating weights, but through linguistic feedback,"
  keeping reflections in an "episodic memory buffer to induce better decision-making in
  subsequent trials." [arxiv 2303.11366](https://arxiv.org/pdf/2303.11366)
- **SAGE** — User/Assistant/Checker self-evolving loop; iterative feedback + reflection + memory
  optimization, "without any additional training." [arxiv 2409.00872](https://arxiv.org/pdf/2409.00872)
- **CER** (Contextual Experience Replay) — "accumulates and synthesizes past experiences into a
  dynamic memory buffer," retrieves/replays on new tasks. [arxiv 2506.06698](https://arxiv.org/pdf/2506.06698)
- **ERL** (Experiential Reflective Learning) — "reflects on task trajectories and outcomes to
  generate heuristics… actionable lessons that transfer across tasks," injected into context at
  test time. [arxiv 2603.24639](https://arxiv.org/pdf/2603.24639)

**Maps to:** `learn.py` (reflect → strategy) + `journal.py` (the memory buffer). This is a
direct, multi-source-corroborated template for ideate→produce→measure→learn.

---

## F-SI2 — Formalize the loop as policy refinement with an iteration cap ✅ high
**Vote:** 3-0. Source: SAGE [2409.00872](https://arxiv.org/pdf/2409.00872).

The loop is policy refinement: agent A iteratively updates policy πθ on Checker feedback fₜ to
maximize expected reward R, with reflection rₜ stored in long-term memory M_L; "this process
continues until the checker validates the output or the iteration limit N is reached."

**Maps to:** the **iteration cap N is your per-video budget gate** (`--max-cost`,
`tiers.py`). Gives a principled termination/cost-cap framing for the production loop.

---

## F-SI3 — Reflective-memory gains are real and largest on cheap models ✅ high
**Vote:** 3-0 (CER/ERL); SAGE headline 2-1.

Measured across diverse agent benchmarks:
- **SAGE** up to **2.26×** on closed-source models, 57.7–100% on open-source, "particularly
  notable effects on smaller models" (peer-reviewed, Neurocomputing Vol 647, 2025).
- **CER** 36.7% on WebArena, **+51.0% relative** over GPT-4o baseline.
- **ERL** **+7.8%** on Gaia2 (48.3→56.1%), beating ExpeL (50.9) and AutoGuide (50.8).

**Why it matters for the studio:** the smaller-model effect means you can run **cheap LLMs**
(your `stub`/Groq/Gemini-Flash script tier) and recover quality through the loop.
**Caveat:** benchmarks are web-agent / reasoning domains — transfer to video production is
**inferential, not demonstrated**. The mechanism is general; the magnitude is not promised here.

---

## F-SI4 — Episodic memory is the right substrate ✅ high
**Vote:** 3-0. Sources: ["Episodic Memory is the Missing Piece for Long-Term LLM Agents"
2502.06975](https://arxiv.org/pdf/2502.06975) (MPI / Intel Labs / UT Austin) + Reflexion.

Long-term agents "must address the challenge of continually learning and retaining long-term
knowledge"; "episodic memory supports **single-shot learning of instance-specific contexts**" —
learning from a single exposure (one video's outcome) without gradient updates.

**Maps to:** each published video = one **episode** (theme, effects, animators, cost, metrics,
outcome). Store it as an instance-specific memory the **ideator can retrieve by similarity** —
this is the concrete upgrade to `journal.py` (today it's append-only; reflection reads the whole
list rather than the *relevant* episodes).

---

## F-SI5 — LangGraph is a viable durable backbone (but plain Python already suffices) ✅ medium
**Vote:** 2-0 on the core claim; two sub-claims refuted (1-0). Source:
[LangGraph durable-execution docs](https://docs.langchain.com/oss/python/langgraph/durable-execution).

LangGraph "saves a snapshot of the graph state at every step… organized into threads,"
giving "fault-tolerance and error recovery: if one or more nodes fail… you can restart your
graph from the last successful step."

- **Caveat (verification-surfaced):** a third-party critique (Diagrid) affirms the snapshot
  mechanism but argues **checkpointing alone is not full production durable execution** (no
  automatic failure detection / distributed coordination). Two sub-claims — three durability
  modes (`exit`/`async`/`sync`) and node-resume-without-re-execution — **did not survive**.
- **Studio implication:** your **idempotent stages + `project.json` manifest already give free
  resume** (`studio run --run-id` skips `is_done` stages). LangGraph is **optional** — reach for
  it only if you need branching/state machines beyond the linear `STAGE_ORDER`. Matches the
  existing call in [`../10-architecture/orchestration.md`](../10-architecture/orchestration.md).

---

## What this validates in `studio/marketing/`

| Paper concept | Your code today | Research-backed upgrade |
|---|---|---|
| Episodic memory buffer (F-SI1, F-SI4) | `journal.py` append-only Entry ledger | **Retrieve relevant past episodes by similarity** and inject into `ideate` context |
| Reflection → policy (F-SI1, F-SI2) | `learn.py` reflect → `Strategy` | Already aligned; treat `--max-cost` as the SAGE iteration cap N |
| Reward signal | `score.py` virality composite | Re-tune weights to the validated signal order (F-SI9) |
| Exploit/explore policy | fixed 60/40 in `ideate.py` | **Replace** with a contextual bandit (F-SI6); warm-start it (F-SI7) |
| Durable execution (F-SI5) | idempotent stages + manifest | Sufficient; LangGraph only if branching needed |

**Bottom line:** no rewrite needed. The highest-value, evidence-backed change is making the
journal a **retrieval-based episodic memory** (done — `memory.py`); the next is **replacing the
fixed 60/40 with a warm-started contextual bandit** (F-SI6/F-SI7) and **re-tuning the virality
weights** (F-SI9).

---

## Re-run findings — explore/exploit, persistence, virality, attribution

Focused re-run (2026-06-05): 5 angles on the three contested pieces, 24 sources, 103 claims,
**24/25 confirmed**. Resolves [open-questions Q8–Q11](open-questions.md).

### F-SI6 — Drop the fixed 60/40; use a CONTEXTUAL bandit ✅ high
**Vote:** 3-0 (two findings).

A fixed 60/40 split is just a **fixed-rate ε≈0.6 exploration policy** — the literature flags it
as wasteful: it ignores the base rate of good content and **over-explores weak arms**. A
uniform Beta(1,1) prior "implicitly assign[s] new items a 50% success probability… in
large-scale marketplaces where the base rate of high-performing content is far lower, this
optimistic prior systematically over-explores weak items." Replace with a **contextual bandit**
(LinUCB or Thompson Sampling) using **theme/effect features as context**: LinUCB showed a
**12.5% click lift over a context-free bandit, and the advantage grows when data is scarce** —
exactly the studio's regime (a handful of videos/week).
[Springer KAIS 2023](https://link.springer.com/article/10.1007/s10115-023-01861-2) ·
[Dynamic-Prior TS 2602.00943](https://arxiv.org/pdf/2602.00943) ·
[LinUCB / Li et al. WWW 2010](https://arxiv.org/abs/1003.0146)

### F-SI7 — Warm-start the bandit prior; calibrate exploration to the channel ✅ high
**Vote:** 3-0 (multiple findings).

Don't explore blindly in cold-start — **warm-start the prior** from side-information (theme/effect
features, a pre-trained Bayesian posterior, or expert priors). Warm-started Linear Thompson
Sampling **beat cold-started both early and cumulatively**. Calibrate the exploration rate to
the channel's **own incumbent performance distribution** (Dynamic-Prior TS): effective ε as low
as **1–3%**, giving **+9.5% cumulative reward** (simulation) and, in a production system serving
millions, a significant success-metric lift with a **21% relative cut in wasted (regretted)
impressions** vs a heavy fixed split. **Caveat:** a *misspecified* prior causes negative
transfer ("disastrous result") — seed conservatively and let data dominate fast. Initialize a
new video's context from **content features** (scene-theme text + animator/fx tags) before any
feedback exists. [Springer KAIS 2023](https://link.springer.com/article/10.1007/s10115-023-01861-2) ·
[Dynamic-Prior TS 2602.00943](https://arxiv.org/pdf/2602.00943) ·
[content cold-start, RecSys '25 2507.19473](https://arxiv.org/abs/2507.19473)

### F-SI8 — For a deep/non-closed-form reward model, use Bootstrap TS / GuideBoot ✅ high
**Vote:** 3-0 (2-1 on the complexity claim).

If the reward model has no closed-form posterior (deep/logit/probit), **Bootstrap Thompson
Sampling** approximates TS at **O(1) per step** and matches its regret; **GuideBoot** extends
this to deep contextual bandits. Lets the studio keep TS-style exploration without expensive
MCMC. **Caveat:** too few bootstrap replicates → too greedy (linear-regret risk).
[BTS 1410.4009](https://arxiv.org/pdf/1410.4009) ·
[GuideBoot](https://www.researchgate.net/publication/353344814)

### F-SI9 — Virality signals: log retention/watch-time first, likes last ✅ high
**Vote:** 3-0.

Platforms reward **watch time, saves, and shares over passive likes/comments**; watch time is
the #1 Reels ranking factor and shares/sends are weighted **3–5× likes** for new-audience reach.
Recommended **log/weight order** for the score:
**(1) avg view % / retention / completion → (2) watch time → (3) view velocity → (4)
shares/sends → (5) saves → (6) rewatches → (7) comments → (8) subs gained → (9) likes.**
**Caveat:** primary source is Instagram-Reels-centric (TikTok/Shorts by analogy); the claim
"TikTok shares are the single fastest-rising signal" was **REFUTED 0-3** — don't over-weight raw
share-count growth. [Socialinsider benchmarks](https://www.socialinsider.io/social-media-benchmarks) ·
[Hootsuite / Mosseri](https://blog.hootsuite.com/instagram-algorithm)

> **`score.py` today:** 0.5 velocity / 0.2 retention / 0.2 engagement / 0.1 subs. F-SI9 says
> **retention/watch-time should lead, not velocity**, and shares/saves should be separated from
> "engagement" and weighted above likes/comments. Re-tune accordingly (needs the analytics to
> expose shares/saves/avg-view-%; see Q10).

### F-SI10 — Persistence: shape the journal as episodic memory; embedded-first stack ✅ high
**Vote:** 3-0 (position paper).

Design the journal as a **structured episodic memory store** with the five properties (long-term
storage, explicit reasoning, single-shot learning, instance-specific, contextual) — one
context-tagged row per video/episode + semantic retrieval over lessons (which `memory.py`
already approximates lexically). An **embedded-first SQLite/DuckDB + local vector index** fits;
**graduate to Postgres+pgvector at scale**. **Caveat:** no verified head-to-head DB/vector
benchmark survived — the *engine ranking* is an engineering inference, not cited (still open, Q9).
[Episodic Memory 2502.06975](https://arxiv.org/pdf/2502.06975)

### F-SI11 — Small-sample attribution: DAG + small experiments + TreeSHAP ✅ high
**Vote:** 3-0 (2-1 on the 6.8% visual-lift claim).

To attribute success to **theme vs specific effect/animator** with only a few videos/week:
1. Encode assumptions in a **DAG** and apply a **Pearl-style identification (ID)** to derive
   *exactly* which confounders to adjust for (posting time, media type, paid reach, follower
   count) — and which **mediators NOT to condition on** (naive CV-based covariate selection can
   bias by adjusting a mediator).
2. **Combine** the observational journal with **small targeted experiments** (use observed
   best/worst arms to set the experiment's range).
3. Infer with **Bayesian mixed-effects** (partial pooling across theme/channel groups) and use
   **TreeSHAP** over a virality model whose features include **both theme tags and effect/fx/
   animator tags** to separate their contributions (visual features carried independent signal;
   image-level features outranked caption topics). **Caveat:** visual-attribution evidence is a
   small Instagram still-image study — video transfer is by analogy.
[Causal post-timing, Springer 2022](https://link.springer.com/article/10.1007/s10260-022-00664-z) ·
[visual popularity + TreeSHAP 2405.02367](https://arxiv.org/html/2405.02367v2)

### Still open after the re-run
- **DB engine benchmark** — no SQLite-vs-DuckDB / pgvector-vs-LanceDB head-to-head survived (Q9).
- **Transfer to the expensive-pull regime** — bandit math assumes *many cheap* pulls; here each
  pull is a *full rendered video*. How well the lifts transfer is unproven.
- **Context-feature set** — which theme/effect/format/timing features actually carry signal per
  channel, validated on small samples.
- **Reward shape** — single scalar virality composite vs a multi-objective/vector bandit, and
  whether that changes the cold-start prior calibration.

---

## Method

Two passes. **Pass 1** (loop architecture/orchestration): 24 sources, 116 claims, 12 confirmed —
angles 3–5 crashed in verification (subagent fault, not refutation). **Pass 2** (focused re-run
on angles 3–5): 24 sources, 103 claims, **24/25 confirmed, 1 refuted** (TikTok-shares-fastest).
Each claim checked by 3 independent adversarial agents instructed to **refute**; survives on
≥2/3 confirm. Source quality + vote margin drive the confidence tags above.
