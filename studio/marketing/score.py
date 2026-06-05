"""Virality scoring — turn raw YouTube metrics into a single comparable signal.

Two layers:
  - `virality(m)`  absolute composite (log-damped velocity + retention + engagement
    + subs-conversion). Works for any single video.
  - `relativize(scores)`  percentile rank WITHIN the channel's own portfolio. This is
    the real signal: "viral" only means anything relative to your own baseline. It's
    only meaningful once enough videos exist (see journal.BOOTSTRAP_TARGET) — below
    that, treat scores as cold-start absolutes, not verdicts.

Weights are heuristic and intended to be tuned once a channel has real history.
"""

from __future__ import annotations

import math

from studio.marketing.journal import Metrics

# composite weights — velocity dominates (it's what "viral" feels like), but retention
# and engagement guard against cheap-reach views that don't convert.
W_VELOCITY = 0.5
W_RETENTION = 0.2
W_ENGAGEMENT = 0.2
W_SUBS = 0.1

WIN_PCTILE = 75.0   # >= this percentile in the portfolio == a winner
LOSS_PCTILE = 25.0  # <= this == a loss


def derive(m: Metrics) -> Metrics:
    """Fill velocity + engagement from the raw counts (pure)."""
    age = max(m.age_days, 0.5)
    m.velocity = round(max(m.views, 0) / age, 3)
    m.engagement = round((m.likes + m.comments) / max(m.views, 1), 5)
    return m


def virality(m: Metrics) -> float:
    """Absolute composite score for one video (higher = more viral)."""
    ret = (m.retention or 0.0) / 100.0
    subs_conv = m.subs_gained / max(m.views, 1)
    score = (
        W_VELOCITY * math.log10(m.velocity + 1)
        + W_RETENTION * ret
        + W_ENGAGEMENT * min(m.engagement * 20, 1.0)   # ~5% engagement saturates
        + W_SUBS * min(subs_conv * 50, 1.0)            # ~2% sub-rate saturates
    )
    return round(score, 4)


def relativize(scores: list[float]) -> list[float]:
    """Percentile rank (0-100) of each score within the list."""
    n = len(scores)
    if n <= 1:
        return [50.0] * n
    return [round(100.0 * sum(s <= x for s in scores) / n, 1) for x in scores]


def outcome(percentile: float | None, cold_start: bool) -> str:
    if cold_start or percentile is None:
        return "cold-start"
    if percentile >= WIN_PCTILE:
        return "win"
    if percentile <= LOSS_PCTILE:
        return "loss"
    return "neutral"
