#!/usr/bin/env python
"""Enforce the low-views prune rule for a channel: unlist any PUBLIC video that
is >= MIN_AGE_H old and has < MIN_VIEWS views. Uses the YouTube Data API for
current view counts (no maturation delay, unlike `marketing measure`).

Dry-run by default; pass --apply to actually unlist. Safe to run repeatedly.

    python scripts/prune_low_views.py --channel pilot-channel [--apply]
"""
from __future__ import annotations

import argparse

from studio.providers import analytics, publish as pub
from studio.marketing import journal as mj, score as mscore

MIN_VIEWS = 25
MIN_AGE_H = 24


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="pilot-channel")
    ap.add_argument("--apply", action="store_true", help="actually unlist (default: dry-run)")
    ap.add_argument("--min-views", type=int, default=MIN_VIEWS)
    ap.add_argument("--min-age-h", type=float, default=MIN_AGE_H)
    args = ap.parse_args()

    j = mj.load(args.channel)
    cands = [e for e in j.entries
             if e.video_id and not e.unlisted and not getattr(e, "deleted", False)]
    stats = analytics.video_stats(list({e.video_id for e in cands}), args.channel)

    hits = []
    for e in cands:
        s = stats.get(e.video_id)
        if not s:                      # not found / not owned — skip
            continue
        age_h = s["age_days"] * 24
        if age_h >= args.min_age_h and s["views"] < args.min_views:
            hits.append((e, s, age_h))

    if not hits:
        print("prune: nothing to unlist")
        return

    changed = False
    for e, s, age_h in hits:
        tag = f"{e.id} {e.video_id} ({s['views']}v, {age_h/24:.1f}d)"
        if not args.apply:
            print(f"prune[dry]: would unlist {tag}")
            continue
        try:
            pub.set_privacy(e.video_id, "unlisted", args.channel)
            e.unlisted = True
            changed = True
            print(f"prune: unlisted {tag}")
        except Exception as ex:        # 403 for videos owned by another channel, etc.
            print(f"prune: FAILED {tag}: {ex}")

    if changed:
        measured = j.measured()
        for x, p in zip(measured, mscore.relativize([x.virality for x in measured])):
            x.percentile = p
            x.outcome = mscore.outcome(p, j.in_cold_start)
        mj.save(j)
        print(f"prune: done, {sum(1 for e,_,_ in hits if e.unlisted)} unlisted, "
              f"stats recomputed over {len(measured)} public videos")


if __name__ == "__main__":
    main()
