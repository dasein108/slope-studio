---
name: marketing-deploy
description: >
  Use to produce + publish a chosen backlog bet and bind it to the journal so it can be
  measured later. Calls the film-maker skill to render+upload, sized to the per-video budget,
  then links the run. One lego-block of the growth loop. Fed by marketing-backlog; precedes
  marketing-measure (after a maturation wait).
---

# marketing-deploy — produce, publish, link

Turn one chosen bet (`entry_id` + idea, from marketing-backlog) into a published Short bound
to its journal entry.

## Do this

1. **Produce + publish** via the **film-maker** skill (it owns the pipeline). Size the budget
   to your **average budget per video**:
   ```bash
   studio estimate <run_id>            # if iterating an existing run, price stage 3 first
   studio run "<idea>" --duration 60 --tier <cheap|balanced> --max-cost <avg $/video> \
     --publish-to youtube --privacy public --channel <name>
   ```
   `--tier cheap` ≈ stills + free motion; `balanced` spends `--max-cost` on AI clips for hero
   scenes. Stage 3 aborts pre-flight if the estimate exceeds `--max-cost`.
2. **Link** the run to the bet (so measure can find the video):
   ```bash
   studio marketing link <entry_id> <run_id> --channel <name>
   ```
   Pulls the YouTube id from `runs/<run_id>/07_publish.json`; sets `status: deployed`.
3. **Wait** before measuring — give the Short **48–72h+** to accrue watch time.

## Notes
- Today `link` captures `run_id`/`video_id` only. Capturing per-video **cost · duration ·
  animators/fx/model** into the entry (for budget tracking + effect attribution) is roadmap
  **T3** — until then read those from `runs/<run_id>/project.json` if needed.
- Repeat backlog→deploy until ~10 videos are live to exit cold-start.

## Memory touched
Writes `run_id`, `video_id`, `video_url`, `status: deployed` onto the entry.
Full model: **marketing-memory** / [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
</content>
