---
name: marketing-journal
description: >
  Use to inspect a channel's growth state — current phase (cold-start vs optimizing), the
  learned strategy/direction, the backlog, and every bet's outcome. Read-only observability.
  One lego-block of the growth loop; start here before ideating or reporting.
---

# marketing-journal — read the loop's state

Read-only. The first thing to run before any decision, so bets reflect the current direction.

## Do this

```bash
studio marketing journal --channel <name>     # phase + strategy + every bet's outcome table
studio marketing backlog --channel <name>     # the planned (queued) bets + explore/exploit mix
studio marketing recall "<query>" --channel <name>   # the past MEASURED bets most relevant to a query
```

What you'll see: the **phase** (`COLD START n/10` vs `OPTIMIZING`), the `Strategy`
(niche, current_direction, winning/losing patterns, next_seeds), and a table of every bet
(id · status · idea · virality · percentile · outcome).

## Under the hood
- Durable store: `runs/_marketing/<name>/journal.json` (machine) + `journal.md` (human render).
- Per-video measurement snapshots: `runs/<run_id>/08_stats.json`, `08_comments.json`.

## Memory touched
Read-only. To understand WHAT each field means and how it's written, read **marketing-memory**
/ [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
</content>
