"""T8 — warm-started Thompson-sampling bandit for picking the next bet to produce.

Replaces "first-in-queue + a fixed 60/40 explore/exploit split" with an adaptive policy. Per the
verified research (F-SI6/F-SI7 in docs/20-research/self-improving-loop.md): a fixed split
over-explores weak arms; a contextual Thompson-sampling bandit that uses the bet's own features as
context beats it, and warming the prior from the channel's base rate (rather than a flat
Beta(1,1)) avoids the over-exploration of an optimistic uniform prior.

Design, kept dependency-free and honest about the data:
- **Context = what's known BEFORE production**: a bet's `theme` + `tags`. (Effects/animators are
  only known post-render, so they're a learn-side attribution concern, not a selection feature.)
- **Reward = a measured WIN** (percentile ≥ 75). Only bets measured in the optimizing phase
  (real percentile + win/loss/neutral outcome) count as evidence; cold-start measurements carry
  no relative signal and are ignored.
- **Per-feature Beta-Bernoulli posteriors**, warm-started from the channel base rate with a weak
  pseudo-count so data dominates quickly. A candidate is scored by Thompson-sampling each of its
  features and averaging — arms with little history have wide posteriors and so self-explore.

`pick()` is stochastic by nature (that's the exploration); callers pass a state-seeded RNG so the
same journal state yields the same pick (so `tick` and `autopilot` agree within a tick).
"""

from __future__ import annotations

import random
from collections import defaultdict

from studio.marketing.journal import Entry

WIN_PCTILE = 75.0


def _features(e: Entry) -> list[tuple[str, str]]:
    """Selection context known at planning time: theme + tags."""
    feats: list[tuple[str, str]] = []
    if e.theme:
        feats.append(("theme", e.theme.strip().lower()))
    feats += [("tag", t.strip().lower()) for t in e.tags if t.strip()]
    return feats


def _evidence(measured: list[Entry]) -> list[tuple[Entry, bool]]:
    """Measured bets that carry RELATIVE signal, each tagged win=True/False."""
    out = []
    for e in measured:
        if e.percentile is None or e.outcome not in ("win", "loss", "neutral"):
            continue  # cold-start / unscored → no relative signal
        out.append((e, e.percentile >= WIN_PCTILE))
    return out


def _base_rate(evidence: list[tuple[Entry, bool]]) -> float:
    if not evidence:
        return 0.5
    return sum(1 for _, win in evidence if win) / len(evidence)


def posteriors(measured: list[Entry], prior_strength: float = 2.0
               ) -> dict[tuple[str, str], list[float]]:
    """Per-feature Beta(alpha, beta), warm-started from the channel base rate."""
    ev = _evidence(measured)
    base = _base_rate(ev)
    pa, pb = max(base * prior_strength, 0.5), max((1.0 - base) * prior_strength, 0.5)
    stats: dict[tuple[str, str], list[float]] = defaultdict(lambda: [pa, pb])
    for e, win in ev:
        for f in _features(e):
            stats[f][0 if win else 1] += 1.0
    return stats


def _prior(measured: list[Entry], prior_strength: float) -> tuple[float, float]:
    base = _base_rate(_evidence(measured))
    return max(base * prior_strength, 0.5), max((1.0 - base) * prior_strength, 0.5)


def score(e: Entry, stats: dict, prior: tuple[float, float], rng: random.Random) -> float:
    """Thompson sample: draw each feature's win-prob, average. Featureless → prior draw."""
    feats = _features(e)
    if not feats:
        return rng.betavariate(*prior)
    samples = [rng.betavariate(*stats.get(f, prior)) for f in feats]
    return sum(samples) / len(samples)


def rank(planned: list[Entry], measured: list[Entry], prior_strength: float = 2.0,
         rng: random.Random | None = None) -> list[Entry]:
    """Planned bets, best Thompson draw first."""
    rng = rng or random.Random()
    stats = posteriors(measured, prior_strength)
    prior = _prior(measured, prior_strength)
    scored = [(score(e, stats, prior, rng), e) for e in planned]
    scored.sort(key=lambda t: t[0], reverse=True)
    return [e for _, e in scored]


def pick(planned: list[Entry], measured: list[Entry], prior_strength: float = 2.0,
         rng: random.Random | None = None) -> Entry | None:
    """The next bet to produce, or None if the backlog is empty."""
    if not planned:
        return None
    return rank(planned, measured, prior_strength, rng)[0]
