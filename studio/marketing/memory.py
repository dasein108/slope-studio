"""Episodic recall over the journal — retrieve the RELEVANT past bets, not the recent ones.

Research backing: a self-improving loop should retrieve the *relevant* past episodes and
inject their lessons into the next decision (Reflexion's "episodic memory buffer", ERL's
"actionable lessons that transfer", CER's experience replay). See
`docs/20-research/self-improving-loop.md` (F-SI1, F-SI4).

This stays deliberately dependency-free: relevance is lexical (token overlap), so it works
offline with no embedding key and no vector DB. Moving to embeddings + a vector store is the
documented next step but is gated on open question Q9 (`docs/20-research/open-questions.md`) —
so the seam is here (`_relevance`) but the default is free and local. Each measured Entry is
one episode; `recall()` ranks them against a query built from the channel's current direction.
"""

from __future__ import annotations

import re

from studio.marketing.journal import Entry, Journal

# words too generic to carry relevance signal
_STOP = frozenset(
    "the a an and or of to in on for with is are be this that it as at by from into "
    "you your we our they their he she his her its about over under more most very how "
    "what why when who which will would can could should video short shorts".split()
)


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in _STOP}


def _relevance(query: set[str], doc: set[str]) -> float:
    """Overlap coefficient — robust when episode cards are much shorter than the query."""
    if not query or not doc:
        return 0.0
    return len(query & doc) / min(len(query), len(doc))


def episode_card(e: Entry) -> str:
    """One compact, prompt-ready line summarizing a measured bet and what it taught."""
    vir = "?" if e.virality is None else f"{e.virality:.3f}"
    pct = "" if e.percentile is None else f" p{e.percentile:.0f}"
    out = e.outcome or "?"
    bits = [f"[{out}{pct} · vir {vir}]", f"theme={e.theme or '-'}", f"idea: {e.idea}"]
    if e.hook:
        bits.append(f'hook: "{e.hook}"')
    if e.learnings:
        bits.append(f"lesson: {e.learnings}")
    return " | ".join(bits)


def _episode_tokens(e: Entry) -> set[str]:
    return _tokens(" ".join([e.idea, e.hook, e.theme, e.assumption, e.learnings, *e.tags]))


def recall(j: Journal, query: str, k: int = 6) -> list[Entry]:
    """Top-k measured episodes most relevant to `query`, best-relevance first.

    Ties broken by virality (so a relevant winner outranks a relevant flop). Only measured
    bets are recalled — an unmeasured bet has no lesson yet. Returns [] before anything is
    measured, in which case the caller should fall back to strategy-only prompting.
    """
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[float, float, Entry]] = []
    for e in j.measured():
        rel = _relevance(q, _episode_tokens(e))
        if rel > 0.0:
            scored.append((rel, e.virality or 0.0, e))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [e for _, _, e in scored[:k]]


def recall_block(j: Journal, query: str, k: int = 6) -> str:
    """Render recalled episodes as a prompt block (empty string if nothing measured yet)."""
    eps = recall(j, query, k)
    if not eps:
        return ""
    return "\n".join(f"- {episode_card(e)}" for e in eps)
