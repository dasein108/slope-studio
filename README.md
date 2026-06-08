# Slope Studio

![Slope Studio — automated AI short-video studio](assets/cover.png)

> 📖 **Read the build story:** [**Zero to Autopilot — Part 1: I Built an AI That Runs a YouTube Channel**](https://dev.to/dasein108/zero-to-autopilot-part-1-i-built-an-ai-that-runs-a-youtube-channel-the-landscape-and-my-10-1ki6)
> — a 7-part series building this repo from scratch: the cost collapse ($10 → $0.06/video), free ffmpeg effects, the memory layer, the explore/exploit bandit, and full autonomy.

Automated short-video studio: **idea → published Short**. Faceless MVP, balanced tier, YouTube-first, plain Python CLI.

Each of the 7 stages is an independent `studio` subcommand; `studio run` chains them with resume. Every paid stage has a **free fallback**, so the full pipeline runs end-to-end with **zero API keys** (degraded quality), then you swap real providers in via `--provider`.

**▶ Want the hands-off, minimal-effort way to run everything?** Read the
[operator guide](docs/00-overview/operator-guide.md) — every skill + feature, and the
exact human steps, in one page.

**🎬 Effects gallery (live):** [**dasein108.github.io/slope-studio**](https://dasein108.github.io/slope-studio/) —
every free animator, atmosphere overlay, FX look, and transition, playing in one page.
All motion is generated from a single still in ffmpeg, at **$0** per effect.

Full research + architecture: see [`docs/`](docs/) (start at [`docs/README.md`](docs/README.md)).

## 🤖 Agent-native workflow

Slope Studio isn't just a CLI for humans — it ships **Claude Code skills** (`.claude/skills/`) so an AI agent can operate the whole studio: pick what to make, render it, publish it, then measure how it did and learn. The marketing loop described below lives in those skills; the agent drives the same `studio` commands you would, but decides *what* and *when* on its own.

| Skill | What the agent does with it |
|-------|------------------------------|
| `film-maker` | Produce / render / debug / publish a Short from an idea — drives the `studio` CLI end-to-end (providers, cost control, artifact inspection, troubleshooting). |
| `marketing-guru` | Run the whole ideate→deploy→measure→learn cycle, or read channel state / pick the next bet / write a growth brief. Composes the lego-block skills below. |
| `marketing-ideate` | Decide *what* to make next — generate falsifiable viral bets (web-search current trends + recall the channel's past winners), persist to the backlog. |
| `marketing-deploy` | Produce + publish a chosen bet (sized to budget) and bind the run to the journal so it can be measured later. |
| `marketing-measure-learn` | 48–72h after publishing, score each bet's virality vs the channel's own portfolio, then reflect on which assumptions held → update strategy + seeds. |
| `marketing-autopilot` | Hands-off scheduled driver — each tick does the one action the loop says is due, handling the measurement-maturation wait with no operator in the seat. |
| `youtube-branding` | Generate a full brand kit (banner, avatar, transparent watermark logo, keywords, description) from a channel name + slogan + niche. |

**The demo moment:** open this repo in [Claude Code](https://claude.com/claude-code) and say *"produce and publish a short about why octopuses are basically aliens"* — the agent scripts it, renders the visuals + voice, stitches, and uploads to YouTube.

## Install

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[fal]"        # add ,youtube for publishing
cp .env.example .env              # fill FAL_KEY etc (all optional)
```
Requires `ffmpeg` + `ffprobe` on PATH.

## Quickstart (free path, no keys)

```bash
# full pipeline, offline stub script + pollinations + ken-burns + edge-tts
studio run "why octopuses are basically aliens" --duration 30 \
  --script-provider stub --image-provider pollinations \
  --video-provider kenburns --voice-provider edge
```

## Pick a tier (the cost knob)

`--tier` sets all providers + video strategy; `--max-cost` (default $3) caps spend.
AI video is billed **per second** — run `studio estimate <id>` before stage 3.

```bash
studio estimate <run-id> --budget 3                 # preview video cost per model

# cheap: FLUX-schnell stills (all scenes) + free Ken-Burns motion (~$0.15 / 150s)
studio run "the chemistry of humor" --duration 150 --tier cheap

# balanced: stills + SMART AI video filling the budget on the best scenes
studio run "the chemistry of humor" --duration 150 --tier balanced --video-model ltx --max-cost 3

# premium: AI on every scene (uncap with --max-cost 0)
studio run "topic" --duration 60 --tier premium --max-cost 0
```

| tier | images | video | ~cost / 150s |
|------|--------|-------|--------------|
| free | offline stub | kenburns | $0 |
| cheap | FLUX schnell (all) | kenburns (pan/zoom) | ~$0.15 |
| balanced | Nano Banana hero + FLUX bg | **auto** AI within `--max-cost` | = max-cost |
| premium | Nano Banana hero + FLUX bg | AI every scene | $6–10+ |

> Images: `cheap` = all FLUX schnell (~$0.006/img). `balanced`/`premium` use Nano Banana for hero/character scenes and FLUX schnell for `image_role:bg` backgrounds.

Video `--strategy`: `kenburns` · `all` · `hybrid` (`--ai-scenes 1,7,15`) · `auto` (smart fill).

## Per-stage (decomposed)

```bash
RID=$(studio init "octopuses are aliens" --duration 150)
studio script  $RID
studio visuals $RID --provider fal-nanobanana
studio clips   $RID --provider fal-i2v --model kling
studio stitch  $RID --transition fade
studio voice   $RID --provider edge --captions burn
studio save    $RID
studio publish $RID --target youtube --privacy public
studio status  $RID
```

Artifacts live in `runs/<id>/` (see [`docs/00-overview/pipeline-stages.md`](docs/00-overview/pipeline-stages.md)). Stages are idempotent: re-running skips existing output (use `--force` on visuals/clips to regenerate).

## Providers

| Stage | Options | Free fallback |
|-------|---------|---------------|
| script | openai · gemini · groq · openrouter · ollama · **stub** | stub (offline) |
| visuals | **fal-nanobanana** ($0.039/img) · pollinations · **stub** | stub (offline) |
| clips | strategy: kenburns(free) · auto · hybrid · all; model: ltx · **kling** · wan · hailuo · seedance | kenburns |
| voice | openai-tts · **edge** | edge |
| publish | youtube · tiktok (stub: audit-gated) | — |

**Cost reality:** AI video is per-second (kling $0.07/s → 150s ≈ $10.50; ltx ≈ $6).
No hosted AI-video model fits $2–3 for 150s — use `kenburns` (free) or `auto`/`hybrid`
to animate only hero scenes within budget. See `docs/10-architecture/cost-model.md`.

## Grow the channel (viral loop)

Producing a Short is half the job; growing a channel is the other half. The
**`marketing-guru`** workflow runs a closed feedback loop — **ideate → deploy → measure
→ learn** — backed by a per-channel journal, so each video is a falsifiable bet and the
next idea is steered by what actually went viral *for your channel*.

```bash
studio marketing ideate  --channel pols --provider gpt-4o-mini --n 3   # record viral bets
#   → deploy each with: studio run "<idea>" --publish-to youtube --channel pols
studio marketing link    j0001 <run-id> --channel pols                 # bind run → bet
studio marketing measure --channel pols                                # virality vs portfolio
studio marketing learn   --channel pols --provider gpt-4o-mini         # update strategy
studio marketing journal --channel pols                                # see the ledger
```

First **10 videos are exploration** (no baseline yet); after that the loop ranks winners
vs losers and exploits. Stats/comments use the readonly scope publishing already grants;
retention is best-effort (one optional re-auth). Full guide:
[`docs/50-marketing/`](docs/50-marketing/) + the `marketing-guru` skill.

## Effects gallery (build & deploy)

The [live gallery](https://dasein108.github.io/slope-studio/) is a single static page
(`index.html`) auto-built from the rendered demo clips in `examples/out/`, served from the
`gh-pages` branch. To regenerate after changing or adding an effect:

```bash
# 1. (re)render the demo clips into examples/out/  (gitignored)
python examples/make_examples.py                 # all effects
python examples/make_examples.py <effect> --frames   # just one

# 2. rebuild index.html + deploy to GitHub Pages
make gallery            # uses existing clips; recompresses heavy ones; pushes gh-pages
#   make gallery-render  # re-render ALL effects first, then deploy (slow)
#   make gallery-open    # open the live site
```

`make gallery` runs `scripts/deploy_gallery.sh`: it rebuilds `index.html`
(`examples/build_index.py`), recompresses any clip > 4 MB to web-friendly 720p H.264, and
publishes `index.html` + `examples/out/*.mp4` to `gh-pages` via a throwaway git worktree —
so `main` and your working tree are never touched. The demo media stays **out** of `main`
(it's gitignored and regenerable); only the `gh-pages` deploy branch carries it.

## Full CLI reference

Everything is one `studio` Typer app. `studio --help` (or `studio <cmd> --help`) lists flags.

**Pipeline stages** (run a single stage, or chain them with `run`):

| Command | What it does |
|---------|--------------|
| `studio init "<idea>" --duration N --aspect 9:16` | create a run, print its `<id>` |
| `studio script <id>` | idea → `01_script.json` (timed scenes + narration) |
| `studio visuals <id> [--provider …] [--force]` | scenes → `02_visuals/scene_NN.png` |
| `studio narrate <id> [--voice …]` | per-scene TTS → `05_voice/scenes/*.mp3` + `timing.json` + `captions.srt` |
| `studio clips <id> [--strategy …] [--model …] [--max-cost N]` | stills → `03_clips/scene_NN.mp4` (animate) |
| `studio stitch <id> [--transition …]` | clips → `04_stitched.mp4` |
| `studio audio <id>` | optional SFX + music bed |
| `studio voice <id> [--captions burn]` | narration + music → `05_voice/final.mp4` |
| `studio save <id>` | → `06_final.mp4` master + `06_final.json` |
| `studio metadata <id>` | SEO-polish title/description/tags |
| `studio thumbnail <id>` | generate `06_thumb.png` |
| `studio publish <id> --target youtube --privacy public` | upload (tiktok audit-gated) |

**Orchestrate & observe:**

| Command | What it does |
|---------|--------------|
| `studio run "<idea>" --duration N --tier T --max-cost C` | chain every stage idea → published |
| `studio estimate <id> --budget C` | preview AI-video cost per model **before** spending |
| `studio status <id>` | render the manifest (per-stage provider, cost, done-flag) |
| `studio yt-channel` | YouTube channel OAuth / info |
| `studio brand <spec.json>` | generate a brand kit (banner, avatar, watermark, keywords, description) → `runs/_brand/<slug>/` |

**Marketing / growth loop** (`studio marketing <cmd> --channel <name>`):

| Command | What it does |
|---------|--------------|
| `ideate [--n 3] [--provider …]` | generate falsifiable viral bets → backlog |
| `add` | manually add a bet to the backlog |
| `backlog` | list planned bets (and the bandit's pick) |
| `recall "<query>"` | episodic recall — past bets relevant to a query |
| `strategy` | view the learned long-term strategy |
| `budget [--per-video N \| --per-minute N]` | set the spend cap that sizes each render |
| `bandit` | show the Thompson-sampling ranking of planned bets |
| `link <bet-id> <run-id>` | bind a produced run → its bet (so it can be measured) |
| `measure` | fetch stats + comments, score virality vs portfolio |
| `learn [--provider …]` | reflect on measured bets → update strategy + seeds |
| `journal` | print the per-channel ledger |
| `report` | growth brief |
| `tick` | run the **one** action the loop engine says is due (cron-friendly) |
| `autopilot` | run the loop for a session (handles the 48–72h measurement wait) |

**Make targets** (dev/ops helpers):

| Target | What it does |
|--------|--------------|
| `make gallery` | deploy the effects gallery to GitHub Pages |
| `make gallery-render` | re-render all effect demos, then deploy |
| `make lint` | `ruff check studio/` |

## Status & roadmap

MVP = faceless scene videos. Follow-ups tracked: avatar narrator, mixed avatar+B-roll, RunPod self-host cost pilot, commercial TTS, TikTok audit. See [`docs/20-research/open-questions.md`](docs/20-research/open-questions.md).
