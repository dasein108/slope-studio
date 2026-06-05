"""studio — CLI. Each stage is a subcommand; `run` chains them with resume."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from studio import config, manifest, paths, tiers
from studio.stages import audio as audio_stage
from studio.stages import clips as clips_stage
from studio.stages import metadata as metadata_stage
from studio.stages import narrate as narrate_stage
from studio.stages import publish as publish_stage
from studio.stages import save as save_stage
from studio.stages import script as script_stage
from studio.stages import stitch as stitch_stage
from studio.stages import visuals as visuals_stage
from studio.stages import voice as voice_stage

app = typer.Typer(add_completion=False, help="Automated short-video studio (faceless MVP).")
console = Console()

marketing_app = typer.Typer(add_completion=False,
                            help="marketing-guru — viral growth loop (ideate→deploy→measure→learn).")
app.add_typer(marketing_app, name="marketing")

STAGE_ORDER = ["script", "visuals", "narrate", "clips", "stitch", "audio", "voice", "save"]


def _slug(text: str, n: int = 24) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n] or "video"


def _load(run_id: str) -> tuple[Path, manifest.Manifest]:
    d = paths.run_dir(run_id)
    return d, manifest.load(d)


# --------------------------------------------------------------------------- init
@app.command()
def init(idea: str, duration: int = 150, aspect: str = "9:16",
         voice: bool = True, style: str = "", tier: str = "balanced",
         run_id: Optional[str] = None) -> str:
    """Create a run directory + manifest."""
    rid = run_id or f"{datetime.now():%Y%m%d_%H%M%S}_{_slug(idea)}"
    d = paths.run_dir(rid)
    d.mkdir(parents=True, exist_ok=True)
    m = manifest.Manifest(id=rid, idea=idea, duration_s=duration, aspect=aspect,
                          voice=voice, style=style, tier=tier)
    manifest.save(d, m)
    console.print(f"[green]created[/] {rid}")
    return rid


# ----------------------------------------------------------------------- per-stage
@app.command()
def script(run_id: str, provider: Optional[str] = None) -> None:
    """Stage 1 — idea -> timed scenario JSON."""
    d, m = _load(run_id)
    prov = provider or config.default_provider("script")
    s, lat, cost = script_stage.run(d, m.idea, m.duration_s, m.aspect, m.voice, m.style, prov)
    problems = s.validate_timing()
    if problems:
        console.print(f"[yellow]timing warnings:[/] {problems}")
    m.record("script", done=True, provider=prov, cost_usd=cost, latency_s=lat, n=len(s.scenes))
    manifest.save(d, m)
    console.print(f"[green]script[/] {len(s.scenes)} scenes via {prov}")


@app.command()
def visuals(run_id: str, provider: Optional[str] = None,
            cheap_provider: Optional[str] = None,
            char_ref: Optional[Path] = None, force: bool = False,
            parallax_plates: bool = False) -> None:
    """Stage 2 — keyframe image per scene. Scenes with image_role="bg" use
    --cheap-provider (cheaper model for backgrounds/overlays); hero/character use
    --provider (quality + character ref).

    --parallax-plates: also generate a separate background plate (subject removed) for
    each animator:"parallax" scene → true layered 2.5D (no torn frame). +1 image/scene;
    on by default for balanced/premium tiers via `run`."""
    d, m = _load(run_id)
    prov = provider or config.default_provider("visuals")
    cheap = cheap_provider or config.default_provider("visuals_cheap")
    r = visuals_stage.run(d, prov, char_ref=char_ref, force=force, cheap_provider=cheap,
                          parallax_plates=parallax_plates)
    m.record("visuals", done=True, provider=prov, cost_usd=r.cost_usd, latency_s=r.latency_s,
             note=r.note)
    manifest.save(d, m)
    console.print(f"[green]visuals[/] {r.note} via {prov}  ${r.cost_usd}")


def _parse_ids(spec: str | None) -> set[int] | None:
    """'1,7,15' -> {1,7,15}; '' or None -> None (all scenes)."""
    if not spec:
        return None
    return {int(x) for x in spec.replace(" ", "").split(",") if x}


@app.command()
def narrate(run_id: str, provider: Optional[str] = None, voice: str = "",
            tone: str = "") -> None:
    """Pre-clips TTS: synth each scene, derive clip durations + aligned captions.

    --voice man|woman|cartoon|narrator  --tone neutral|serious|mystical|friendly|sad|excited
    (per-scene `tone` in the scenario overrides). See docs/30-animation/voices.md.
    """
    d, m = _load(run_id)
    prov = provider or config.default_provider("voice")
    r = narrate_stage.run(d, prov, voice_name=voice, tone=tone)
    m.record("narrate", done=True, provider=prov, cost_usd=r.cost_usd,
             latency_s=r.latency_s, note=r.note)
    manifest.save(d, m)
    console.print(f"[green]narrate[/] {r.note} via {prov}")


@app.command()
def clips(run_id: str, strategy: str = "auto", model: str = "kling",
          ai_scenes: Optional[str] = None, max_cost: float = 3.0,
          force: bool = False) -> None:
    """Stage 3 — video clips. --strategy kenburns|all|hybrid|auto.

    kenburns=free, all=AI every scene, hybrid=--ai-scenes 1,7,15, auto=smart fill
    within --max-cost. Per-second AI cost is estimated and the stage ABORTS/trims so
    spend never exceeds --max-cost (0 disables). Preview with `studio estimate`.
    """
    d, m = _load(run_id)
    if ai_scenes:
        strategy = "hybrid"
    r = clips_stage.run(d, strategy=strategy, model=model,
                        ai_scene_ids=_parse_ids(ai_scenes), max_cost=max_cost or None,
                        force=force)
    m.record("clips", done=True, provider=r.provider, cost_usd=r.cost_usd,
             latency_s=r.latency_s, note=r.note)
    manifest.save(d, m)
    console.print(f"[green]clips[/] {r.note}  ${r.cost_usd}")


@app.command()
def stitch(run_id: str, transition: str = "cut", transition_s: float = 0.4) -> None:
    """Stage 4 — glue clips with per-scene transitions (this is the global default)."""
    d, m = _load(run_id)
    r = stitch_stage.run(d, transition=transition, transition_s=transition_s)
    m.record("stitch", done=True, provider=r.provider, note=r.note)
    manifest.save(d, m)
    console.print(f"[green]stitch[/] {r.note}")


@app.command()
def audio(run_id: str, sfx_provider: Optional[str] = None,
          music_provider: Optional[str] = None, force: bool = False) -> None:
    """Stage 5b — generate sound effects (per-scene `sfx` cues) + a music bed
    (`Script.music`). Commercial-safe sources. The voice stage mixes them in."""
    d, m = _load(run_id)
    sp = sfx_provider or config.default_provider("sfx")
    mp = music_provider or config.default_provider("music")
    r = audio_stage.run(d, sp, mp, force=force)
    m.record("audio", done=True, provider=r.provider, cost_usd=r.cost_usd,
             latency_s=r.latency_s, note=r.note)
    manifest.save(d, m)
    console.print(f"[green]audio[/] {r.note}  ${r.cost_usd}")


@app.command()
def voice(run_id: str, provider: Optional[str] = None, voice_name: str = "",
          captions: str = "burn", music: Optional[Path] = None) -> None:
    """Stage 5 — TTS voiceover + captions, muxed over video."""
    d, m = _load(run_id)
    prov = provider or config.default_provider("voice")
    r = voice_stage.run(d, prov, voice=voice_name, captions=captions, music=music)
    m.record("voice", done=True, provider=prov, cost_usd=r.cost_usd, latency_s=r.latency_s,
             note=r.note)
    manifest.save(d, m)
    console.print(f"[green]voice[/] {r.note} via {prov}  ${r.cost_usd}")


@app.command()
def save(run_id: str) -> None:
    """Stage 6 — encode platform master + metadata."""
    d, m = _load(run_id)
    r = save_stage.run(d)
    m.record("save", done=True, provider=r.provider, note=r.note)
    manifest.save(d, m)
    console.print(f"[green]save[/] {r.path}")


@app.command()
def metadata(run_id: str, provider: Optional[str] = None) -> None:
    """SEO-polish title/description/tags for publishing → 06_final.json."""
    d, m = _load(run_id)
    prov = provider or config.default_provider("script")
    r = metadata_stage.run(d, prov)
    m.record("metadata", done=True, provider=prov, note=r.note)
    manifest.save(d, m)
    console.print(f"[green]metadata[/] {r.note}")


def _title_author(meta: dict, script_obj) -> tuple[str, str]:
    """Best-effort (title, author) for the thumbnail from metadata/topic.
    Splits on ' — '/' - '/' | ' and an 'X by Y' pattern."""
    import re as _re
    topic = (getattr(script_obj, "topic", "") or meta.get("title", "")).strip()
    author = ""
    m = _re.search(r"\bby\s+([A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,2})", topic)
    if m:
        author = m.group(1)
        topic = topic[:m.start()].rstrip(" ,—-|")
    parts = _re.split(r"\s+[—\-|]\s+", topic)
    title = parts[0].strip()
    if not author and len(parts) > 1:        # "Title — Author"
        author = parts[1].strip()
    title = _re.sub(r"^(a|an|the)\s+parable.*$", "", title, flags=_re.I).strip() or title
    return title, author


@app.command()
def thumbnail(run_id: str, at: float = 6.0, title: str = "", author: str = "",
              hook: str = "") -> None:
    """Generate a YouTube preview/thumbnail (06_thumb.png) from a hero frame of the
    master: a balanced hook + the AUTHOR/title. Auto-set when you `publish`. Override
    --title/--author/--hook or pick the source moment with --at <seconds>."""
    import json as _json

    from studio import ffmpeg
    from studio.models import Script
    from studio.providers import cardgen

    d, _ = _load(run_id)
    master = paths.master(d)
    if not master.exists():
        raise typer.BadParameter("no master; run save first")
    script_obj = Script.model_validate_json(paths.script_json(d).read_text())
    meta = _json.loads(paths.meta_json(d).read_text()) if paths.meta_json(d).exists() else {}
    auto_t, auto_a = _title_author(meta, script_obj)
    frame = d / "_thumb_src.png"
    ffmpeg.grab_frame(master, frame, at)
    cardgen.thumbnail(frame, paths.thumbnail(d), title or auto_t, author or auto_a, hook)
    frame.unlink(missing_ok=True)
    console.print(f"[green]thumbnail[/] {paths.thumbnail(d)}  "
                  f"(title={title or auto_t!r} author={author or auto_a!r})")


@app.command()
def publish(run_id: str, target: str = "youtube", privacy: str = "public",
            channel: str = "") -> None:
    """Stage 7 — optional publish. --channel NAME selects a per-channel token
    (token_<NAME>.json) for multi-channel accounts. Verify first with `yt-channel`."""
    d, m = _load(run_id)
    r = publish_stage.run(d, target, privacy=privacy, channel=channel)
    m.record("publish", done=True, provider=target, note=r.note)
    manifest.save(d, m)
    console.print(f"[green]published[/] {r.note}")


@app.command("yt-channel")
def yt_channel(channel: str = "") -> None:
    """Authorize (browser, first time) and print WHICH YouTube channel a token is
    bound to — verify before uploading. --channel NAME uses token_<NAME>.json."""
    from studio.providers import publish as pub
    info = pub.channel_info(channel)
    tok = pub._token_path(channel)
    console.print(f"[bold]token:[/] {tok}  →  [green]{info['title']}[/]  {info['url']}")


# ----------------------------------------------------------------------------- run
@app.command()
def run(idea: str, duration: int = 150, aspect: str = "9:16", with_voice: bool = True,
        style: str = "", tier: str = "balanced",
        script_provider: Optional[str] = None, image_provider: Optional[str] = None,
        cheap_image_provider: Optional[str] = None,
        video_strategy: Optional[str] = None, video_model: Optional[str] = None,
        voice_provider: Optional[str] = None, captions: str = "burn",
        voice_name: str = "", tone: str = "",
        sfx_provider: Optional[str] = None, music_provider: Optional[str] = None,
        transition: str = "cut", char_ref: Optional[Path] = None,
        ai_scenes: Optional[str] = None,
        publish_to: Optional[str] = None, privacy: str = "public", channel: str = "",
        from_stage: str = "script", to_stage: str = "save",
        run_id: Optional[str] = None, max_cost: float = 3.0) -> None:
    """Full pipeline idea -> master (+ optional publish), with resume.

    --tier free|cheap|balanced|premium sets all stage providers + video strategy;
    any --*-provider / --video-strategy / --video-model flag overrides the preset.
    Spend is capped by --max-cost (0 disables); the clips stage trims/aborts to fit.
    """
    p = tiers.preset(tier)
    sp = script_provider or p["script"]
    ip = image_provider or p["image"]
    icp = cheap_image_provider or p["image_cheap"]
    vp = voice_provider or p["voice"]
    sfxp = sfx_provider or p["sfx"]
    musicp = music_provider or p["music"]
    strat = "hybrid" if ai_scenes else (video_strategy or p["strategy"])
    vmodel = video_model or tiers.DEFAULT_MODEL_BY_TIER.get(tier, "kling")

    if run_id and manifest.manifest_path(paths.run_dir(run_id)).exists():
        rid = run_id  # resume an existing run
    else:
        rid = init(idea, duration, aspect, with_voice, style, tier, run_id=run_id)
    d, m = _load(rid)
    console.print(f"[dim]tier={tier} script={sp} image={ip}(hero)/{icp}(bg) "
                  f"video={strat}/{vmodel} voice={vp} max_cost=${max_cost}[/]")

    order = STAGE_ORDER[STAGE_ORDER.index(from_stage): STAGE_ORDER.index(to_stage) + 1]
    for stage in order:
        if m.is_done(stage) and run_id:  # resume only when reusing a run
            console.print(f"[dim]skip {stage} (done)[/]")
            continue
        console.print(f"[bold cyan]» {stage}[/]")
        if stage == "script":
            script(rid, sp)
        elif stage == "visuals":
            # balanced+ → generate separate bg plates so parallax is true layered 2.5D
            # (different fg/bg images); cheap/free → single image (parallax = clean pan).
            visuals(rid, ip, icp, char_ref, False, parallax_plates=tier in ("balanced", "premium"))
        elif stage == "narrate":
            if with_voice:
                narrate(rid, vp, voice_name, tone)
            else:
                console.print("[dim]skip narrate (no voice)[/]")
        elif stage == "clips":
            # hand the clips stage whatever budget remains after images.
            # 0.0 == guard disabled; a tiny floor keeps the guard ON (→ all kenburns).
            cap = 0.0 if not max_cost else max(0.0001, round(max_cost - m.total_cost_usd, 4))
            clips(rid, strat, vmodel, ai_scenes, cap, False)
        elif stage == "stitch":
            stitch(rid, transition)
        elif stage == "audio":
            if with_voice:
                audio(rid, sfxp, musicp, False)
            else:
                console.print("[dim]skip audio (no voice)[/]")
        elif stage == "voice":
            voice(rid, vp, "", captions, None)
        elif stage == "save":
            save(rid)
        _, m = _load(rid)

    if publish_to:
        metadata(rid, sp)        # SEO-polish title/desc/tags before upload
        publish(rid, publish_to, privacy, channel)
    console.print(f"[bold green]done[/] {rid}  total ${m.total_cost_usd}")


# -------------------------------------------------------------------------- status
@app.command()
def estimate(run_id: str, budget: float = 3.0) -> None:
    """Preview stage-3 video cost per model BEFORE spending, and how much fits `budget`."""
    from studio.models import Script
    from studio.providers import video as vid

    d, _ = _load(run_id)
    s = Script.model_validate_json(paths.script_json(d).read_text())
    secs = [sc.duration_s for sc in s.scenes]
    total_s = sum(secs)
    img_cost = round(0.039 * len(s.scenes), 3)  # Nano Banana stills (verified)

    t = Table(title=f"{run_id}: {len(s.scenes)} scenes, {total_s:.0f}s video  "
                    f"(+~${img_cost} Nano Banana stills)")
    for col in ("video model", "full-AI cost", "AI scenes within budget", "total (full-AI)"):
        t.add_column(col)
    t.add_row("kenburns (free)", "$0.0", "all (free)", f"${img_cost}")
    for name in ("ltx", "wan", "kling", "seedance", "hailuo"):
        full = round(sum(vid.estimate_cost("fal-i2v", name, x) for x in secs), 2)
        # greedily count scenes that fit (budget - images) at this model
        room, fit = budget - img_cost, 0
        for x in secs:
            c = vid.estimate_cost("fal-i2v", name, x)
            if room - c < 0:
                break
            room -= c
            fit += 1
        t.add_row(name, f"${full}", f"{fit}/{len(secs)} scenes", f"${round(full + img_cost, 2)}")
    console.print(t)
    console.print(f"[dim]Hybrid: animate only the hero scenes with --ai-scenes 1,7,15 "
                  f"(Ken-Burns the rest) to stay under ${budget}. Pre-flight aborts if over.[/]")


@app.command()
def status(run_id: str) -> None:
    """Show manifest: stages done, provider, cost, timing."""
    _, m = _load(run_id)
    t = Table(title=f"{m.id}  (total ${m.total_cost_usd})")
    for col in ("stage", "done", "provider", "cost", "latency", "note"):
        t.add_column(col)
    for stage in STAGE_ORDER + ["publish"]:
        r = m.stages.get(stage)
        if r:
            t.add_row(stage, "✓" if r.done else "·", r.provider,
                      f"${r.cost_usd}", f"{r.latency_s}s", r.note)
        else:
            t.add_row(stage, "·", "-", "-", "-", "-")
    console.print(t)


# ============================================================ marketing-guru loop
def _deploy_cmd(e, channel: str) -> str:
    """The film-maker command that turns a journal bet into a published Short."""
    idea = e.idea.replace('"', "'")
    ch = f" --channel {channel}" if channel else ""
    return (f'studio run "{idea}" --duration 60 --tier cheap '
            f'--publish-to youtube --privacy public{ch}')


@marketing_app.command("ideate")
def m_ideate(channel: str = "", provider: Optional[str] = None, n: int = 1,
             signals: Optional[Path] = None, niche: str = "") -> None:
    """Step 1 — generate the next viral bet(s) and record them in the journal.

    --signals FILE feeds live trend/narrative notes (the skill gathers these via web
    search). --niche sets the channel's theme once. Each idea is saved as a `planned`
    entry; the printed `studio run` command deploys it (step 2)."""
    from studio.marketing import ideate as mideate
    from studio.marketing import journal as mj

    j = mj.load(channel)
    prov = provider or config.default_provider("script")
    sig = signals.read_text() if signals and signals.exists() else ""
    ideas = mideate.generate(j, prov, n=n, signals=sig, niche=niche)
    for d in ideas:
        e = mj.Entry(id=j.next_id(), idea=d.get("idea", ""), hook=d.get("hook", ""),
                     assumption=d.get("assumption", ""), goal=d.get("goal", ""),
                     theme=d.get("theme", ""), tags=d.get("tags", []),
                     explore=j.in_cold_start)
        j.entries.append(e)
        console.print(f"[green]{e.id}[/] {e.idea}")
        console.print(f"  [dim]hook:[/] {e.hook}")
        console.print(f"  [dim]assumption:[/] {e.assumption}  [dim]goal:[/] {e.goal}")
        console.print(f"  [cyan]deploy →[/] {_deploy_cmd(e, channel)}")
    mj.save(j)
    if j.in_cold_start:
        console.print(f"[yellow]cold start:[/] {j.deployed_count}/{j.bootstrap_target} "
                      f"deployed — exploring; relative virality unlocks at {j.bootstrap_target}.")


@marketing_app.command("link")
def m_link(entry_id: str, run_id: str, channel: str = "") -> None:
    """Step 2 — attach a produced run (and its YouTube id) to a journal bet."""
    from studio.marketing import journal as mj
    from studio.providers import analytics

    j = mj.load(channel)
    e = j.get(entry_id)
    if not e:
        raise typer.BadParameter(f"no entry {entry_id} in {channel or 'default'} journal")
    e.run_id = run_id
    e.status = "deployed"
    pj = paths.publish_json(paths.run_dir(run_id))
    if pj.exists():
        import json as _json
        note = _json.loads(pj.read_text()).get("result", "")
        e.video_id = analytics.video_id_from_url(note)
        e.video_url = note.split()[0] if note else ""
    mj.save(j)
    console.print(f"[green]linked[/] {entry_id} → run {run_id}  video={e.video_id or '(none)'}")


@marketing_app.command("measure")
def m_measure(channel: str = "", comments_n: int = 60) -> None:
    """Step 3 — fetch stats + comments for deployed bets, score virality RELATIVE
    to this channel's portfolio, and write results back to the journal."""
    import json as _json

    from studio.marketing import journal as mj
    from studio.marketing import score as mscore
    from studio.providers import analytics

    j = mj.load(channel)
    targets = [e for e in j.entries if e.video_id and e.status in ("deployed", "measured")]
    if not targets:
        console.print("[yellow]nothing to measure[/] — link deployed runs first (`marketing link`).")
        return
    stats = analytics.video_stats([e.video_id for e in targets], channel)
    for e in targets:
        st = stats.get(e.video_id)
        if not st:
            continue
        m = mj.Metrics(views=st["views"], likes=st["likes"], comments=st["comments"],
                       age_days=st["age_days"], fetched_at=mj._now())
        m.retention = analytics.retention(e.video_id, channel)
        m.subs_gained = analytics.subs_gained(e.video_id, channel)
        mscore.derive(m)
        e.metrics = m
        e.published_at = e.published_at or st["published_at"]
        e.virality = mscore.virality(m)
        e.status = "measured"
        cmts = analytics.comments(e.video_id, channel, limit=comments_n)
        e.comments_sample = [c["text"] for c in cmts[:15]]
        if e.run_id:
            d = paths.run_dir(e.run_id)
            if d.exists():
                paths.stats_json(d).write_text(_json.dumps({**st, "virality": e.virality},
                                                           indent=2))
                paths.comments_json(d).write_text(_json.dumps(cmts, indent=2))
    # relativize across the whole measured portfolio
    measured = j.measured()
    pcts = mscore.relativize([e.virality for e in measured])
    for e, p in zip(measured, pcts):
        e.percentile = p
        e.outcome = mscore.outcome(p, j.in_cold_start)
    mj.save(j)
    _marketing_table(j)


@marketing_app.command("learn")
def m_learn(channel: str = "", provider: Optional[str] = None) -> None:
    """Step 3b — reflect on measured bets → update strategy + next idea seeds."""
    from studio.marketing import journal as mj
    from studio.marketing import learn as mlearn

    j = mj.load(channel)
    prov = provider or config.default_provider("script")
    note = mlearn.reflect(j, prov)
    mj.save(j)
    console.print(f"[green]learn[/] {note}")
    if j.strategy.current_direction:
        console.print(f"[bold]next direction:[/] {j.strategy.current_direction}")
    for s in j.strategy.next_seeds:
        console.print(f"  [dim]seed:[/] {s}")


@marketing_app.command("journal")
def m_journal(channel: str = "") -> None:
    """Show the growth journal — phase, strategy, and every bet's outcome."""
    from studio.marketing import journal as mj

    j = mj.load(channel)
    s = j.strategy
    phase = (f"COLD START {j.deployed_count}/{j.bootstrap_target}"
             if j.in_cold_start else f"OPTIMIZING ({j.deployed_count} deployed)")
    console.print(f"[bold]{channel or 'default'}[/] — {phase}")
    if s.current_direction:
        console.print(f"[bold]direction:[/] {s.current_direction}")
    if s.winning_patterns:
        console.print(f"[green]winning:[/] {'; '.join(s.winning_patterns)}")
    if s.losing_patterns:
        console.print(f"[red]losing:[/] {'; '.join(s.losing_patterns)}")
    _marketing_table(j)


@marketing_app.command("report")
def m_report(channel: str = "", provider: Optional[str] = None) -> None:
    """Write a full markdown growth brief (measure + learn rollup) to disk."""
    from studio.marketing import journal as mj
    from studio.marketing import learn as mlearn

    j = mj.load(channel)
    mlearn.reflect(j, provider or config.default_provider("script"))
    mj.save(j)
    out = paths.marketing_report_md(channel)
    out.write_text(mj.render_md(j))
    console.print(f"[green]report[/] {out}")


def _marketing_table(j) -> None:
    t = Table(title=f"journal: {j.channel or 'default'}  ({j.deployed_count} deployed)")
    for col in ("id", "status", "idea", "virality", "%ile", "outcome"):
        t.add_column(col)
    for e in j.entries:
        t.add_row(e.id, e.status, e.idea[:46],
                  "-" if e.virality is None else f"{e.virality:.3f}",
                  "-" if e.percentile is None else f"{e.percentile:.0f}",
                  e.outcome or "-")
    console.print(t)


if __name__ == "__main__":
    app()
