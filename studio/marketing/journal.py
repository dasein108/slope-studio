"""The growth journal — the durable memory of the viral loop.

One JSON ledger per channel (`runs/_marketing/<channel>/journal.json`) plus a
human-readable `journal.md`. Every entry records a bet and, once measured, its
outcome. `Strategy` accumulates what the loop has learned so the NEXT idea is
better than the last.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from studio import paths

BOOTSTRAP_TARGET = 10  # videos needed before relative virality scoring is meaningful


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Metrics(BaseModel):
    """Raw + derived performance pulled from YouTube for one video."""

    views: int = 0
    likes: int = 0
    comments: int = 0
    retention: float | None = None        # averageViewPercentage 0-100 (None if no scope)
    subs_gained: int = 0
    age_days: float = 0.0
    velocity: float = 0.0                 # views / day
    engagement: float = 0.0               # (likes + comments) / views
    fetched_at: str = ""


class Entry(BaseModel):
    """A single bet: an idea + the assumption it tests, tracked to its outcome."""

    id: str
    created: str = Field(default_factory=_now)
    # --- the bet (step 1) ---
    idea: str
    hook: str = ""
    assumption: str = ""                  # WHY we think this goes viral
    goal: str = ""                         # the target, e.g. ">P75 view-through"
    theme: str = ""
    tags: list[str] = Field(default_factory=list)
    explore: bool = True                   # exploration bet vs exploitation of a known winner
    # --- deployment (step 2) ---
    status: str = "planned"               # planned | deployed | measured
    run_id: str = ""
    video_id: str = ""
    video_url: str = ""
    published_at: str = ""
    # --- measurement (step 3) ---
    metrics: Metrics | None = None
    virality: float | None = None         # absolute composite score
    percentile: float | None = None       # 0-100 within this channel's portfolio
    outcome: str = ""                     # win | loss | neutral | cold-start
    comments_sample: list[str] = Field(default_factory=list)
    learnings: str = ""                   # what this bet taught us (filled by `learn`)


class Strategy(BaseModel):
    """Accumulated direction — the loop's current thesis about what goes viral."""

    niche: str = ""
    current_direction: str = ""
    winning_patterns: list[str] = Field(default_factory=list)
    losing_patterns: list[str] = Field(default_factory=list)
    next_seeds: list[str] = Field(default_factory=list)  # concrete idea seeds for ideate
    updated_at: str = ""


class Journal(BaseModel):
    channel: str = ""
    bootstrap_target: int = BOOTSTRAP_TARGET
    strategy: Strategy = Field(default_factory=Strategy)
    entries: list[Entry] = Field(default_factory=list)

    # -- queries --
    def next_id(self) -> str:
        return f"j{len(self.entries) + 1:04d}"

    def get(self, entry_id: str) -> Entry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    def measured(self) -> list[Entry]:
        return [e for e in self.entries if e.status == "measured" and e.virality is not None]

    @property
    def deployed_count(self) -> int:
        return sum(1 for e in self.entries if e.status in ("deployed", "measured"))

    @property
    def in_cold_start(self) -> bool:
        return self.deployed_count < self.bootstrap_target


# --------------------------------------------------------------------------- io
def load(channel: str = "") -> Journal:
    p = paths.journal_json(channel)
    if p.exists():
        return Journal.model_validate_json(p.read_text())
    return Journal(channel=channel)


def save(j: Journal) -> None:
    d = paths.marketing_dir(j.channel)
    d.mkdir(parents=True, exist_ok=True)
    paths.journal_json(j.channel).write_text(j.model_dump_json(indent=2))
    paths.journal_md(j.channel).write_text(render_md(j))


def render_md(j: Journal) -> str:
    """Human-readable ledger — the at-a-glance state of the growth loop."""
    s = j.strategy
    out = [f"# Growth journal — {j.channel or 'default'}", ""]
    phase = (f"COLD START ({j.deployed_count}/{j.bootstrap_target} deployed — exploring; "
             f"relative scoring unlocks at {j.bootstrap_target})"
             if j.in_cold_start else f"OPTIMIZING ({j.deployed_count} deployed)")
    out += [f"**Phase:** {phase}", ""]
    if s.niche:
        out.append(f"**Niche:** {s.niche}")
    if s.current_direction:
        out += ["", "## Current direction", s.current_direction]
    if s.winning_patterns:
        out += ["", "## What's working", *[f"- {p}" for p in s.winning_patterns]]
    if s.losing_patterns:
        out += ["", "## What's not", *[f"- {p}" for p in s.losing_patterns]]
    if s.next_seeds:
        out += ["", "## Next idea seeds", *[f"- {p}" for p in s.next_seeds]]
    out += ["", "## Bets", "",
            "| id | status | idea | hook | assumption | virality | %ile | outcome |",
            "|----|--------|------|------|------------|----------|------|---------|"]
    for e in j.entries:
        vir = "-" if e.virality is None else f"{e.virality:.3f}"
        pct = "-" if e.percentile is None else f"{e.percentile:.0f}"
        out.append(f"| {e.id} | {e.status} | {e.idea[:40]} | {e.hook[:30]} | "
                   f"{e.assumption[:40]} | {vir} | {pct} | {e.outcome or '-'} |")
    return "\n".join(out) + "\n"
