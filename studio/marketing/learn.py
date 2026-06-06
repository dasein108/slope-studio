"""Step 3b of the loop — reflect on measured bets and steer the next idea.

Feeds the measured portfolio (each bet's assumption + virality + retention + top
audience comments) to an LLM and asks: which assumptions held? what pattern wins
here? what's the single best next direction + concrete idea seeds? The result is
written back into the journal's `Strategy`, which `ideate` then consumes — closing
the loop. Deterministic fallback derives patterns from percentile ranks alone.
"""

from __future__ import annotations

import json

from studio.marketing import journal as jrnl
from studio.providers import llm

SYSTEM = """You are a growth analyst for short-form video. You compare each video's
PRE-STATED assumption against its measured virality to learn what actually drives
this specific audience. Be concrete and falsifiable. Output ONLY valid JSON."""

USER_TMPL = """Channel niche: {niche}
Phase: {phase}
Portfolio ({n} measured videos), best to worst:
{table}

For context, virality is a composite of view-velocity, retention, and engagement,
ranked as a percentile within THIS channel.

Analyze and return JSON exactly:
{{
  "winning_patterns": ["concrete traits of the top performers"],
  "losing_patterns": ["concrete traits of the bottom performers"],
  "current_direction": "one paragraph: the thesis for what to make next and why",
  "next_seeds": ["3-5 specific next idea seeds that exploit the winners"],
  "entry_learnings": {{"<entry_id>": "one line: did its assumption hold?"}}
}}"""


def _row(e: jrnl.Entry) -> str:
    m = e.metrics
    ret = "n/a" if not m or m.retention is None else f"{m.retention:.0f}%"
    views = m.views if m else 0
    cm = " | ".join(c[:80] for c in e.comments_sample[:3])
    return (f"[{e.id}] pct={e.percentile:.0f} vir={e.virality:.3f} views={views} "
            f"ret={ret} | idea: {e.idea} | hook: {e.hook} | assumption: {e.assumption}"
            + (f" | top comments: {cm}" if cm else ""))


def _fallback(j: jrnl.Journal) -> None:
    """No LLM: derive coarse patterns from percentile ranks."""
    measured = sorted(j.measured(), key=lambda e: e.percentile or 0, reverse=True)
    if not measured:
        return
    top = measured[: max(1, len(measured) // 4)]
    bot = measured[-max(1, len(measured) // 4):]
    s = j.strategy
    s.winning_patterns = [f"theme '{e.theme}': {e.hook[:60]}" for e in top if e.theme or e.hook]
    s.losing_patterns = [f"theme '{e.theme}': {e.idea[:60]}" for e in bot]
    s.next_seeds = [f"more like: {e.idea}" for e in top]
    s.current_direction = ("Cold-start heuristic: double down on the top-quartile themes "
                           "above; the loop needs an LLM key for deeper analysis.")


def reflect(j: jrnl.Journal, provider: str) -> str:
    """Update j.strategy (and per-entry learnings) from measured bets. Returns a note."""
    measured = sorted(j.measured(), key=lambda e: e.virality or 0, reverse=True)
    if not measured:
        return "no measured videos yet — deploy + `marketing measure` first"
    phase = "cold-start" if j.in_cold_start else "optimizing"
    if not provider or provider == "stub":
        _fallback(j)
        j.strategy.updated_at = j.last_learn_at = jrnl._now()
        return f"updated strategy from {len(measured)} videos (heuristic, no LLM)"
    table = "\n".join(_row(e) for e in measured)
    user = USER_TMPL.format(niche=j.strategy.niche or "(unset)", phase=phase,
                            n=len(measured), table=table)
    try:
        data = json.loads(llm.complete(provider, SYSTEM, user))
        s = j.strategy
        s.winning_patterns = data.get("winning_patterns") or s.winning_patterns
        s.losing_patterns = data.get("losing_patterns") or s.losing_patterns
        s.current_direction = data.get("current_direction") or s.current_direction
        s.next_seeds = data.get("next_seeds") or s.next_seeds
        s.updated_at = j.last_learn_at = jrnl._now()
        for eid, note in (data.get("entry_learnings") or {}).items():
            e = j.get(eid)
            if e:
                e.learnings = note
        return f"strategy updated from {len(measured)} videos via {provider}"
    except Exception as e:
        _fallback(j)
        j.strategy.updated_at = j.last_learn_at = jrnl._now()
        return f"heuristic fallback (LLM failed: {str(e)[:60]})"
