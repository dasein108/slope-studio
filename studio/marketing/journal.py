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
    # --- production telemetry (filled at link from the run manifest; T3) ---
    cost_usd: float = 0.0                  # measured $ to produce this video
    duration_s: float = 0.0               # final video length (seconds)
    tier: str = ""                        # free | cheap | balanced | premium
    video_model: str = ""                 # i2v model used (kling|ltx|… or kenburns)
    animators: list[str] = Field(default_factory=list)   # distinct animators across scenes
    effects: list[str] = Field(default_factory=list)     # distinct fx + atmosphere used
    providers: dict[str, str] = Field(default_factory=dict)  # stage -> provider
    n_scenes: int = 0
    # --- measurement (step 3) ---
    metrics: Metrics | None = None
    virality: float | None = None         # absolute composite score
    percentile: float | None = None       # 0-100 within this channel's portfolio
    outcome: str = ""                     # win | loss | neutral | cold-start
    comments_sample: list[str] = Field(default_factory=list)
    learnings: str = ""                   # what this bet taught us (filled by `learn`)

    # cross-posting: platform -> "<iso>|<publish_id>" stamp. Presence = already posted
    # there, so the crosspost picker never re-uploads the same winner. {} = not yet.
    crossposts: dict[str, str] = Field(default_factory=dict)


class BudgetConfig(BaseModel):
    """Per-channel spend budget. Either a flat cap per video, or a rate per minute of video
    (the per-video --max-cost is then rate × video-minutes)."""

    mode: str = ""          # "" (unset) | per_video | per_minute
    amount: float = 0.0     # USD per video (per_video) OR USD per minute (per_minute)

    def cap_for(self, duration_s: float) -> float | None:
        """The --max-cost for a video of this length, or None if the budget is unset."""
        if self.mode == "per_video":
            return round(self.amount, 4)
        if self.mode == "per_minute":
            return round(self.amount * max(duration_s, 1.0) / 60.0, 4)
        return None

    def describe(self) -> str:
        if self.mode == "per_video":
            return f"${self.amount:.2f} per video"
        if self.mode == "per_minute":
            return f"${self.amount:.2f} per minute of video"
        return "(unset)"


class LoopConfig(BaseModel):
    """Cadence + maturation knobs for the autonomous driver (T1). The driver is a state
    machine over TIME because a published video must mature before its metrics are meaningful."""

    maturation_hours: float = 60.0          # wait this long after publish before measuring
    min_hours_between_produces: float = 20.0  # produce cadence (≈ 1/day at 20h)
    daily_produce_cap: int = 2              # max videos produced per rolling 24h
    learn_every: int = 3                    # reflect after this many NEW measured bets
    backlog_min: int = 2                    # ideate when planned bets drop below this
    target_duration_s: int = 60             # planned length → sizes the budget cap
    select: str = "bandit"                  # next-bet picker: bandit (T8) | fifo (first-in-queue)
    prior_strength: float = 2.0             # bandit warm-start pseudo-count


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
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    last_learn_at: str = ""                # ISO ts of the last strategy reflection
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
    out += [f"**Phase:** {phase}", f"**Budget:** {j.budget.describe()}", ""]
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
            "| id | status | idea | theme | cost | dur | model | virality | %ile | outcome |",
            "|----|--------|------|-------|------|-----|-------|----------|------|---------|"]
    for e in j.entries:
        vir = "-" if e.virality is None else f"{e.virality:.3f}"
        pct = "-" if e.percentile is None else f"{e.percentile:.0f}"
        cost = "-" if not e.cost_usd else f"${e.cost_usd:.2f}"
        dur = "-" if not e.duration_s else f"{e.duration_s:.0f}s"
        out.append(f"| {e.id} | {e.status} | {e.idea[:40]} | {e.theme[:14]} | {cost} | {dur} | "
                   f"{e.video_model or '-'} | {vir} | {pct} | {e.outcome or '-'} |")
    return "\n".join(out) + "\n"
