"""T1 — the autonomous loop engine: decide what's DUE, given the clock.

The crux is **deferred measurement**: a published Short needs ~2-3 days before its metrics mean
anything, so the loop is a state machine over TIME, not a straight-line script. `plan()` is a
pure decision (no side effects, no network) — it inspects the journal + the current time and
returns a `Plan` telling the driver which one action to take next:

    measure  →  one or more videos have matured; fetch their stats
    learn    →  enough new measurements have accrued; reflect into strategy
    ideate   →  the backlog is running low; generate fresh bets
    produce  →  cadence allows another video; make the next backlog bet (budget-sized)
    idle     →  nothing due (waiting on maturation or the produce cadence)

The driver (`studio marketing autopilot`, or the `marketing-autopilot` skill, or a cron wrapper)
executes the action using the existing deterministic helpers + agent reasoning, then ticks again.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from studio.marketing import bandit
from studio.marketing import journal as jrnl


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _age_hours(ts: str, now: datetime) -> float:
    d = _parse(ts)
    if d is None:
        return 1e9
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return (now - d).total_seconds() / 3600.0


class Plan(BaseModel):
    now: str
    phase: str                              # cold-start | optimizing
    next: str = "idle"                      # measure | learn | ideate | produce | idle
    measure_due: list[str] = Field(default_factory=list)   # entry ids ready to measure
    learn: bool = False                     # enough new measurements to reflect
    produce_entry: str = ""                 # the bet to produce next
    produce_max_cost: float | None = None   # budget cap for that produce (None = budget unset)
    target_duration_s: int = 60
    note: str = ""                          # human-readable reason for `next`


def _pick_next(j: jrnl.Journal, planned: list, cfg) -> object:
    """Choose the next bet to produce. Bandit (T8) by default; `fifo` = first-in-queue.

    The bandit RNG is seeded from the journal state so repeated plan() calls in the SAME state
    agree (tick and autopilot pick the same bet); it re-randomizes as the journal grows.
    """
    if cfg.select != "bandit":
        return planned[0]
    seed = len(j.entries) * 1000 + len(j.measured())
    return bandit.pick(planned, j.measured(), cfg.prior_strength,
                       rng=random.Random(seed)) or planned[0]


def plan(j: jrnl.Journal, now: datetime | None = None) -> Plan:
    """Pure decision: what should the loop do next? No side effects, no network."""
    now = now or datetime.now(timezone.utc)
    cfg = j.loop
    phase = "cold-start" if j.in_cold_start else "optimizing"

    # 1) measurement — deployed videos past the maturation window, not yet measured
    measure_due = [
        e.id for e in j.entries
        if e.status == "deployed" and e.video_id and e.published_at
        and _age_hours(e.published_at, now) >= cfg.maturation_hours
    ]

    # 2) learn — count measurements newer than the last reflection
    new_measured = [
        e for e in j.measured()
        if not j.last_learn_at or (e.metrics and e.metrics.fetched_at > j.last_learn_at)
    ]
    learn = len(new_measured) >= cfg.learn_every

    # 3) produce / ideate cadence
    planned = [e for e in j.entries if e.status == "planned"]
    produced_24h = sum(1 for e in j.entries if e.published_at and _age_hours(e.published_at, now) < 24)
    last_deploy_age = min(
        (_age_hours(e.published_at, now) for e in j.entries if e.published_at), default=1e9
    )

    p = Plan(now=now.isoformat(timespec="seconds"), phase=phase, learn=learn,
             measure_due=measure_due, target_duration_s=cfg.target_duration_s)

    # priority: measure matured videos → reflect → keep the backlog full → produce → idle
    if measure_due:
        p.next, p.note = "measure", f"{len(measure_due)} video(s) matured (≥{cfg.maturation_hours:.0f}h)"
    elif learn:
        p.next, p.note = "learn", f"{len(new_measured)} new measured bets since last reflection"
    elif len(planned) < cfg.backlog_min:
        p.next, p.note = "ideate", f"backlog low ({len(planned)} < {cfg.backlog_min})"
    elif last_deploy_age >= cfg.min_hours_between_produces and produced_24h < cfg.daily_produce_cap:
        e = _pick_next(j, planned, cfg)
        p.next, p.produce_entry = "produce", e.id
        p.produce_max_cost = j.budget.cap_for(cfg.target_duration_s)
        p.note = f"produce next bet {e.id} ({cfg.select}): {e.idea[:46]}"
    elif produced_24h >= cfg.daily_produce_cap:
        p.note = f"idle — daily produce cap reached ({produced_24h}/{cfg.daily_produce_cap})"
    else:
        p.note = (f"idle — cadence: {last_deploy_age:.0f}h since last deploy "
                  f"(< {cfg.min_hours_between_produces:.0f}h)")
    return p
