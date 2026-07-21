# Slope Studio — Skills Reference

Reference for every agent skill in this repo: what it does, when to reach for it, its
real commands, and how the skills chain together. For the pipeline itself (stages,
architecture, providers), start at [`docs/README.md`](README.md) and
[`.agent-instructions/shared.md`](../.agent-instructions/shared.md). This document
covers the *skills layer* on top of that pipeline.

## Overview

Skills are defined in two layers:

1. **`.claude/skills/<skill>/SKILL.md`** — a thin Claude Code adapter. It carries the
   frontmatter (`name` + `description`, used for auto-triggering) and one instruction:
   read the canonical skill body.
2. **`.agent-instructions/skills/<skill>/SKILL.md`** — the canonical skill, tool-agnostic,
   shared by Claude Code, Codex, and any other agent working in this repo. This is where
   the actual workflow, commands, and rules live. Some skills also ship sibling files here
   (e.g. `film-maker/film-maker-guides.md`, `marketing-guru/references/*.md`,
   `youtube-branding/example-spec.json`).

Per [`CLAUDE.md`](../CLAUDE.md), the adapter is never duplicated — if it conflicts with
the canonical body, the canonical body wins. To invoke a skill, either let it
auto-trigger off its description, or explicitly ask for it by name ("use the film-maker
skill to render this idea").

All of these skills drive the `studio` CLI (`studio/cli.py`), the 7-stage pipeline
(`script → visuals → narrate → clips → stitch → audio → voice → save → publish`) and its
`studio marketing` sub-app. The skills are the *thinking* layer; the CLI commands are I/O
helpers.

## Skill index

| Skill | Purpose | Primary trigger |
|---|---|---|
| [`film-maker`](#film-maker) | Operator playbook for the whole video pipeline, stage by stage | Produce/render/debug/publish a Short or landscape video from an idea |
| [`story-illustrator`](#story-illustrator) | Long-form story/audiobook illustration with consistent recurring characters | Illustrate an existing story/audiobook text; character drift debugging |
| [`sound-designer`](#sound-designer) | Design + produce the music bed and per-scene SFX for a run | A video feels silent/flat; needs atmosphere or a score |
| [`marketing-guru`](#marketing-guru) | Umbrella orchestrator for a channel's ideate→deploy→measure→learn growth loop | Run the whole growth loop, or read channel state / pick the next bet |
| [`marketing-ideate`](#marketing-ideate) | Generate falsifiable viral bets into the backlog | Decide what video to make next |
| [`marketing-deploy`](#marketing-deploy) | Produce + publish a chosen bet, then link it to the journal | Turn a backlog bet into a published, journal-bound video |
| [`marketing-measure-learn`](#marketing-measure-learn) | Score virality, then reflect assumptions into strategy | 48–72h+ after publishing, to close the loop |
| [`marketing-autopilot`](#marketing-autopilot) | Hands-off scheduler: each tick does the one due action | Recurring/cron-style unattended operation of the growth loop |
| [`youtube-branding`](#youtube-branding) | Generate a full YouTube brand kit (banner, avatar, logo, watermark, copy) | Brand or rebrand a channel |

## Per-skill sections

### Video production

#### film-maker

**What it does.** The operator playbook for `studio`, the 7-stage CLI that turns a text
idea into a finished vertical Short (or landscape video). It documents environment setup,
every stage's commands and providers, aspect-ratio handling, the content-critic gate, cost
control, and troubleshooting. Its companion file, `film-maker-guides.md`, is the
"marvelous effects" quality playbook — animator choice, parallax/slice/manim rules,
pacing/variety checklists, captions, and the operator's standing creative preferences.

**When to use it.** Whenever the user wants to produce, generate, render, run, debug,
observe, thumbnail, or publish a short vertical video or landscape video from an idea, or
to run/inspect any single pipeline stage.

**Key workflow.**
- Whole video in one command, tier-driven:
  ```bash
  studio run "the chemistry of humor" --duration 150 --tier cheap
  studio run "topic" --tier balanced --video-model ltx --max-cost 3 --publish-to youtube --privacy public
  ```
  `--tier free|cheap|balanced|premium` sets every stage's provider; any `--*-provider` /
  `--video-strategy` / `--video-model` flag overrides it. `--max-cost` (default $3) caps
  whole-video spend; clips trims/aborts pre-flight to fit.
- Per-stage, for iterating/debugging:
  ```bash
  RID=$(studio init "octopuses are aliens" --duration 60 | awk '{print $2}')
  studio script $RID --provider stub
  studio critic $RID                 # 1.5 content gate: topic revealed / fact explained / interesting / emotion
  studio visuals $RID --provider fal-nanobanana
  studio narrate $RID                 # TTS per scene → drives clip durations
  studio estimate $RID --budget 3     # ALWAYS before clips — AI video is billed per second
  studio clips $RID --strategy auto --model ltx --max-cost 3
  studio stitch $RID --transition fade --transition-s 0.4
  studio audio  $RID
  studio voice  $RID --provider edge  # captions OFF by default
  studio save   $RID
  studio thumbnail $RID --at 6        # REQUIRED for landscape/long-form before publish
  studio metadata $RID                # SEO title/desc/tags (auto-runs before publish)
  studio publish $RID --target youtube --privacy public
  studio status $RID                  # provider/cost/latency table, always report this
  ```
- Aspect: `studio run "topic" --aspect 16:9 --duration 600` for classic landscape YouTube;
  default is `9:16` vertical Shorts. A 9:16 upload is only a *Short* if ≤180s.
- Retire/reupload: `studio unlist <VIDEO_ID> --channel <name>` to hide a live video (and
  reflect it out of journal stats); `scripts/reupload_as_shorts.py` to retire + reupload
  the master as a 9:16 Short.
- The **critic gate** (`studio critic`, wired into `studio run --critic on|strict|off`)
  blocks rendering a wired-but-empty scenario — never run paid `visuals`/`clips` on a
  `--script-provider stub` script (offline wiring placeholder text only).

**Related skills.** `sound-designer` is its audio half (produces the music/SFX layer for
an already-scripted run). `marketing-deploy` calls into `film-maker`'s `studio run` to
turn a chosen growth-loop bet into a published video. `story-illustrator` reuses the same
pipeline stages for long-form character-driven work instead of one-shot Shorts.
`youtube-branding` sits upstream, producing the channel identity that videos publish into.

---

#### story-illustrator

**What it does.** The operator playbook for long-form story/audiobook illustration videos
with consistent recurring characters. It solves character-look drift: a locked character
card (descriptor + anchor image) is injected verbatim into every scene prompt, and a
vision drift-gate compares each rendered frame against the card and regenerates once with
corrections if it drifts.

**When to use it.** Illustrating an existing story or audiobook text as a video; building
a character card from a reference-image folder (`characters/<name>/`) or from the story
text alone (no pictures — whole-story analysis locks a constant look); storyboarding prose
into scenes; debugging character look drift between generated images.

**Key workflow.**
```bash
studio characters-build gurdjieff --portrait --style "painterly 1900s oil"   # image-backed card
studio characters-extract "the abbot" stories/ch1.txt                        # text-derived card
studio storyboard story.txt --duration 1800 --aspect 16:9 \
    --style "painterly, muted, 1900s" --characters-root characters/
studio visuals  <run_id> --characters-root characters/    # drift gate ON
studio narrate  <run_id> && studio clips <run_id> --strategy kenburns
studio stitch   <run_id> && studio audio <run_id> && studio voice <run_id> && studio save <run_id>
```
For a whole book: `pdftotext` → `studio book-split` → build the recurring cast **once**
from chapter 1 → loop `studio storyboard`/`visuals`/`narrate`/`clips`/`stitch`/`audio`/
`voice`/`save` per chapter, reusing the frozen cards. Character age is **story-time age**
(age at the point in the narrative being illustrated, not a fixed guess) — this is the one
input the skill will not default; ask the operator if the story's timeline is unclear.
Sound policy is sparse/quiet/cheap (`--sfx-provider freesound --music-provider synth`,
`gain_db: -14`, ≤1 sfx cue per 5 beats).

**Related skills.** Shares the `film-maker` pipeline stages (`visuals`/`narrate`/`clips`/
`stitch`/`audio`/`voice`/`save`) but adds the character-card and storyboard layer in
front. `sound-designer`'s general sound taste applies, though story-illustrator defaults
to a sparser, cheaper policy than a one-shot Short.

---

#### sound-designer

**What it does.** The audio counterpart to `film-maker`'s art-direction: designs and
produces the whole license-safe sound layer for a run — one coherent music mood/arrangement
for the piece plus per-scene SFX cues — using only paid/generated providers under the
operator's control, synthetic ffmpeg audio, CC0/public-domain Freesound, or local assets
with explicit reusable rights.

**When to use it.** A video feels silent, flat, or needs atmosphere; adding music + sound
effects to scenes the clip maker already produced; general "sound design" / "score" /
"make this feel produced" requests.

**Key workflow.**
1. Read `runs/<id>/01_script.json` (`Scene.narration`, `visual_prompt`, mood/`tone`,
   existing `sfx`; top-level `Script.music`).
2. Inspect the available library: `find assets/audio/music assets/audio/sfx -maxdepth 1 -type f`.
3. Author `Script.music` (one mood/arrangement phrase, with movement cues like "fade in
   slowly", "swell at the reveal") and each scene's `sfx` list
   (`{prompt, at, dur, gain_db}` — accents 0.2–2.0s, 5.0s hard max).
4. Edit `01_script.json` directly, then produce:
   ```bash
   studio audio <id> --music-provider local --sfx-provider local   # or synth as $0 fallback
   studio voice <id>       # ducks music under narration
   studio save  <id>
   ```
Provider ladder (quality-first, license-safe): `fal-stable-audio`/`fal-elevenlabs-sfx`
when budget allows → vetted `local`/`freesound` (CC0/public-domain) → `synth` ($0
ffmpeg-generated fallback) → `silence`. Never the same drone under every video; ≤1–2 sfx
per scene; no SFX family repeated within 30s (cooldown enforced by the stage as backstop).

**Related skills.** Operates on runs already produced by `film-maker` (or
`story-illustrator`). Referenced directly from `film-maker-guides.md` §11 as "its own
role" whenever a Short needs sound without a full re-render.

---

### Marketing / growth loop

#### marketing-guru

**What it does.** The umbrella orchestrator for a channel's viral-growth loop: a closed
`ideate → deploy → measure → learn` cycle backed by a persistent per-channel journal
(`runs/_marketing/<channel>/journal.json`). It composes the four lego-block skills below
and additionally owns the thin read/pick/report helpers — journal state, backlog pick,
and growth-brief writing — that don't warrant their own skill.

**When to use it.** Running the whole loop, not knowing which step is needed, or wanting
to read channel state / pick the next bet / write a growth brief. For one creative step,
invoke that step's skill directly instead.

**Key workflow.**
```bash
studio marketing journal  --channel <name>            # phase (COLD START n/10 | OPTIMIZING) + strategy + bet table
studio marketing backlog  --channel <name>            # planned bets, explore/exploit mix
studio marketing recall   "<query>" --channel <name>  # past measured bets relevant to a query
studio marketing bandit   --channel <name>            # shipped Thompson-bandit theme/tag win-rates (primary selector)
studio marketing report   --channel <name> --provider <llm>   # writes runs/_marketing/<name>/report.md
```
Loop order: **youtube-branding** (once/on rebrand) → journal (read state) →
**marketing-ideate** → backlog (pick) → **marketing-deploy** → wait 48–72h+ →
**marketing-measure-learn** → back to ideate. **Cold-start rule:** relative virality is
meaningless until ~10 videos exist — deploy the first 10 as diverse exploration bets
before `measure`/`learn` start ranking and exploiting. Deeper analysis (age-normalized
slices across theme/cost/music/effects/providers) via
`studio marketing due-snapshots|snapshots|insights|slice|compare|export`.

**Related skills.** Sits above `marketing-ideate`, `marketing-deploy`,
`marketing-measure-learn` (the per-step lego blocks) and `marketing-autopilot` (the
hands-off scheduled driver). `youtube-branding` is its channel-setup lego-block, run once
before the loop starts. `marketing-deploy` hands off into `film-maker` for the actual
production.

---

#### marketing-ideate

**What it does.** Generates N falsifiable viral bets — `idea` · `hook` (literal 0–3s
scroll-stopper) · `assumption` (why it should go viral, must be falsifiable) · `goal`
(measurable) · `theme` · `tags` — and persists them to the backlog. The agent does the
reasoning (web search for live trend signal + recall of the channel's past winners); the
CLI is pure persistence.

**When to use it.** Deciding what short video to make next for a channel.

**Key workflow.**
```bash
studio marketing journal --channel <name>                       # 1. read phase + direction
# 2. WebSearch trending formats/hooks/news pegs in the niche
studio marketing recall "<niche / direction / theme>" --channel <name>   # 3. recall what worked
# 4. reason bets: cold-start → maximize diversity; optimizing → lean into winners + ≥1 exploration bet
studio marketing add "<idea>" --hook "<hook>" --assumption "<why>" --goal "<target>" \
  --theme "<theme>" --tags "a,b,c" --channel <name>                       # 5. persist (--exploit for exploit bets)
```
Scripted non-agent fallback: `studio marketing ideate --provider <llm> --signals <file> --niche "<niche>" --n 3`.

**Related skills.** Feeds the backlog that `marketing-guru`'s backlog step and
`marketing-autopilot`'s `produce` action pick from. Reads the `strategy`/`next_seeds`
that `marketing-measure-learn` writes.

---

#### marketing-deploy

**What it does.** Turns one chosen backlog bet into a published Short bound to its journal
entry: sizes the spend to the channel's budget, calls `film-maker`'s `studio run` to
produce and publish, then links the run back to the bet (capturing production telemetry —
cost, duration, animators/fx/model — for later learning).

**When to use it.** Producing and publishing a bet that's already been picked from the
backlog.

**Key workflow.**
```bash
CAP=$(studio marketing budget --channel <name> --for-duration <duration_s>)   # 1. spend cap
studio run "<idea>" --duration 60 --tier cheap --max-cost $CAP \
  --publish-to youtube --privacy public --channel <name>                       # 2. produce+publish
studio marketing link <entry_id> <run_id> --channel <name>                     # 3. link to the bet
```
Then **wait 48–72h+** before measuring. Set the budget once via
`studio marketing budget --channel <name> --per-video 0.60` or `--per-minute 0.40`.
Repeat backlog→deploy until ~10 videos are live to exit cold-start.

**Related skills.** The bridge between `marketing-guru`'s backlog pick and `film-maker`'s
production pipeline; hands off to `marketing-measure-learn` after the maturation wait.

---

#### marketing-measure-learn

**What it does.** Closes the loop in two ordered steps: **measure** (deterministic —
fetch YouTube stats/comments, compute a virality composite, rank each deployed bet into a
percentile within the channel's own portfolio, tag win/loss/neutral/cold-start), then
**learn** (agent-driven reflection — compare each bet's pre-stated assumption against the
measured outcome, extract winning/losing patterns, and write the next strategy + idea
seeds).

**When to use it.** 48–72h+ after publishing, to measure deployed bets, score virality,
test assumptions, and update the learned channel strategy.

**Key workflow.**
```bash
# Step 1 — measure
studio marketing measure --channel <name> --comments-n 60

# Step 1.5 — snapshot + slice (age-normalized analysis before changing strategy)
studio marketing due-snapshots --channel <name>
studio marketing snapshots     --channel <name> --buckets 1,3,7,14,30
studio marketing insights      --channel <name> --json
studio marketing slice   --channel <name> --bucket 7d --group-by theme,effects,animators --metric virality
studio marketing compare --channel <name> effects=glitch --bucket 14d --metric virality

# Step 2 — learn (agent reflects, then persists)
studio marketing journal --channel <name>
studio marketing recall  "<theme under review>" --channel <name>
studio marketing strategy --channel <name> \
  --direction "<thesis paragraph>" --winning "trait a;trait b" --losing "trait c" \
  --seeds "seed 1;seed 2;seed 3" --note j0007=cosmic-scale shock hooks beat soft intros
```
Scripted non-agent fallback for learn: `studio marketing learn --provider <llm>`.
Cold-start (<10 deployed) means percentiles are meaningless — every outcome reads
`cold-start`.

**Related skills.** Consumes what `marketing-deploy` linked; the `strategy`/`next_seeds`
it writes are exactly what `marketing-ideate` reads on the next cycle — this is where the
loop closes.

---

#### marketing-autopilot

**What it does.** The hands-off scheduling driver for the growth loop. Each tick it asks
the engine (`studio/marketing/loop.py`, a state machine over time) what's actually due —
because a published video must mature ~48–72h before its metrics mean anything — and does
that one action, deferring the real creative work to the per-step lego-block skills.

**When to use it.** Hands-off scheduling of the growth loop on a recurring cadence, with
no operator watching each tick.

**Key workflow.**
```bash
studio marketing tick --channel <name> --json
```
| `next` | what to do |
|---|---|
| `measure` | `studio marketing measure --channel <name>` |
| `learn` | invoke `marketing-measure-learn` (its learn step) |
| `ideate` | invoke `marketing-ideate` |
| `produce` | invoke `marketing-deploy` for `produce_entry` at `produce_max_cost` |
| `idle` | nothing due — wait for the next tick |

Run continuously via the `/loop` or `/schedule` skill re-invoking this skill on an
interval, or headless via `studio marketing autopilot --channel <name> [--produce]`
(scripted ideate/learn fallbacks; `--produce` gates real spend/publish, e.g. from cron).
Before first run: `studio marketing budget --channel <name> --per-minute 0.40` (or
`--per-video`). Cadence/maturation knobs live in `Journal.loop`
(`maturation_hours`, `min_hours_between_produces`, `daily_produce_cap`, `learn_every`,
`backlog_min`, `target_duration_s`) — edit `runs/_marketing/<name>/journal.json` to tune.

**Related skills.** A thin scheduling wrapper over `marketing-guru`'s loop; delegates
every actual action to `marketing-ideate`, `marketing-deploy`, or
`marketing-measure-learn`.

---

### Publishing / branding

#### youtube-branding

**What it does.** Generates a complete, upload-ready YouTube channel brand kit — banner
(2560×1440), profile picture (1024×1024), transparent logo/watermark (1024² and 512²), and
channel keywords/description — from a channel name, slogan, and niche. The agent authors
the brand identity (palette, emblem concept, banner scene) as a spec JSON; the
`studio brand` CLI does the mechanical generation (Nano Banana art, Pillow wordmark
overlay, rembg transparency cut).

**When to use it.** Branding or rebranding a YouTube (or other) channel: designing/
generating a banner, avatar, logo, watermark, or writing channel keywords/description.

**Key workflow.**
1. Gather channel name, slogan, niche/aesthetic.
2. Copy `.agent-instructions/skills/youtube-branding/example-spec.json` and author every
   field — `style` must end with `no text, no letters, no words` (the wordmark is
   Pillow-overlaid afterward, never trust the image model to spell); `logo_prompt` is a
   flat iconic emblem on a plain background (rembg cuts it); `banner_prompt` leaves empty
   negative space across the center for the wordmark.
3. Optional free dry-run: `studio brand myspec.json --provider stub` (throwaway `slug`).
4. Generate the real kit (~$0.12 — three Nano Banana stills @ $0.039):
   ```bash
   studio brand myspec.json
   ```
5. Eyeball `banner.png` / `profile.png` / `logo.png` in `runs/_brand/<slug>/` for wordmark
   legibility, clean transparent cut, and consistent motif across logo/profile.
6. Deliver asset paths, keywords, description; optionally overlay `logo_512.png` as an
   on-video watermark via ffmpeg.

**Related skills.** `marketing-guru`'s channel-setup lego-block, run once before the
ideate→deploy→measure→learn loop starts (or on rebrand). Produces static brand art only —
`film-maker` produces the actual videos.

## How the skills fit together

**Single-video production (no growth loop):**
```
idea → film-maker (script → critic → visuals → narrate → clips → stitch
       → audio → voice → save → thumbnail → metadata → publish)
                     ↑
            sound-designer (audio polish on an existing run)
```
For long-form character-driven work, `story-illustrator` replaces the script/storyboard
front end but reuses the same `visuals`/`narrate`/`clips`/`stitch`/`audio`/`voice`/`save`
stages.

**Channel growth loop (repeats):**
```
youtube-branding (once/on rebrand)
        │
        ▼
   marketing-guru: journal (read state)
        │
        ▼
marketing-ideate ──► backlog (pick) ──► marketing-deploy ──► film-maker (produce+publish)
        ▲                                                          │
        │                                                    wait 48–72h+
        │                                                          ▼
        └──────────────── strategy + next_seeds ◀── marketing-measure-learn
```
`marketing-autopilot` runs this whole cycle unattended: each tick it asks the loop engine
what's due (`measure` / `learn` / `ideate` / `produce` / `idle`) and delegates that one
action to the matching lego-block skill, handling the 48–72h measurement-maturation wait
automatically. The **cold-start rule** applies throughout: the first ~10 deployed videos
are treated as diverse exploration bets, since relative virality is meaningless before
that — only then do `measure`/`learn` start ranking winners and the loop starts exploiting
them.
