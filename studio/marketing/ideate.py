"""Step 1 of the loop — generate the next viral bet(s).

Synthesizes a new idea + hook + the assumption behind it, biased by:
  - the journal's accumulated strategy (winning/losing patterns, current direction),
  - optional live trend signals the marketing-guru SKILL gathered via web search,
  - the channel niche.

In COLD START (< bootstrap videos) it maximizes thematic DIVERSITY to map the space;
afterwards it EXPLOITS proven winners while still reserving exploration bets.
Falls back to a deterministic seed idea when no LLM key is present.
"""

from __future__ import annotations

import json

from studio.marketing import journal as jrnl
from studio.providers import llm

SYSTEM = """You are a viral short-form video strategist (YouTube Shorts / TikTok).
You design FALSIFIABLE bets: each idea pairs a concrete hook with the explicit
assumption about audience psychology that makes it go viral, and a measurable goal.
Optimize for: a 0-3s scroll-stopping hook, high curiosity gap, emotional payoff,
and rewatch/share triggers. Output ONLY valid JSON."""

USER_TMPL = """Channel niche: {niche}
Phase: {phase}
Current strategic direction: {direction}
Patterns that WORKED so far: {winning}
Patterns that FAILED so far: {losing}
Idea seeds queued: {seeds}
Live trend/narrative signals (from web research, may be empty):
{signals}

Already-tried ideas (do NOT repeat): {tried}

Generate {n} NEW short-video bet(s). {mode_hint}
Return JSON exactly:
{{
  "ideas": [
    {{
      "idea": "one-line concept",
      "hook": "the literal first 1-2 spoken/on-screen lines (0-3s scroll-stopper)",
      "assumption": "the psychological reason this should go viral (falsifiable)",
      "goal": "measurable target, e.g. 'top-quartile velocity' or '>50% retention'",
      "theme": "short theme tag",
      "tags": ["3-6", "lowercase", "keywords"]
    }}
  ]
}}"""


def _fallback(j: jrnl.Journal, n: int) -> list[dict]:
    niche = j.strategy.niche or "unusual knowledge: science, mystery, cosmos"
    seeds = j.strategy.next_seeds or [
        "a counterintuitive fact that contradicts common sense",
        "a hidden mechanism behind an everyday thing",
        "an unsettling truth from deep history or the cosmos",
    ]
    out = []
    for i in range(n):
        seed = seeds[i % len(seeds)]
        out.append({
            "idea": seed,
            "hook": "You were taught this wrong.",
            "assumption": "Curiosity-gap + authority-subversion drives watch-through.",
            "goal": "beat the channel's median velocity",
            "theme": niche.split(":")[0],
            "tags": ["shorts", "science", "mystery", "didyouknow"],
        })
    return out


def generate(j: jrnl.Journal, provider: str, n: int = 1,
             signals: str = "", niche: str = "") -> list[dict]:
    """Return a list of idea dicts (NOT yet written to the journal)."""
    if niche:
        j.strategy.niche = niche
    if not provider or provider == "stub":
        return _fallback(j, n)
    cold = j.in_cold_start
    mode_hint = (
        "COLD START: make the bets THEMATICALLY DIVERSE to probe what this audience "
        "rewards — vary theme, hook style, and emotion across them."
        if cold else
        "OPTIMIZING: lean into the winning patterns, but make at least one an "
        "exploration bet into adjacent territory."
    )
    tried = "; ".join(e.idea for e in j.entries[-30:]) or "(none yet)"
    user = USER_TMPL.format(
        niche=j.strategy.niche or "unusual knowledge: science, mystery, cosmos",
        phase="cold-start (exploring)" if cold else "optimizing",
        direction=j.strategy.current_direction or "(not set — first explore)",
        winning="; ".join(j.strategy.winning_patterns) or "(unknown)",
        losing="; ".join(j.strategy.losing_patterns) or "(unknown)",
        seeds="; ".join(j.strategy.next_seeds) or "(none)",
        signals=signals.strip()[:3000] or "(none provided)",
        tried=tried, n=n, mode_hint=mode_hint,
    )
    try:
        data = json.loads(llm.complete(provider, SYSTEM, user))
        ideas = data.get("ideas") or []
        return ideas[:n] if ideas else _fallback(j, n)
    except Exception:
        return _fallback(j, n)
