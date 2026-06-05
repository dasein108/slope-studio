# Workflow Diagrams

Visual reference for how Slope Studio actually runs, drawn from the implemented code
(`studio/`). Mermaid diagrams — GitHub renders them inline. Companion to
[`pipeline-stages.md`](../00-overview/pipeline-stages.md) (artifact contracts) and
[`module-map.md`](module-map.md) (every module's surface).

> Ground truth: `studio/cli.py` `STAGE_ORDER`, the stage functions in `studio/stages/`,
> and `studio/paths.py`. If a diagram and the code disagree, the code wins — fix the diagram.

---

## 1. Pipeline DAG — the 8 stages (+ optional publish)

`STAGE_ORDER = ["script", "visuals", "narrate", "clips", "stitch", "audio", "voice", "save"]`.
`narrate` and `audio` run only when voice is on. `metadata` + `publish` run only when a
publish target is requested.

```mermaid
flowchart TD
    idea([text idea]) --> script

    script[["1 · script<br/>LLM → 01_script.json"]]
    visuals[["2 · visuals<br/>image gen → 02_visuals/scene_NN.png"]]
    narrate[["2.5 · narrate<br/>TTS → per-scene mp3 + timing.json + captions.srt"]]
    clips[["3 · clips<br/>i2v / kenburns → 03_clips/scene_NN.mp4"]]
    stitch[["4 · stitch<br/>ffmpeg → 04_stitched.mp4 (no audio)"]]
    audio[["5b · audio<br/>sfx + music → 05b_sfx/ + 05c_music.mp3"]]
    voice[["5 · voice<br/>mux narration+sfx+music+captions → 05_voice/final.mp4"]]
    save[["6 · save<br/>encode master → 06_final.mp4 + 06_final.json"]]
    metadata[["6.5 · metadata<br/>LLM SEO → 06_final.json"]]
    publish[["7 · publish<br/>upload → 07_publish.json"]]

    script --> visuals --> narrate --> clips --> stitch --> audio --> voice --> save
    save -.->|publish requested| metadata -.-> publish

    narrate -. "timing.json drives durations" .-> clips
    narrate -. timing.json .-> stitch
    narrate -. per-scene mp3 .-> voice
    audio -. placements.json + music .-> voice

    classDef opt fill:#fff3cd,stroke:#d9a800;
    class narrate,audio,metadata,publish opt;
```

Yellow nodes are conditional. `narrate`/`audio` gate on `--with-voice` (default on);
`metadata`/`publish` gate on `--publish-to`.

---

## 2. Artifact data-flow inside `runs/<id>/`

Every stage reads files, writes files. `project.json` (the manifest) is updated after each.

```mermaid
flowchart LR
    subgraph run["runs/&lt;id&gt;/"]
        proj[(project.json<br/>manifest)]
        s01[01_script.json]
        s02[02_visuals/scene_NN.png<br/>+ scene_NN_bg.png]
        s025a[05_voice/scenes/scene_NN.mp3]
        s025b[05_voice/timing.json]
        s025c[05_voice/captions.srt]
        s03[03_clips/scene_NN.mp4]
        s04[04_stitched.mp4]
        s05b[05b_sfx/scene_*.mp3<br/>+ placements.json]
        s05c[05c_music.mp3]
        s05[05_voice/final.mp4]
        s06[06_final.mp4]
        s06j[06_final.json]
        s06t[06_thumb.png]
        s07[07_publish.json]
        s08[08_stats.json<br/>08_comments.json]
    end

    s01 --> s02 --> s025a
    s01 --> s025a
    s025a --> s025b
    s025a --> s025c
    s02 --> s03
    s025b --> s03 --> s04
    s025b --> s04
    s01 --> s05b
    s025b --> s05b --> s05c
    s04 --> s05
    s025a --> s05
    s025c --> s05
    s05b --> s05
    s05c --> s05
    s05 --> s06 --> s07
    s06j --> s07
    s06t -.-> s07
    s07 -.->|marketing measure| s08

    proj -.-> s01 & s03 & s06
```

Path source of truth: `studio/paths.py`.

---

## 3. `studio run` chainer — control flow

How `cli.run()` walks `STAGE_ORDER` with resume, conditional stages, and budget gating.

```mermaid
flowchart TD
    start([studio run idea]) --> tier{--tier preset}
    tier --> ov[apply tier providers<br/>--*-provider flags override]
    ov --> res{--run-id given<br/>& run exists?}
    res -->|yes| resume[resume: skip stages<br/>already m.is_done]
    res -->|no| init[init: new run dir + manifest]
    resume --> loop
    init --> loop

    loop[walk STAGE_ORDER<br/>from --from-stage to --to-stage]
    loop --> isdone{stage done<br/>& resuming?}
    isdone -->|yes| loop
    isdone -->|no| which{which stage?}

    which -->|narrate / audio| von{--with-voice?}
    von -->|no| loop
    von -->|yes| runstage
    which -->|clips| cap[cap = max_cost − cost so far]
    cap --> runstage
    which -->|other| runstage

    runstage[run stage fn → GenResult] --> rec[manifest.record + save]
    rec --> more{more stages?}
    more -->|yes| loop
    more -->|no| pub{--publish-to set?}
    pub -->|yes| meta[metadata → publish]
    pub -->|no| done
    meta --> done([print run id + total cost])
```

---

## 4. Clips stage — strategy + budget gating

Stage 3 is ~90% of cost. `--strategy` decides which scenes get paid AI video; `--max-cost`
hard-caps spend. Free animators (kenburns and friends) never abort the pipeline.

```mermaid
flowchart TD
    start([clips run_id]) --> strat{--strategy}

    strat -->|kenburns| allfree[every scene → free animator]
    strat -->|all| preflight
    strat -->|hybrid| preflight
    strat -->|auto| rank[rank scenes by<br/>_effective_priority<br/>hook · outro · spread · Scene.priority]

    preflight{est cost ≤ max_cost?}
    preflight -->|no| abort[[BudgetError — abort pre-flight]]
    preflight -->|yes| genloop

    rank --> budgetloop[greedily AI highest-priority<br/>while cumulative ≤ max_cost]
    budgetloop --> kbrest[remaining scenes → kenburns]

    genloop[for each AI scene:<br/>fal-i2v at --model] --> runtimecap{next clip would<br/>exceed max_cost?}
    runtimecap -->|yes| stop[stop AI, kenburns the rest]
    runtimecap -->|no| genloop

    allfree --> animate
    kbrest --> animate
    genloop --> animate
    stop --> animate

    animate[animate.render per scene<br/>fall back to kenburns on error] --> norm[normalize each clip to<br/>timing.json duration]
    norm --> done([03_clips/scene_NN.mp4])
```

Run `studio estimate <id>` first — it prices stage 3 per model before you spend.

---

## 5. Audio/video sync — narration drives everything

The whole pipeline length equals the narration length. `narrate` writes `timing.json`
(`{scene_id: seconds}`) from real TTS durations; clips, stitch, and mux all honor it.

```mermaid
flowchart LR
    n[narrate:<br/>TTS each scene<br/>+ PAD_S] --> t[(timing.json<br/>scene_id → secs)]
    t --> c[clips:<br/>normalize each clip<br/>target_dur = timing]
    t --> s[stitch:<br/>concat_xfade_seq<br/>overlap-compensated<br/>len = Σ durations]
    t --> a[audio:<br/>global sfx offsets<br/>= scene_offset + cue.at]
    n --> v[voice:<br/>concat per-scene mp3<br/>mux_audio holds tail<br/>never truncates]
    s --> v
    a --> v
    v --> out([06_final.mp4<br/>len == narration ± tail])

    nofx{{no narrate stage?<br/>fall back to Scene.duration_s}}
    nofx -.-> c & s & a
```

Don't reintroduce `-shortest`-style trimming — `mux_audio` deliberately holds the last
frame + tail so audio never gets cut.

---

## 6. Free-animator dispatch (`animate.render`)

Per-scene, free, context-driven. `Scene.animator` picks the base motion; `Scene.atmosphere`
and `Scene.fx` are optional post-passes. Anything that fails degrades to `kenburns`.

```mermaid
flowchart TD
    scene([Scene]) --> base{Scene.animator}
    base -->|static/none/hold| b1[hold still]
    base -->|kenburns / ''| b2[slow pan+zoom · DEFAULT]
    base -->|motion-*| b3[ffmpeg motion preset]
    base -->|kinetic| b4[zoom + slide-up headline]
    base -->|parallax| b5[sharp subject + inpainted bg drift]
    base -->|blurred-parallax| b6[blurred depth planes pan]
    base -->|slice| b7[split halves slide together]
    base -->|puppet/cutout| b8[rembg figure idle/hop/shake/nod]
    base -->|talkinghead| b9[Rhubarb 2D mouth lip-sync]
    base -->|manim| b10[true vector animation]
    base -->|unknown| b2

    b1 & b2 & b3 & b4 & b5 & b6 & b7 & b8 & b9 & b10 --> atmo{Scene.atmosphere?}
    atmo -->|rain/snow/embers/sparks/blood/petals/wind/leaves/fog| ov[particle overlay]
    atmo -->|none| fx
    ov --> fx{Scene.fx?}
    fx -->|grain/vignette/chroma/glitch/sunrise/sunset/godrays/flash-*| look[post_fx look pass]
    fx -->|none| out
    look --> out([03_clips/scene_NN.mp4])

    err{{any step errors}} -.->|fallback| b2
```

Full catalog + ffmpeg/Manim recipes: [`../30-animation/`](../30-animation/README.md).

---

## 7. Marketing loop — ideate → deploy → measure → learn

Per-channel journal at `runs/_marketing/<channel>/`. Cold-start (first 10 deployed)
explores; after that it exploits. `film-maker` produces; `marketing-guru` decides + judges.

```mermaid
flowchart TD
    seeds[(strategy.next_seeds<br/>winning/losing patterns)] --> ideate
    signals[/web-search trend signals/] -.-> ideate
    ideate[["marketing ideate<br/>LLM → bets {idea,hook,assumption,goal}"]]
    ideate --> plan[Entry status=planned<br/>j0001, j0002, …]

    plan --> deploy[["studio run … --publish-to youtube<br/>(film-maker)"]]
    deploy --> link[["marketing link entry_id run_id<br/>status=deployed + video_id"]]

    link --> measure[["marketing measure<br/>analytics: views·likes·comments<br/>retention·subs (best-effort)"]]
    measure --> score[score.virality composite<br/>0.5·velocity +0.2·retention<br/>+0.2·engagement +0.1·subs]
    score --> pct[relativize → percentile<br/>outcome: win≥75 · loss≤25 · neutral]
    pct --> measured[Entry status=measured<br/>+ 08_stats.json / 08_comments.json]

    measured --> learn[["marketing learn<br/>LLM reflect on portfolio"]]
    learn --> update[update strategy:<br/>direction + patterns + next_seeds]
    update --> seeds

    cold{deployed &lt; 10?}
    cold -->|cold-start| explore[ideate = maximize diversity<br/>outcome forced cold-start]
    cold -->|optimizing| exploit[ideate = exploit winners<br/>+ reserve exploration]
```

Reference: [`../50-marketing/`](../50-marketing/README.md). Score math: `studio/marketing/score.py`.

---

## 8. Provider selection (`config.default_provider`)

Each stage's default provider is chosen by which API keys are present in `.env`, else a
free fallback. `--*-provider` flags and `--tier` presets override.

```mermaid
flowchart TD
    subgraph script
      sc{OPENAI→GEMINI→GROQ<br/>→OPENROUTER→OLLAMA?} -->|yes| sca[that LLM]
      sc -->|no key| scb[stub · offline split]
    end
    subgraph visuals
      vi{FAL_KEY?} -->|yes| via[fal-nanobanana]
      vi -->|no| vib[card · Pillow offline]
    end
    subgraph clips
      cl{FAL_KEY?} -->|yes| cla[fal-i2v]
      cl -->|no| clb[kenburns · free]
    end
    subgraph voice
      vo{OPENAI_API_KEY?} -->|yes| voa[openai-tts]
      vo -->|no| vob[edge · free]
    end
    subgraph audio
      au{FAL_KEY / FREESOUND?} -->|yes| aua[fal / freesound]
      au -->|no| aub[local pack → silence]
    end
```

Source: `studio/config.py`. Tier presets in `studio/tiers.py` set these in bulk.

---

## 9. Publish + analytics OAuth (token reuse)

One per-channel OAuth token (`token_<channel>.json`) is shared by publish and analytics.
Analytics adds the `yt-analytics.readonly` scope (one-time re-consent).

```mermaid
flowchart TD
    call([publish or analytics call]) --> tok{token_&lt;channel&gt;.json<br/>valid?}
    tok -->|valid| use[use creds]
    tok -->|expired + refresh| refresh[refresh token] --> use
    tok -->|missing/invalid| flow[InstalledAppFlow<br/>browser consent<br/>pick channel] --> use

    use --> what{operation}
    what -->|publish youtube| up[videos.insert + thumbnail<br/>→ 07_publish.json]
    what -->|publish tiktok| tt[[NotImplementedError<br/>audit-gated, private-only]]
    what -->|measure| an[Data API: stats/comments<br/>Analytics API: retention/subs<br/>best-effort]
```

Scopes: `youtube.upload` + `youtube.readonly` (+ `yt-analytics.readonly` for retention/subs).
Source: `studio/providers/publish.py` `_creds()`, `studio/providers/analytics.py`.

---

## 10. Module dependency map

How `studio/` packages depend on each other.

```mermaid
flowchart TD
    cli[cli.py · typer app] --> stages[stages/*]
    cli --> manifest[manifest.py]
    cli --> tiers[tiers.py]
    cli --> config[config.py]
    cli --> marketing[marketing/*]

    stages --> providers[providers/*]
    stages --> animate[animate.py]
    stages --> ffmpeg[ffmpeg.py]
    stages --> canvas[canvas.py]
    stages --> paths[paths.py]
    stages --> models[models.py]
    stages --> manifest

    animate --> ffmpeg
    animate --> providers
    providers --> base[providers/base.py · GenResult]
    providers --> cardgen[providers/cardgen.py]
    providers --> voices[voices.py]
    marketing --> providers
    marketing --> paths
    ffmpeg --> canvas
    cardgen --> canvas
```

Per-module detail: [`module-map.md`](module-map.md).
</content>
</invoke>
