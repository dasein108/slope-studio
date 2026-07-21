"""Effectiveness reporting.

The daily loop optimizes what is fast and measurable — likes, replies, survival
by style tag. The switchback section is the honest check on whether any of that
translates into subscribers.
"""

from __future__ import annotations

import sqlite3

from studio.guerrilla import experiment, track

LATEST_METRIC = """
SELECT m.* FROM comment_metrics m
JOIN (SELECT comment_id, MAX(checked_at) AS latest
      FROM comment_metrics GROUP BY comment_id) l
  ON l.comment_id = m.comment_id AND l.latest = m.checked_at
"""


def by_style(conn: sqlite3.Connection) -> list[dict]:
    """Per-style-tag averages, best first. This is what steers composition."""
    rows = list(conn.execute(f"""
        SELECT c.style_tag AS style_tag,
               COUNT(*) AS n,
               AVG(m.likes) AS mean_likes,
               AVG(m.replies) AS mean_replies,
               AVG(CASE WHEN m.status = 'live' THEN 1.0 ELSE 0.0 END) AS survival
        FROM comments c JOIN ({LATEST_METRIC}) m ON m.comment_id = c.comment_id
        GROUP BY c.style_tag"""))
    out = [{"style_tag": r["style_tag"], "n": r["n"],
            "mean_likes": round(r["mean_likes"] or 0.0, 2),
            "mean_replies": round(r["mean_replies"] or 0.0, 2),
            "survival": round(r["survival"] or 0.0, 3)} for r in rows]
    out.sort(key=lambda d: (d["mean_likes"], d["mean_replies"]), reverse=True)
    return out


def skip_breakdown(conn: sqlite3.Connection) -> list[dict]:
    """Why candidates were rejected. Rising counts mean the gates need tuning."""
    rows = list(conn.execute(
        """SELECT skip_reason AS reason, COUNT(*) AS n FROM videos
           WHERE decision LIKE 'skipped%' AND skip_reason != ''
           GROUP BY skip_reason ORDER BY n DESC"""))
    return [{"reason": r["reason"], "n": r["n"]} for r in rows]


def render(conn: sqlite3.Connection) -> str:
    lines = ["# Guerrilla Marketing Report", ""]

    posted = conn.execute("SELECT COUNT(*) c FROM comments").fetchone()["c"]
    seen = conn.execute("SELECT COUNT(*) c FROM videos").fetchone()["c"]
    tracked = conn.execute("SELECT COUNT(*) c FROM comment_metrics").fetchone()["c"]
    # `track.survival_rate` returns 1.0 on an empty database by contract (its
    # callers, like the circuit breaker, need "no evidence of a problem" rather
    # than a crash). Printing that as "100.0%" here would read as "the channel
    # is safe" to the operator when really nothing has been checked yet.
    survival_line = (f"{track.survival_rate(conn):.1%}" if tracked
                     else "n/a (no tracked comments)")
    lines += [f"Comments posted: **{posted}** across **{seen}** candidate videos seen.",
              f"Comment survival rate: **{survival_line}**", ""]

    breaker = track.breaker_status(conn)
    if breaker["tripped"]:
        lines += [f"**Circuit breaker: TRIPPED** at {breaker['tripped_at']} "
                  f"(survival was {breaker['rate_at_trip']:.0%}) — run `guerrilla resume` "
                  "only after investigating a possible shadowban.", ""]

    lines += ["## By style tag", ""]
    styles = by_style(conn)
    if styles:
        lines += ["| style | n | mean likes | mean replies | survival |",
                  "|---|---|---|---|---|"]
        lines += [f"| {s['style_tag']} | {s['n']} | {s['mean_likes']} | "
                  f"{s['mean_replies']} | {s['survival']:.0%} |" for s in styles]
    else:
        lines.append("_no tracked comments yet_")
    lines.append("")

    lines += ["## Why videos were skipped", ""]
    skips = skip_breakdown(conn)
    if skips:
        lines += ["| reason | count |", "|---|---|"]
        lines += [f"| {s['reason']} | {s['n']} |" for s in skips]
    else:
        lines.append("_no skips recorded yet_")
    lines.append("")

    r = experiment.readout(conn)
    lines += ["## Switchback readout", "",
              f"- verdict: **{r['verdict']}**",
              f"- ON days: {r['on_days']} (mean {r['on_mean']} subs/day)",
              f"- OFF days: {r['off_days']} (mean {r['off_mean']} subs/day)",
              f"- lift: {r['lift']} subs/day (95% CI {r['ci_low']} to {r['ci_high']})", ""]
    if r.get("contaminated_days"):
        lines.append(
            f"**Warning:** {r['contaminated_days']} OFF day(s) had comments posted anyway "
            "— excluded from the comparison above. Treat this readout as unreliable until "
            "the switchback gating that stops OFF-day ticks is fixed.")
        lines.append("")
    if r["verdict"] == "null":
        lines.append("A null verdict means the comment activity has no detectable effect "
                     "on subscriber gain. That is a legitimate result — consider stopping.")
    return "\n".join(lines) + "\n"
