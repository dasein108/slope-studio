"""Switchback: the only design that answers "is this worth running at all?".

Per-comment attribution does not exist — YouTube exposes no referrer that
distinguishes a subscriber who arrived via a comment. So causality has to come
from turning the whole system on and off and comparing.

4 days on / 2 days off. The 2:1 imbalance means the off-state baseline
accumulates at half the rate, so a readable answer takes roughly 8 weeks.

Expect a null. That is a real and useful answer, and this module is built to
report it honestly rather than to find an effect.
"""

from __future__ import annotations

import random
import sqlite3
import statistics
from datetime import date

ON_DAYS = 4
OFF_DAYS = 2
# At 4-on/2-off, 20 off-days takes ~60 calendar days to accumulate — matching
# the ~8-week horizon this module's own docstring already promises. It also
# keeps the plain percentile bootstrap's false-positive rate close to nominal:
# measured FP rate under a true null was 10.6% at 5/5, dropping toward ~5% as
# the per-arm sample size approaches 20. Below this, `readout` is more likely
# to call noise a real effect than to earn its own docstring's honesty claim.
MIN_DAYS_PER_ARM = 20


def state_for(day: date, start: date, on_days: int = ON_DAYS,
              off_days: int = OFF_DAYS) -> str:
    """Which arm a calendar day belongs to."""
    delta = (day - start).days
    if delta < 0:
        return "off"
    return "on" if (delta % (on_days + off_days)) < on_days else "off"


def record_day(conn: sqlite3.Connection, date_iso: str, subs_gained: int = 0,
               views: int = 0, channel_page_views: int = 0, comments_posted: int = 0,
               state: str = "off", published_video: bool = False) -> None:
    conn.execute(
        """INSERT INTO channel_daily (date, subs_gained, views, channel_page_views,
                                      comments_posted, switchback_state, published_video)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
             subs_gained = excluded.subs_gained,
             views = excluded.views,
             channel_page_views = excluded.channel_page_views,
             comments_posted = excluded.comments_posted,
             switchback_state = excluded.switchback_state,
             published_video = excluded.published_video""",
        (date_iso, subs_gained, views, channel_page_views, comments_posted,
         state, 1 if published_video else 0))
    conn.commit()


def _bootstrap_ci(on: list[float], off: list[float], iterations: int,
                  seed: int) -> tuple[float, float]:
    """Percentile bootstrap CI for the difference in means. Stdlib only."""
    rng = random.Random(seed)
    diffs = []
    for _ in range(iterations):
        a = statistics.fmean(rng.choices(on, k=len(on)))
        b = statistics.fmean(rng.choices(off, k=len(off)))
        diffs.append(a - b)
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]
    hi = diffs[int(0.975 * len(diffs)) - 1]
    return round(lo, 3), round(hi, 3)


def readout(conn: sqlite3.Connection, iterations: int = 2000, seed: int = 0) -> dict:
    """Compare subscriber gain on ON days vs OFF days, excluding publish days.

    `rollup.run` labels every day on/off purely from the calendar schedule — it has
    no way to know whether the loop actually ran that day (`experiment_start` may
    not have been wired into a given tick, or the loop may have been run manually).
    An OFF day with `comments_posted > 0` is contaminated: the arms are no longer
    comparable, and trusting the calendar label there would silently compare two
    "on" populations while reporting one of them as "off". Such days are excluded
    from the comparison and counted in `contaminated_days` instead.
    """
    rows = list(conn.execute(
        "SELECT switchback_state, subs_gained, comments_posted FROM channel_daily "
        "WHERE published_video = 0"))
    contaminated = sum(1 for r in rows
                       if r["switchback_state"] == "off" and r["comments_posted"] > 0)
    on = [float(r["subs_gained"]) for r in rows if r["switchback_state"] == "on"]
    off = [float(r["subs_gained"]) for r in rows
           if r["switchback_state"] == "off" and r["comments_posted"] == 0]

    result = {"on_days": len(on), "off_days": len(off), "on_mean": 0.0, "off_mean": 0.0,
              "lift": 0.0, "ci_low": 0.0, "ci_high": 0.0, "verdict": "insufficient_data",
              "contaminated_days": contaminated}
    if len(on) < MIN_DAYS_PER_ARM or len(off) < MIN_DAYS_PER_ARM:
        return result

    result["on_mean"] = round(statistics.fmean(on), 3)
    result["off_mean"] = round(statistics.fmean(off), 3)
    result["lift"] = round(result["on_mean"] - result["off_mean"], 3)
    lo, hi = _bootstrap_ci(on, off, iterations, seed)
    result["ci_low"], result["ci_high"] = lo, hi
    if lo > 0:
        result["verdict"] = "positive"
    elif hi < 0:
        result["verdict"] = "negative"
    else:
        result["verdict"] = "null"
    return result
