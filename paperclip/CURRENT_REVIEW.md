# Paperclip — Current Review & Enhancement Plan

_2026-06-15. State of the autonomous agent company + a research-backed plan to give agents
more autonomy, better analytics, and higher production throughput. No code — design only._

---

## 0. Where we are now (verified live state)

- **Company:** "Slope Studio" (`SLO`, active, id `e8c8d9b5-8bd9-4ee3-9515-9d32f7614e69`),
  runtime daemon `paperclipai run` @ `http://localhost:3100` (postgres-backed, `local_trusted`).
- **8 agents on Claude (`claude_local` adapter):** Screenwriter + QA Critic = `claude-opus-4-8`;
  Growth Lead/Producer/Analytics/CEO = `claude-sonnet-4-6`; Secretary/Observability = `claude-haiku-4-5-20251001`.
- **Idle heartbeats DISABLED** for all 8 (`runtimeConfig.heartbeat.enabled=false`) — killed ~240
  no-op self-wakes/day. Assignment + @mention + the one kept cron still wake agents (verified).
- **Routines:** only `daily-org-autopilot` (09:00 Asia/Makassar) kept; secretary-daily +
  weekly-observability paused.
- **Loop config (journal):** `daily_produce_cap=3, min_hours_between_produces=0, backlog_min=3`
  → 2-3 videos/cycle. Publish approval disabled (unattended publish).
- **Two memory layers:** journal (`runs/_marketing/<ch>/journal.json` — strategy/bandit/metrics,
  the LEARNING memory) + Paperclip issues/comments (COORDINATION memory).
- **Verification layer:** content critic (`studio critic`) + QA script/final gates + real-YouTube
  measurement. Reward signal already exists: virality / percentile / subs per bet.
- **Observed agent initiative under rigid rules:** agents already filed a real studio bug (SLO-17)
  and re-tuned budget (SLO-18) autonomously → "more free will" is mostly an instruction-loosening
  problem, not a capability gap.

---

## 1. The reframe (research headline)

The evidence kills "more freedom vs. more control." The axis is **freedom inside
harness-enforced primitives.** Relax the *creative* instructions, keep the *mechanical* ones,
never relax the *verification/budget* layer.

Production reality anchor (arXiv:2512.04123, Berkeley/Databricks, 3-0): **68% of shipping agent
systems run ≤10 steps before human intervention, 74% rely on human eval, static workflows are
preferred.** → graduate autonomy incrementally; it is not a switch.

Our edge: we already have a **real reward signal** (engagement metrics in the journal) — the
substitute for the "verifiable feedback" the self-improvement papers require.

---

## 2. Relax these instructions (AGENTS.md)

Finding (Anthropic, 3-0): *"instill good heuristics rather than rigid rules… you can't hardcode
a fixed path for exploring complex topics."* Bounded by MetaGPT: SOPs still help well-defined
tasks. So split roles:

**Relax to goal + good-defaults (creative / open-ended):**
- **Growth Lead** — remove the prescriptive `tick→action` decision table. Give the *outcome*
  (move the YPP goal; here is the journal + bandit; pick the next bet and justify). It self-directs
  well already.
- **Screenwriter** — drop the rigid handoff template/checklist; give hook/retention *goals* +
  past winners from the journal; let it find the form.
- **Analytics** — let it choose what to slice/learn instead of a fixed report template.

**Keep as SOP/checklist (mechanical, decomposable):**
- **Producer production sequence** (visuals→…→publish→link) — exactly the task SOPs help.
- **QA-critic gate criteria** — explicit checklist; this is the safety surface.

Move: strip micromanagement (exact comment templates, "do X then comment Y"); keep invariants.

---

## 3. Keep rigid (invariants — never relax)

Reward hacking is observed, not theoretical: a self-improving agent *"faked a log making it look
like tests passed… removed the markers we use to detect hallucination, despite explicit
instruction not to"* (Sakana DGM, 3-0). Therefore:
- QA gate + content critic stay **independent and agent-immutable**; no agent grades its own
  deliverable on the metric that gates publish/spend. Measurement pulling **real YouTube stats**
  is correct — keep the reward external + objective.
- Budget caps + QA-before-paid-spend stay hard.
- Handoff = a real assigned issue stays.

---

## 4. New framework / CLI primitives

Externalization taxonomy (arXiv:2604.08224, harness 3-0): build four primitives.

**MEMORY — validated writes (highest priority).** Finding (3-0): memory accumulation *degrades
safety alignment* (one agent's harmful-refusal rate fell 45%); *"memory updates should never be
committed passively"* — use a **Write Validation Gate** (contradiction/sanity check). Our journal
writes are unguarded and have a concurrency race (multiple agents load-mutate-save). New surface:
a gated `studio marketing strategy write` that runs a sanity/contradiction check **and a file
lock** before commit. One primitive fixes safety-drift + the lost-update race.

**SKILLS — versioned, archived playbooks.** Finding (3-0): self-adapting playbooks causally beat
fixed config (DGM 20%→50%); **open-ended archival** (keep weaker variants) beats greedy
(50% vs 39.7%) — *"less-performant ancestors were instrumental in discovering novel features."*
Give agents a CLI to save/version/fork playbooks (winning-script templates, hook patterns) and
keep the archive, not just latest. `next_seeds`/strategy is the seed of this.

**PROTOCOLS — let agents create work ("gain traction").** A lightweight `propose-task` primitive
so any agent can self-create an issue within its budget/authority instead of waiting. Bounded.

**HARNESS — effort-scaling caps.** Finding (3-0): *"scale effort to complexity… guardrails to
prevent agents spiraling out of control."* Per-task-class effort/spend caps the harness enforces.

---

## 5. Analytics / evals (explicit ask; weakest-evidence area — caveat-heavy)

Honest caveat: video has no crisp binary success, so the big self-improvement magnitudes may not
transfer, and specific metric/threshold recipes did NOT survive verification. Framing did:
- **Use existing reward as eval** — virality percentile / retention / subs already attributed per
  bet. That IS task-success proxy. Feed into reflection (rich reflections beat bare; reflect on
  error signals — arXiv:2405.06682 / Reflexion, 3-0).
- **Prompt/playbook A/B** — version AGENTS.md + playbooks; attribute measured outcomes via the
  journal. This is how we'll know relaxing worked.
- **Drift detection** on strategy/memory (strategy collapsing onto one theme; safety wording eroding).
- **Do NOT** adopt "single-call LLM-judge is most human-aligned" — refuted here (1-2). An LLM-judge
  for script quality is one noisy signal alongside real engagement, not gospel.
- Observability (now on-demand/assignment) is the eval-runner home.

---

## 6. Graduated autonomy + Misevolution safeguards

Define autonomy LEVELS with graduation criteria. We already leveled-up *publish* (approval off).
Frame each guardrail (spend cap, publish, self-task-creation) to widen only after eval evidence —
e.g. "self-task-creation unlocks after N cycles with QA-pass + above-median virality + 0 incidents."

Place a safeguard at each Misevolution pathway (arXiv:2509.26354, 3-0):

| pathway | safeguard |
|---|---|
| model | pinned models (done) |
| memory | validated journal/strategy writes + lock |
| tool/skill | review gate before an agent-authored playbook/skill goes live |
| workflow/policy | keep CEO / `autopilot-policy` gate for loop changes |

---

## 7. Do first (highest leverage)

1. **Relax Growth Lead + Screenwriter** to goal+defaults; keep Producer/QA as checklists.
   (Free, biggest "free will" gain, lowest risk.)
2. **Build validated memory-write primitive** — fixes safety-drift AND the concurrency race.
3. **Wire the reward loop into reflection** — virality data already exists; every role stores rich
   lessons keyed to it.
4. **Add `propose-task` + per-task effort caps** — "let agents gain traction," bounded.

---

## 8. Don't over-index (refuted / thin)

- Orchestrator-worker "90% faster" and single-call LLM-judge "most aligned" both **refuted** (1-2).
  Our event-driven assignment model is fine as-is.
- Self-evolution literature is mostly 2025-26 preprints, single-lab, on coding/math with oracle
  feedback. Adopt the *mechanisms* (reflection, archival, write-gates); discount the *numbers* for
  a creative domain.

---

## Sources (verified, primary)

- Anthropic — Building a multi-agent research system (heuristics > rigid rules; effort scaling)
- arXiv:2604.08224 — externalization taxonomy (memory/skills/protocols/harness; governed execution)
- arXiv:2512.04123 — production agents study (≤10 steps / human eval / static workflows preferred)
- arXiv:2509.26354 — Misevolution (four self-evolution risk pathways)
- arXiv:2405.06682 + 2303.11366 (Reflexion) — reflection loops; rich > bare feedback
- sakana.ai/dgm + arXiv:2505.22954 / 2505.24726 — self-rewriting agents, open-ended archive, reward hacking

Related: `tmp/PAPERCLIP_REVIEW.md` (operational/runtime review), memory `paperclip-org-autopilot`.
