# Trends, narratives & hot themes — feeding live signal into ideation

The CLI has no internet; **you (the skill) are the research layer**. Before `ideate`,
gather current signal with your `WebSearch` tool (and Context7 for any platform/API
mechanics), distill it to a short bullet file, and pass it via `--signals`.

## What to search for

Tailor to the channel's niche (read it from the journal `strategy.niche` or the brand
kit in `brand/<channel>/about.md`). For the POLS channels (unusual knowledge: science,
mystery, cosmos), good queries:
- `trending youtube shorts <niche> this week`
- `viral tiktok <niche> hooks 2026`
- `<niche> news hook OR "did you know"` — fresh facts with a built-in narrative
- `most viewed shorts <topic>` — reverse-engineer the hook archetype
- seasonal / news pegs: anniversaries, discoveries, releases, anything with built-in search demand

## What makes a signal useful

Capture the **why it spread**, not just the topic:
- the **hook archetype** (question, bold claim, countdown, "you were lied to", visual shock),
- the **emotion** (awe, fear, curiosity, outrage, satisfaction),
- the **format** (single-fact reveal, list, story arc, myth-bust),
- any **timely peg** that gives it search/recommendation tailwind right now.

## Turn it into a signals file

Write `/tmp/signals.md` (or anywhere) as terse bullets — `ideate` passes it to the LLM
verbatim (capped ~3k chars):

```
- "X explained in 30s" myth-bust format trending in science shorts; hook = bold wrong belief stated first
- cosmic-horror framing ("space is worse than you think") spiking; emotion = awe+dread
- anniversary peg: <event> this month → built-in search demand
- countdown hooks ("5 things... #1 will...") still high CTR in this niche
```

Then:
```bash
studio marketing ideate --channel <name> --signals /tmp/signals.md \
  --provider gpt-4o-mini --n 3
```

## Closing the loop with trends

After a few cycles, cross-check the trends you bet on against the journal's
`winning_patterns`. If a trend type keeps losing for *this* audience, stop feeding it —
the channel's own measured history outranks generic "what's trending" every time.
