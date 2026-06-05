---
name: marketing-backlog
description: >
  Use when choosing which queued bet to produce next, or to review/curate a channel's
  backlog. Shows the planned (not-yet-deployed) bets and the explore/exploit balance; the
  AGENT picks the next one per the ~60/40 rule. One lego-block of the growth loop. Feeds
  marketing-deploy; fed by marketing-ideate.
---

# marketing-backlog — pick what to make next

The backlog = every journal entry with `status: planned`. This skill reviews it and chooses
the next bet to hand to **marketing-deploy**. The CLI lists; YOU decide.

## Do this

1. **See the queue + balance:**
   ```bash
   studio marketing backlog --channel <name>
   ```
   Prints each planned bet tagged `explore`/`exploit` and the current counts.
2. **Apply the 60/40 rule** across what actually gets PRODUCED:
   - ~**60% exploitation** (bets that lean on proven winning patterns), ~**40% exploration**
     (fresh themes to dig new niches).
   - **Cold-start (<10 deployed): everything is exploration** regardless of tags — you have no
     baseline yet.
3. **Choose** the bet that best advances `strategy.current_direction` while keeping the balance.
   Sanity-check it isn't a near-dupe of a past loser:
   ```bash
   studio marketing recall "<candidate idea/theme>" --channel <name>
   ```
4. **Hand off** the chosen `entry_id` + idea to **marketing-deploy**.

## Curating
Empty backlog → run **marketing-ideate** first. To prune stale/duplicate planned bets there is
no delete command yet (roadmap T2) — edit `runs/_marketing/<name>/journal.json` directly and
re-save, or just leave them unpicked.

## Memory touched
Reads `planned` entries; the 60/40 split is recorded per-entry as `explore: true/false`.
Full model: **marketing-memory** / [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
</content>
