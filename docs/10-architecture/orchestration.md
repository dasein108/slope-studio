# Orchestration — How to Chain the Stages

> ⚠️ The deep-research pass did **not** verify any orchestration-framework claim (gap noted in [`../20-research/open-questions.md`](../20-research/open-questions.md)). This is engineering judgment (🔶), not cited research.

The pipeline is a mostly-linear DAG with **fan-out** inside stages 2 and 3 (N scenes in parallel) and one ordering wrinkle (avatar mode: TTS before video). The orchestration question is: what runs the chain, handles retries/cost/resume, and exposes the per-stage CLIs.

## Option A — Plain Python CLI + thin DAG (recommended default)

A `click`/`typer` CLI where each stage is a subcommand reading/writing the run dir; a top-level `run` command chains them. Concurrency via `asyncio`/`concurrent.futures` for the fan-out stages.

- **Pros:** zero framework lock-in; each stage trivially runnable standalone (the user's explicit ask); easy to read; cheapest to maintain; manifest-based resume is simple; provider adapters are just functions.
- **Cons:** you hand-write retry/branch/state logic; no built-in graph viz or durable state.
- **Best when:** you want the decomposed-CLI + single-pipeline duality with minimal deps. **This matches the requirements most directly.**

```
studio script ... && studio visuals ... && studio clips ... && \
studio stitch ... && studio voice ... && studio save ... && studio publish ...
# or:
studio run --idea "..." --duration 150 --tier balanced --publish youtube
```

## Option B — LangGraph (recommended if you want a real state machine)

Graph of nodes with typed shared state, conditional edges, retries, checkpointing (durable resume), and human-in-the-loop pauses.

- **Pros:** native branching (avatar-vs-scene mode), retries/fallbacks per node, checkpointer = free resume + crash recovery, parallel fan-out, observability (LangSmith). Great if the pipeline grows conditional logic (re-roll bad images, fallback providers, approval gates).
- **Cons:** dependency weight; state-graph boilerplate; the per-stage "standalone CLI" still needs to be exposed separately (wrap each node's core fn in a CLI too).
- **Best when:** you want robust retries/branching/resume and may add agentic decisions (e.g., a vision-LLM judging images and looping).

## Option C — LangChain (not recommended as the spine)

LangChain shines for LLM-app glue (prompt templates, model adapters, output parsers) — useful **inside stage 1** (and maybe stage-2 prompt building). But as the *pipeline* orchestrator it's awkward (LCEL chains aren't a natural fit for long media DAGs). Use LangChain *components* within stages if convenient; don't make it the backbone. Prefer LangGraph if you want the LangChain ecosystem's orchestration.

## Option D — Claude Code skills + workflows

Claude Code can author/run this as a **Skill** (the per-stage CLIs + a SKILL.md) and a **Workflow** (deterministic multi-agent fan-out for the parallel scene generation + adversarial quality checks).

- **Pros:** you (the operator) drive it conversationally; Workflows give real parallel fan-out + verification (e.g., generate 3 image candidates per scene, judge, pick best); great for the *build/iterate* phase and for human-in-the-loop creative direction.
- **Cons:** not a headless unattended production server by itself (it's an interactive/agent harness); for cron'd autonomous publishing you still want Option A/B underneath. Best as the **dev cockpit + creative-QA layer** on top of the plain CLIs.
- **Best when:** interactive studio use, creative iteration, multi-candidate selection, "make me 5 variants and pick the best."

## Recommendation

**Hybrid, in order of build:**
1. **Plain Python CLI (Option A)** as the substrate — each stage a standalone command + a `run` chainer. Satisfies "decomposed CLI components AND combined pipeline" directly.
2. Wrap it in **LangGraph (Option B)** *only when* you need durable resume, provider fallbacks, conditional avatar/scene branching, or re-roll loops. The CLI fns become node bodies.
3. Use **Claude Code skills/workflows (Option D)** as the interactive cockpit + multi-candidate creative QA during production; it calls the same CLIs.
4. Borrow **LangChain (Option C)** pieces inside stage 1 only if helpful.

### Cross-cutting orchestration concerns (any option)
- **Manifest/state:** single `project.json` updated per stage; records provider, cost, timing, artifact paths → enables resume + measured cost-per-video.
- **Idempotency:** stages skip if output exists + inputs unchanged (hash inputs).
- **Concurrency:** fan out scenes in stages 2/3 (asyncio + a semaphore to respect provider rate limits).
- **Provider adapters:** one interface per stage (`generate_image`, `generate_clip`, `tts`, `publish`), provider chosen by `--provider`/config → swap without touching the pipeline.
- **Retries/fallbacks:** per provider-call retry with backoff; optional fallback chain (e.g., Kling → Hailuo → Ken-Burns).
- **Cost guard:** estimate before stage 3; abort if over `--max-cost`.
