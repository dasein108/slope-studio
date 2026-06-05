---
name: marketing-report
description: >
  Use to write a full markdown growth brief for a channel (a measure + learn rollup) to disk.
  Run after a measurement cycle to snapshot the state for humans. One lego-block of the growth
  loop; read-mostly.
---

# marketing-report — write the growth brief

```bash
studio marketing report --channel <name> --provider <llm>
```
Writes `runs/_marketing/<name>/report.md` — the channel's phase, current direction,
winners/losers with their assumptions (held or refuted), and the next bets. Run it after
**marketing-measure** + **marketing-learn** so it reflects the latest cycle.

For a quick interactive read instead of a written file, use **marketing-journal**.

## Memory touched
Read-mostly (reads journal + strategy; with `--provider` may run a reflection pass first).
Full model: **marketing-memory** / [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
</content>
