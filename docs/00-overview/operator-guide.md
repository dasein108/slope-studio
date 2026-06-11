# Operator guide — run the whole studio with minimal effort

**Start here.** This is the one page that ties every skill + feature together and shows the
lowest-touch way to go from nothing → a channel that produces and self-optimizes Shorts.

You drive it by **talking to Claude Code** (it invokes the skills) or by running `studio`
commands directly. Two skills do everything:

| Skill | Owns | Say something like |
|-------|------|--------------------|
| **`film-maker`** | make + publish one video | *"produce a 60s Short about why octopuses are aliens and publish it to the pols channel"* |
| **`marketing-guru`** | decide WHAT to make + judge how viral it was (the growth loop) | *"run the growth loop for the pols channel"* / *"what should we make next?"* / *"how did our last videos do?"* |

---

## 0. What's automated vs. what needs you

| Automated (zero/low touch) | Needs a human (once or rarely) |
|---|---|
| Script → visuals → narrate → clips → stitch → voice → save (the 7 stages) | One-time Google OAuth setup (`client_secret.json`) — ~20 min, once |
| SEO title/description/tags (metadata stage) | Channel art + avatar upload in YouTube Studio — ~3 min, once (API can't set avatar) |
| Publishing to YouTube | Putting API keys in `.env` (optional — free path works without) |
| Idea generation + hooks + assumptions (marketing-guru `ideate`) | Approving spend tier / `--max-cost` (or accept the $0 free path) |
| Trend/narrative web research (the skill does it) | Waiting 48–72h before judging a video (just calendar time) |
| Virality scoring + learning + next-idea steering | TikTok: a 2–4 week app audit before public auto-publish (YouTube has none) |

**Bottom line:** after a ~30-minute one-time setup, a full cycle (idea → published →
measured → next idea) needs only a few minutes of your attention per batch, plus waiting.

---

## 1. One-time setup (~30 min, once)

```bash
cd /Users/dasein/dev/slope-studio
uv venv && source .venv/bin/activate
uv pip install -e ".[fal,youtube]"     # fal = AI images/video; youtube = publishing
cp .env.example .env                    # fill keys you have (ALL optional — see below)
command -v ffmpeg ffprobe              # must be on PATH
```

**Keys (`.env`) — all optional, better quality if present:**
- `FAL_KEY` → Nano Banana images + AI video (without it: free stub images + Ken-Burns motion)
- `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` … → better scripts, metadata, ideation, learning (without: deterministic fallbacks)
- The pipeline runs **fully offline with no keys** (degraded quality) — see the free path below.

**YouTube publishing (do once per Google project):** follow
[`../40-publishing/youtube.md`](../40-publishing/youtube.md) — enable YouTube Data API v3,
make a Desktop OAuth client, save `client_secret.json` in the repo root. Then authorize +
confirm the channel:

```bash
studio yt-channel --channel pols       # opens browser once → token_pols.json; prints the channel name
```

**Channel branding (manual, ~3 min, once):** upload avatar + banner in YouTube Studio per
`brand/<channel>/about.md` (the avatar **cannot** be set via API).

**Optional — unlock retention analytics (one re-auth):** add the `yt-analytics.readonly`
scope and re-auth per
[`../../.claude/skills/marketing-guru/references/analytics.md`](../../.claude/skills/marketing-guru/references/analytics.md).
Skippable — the growth loop runs without it.

---

## 2. Make one video (hands-off)

Ask Claude: *"produce a 60s Short about <idea> and publish it public to the pols channel."*
It runs the `film-maker` skill, which is:

```bash
studio run "<idea>" --duration 60 --tier cheap \
  --publish-to youtube --privacy public --channel pols
```

- `--tier free` = $0, fully offline draft. `cheap` ≈ $0.59/150s (real stills + free motion).
  `balanced`/`premium` spend more on AI video. **`--max-cost N`** (default $3) hard-caps spend.
- Drop `--publish-to youtube` to keep it local (`runs/<id>/06_final.mp4`) and review first.
- `studio status <id>` shows every stage, provider, and cost.

Full per-stage control, cost knobs, and troubleshooting live in the **`film-maker`** skill.

---

## 3. Grow the channel (the low-touch loop)

This is the point: **don't hand-pick ideas forever.** Let `marketing-guru` run the loop.

```
ideate → deploy → measure → learn → ideate …
```

Ask Claude: *"run the growth loop for the pols channel"* and it will, per cycle:

1. **ideate** — web-search current trends/narratives, then generate ideas + hooks +
   assumptions into the journal:
   ```bash
   studio marketing ideate --channel pols --provider gpt-4o-mini --signals /tmp/signals.md --n 3
   ```
2. **deploy** — produce + publish each via `film-maker`, then link it to its bet:
   ```bash
   studio marketing link j0001 <run-id> --channel pols
   ```
3. **measure** (after 48–72h) — stats + comments → virality ranked against your own channel,
   plus age-bucket snapshots so 1d / 3d / 7d / 14d / 30d videos compare fairly:
   ```bash
   studio marketing measure --channel pols
   studio marketing snapshots --channel pols --buckets 1,3,7,14,30
   ```
4. **analyze + learn** — find hidden relations across effects, cost, theme, music, sound, and
   animation; then confirm/refute each assumption and update strategy + next ideas:
   ```bash
   studio marketing insights --channel pols --json
   studio marketing slice --channel pols --bucket 7d \
     --group-by theme,effects,animators,music_provider,sfx_provider --metric virality
   studio marketing learn --channel pols --provider gpt-4o-mini
   studio marketing journal --channel pols     # see phase, winners, direction
   ```

**Cold start:** the first **10 videos are diverse exploration** (no relative verdict yet —
there's no baseline). After 10, the loop ranks winners vs losers and steers toward what
goes viral *for this channel*. The journal (`runs/_marketing/<channel>/journal.json`)
tracks the phase automatically.

---

## 4. Minimal-care cadence

A realistic low-touch rhythm once set up:

| When | You do | Time |
|------|--------|------|
| Day 0 | *"ideate + deploy a batch for pols"* → approve tier/cost | ~5 min |
| +2–3 days | *"measure + learn for pols"* → read the journal | ~5 min |
| Repeat | *"run the next growth cycle"* | ~5 min/batch |

Bootstrap = ~10 videos to leave cold start; after that each cycle compounds. The only
unavoidable wait is letting watch-time accrue before measuring (see the loop reference on
cadence).

---

## 5. The $0 path (no keys, no spend, for wiring/drafts)

```bash
studio run "topic" --duration 12 --tier free      # offline stub script/images, ken-burns, edge-tts
```
Produces a real (lower-quality) MP4 with no API keys and no network except free edge-tts.
Use it to learn the flow before spending a cent.

---

## 6. Guardrails & gotchas (read once)

- **AI video is per-second** (kling $0.07/s → 150s ≈ $10.50). Always `studio estimate <id>`
  before stage 3; `--max-cost` aborts/trims before spending. Cheapest real path: `cheap`
  tier (free Ken-Burns motion on real stills).
- **TikTok auto-publish is private-only** until a 2–4 week app audit. YouTube has no such
  gate — it's the default. (`docs/40-publishing/youtube.md`.)
- **Don't measure too early** — a video <48h old has noisy velocity; verdicts are unreliable.
- **Secrets & raw media never go to git** — `.env`, `client_secret*.json`, `token*.json`,
  `runs/` (incl. the journal), and all media files are gitignored. Only code, docs,
  instructions, and skills are committed.
- Full troubleshooting tables: the `film-maker` skill §6.

---

## Where to go deeper

- Produce/debug a video → **`film-maker`** skill (`.claude/skills/film-maker/SKILL.md`)
- Grow/analyze a channel → **`marketing-guru`** skill + [`../50-marketing/`](../50-marketing/)
- Pipeline data-flow → [`pipeline-stages.md`](pipeline-stages.md)
- Cost/tiers → [`../10-architecture/cost-model.md`](../10-architecture/cost-model.md) (tier table in the repo-root `CLAUDE.md`)
- Publishing setup → [`../40-publishing/youtube.md`](../40-publishing/youtube.md)
