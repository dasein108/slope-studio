"""Strategy-drift detection for the viral loop.

Scans the journal for two failure modes:
  1. Topic collapse — >60% of recent bets share the same theme (narrowing kills discovery).
  2. Safety erosion — safety/guardrail language disappears from the strategy direction
     (signals the loop is drifting toward un-reviewed content directions).

Never modifies the strategy autonomously — flags drift for CEO review only.
"""

from __future__ import annotations

from studio.marketing import journal as jrnl
from studio import notify

# safety-adjacent terms whose absence in strategy direction is a yellow flag
_SAFETY_TERMS = frozenset(
    "avoid safe guardrail responsible quality accuracy fact accurate mislead "
    "dangerous harmful offensive policy".split()
)

COLLAPSE_THRESHOLD = 0.60   # >60% of recent bets on same theme = collapse
COLLAPSE_WINDOW = 10        # how many recent bets to inspect


def _recent_themes(j: jrnl.Journal, window: int = COLLAPSE_WINDOW) -> list[str]:
    recent = [e for e in j.entries if e.theme][-window:]
    return [e.theme.split("/")[0].strip().lower() for e in recent]


def _detect_collapse(j: jrnl.Journal, window: int = COLLAPSE_WINDOW) -> str | None:
    themes = _recent_themes(j, window)
    if len(themes) < 3:
        return None
    counts: dict[str, int] = {}
    for t in themes:
        counts[t] = counts.get(t, 0) + 1
    top_theme, top_n = max(counts.items(), key=lambda kv: kv[1])
    ratio = top_n / len(themes)
    if ratio > COLLAPSE_THRESHOLD:
        return (f"topic collapse: '{top_theme}' = {top_n}/{len(themes)} "
                f"({ratio:.0%}) of last {window} bets (threshold {COLLAPSE_THRESHOLD:.0%})")
    return None


def _detect_safety_erosion(j: jrnl.Journal) -> str | None:
    """Flag if a non-empty strategy direction lacks safety-adjacent keywords."""
    direction = (j.strategy.current_direction or "").lower()
    if not direction or len(j.measured()) < 5:
        return None
    tokens = set(direction.replace(",", " ").replace(".", " ").split())
    if not (_SAFETY_TERMS & tokens):
        return "safety erosion: strategy direction lacks safety/accuracy keywords — review for topic drift"
    return None


def detect(j: jrnl.Journal) -> list[str]:
    """Return a list of drift signal strings. Empty = no drift detected."""
    signals: list[str] = []
    c = _detect_collapse(j)
    if c:
        signals.append(c)
    s = _detect_safety_erosion(j)
    if s:
        signals.append(s)
    return signals


def notify_drift(signals: list[str], channel: str = "") -> bool:
    """Send a Telegram alert (best-effort). Returns True if sent."""
    if not signals:
        return False
    ch_label = f" [{channel}]" if channel else ""
    lines = [f"⚠️ Strategy drift detected{ch_label} — CEO review needed:"]
    lines += [f"  • {s}" for s in signals]
    lines.append("Action: run `studio marketing journal` and review recent bets.")
    return notify.telegram("\n".join(lines))
