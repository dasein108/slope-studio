---
name: marketing-deploy
description: >
  Use to produce + publish a chosen backlog bet and bind it to the journal so it can be
  measured later. Calls the film-maker skill to render+upload, sized to the per-video budget,
  then links the run. One lego-block of the growth loop. Fed by the backlog pick (marketing-guru);
  precedes marketing-measure-learn (after a maturation wait).
---

# marketing-deploy — produce, publish, link

Turn one chosen bet (`entry_id` + idea, from the backlog pick in marketing-guru) into a
published Short bound to its journal entry.

## Do this

1. **Get the spend cap** from the channel budget (set once via
   `studio marketing budget --channel <name> --per-video 0.60` or `--per-minute 0.40`):
   ```bash
   CAP=$(studio marketing budget --channel <name> --for-duration <duration_s>)
   ```
   `--for-duration` returns the per-video `--max-cost` (flat for per-video budgets; rate × length
   for per-minute). If it prints `(budget unset)`, set the budget first or pass `--max-cost` by hand.
2. **Produce + publish** via the **film-maker** skill (it owns the pipeline):
   ```bash
   studio estimate <run_id>            # if iterating an existing run, price stage 3 first
   studio run "<idea>" --duration 60 --tier <cheap|balanced> --max-cost $CAP \
     --publish-to youtube --privacy public --channel <name>
   ```
   `--tier cheap` ≈ stills + free motion; `balanced` spends `--max-cost` on AI clips for hero
   scenes. `--max-cost` is the **whole-video** cap (images + clips + music): `run` reserves the
   music bed and auto-downgrades paid fal music to synth if it won't fit, so total spend stays ≤ cap.
   Stage 3 aborts pre-flight if the clip estimate exceeds what's left. Cheapest "still alive"
   recipe ≈ $0.41 (free `motion-*` + one ≤6s ltx hook + free `local` music); see
   `docs/10-architecture/cost-model.md` for the ladder.
3. **Link** the run to the bet (so measure can find the video):
   ```bash
   studio marketing link <entry_id> <run_id> --channel <name>
   ```
   Pulls the YouTube id from `runs/<run_id>/07_publish.json`; sets `status: deployed`.
4. **Wait** before measuring — give the Short **48–72h+** to accrue watch time.

## Notes
- `link` also captures **production telemetry** — cost, duration, animators/fx/model, and
  per-stage providers — from the run manifest into the bet (T3), so `learn` can attribute
  success to the effects used and you can track spend per bet.
- Repeat backlog→deploy until ~10 videos are live to exit cold-start.

Writes `run_id`, `video_id`, `video_url`, `status: deployed`, plus telemetry
(`cost_usd`, `duration_s`, `tier`, `video_model`, `animators`, `effects`, `providers`,
`n_scenes`) onto the entry. Memory model: [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
