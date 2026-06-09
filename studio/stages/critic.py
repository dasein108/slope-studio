"""Stage 1.5 — critic gate: score the scenario for CONTENT before spending on visuals.

The #1 failure mode is a beautifully-animated video that says nothing. This stage scores a
script against four content criteria (see models.CRITIC_CRITERIA) and returns a verdict with
per-criterion pass/score/feedback plus concrete `revision_notes`. The `run` orchestrator loops
script -> critic -> (re-script with feedback) until it passes or a retry cap is hit.

The thinking is the LLM judge's; this module is the I/O helper that prompts it and parses the
verdict. Pure of any retry policy — that lives in the CLI (`_script_with_critic`).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from studio import paths
from studio.models import CRITIC_CRITERIA, CriterionScore, CriticVerdict, Script
from studio.providers import llm

SYSTEM = """You are a ruthless short-form video EDITOR judging whether a scenario is worth
producing. You judge CONTENT, not visuals or motion — a pretty video that teaches nothing is a
failure. Be honest and specific; it is better to decline a weak script than to ship filler.

Score the scenario against EXACTLY these four criteria (use these keys):
- topic_revealed: Does it deliver on its title/promise? A viewer who saw only this must come
  away KNOWING the thing it teased — not merely intrigued. If the title asks a question, the
  body must ANSWER it.
- fact_explained: Is there at least ONE concrete, nameable fact / idea / event (a number, name,
  date, mechanism, turning point) that is STATED **and EXPLAINED** (the what AND the why/how) —
  not just asserted? "It changed everything" with no specifics FAILS.
- informative_interesting: Does it teach something a smart viewer likely didn't know, framed
  with a real curiosity gap? Hollow, generic, or obvious content FAILS.
- emotional_payoff: Does it land a clear emotion (awe, dread, injustice, wonder, the click of a
  paradox)? A flat, emotionless arc FAILS.

For each criterion give: passed (true/false), score (1-5), and feedback (one specific sentence;
if failed, say exactly what is missing and how to fix it). Then write `revision_notes`: a short
paragraph of CONCRETE instructions the writer can apply to fix every failure (name the missing
fact to add, the emotion to land, the beat to cut). Be specific to THIS script.

Output ONLY valid JSON:
{"passed": <true if ALL four passed>,
 "summary": "one-line overall verdict",
 "revision_notes": "concrete fixes, or empty string if passed",
 "scores": [
   {"name": "topic_revealed", "passed": true, "score": 4, "feedback": "..."},
   {"name": "fact_explained", "passed": false, "score": 2, "feedback": "..."},
   {"name": "informative_interesting", "passed": true, "score": 4, "feedback": "..."},
   {"name": "emotional_payoff", "passed": false, "score": 2, "feedback": "..."}
 ]}"""

USER_TMPL = """Judge this scenario.

Title: {title}
Topic: {topic}
Total duration: {duration}s, {n} scenes.

Narration (the spoken content — judge THIS for substance):
{narration}

Scene beats (visual_prompt — context only, do not judge visuals):
{beats}"""


def _verdict_from_raw(raw: str) -> CriticVerdict:
    """Parse the judge's JSON into a CriticVerdict, tolerating extra/missing keys."""
    data = json.loads(raw)
    scores = [
        CriterionScore(
            name=str(s.get("name", "")),
            passed=bool(s.get("passed", False)),
            score=int(s.get("score", 0) or 0),
            feedback=str(s.get("feedback", "")),
        )
        for s in data.get("scores", [])
        if s.get("name") in CRITIC_CRITERIA
    ]
    # Overall pass = the model's flag AND every known criterion actually passing.
    all_pass = bool(data.get("passed", False)) and bool(scores) and all(c.passed for c in scores)
    return CriticVerdict(
        passed=all_pass,
        scores=scores,
        revision_notes=str(data.get("revision_notes", "")),
        summary=str(data.get("summary", "")),
    )


def run(run_dir: Path, script: Script, provider: str) -> tuple[CriticVerdict, float, float]:
    """Score `script`; write 01_critic.json; return (verdict, latency_s, cost_usd).

    `provider == "stub"` auto-passes (the stub script is wiring-only; never gate it).
    """
    t0 = time.time()
    if provider == "stub":
        verdict = CriticVerdict(passed=True, summary="stub — critic skipped (wiring scenario)")
    else:
        narration = "\n".join(
            f"  [{s.id}] {s.narration}" for s in script.scenes if s.narration.strip()
        ) or "  (no narration — silent/visual piece)"
        beats = "\n".join(f"  [{s.id}] {s.visual_prompt}" for s in script.scenes)
        raw = llm.complete(
            provider, SYSTEM,
            USER_TMPL.format(
                title=script.title or script.topic, topic=script.topic,
                duration=script.duration_s, n=len(script.scenes),
                narration=narration, beats=beats),
        )
        verdict = _verdict_from_raw(raw)
    paths.critic_json(run_dir).write_text(verdict.model_dump_json(indent=2))
    return verdict, round(time.time() - t0, 2), 0.0  # critic LLM cost ~0 (cents)
