# Guerrilla Marketing — Targeted Commenting for Indirect Reach

`studio guerrilla` is an autonomous pipeline that posts a small, capped number of on-topic
comments per day under **other creators'** recent videos in a niche adjacent to your channel.
It never mentions your channel, asks for a subscribe, or drops a link. The entire mechanism of
action is indirect: a stranger reads a comment interesting enough to react to, wonders who
wrote it, clicks the commenter's name, and lands on your channel.

> **This is gray-hat.** Automated commenting is spam under YouTube's policy, and comments
> posted via the Data API carry the OAuth client id, so they are attributable back to the
> account that posted them. The design accepts that risk and spends most of its complexity
> on reducing it — rate discipline, content rails, and a circuit breaker that watches for a
> shadowban. Read [`architecture.md`](architecture.md) before running this against a channel
> you care about.

## The idea in one paragraph

A comment's only leverage is curiosity. `compose` grounds every generated comment in a real,
verbatim moment from the target video's transcript — a specific quote, not a paraphrase of the
title — so it reads as one specific person reacting to one specific thing, not a template.
`critic` scores each candidate against disqualifying criteria (no self-promotion, nothing
offensive, every factual claim grounded in the transcript) before it can post. `rails` then
re-checks the same ground truth in code — a deny-list, near-duplicate detection, posting-rate
limits — because prompts are advisory and code is not. `post` is the only module that writes
to YouTube, so there is exactly one chokepoint to audit for ban risk. `track` re-reads posted
comments on a schedule and trips a circuit breaker if too many quietly vanish, which is what a
shadowban looks like from the outside.

## The pipeline

One **tick** runs this sequence, in this order, for cost reasons explained in
[`architecture.md`](architecture.md#pipeline-order-is-a-cost-contract):

```
discover → rank → transcript → topic → highlight → compose → critic → rails → post
```

| Stage | Module | Does |
|---|---|---|
| discover | `discover.py` | poll watchlist channels' uploads playlists for new videos |
| rank | `rank.py` | hard gates (age, comment count, channel size, cooldown) + sort |
| transcript | `transcript.py` | fetch + cache the video's captions; no captions = free skip |
| topic | `topic.py` | classify the video's subject; skip if genuinely unclear |
| highlight | `highlight.py` | find the single most comment-worthy verbatim moment |
| compose | `compose.py` | generate 3+ comment variants reacting to that moment |
| critic | `critic.py` | score every variant; disqualify self-promo / offense / fabrication |
| rails | `rails.py` | pure ban-defense predicates — deny-list, spacing, duplicates, timing |
| post | `post.py` | the only module that calls `commentThreads.insert` |

Two more modules run on a separate schedule, not inside the tick:

| Module | Does |
|---|---|
| `track.py` | re-reads posted comments' survival (live/deleted/held); the circuit breaker |
| `experiment.py` / `rollup.py` | a switchback experiment (4 days on / 2 off) that answers whether this is worth running at all |

## How it fits the marketing docs

The rest of [`50-marketing/`](../README.md) covers the **`marketing-guru`** loop — ideate,
produce, publish, measure, learn — which is about *what video to make next*. Guerrilla
marketing is a different, narrower loop: it doesn't make anything, it only spends a small daily
comment budget trying to pull readers toward videos that already exist. The two share nothing
except the OAuth credentials helper in `studio/providers/publish.py` — guerrilla has its own
SQLite store (`runs/_guerrilla/<channel>/guerrilla.db`) rather than the marketing loop's JSON
journal, because every question this system asks ("which style tag earns likes?", "which
channel tier converts?") is a `GROUP BY`.

## Where to go next

- [`architecture.md`](architecture.md) — every module, the gates and rails, the data model,
  the circuit breaker, the switchback experiment design.
- [`operations.md`](operations.md) — running it: the full `guerrilla` CLI (`tick` / `track` /
  `report` / `queue` / `approve` / `resume` / `rollup` / `watchlist`), setting up an autonomous
  cron, tuning the age window and daily cap, reading the effectiveness report, and the honest
  content-quality ceiling.
- [`deploy.md`](deploy.md) — deploying the pipeline to a remote VPS via the provided Makefile,
  for when the machine you develop on can't reach YouTube reliably enough to run this live.

## Status

Implemented and gated behind manual review at every stage: a `--dry-run` tick prints every
comment it would have posted without posting anything, and the human-in-the-loop `queue` /
`approve` path lets an operator hand-pick from borderline candidates instead of trusting
auto-post. Treat both as required reading before pointing this at a channel that matters to
you.
