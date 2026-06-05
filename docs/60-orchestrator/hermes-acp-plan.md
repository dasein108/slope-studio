# Hermes Orchestrator + ACP Interface — Integration Plan

**Status:** proposal · **Date:** 2026-06-05 · **Scope:** wire NousResearch **Hermes** in as the agentic orchestrator brain, expose **all 12 memory layers** to it as tools, and front the whole thing over **Zed's Agent Client Protocol (ACP)** so the studio drops into an editor's agent panel.

This is the architecture rationale doc; per `CLAUDE.md` keep deep design here and link, don't inline elsewhere.

---

## 0. What the user asked, disambiguated

Three independent concepts that got merged in the request:

| Term | What it actually is | Role in this plan |
|------|---------------------|-------------------|
| **Hermes** | NousResearch open-weight LLM family (Hermes 4 / 4.3), native tool-calling | The **orchestrator brain** — the LLM that *decides* (what to make, when to measure/learn/produce) and *drives* tools |
| **ACP** | Zed's **Agent Client Protocol** — JSON-RPC 2.0 over stdio, editor↔agent | The **interface** — wrap the orchestrator as an ACP agent so Zed / JetBrains / Neovim drive it with streaming, plans, permission dialogs |
| **all memory layers** | The 12 persistence stores already in the repo (journal, telemetry, manifest, recall, …) | Exposed as **typed tools** (read + write) the Hermes brain calls |

Net target: `Zed agent panel ⇄ ACP server ⇄ Hermes tool-calling loop ⇄ {studio CLI seams + memory layers}`.

---

## 1. Current harness — what we're building on

### 1a. Orchestration seams (already exist, all deterministic CLI today)
- **Pipeline chainer:** `cli.py:run()` walks `STAGE_ORDER = [script, visuals, narrate, clips, stitch, audio, voice, save]`, idempotent (skips done stages), budget-guarded (`--max-cost`, clips aborts pre-flight). No LLM decisions in the pipeline itself.
- **Growth-loop decision engine:** `studio/marketing/loop.py:plan(j, now) → Plan` — **pure, no side effects, no network**. Returns `next ∈ {measure, learn, ideate, produce, idle}` + what's due. This is the single best seam for a brain: read `Plan`, optionally override, act.
- **Autopilot:** `cli.py:m_autopilot()` already does "ask `plan()`, do the ONE due action." Today it dispatches to deterministic CLI funcs; the brain replaces/augments this dispatcher.
- **LLM decision points (already LLM, single-shot):** `ideate.generate()` and `learn.reflect()` call `llm.complete(provider, system, user) → JSON str`.

### 1b. LLM abstraction (the seam for Hermes)
- One entry point: `studio/providers/llm.py: complete(provider, system, user) -> str`. Single-shot, stateless, JSON-only. **No tools, no multi-turn, no streaming.**
- Providers dispatch: `stub | ollama | groq | openrouter | openai | gemini`. Three (`groq/openrouter/openai`) already route through a shared `_openai_compatible(base, key, model, system, user)` helper.
- **Consequence:** adding Hermes as a *content* provider is ~4 lines. Adding Hermes as an *agentic orchestrator* needs a **new** entry point (`agentic_loop`) — the current `complete()` can't do tool-call loops.

### 1c. The 12 memory layers (full inventory)
| # | Layer | Location | Scope | Read / Write |
|---|-------|----------|-------|--------------|
| 1 | **Strategy** (long-term thesis) | `runs/_marketing/<ch>/journal.json → strategy` | per-channel | `journal.load/save` |
| 2 | **Episodic bet ledger** | `journal.json → entries[]` (planned→deployed→measured) | per-channel | `journal.load/save` |
| 3 | **Production telemetry** | `Entry.{cost,duration,animators,effects,providers,n_scenes}` via `telemetry.from_run()` | per-bet | captured at `link` |
| 4 | **Per-run manifest** | `runs/<id>/project.json` (`Manifest/StageRecord`) | per-run | `manifest.load/save` |
| 5 | **Run artifacts** | `01_script.json … 08_stats/comments.json` | per-run | per-stage |
| 6 | **Virality scores** | `Entry.{virality,percentile,outcome}` | per-bet | `score.*` |
| 7 | **Episodic recall** | in-mem over `journal.measured()`, lexical overlap | per-channel | `memory.recall(j, query, k)` (read-only) |
| 8 | **Loop / maturation state** | `LoopConfig` + `last_learn_at` in journal | per-channel | `loop.plan` reads |
| 9 | **Voice/timing** | `runs/<id>/05_voice/{timing.json,captions.srt}` | per-run | narrate |
| 10 | **YouTube OAuth** | `token_<ch>.json` (gitignored) | per-channel | `_creds()` |
| 11 | **Brand assets** | `runs/_brand/<slug>/` (banner/logo/keywords) | per-channel | `studio brand` |
| 12 | **Operator memory** | `~/.claude/.../memory/*.md` | global | Claude Code memory |

Layers 1–8 are the brain's working memory (decisions). 9–12 are context/assets. The Journal (1+2) is the single source of truth and is saved on every state change.

---

## 2. Target architecture

```
┌──────────────┐   JSON-RPC 2.0 / stdio   ┌───────────────────────────────────┐
│ Zed / IDE    │◀────────────────────────▶│  studio/acp_server.py (acp.Agent) │
│ (ACP client) │  session/prompt          │  - initialize / session_new       │
│  agent panel │  session/update ◀────────│  - prompt() → run orchestrator    │
└──────────────┘  request_permission      │  - streams plan + tool_call cards │
                                          └──────────────┬────────────────────┘
                                                         │ calls
                                          ┌──────────────▼────────────────────┐
                                          │ studio/orchestrator/agent.py      │
                                          │  Hermes tool-calling loop         │
                                          │  (llm.agentic_loop)               │
                                          └──────────────┬────────────────────┘
                                              tool calls │ (OpenAI tools schema)
                         ┌────────────────────────────────┼─────────────────────────────┐
                         ▼                                ▼                               ▼
              studio/orchestrator/tools.py      pipeline seams                  memory layers
              (typed tool registry)             cli run / per-stage funcs       journal/recall/
                                                                                telemetry/manifest
```

Three new modules, zero changes to existing stage logic:
- `studio/providers/llm.py` — add `hermes` provider + new `agentic_loop()`.
- `studio/orchestrator/` — `agent.py` (the loop), `tools.py` (tool registry mapping to seams + memory).
- `studio/acp_server.py` — ACP agent wrapping the orchestrator.

---

## 3. Phase 1 — Hermes as a provider (smallest, ship first)

**Goal:** Hermes answers `ideate`/`learn`/`script`/`metadata` like any other provider. No agentic behavior yet. Proves serving + cost.

**Serving choice (pick one, all OpenAI-compatible):**
- **OpenRouter** (fastest to wire, confirmed): `nousresearch/hermes-4-70b` ($0.13/$0.40 per 1M) or `-405b` ($1/$3 per 1M). Base `https://openrouter.ai/api/v1`.
- **Nous Portal:** `https://inference-api.nousresearch.com/v1`, models `Hermes-4-70B` / `-405B`.
- **Self-host vLLM:** `--enable-auto-tool-choice --tool-call-parser hermes` (the `Hermes2ProToolParser`, registered `"hermes"`). Needed only when Phase 2 tool-calls must be local/free.
- **Local Ollama:** `hermes3:*` tags today (Hermes 4 GGUF loadable via Modelfile). Tool-calling weaker than vLLM-with-parser.

**Code (≈4 lines in `llm.py`, mirrors the groq/openrouter branch):**
```python
if provider == "hermes":
    return _openai_compatible(
        config.env("HERMES_BASE_URL") or "https://openrouter.ai/api/v1",
        config.env("HERMES_API_KEY"),
        config.env("HERMES_MODEL") or "nousresearch/hermes-4-70b",
        system, user)
```
Add `HERMES_API_KEY`/`HERMES_BASE_URL`/`HERMES_MODEL` to `config.have()` + `.env.example`, and slot `hermes` into `default_provider("script")` priority (after openai, before stub). Recommended sampling per model card: temp 0.6, top-p 0.95, top-k 20.

**Done when:** `studio marketing ideate --provider hermes` and `... learn --provider hermes` produce valid JSON.

---

## 4. Phase 2 — Hermes as the agentic orchestrator brain

The current `complete()` is single-shot. An orchestrator needs the **tool-call loop**: model emits `tool_calls` → we execute → feed `role:"tool"` results → repeat until `stop`.

### 4a. New LLM entry point
```python
# studio/providers/llm.py
def agentic_loop(provider, messages, tools, *, max_steps=12, on_event=None) -> list[dict]:
    """OpenAI tool-calling loop. `tools` = OpenAI function schema list.
    Dispatches tool_calls to a registry, appends role:'tool' results, repeats
    until the model stops or max_steps. on_event(evt) streams progress (→ ACP)."""
```
- Served by vLLM-with-`hermes`-parser / OpenRouter / Nous Portal, this uses the **standard `tools=[...]` param** — **no `<tool_call>` XML hand-rolling**. The server translates Hermes's `<tool_call>` tags ↔ OpenAI `tool_calls` for us.
- Only hand-roll the `<tools>`/`<tool_call>`/`<tool_response>` ChatML format if serving a raw checkpoint with no parser (avoid — prefer vLLM parser or hosted).
- Keep `complete()` untouched for the single-shot stages.

### 4b. Tool registry = the memory layers + seams (`studio/orchestrator/tools.py`)
Each tool is a thin typed wrapper over existing functions. The brain "uses all memory layers" by having a read+write tool per layer:

| Tool | Wraps | Memory layer / seam |
|------|-------|---------------------|
| `loop_plan(channel)` | `loop.plan(j)` | 8 — what's due (read) |
| `journal_read(channel)` | `journal.load` | 1,2 — strategy + ledger (read) |
| `recall(channel, query, k)` | `memory.recall` | 7 — episodic recall (read) |
| `add_bet(channel, idea, hook, assumption, goal, theme, tags, explore)` | `m_add` | 2 — write planned bet |
| `set_strategy(channel, direction, winning, losing, seeds, niche)` | `m_strategy` | 1 — write thesis |
| `backlog(channel)` | `m_backlog` | 2 — planned bets (read) |
| `produce(idea, duration, max_cost, channel)` | subprocess `studio run … --publish-to youtube` | pipeline (write) |
| `link(entry_id, run_id, channel)` | `m_link` | 3 — capture telemetry |
| `measure(channel)` | `m_measure` | 4,5,6 — stats+score (write) |
| `reflect(channel, provider)` | `learn.reflect` | 1 — LLM reflection (write) |
| `run_status(run_id)` | `manifest.load` | 4 — per-run state (read) |
| `brand(spec)` | `studio brand` | 11 — brand kit (write) |

Tools 1–8 + telemetry give the brain the entire working memory; ideate/learn become *optional* (the brain can author bets directly via `add_bet`/`set_strategy`, bypassing the sub-LLM, or call `reflect` to delegate). Operator memory (12) is injected as a system-prompt preamble, not a tool.

### 4c. The orchestrator agent (`studio/orchestrator/agent.py`)
```python
def orchestrate(channel, *, provider="hermes", produce=False, on_event=None) -> dict:
    """One autonomous tick, brain-driven:
       system prompt = growth-strategist role + operator-memory preamble + loop policy
       seed = loop_plan(channel) summary
       → agentic_loop(provider, msgs, TOOLS, on_event=on_event)
       Guardrails: produce gated behind `produce`; spend capped by per-video budget;
       destructive/publish tools require ACP permission (Phase 3)."""
```
- Reuses the existing maturation/cadence policy from `loop.py` as the system-prompt's decision rubric, so the brain's judgment is *bounded* by the proven FSM rather than freelancing.
- `on_event` emits `{plan, tool_call, tool_result, message}` — consumed by CLI (print) or ACP (`session/update`).
- New CLI: `studio marketing orchestrate --channel X [--produce]` — the brain-driven sibling of `autopilot`. Keep `autopilot` (deterministic) as the safe fallback.

**Why Hermes here specifically:** native tool-call training (single-token tags, reliable streaming), high steerability / low refusal — it obeys the orchestration spec rather than hedging mid-pipeline. 70B is the cost/quality sweet spot; 405B for max planning quality.

---

## 5. Phase 3 — ACP interface (drop into Zed)

**Goal:** the orchestrator becomes an ACP agent; Zed's panel drives it with streaming, plan checklists, tool-call cards, and permission dialogs — zero per-editor UI work.

**Use the official Python SDK** (`pip install agent-client-protocol`, `import acp`, v0.10.1, Python ≥3.10,<3.15). Don't hand-roll JSON-RPC-over-stdio.

`studio/acp_server.py`:
```python
import asyncio
from acp import Agent, NewSessionResponse, PromptResponse, run_agent, text_block, update_agent_message
from studio.orchestrator.agent import orchestrate

class StudioAgent(Agent):
    def on_connect(self, conn): self._conn = conn
    async def new_session(self, **kw): return NewSessionResponse(session_id=...)
    async def prompt(self, prompt, session_id, **kw):
        channel = _parse_channel(prompt)               # e.g. "grow @noir-channel"
        async def on_event(evt):                        # map orchestrator → ACP
            if evt.kind == "plan":        await self._conn.session_update(... plan ...)
            elif evt.kind == "tool_call": await self._conn.session_update(... tool_call ...)
            elif evt.kind == "message":   await self._conn.session_update(
                                              session_id, update_agent_message(text_block(evt.text)))
        await asyncio.to_thread(orchestrate, channel, on_event=_bridge(on_event), produce=False)
        return PromptResponse(stop_reason="end_turn")

if __name__ == "__main__": asyncio.run(run_agent(StudioAgent()))
```

**ACP mappings (the "features like acp" the user wants):**
- `initialize` → advertise capabilities (`fs.readTextFile`, `terminal` if we let the editor run `studio` cmds).
- `session/new` → fresh channel context; `session/load` (cap `loadSession`) → replay a channel's recent ticks as `session/update`s.
- Orchestrator `plan` → **`plan`** update (renders as a live checklist of measure/learn/ideate/produce).
- Each tool call → **`tool_call`** (kind `execute`/`fetch`/`edit`) + **`tool_call_update`** (`pending→in_progress→completed`), with `locations` pointing at `runs/<id>/` so Zed "follows along."
- **`session/request_permission`** gates the irreversible tools — **`produce`** (spends money) and **`publish`** — with allow_once / allow_always / reject buttons. This is the right home for the spend/publish confirmation that today is a `--produce` flag.
- Register in the **ACP Registry** so the agent appears in every ACP client (Zed, JetBrains, Neovim, VS Code).

**Payoff:** "grow my noir channel" typed in Zed's panel → live plan checklist, tool cards streaming, a permission prompt before any spend or upload — all native, no bespoke UI.

---

## 6. File-change summary

| File | Change |
|------|--------|
| `studio/providers/llm.py` | + `hermes` branch in `complete()`; + new `agentic_loop()` |
| `studio/config.py` | + `HERMES_*` keys in `have()`; + `hermes` in `default_provider` |
| `.env.example` | + `HERMES_API_KEY` / `HERMES_BASE_URL` / `HERMES_MODEL` |
| `studio/orchestrator/__init__.py` | new package |
| `studio/orchestrator/tools.py` | new — typed tool registry over seams + memory layers |
| `studio/orchestrator/agent.py` | new — `orchestrate()` Hermes loop |
| `studio/acp_server.py` | new — ACP agent (acp SDK) |
| `studio/cli.py` | + `studio marketing orchestrate` command; + `studio acp` (launch ACP server on stdio) |
| `pyproject.toml` | + optional extras `[orchestrator]` (none new — httpx already present), `[acp]` (`agent-client-protocol`) |
| `docs/60-orchestrator/` | this plan + per-tool reference |

No changes to `stages/*`, `ffmpeg.py`, `manifest.py`, `journal.py`, `loop.py` — the brain composes them, doesn't alter them. Matches the repo's "add a provider = one function + a branch" ethos.

---

## 7. Sequencing & verification

1. **Phase 1** — Hermes provider. Verify: `ideate --provider hermes` emits valid JSON; cost lands in journal. *Independently useful even if 2/3 are dropped.*
2. **Phase 2a** — `agentic_loop()` + 3 read tools (`loop_plan`, `journal_read`, `recall`). Verify: brain narrates a correct next-action for a seeded journal **without** any write/produce tool.
3. **Phase 2b** — add write tools (`add_bet`, `set_strategy`, `link`, `measure`, `reflect`); `produce` last and gated. Verify against `autopilot`'s deterministic decision on the same journal (brain should agree on `next`).
4. **Phase 3** — ACP server; smoke against the SDK's reference client, then connect Zed. Verify: plan checklist + tool cards render; `produce`/`publish` raise a permission dialog.

Keep deterministic `autopilot` as the always-available fallback; `orchestrate` is the brain-driven upgrade, never the only path.

---

## 8. Risks & gotchas

- **Tool-call reliability depends on correct serving.** Must enable vLLM `--tool-call-parser hermes` (or use OpenRouter/Nous Portal). Avoid **Hermes 2 Theta** (degraded tool-calls). Keep parser/template matched to the checkpoint (14B=Qwen template, 70B/405B=Llama).
- **Reduced refusals cut both ways** — Hermes obeys the spec but won't self-guardrail; *we* own the spend cap, the `produce`/`publish` permission gate, and content validation.
- **Cost of a thinking, multi-step loop** > single-shot. Bound with `max_steps`, prefer 70B, and disable `<think>` for cheap routing ticks. Existing per-video budget cap still governs actual spend (`clips` aborts over `--max-cost`).
- **Recall is lexical** (layer 7) — fine now; `memory._relevance()` is the single swap point for embeddings later if the ledger grows large.
- **ACP Python SDK provenance:** docs list it first-party, but PyPI author metadata still credits PsiACE and it lives under the `agentclientprotocol` org (not `zed-industries`). Community-originated, adopted as official — pin a version whose `ACP_SCHEMA_VERSION` matches protocol `v1` (what Zed speaks).
- **Don't pay downstream of a `stub` script** (existing gotcha) — the brain's `produce` tool must refuse to run paid stages on a stub script; assert real narration first.

---

## 9. Sources

- Hermes: HF cards `NousResearch/Hermes-4-405B|70B|14B`, `Hermes-4.3-36B`; `NousResearch/Hermes-Function-Calling` (GitHub); vLLM tool-calling docs + `hermes_tool_parser.py`; OpenRouter Hermes 4 pages; Nous Portal API docs; Ollama `hermes3`.
- ACP: `agentclientprotocol.com/protocol/v1/*`; `github.com/agentclientprotocol/{agent-client-protocol,python-sdk}`; PyPI `agent-client-protocol` 0.10.1; `zed.dev/acp` + ACP Registry blog.
- Repo seams: `cli.py` (`run`, `m_autopilot`, marketing sub-app), `marketing/{loop,ideate,learn,memory,score,journal,telemetry}.py`, `providers/{llm,base}.py`, `config.py`, `manifest.py`.
