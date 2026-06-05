---
name: marketing-ideate
description: >
  Use when deciding WHAT short video to make next for a channel — generate falsifiable
  viral bets (idea + hook + assumption + goal + theme). The AGENT does the ideation
  (web-search current trends + recall the channel's past winners), then persists each bet
  to the backlog. One lego-block of the ideate→deploy→measure→learn growth loop. Pairs with
  marketing-backlog (pick next) and marketing-memory (how state persists).
---

# marketing-ideate — generate the next bet(s)

Produce N **falsifiable** bets. Each bet is `idea` · `hook` (literal 0–3s scroll-stopper) ·
`assumption` (WHY it should go viral — must be falsifiable) · `goal` (measurable, e.g.
">P75 velocity") · `theme` · `tags`. You — the agent — do the thinking; the CLI only persists.

## Do this

1. **Read state** — phase + learned direction:
   ```bash
   studio marketing journal --channel <name>
   ```
2. **Gather live signal** (don't bet from stale memory): use `WebSearch` for trending
   formats/hooks/narratives/news pegs in the niche + what comparable channels are blowing up
   with this week.
3. **Recall what worked** here:
   ```bash
   studio marketing recall "<niche / current direction / candidate theme>" --channel <name>
   ```
4. **Reason the bets yourself:**
   - **Cold-start (<10 deployed):** maximize DIVERSITY — vary theme, hook style, emotion to map
     what this audience rewards.
   - **Optimizing (≥10):** lean into the recalled winning patterns, but make **≥1 exploration**
     bet into adjacent territory (the 40% — see marketing-backlog).
5. **Persist each** (no LLM, just I/O):
   ```bash
   studio marketing add "<idea>" --hook "<hook>" --assumption "<why>" --goal "<target>" \
     --theme "<theme>" --tags "a,b,c" --channel <name>      # add --exploit for an exploit bet
   ```

## Fallback (scripted, non-agent)
`studio marketing ideate --provider <llm> --signals <file> --niche "<niche>" --n 3` runs the
built-in LLM generator and writes the bets for you. Use only when you want a quick draft
without agent reasoning.

## Memory touched
Writes `planned` entries → the **backlog**. Reads `strategy` (long-term) + episodic recall.
Full model: **marketing-memory** skill / [`docs/50-marketing/memory.md`](../../../docs/50-marketing/memory.md).
</content>
