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
from studio.providers import audio as audio_costs  # expected_music_cost for whole-video budgeting
from studio.stages import audio as audio_stage
from studio.stages import clips as clips_stage
from studio.stages import critic as critic_stage
from studio.stages import metadata as metadata_stage
from studio.stages import narrate as narrate_stage
from studio.stages import publish as publish_stage
from studio.stages import save as save_stage
from studio.stages import script as script_stage
from studio.stages import stitch as stitch_stage
from studio.stages import storyboard as storyboard_stage
from studio.stages import visuals as visuals_stage
from studio.stages import voice as voice_stage

app = typer.Typer(add_completion=False, help="Automated short-video studio (faceless MVP).")
console = Console()

marketing_app = typer.Typer(add_completion=False,
                            help="marketing-guru — viral growth loop (ideate→deploy→measure→learn).")
app.add_typer(marketing_app, name="marketing")

guerrilla_app = typer.Typer(add_completion=False,
                            help="guerrilla-marketing — targeted commenting for indirect reach.")
app.add_typer(guerrilla_app, name="guerrilla")

watchlist_app = typer.Typer(add_completion=False, help="Manage target channels.")
guerrilla_app.add_typer(watchlist_app, name="watchlist")

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


# ------------------------------------------------------------------ story-illustrator
@app.command("characters-build")
def characters_build(name: str, root: Path = Path("characters"),
                     provider: str = "gemini", portrait: bool = False,
                     portrait_provider: str = "fal-nanobanana", style: str = "",
                     age_shift: int = 0) -> None:
    """Build (or rebuild) a character card from `<root>/<name>/` reference images.

    Vision pass → locked identity descriptor + the cleanest anchor image, written to
    card.json. --portrait additionally renders ONE neutral master portrait from the
    best reference (in --style) and makes it the sole anchor — the strongest
    anti-drift setup for a character reused across many scenes/videos."""
    from studio import characters as chars
    card = chars.build_card(root, name, provider=provider,
                            portrait_provider=portrait_provider if portrait else "",
                            style=style, age_shift=age_shift)
    console.print(f"[green]card[/] {chars.card_path(root, name)}")
    console.print(f"  anchor: {', '.join(card.canonical_refs)}  ({card.note})")
    console.print(f"  descriptor: {card.descriptor[:160]}")


@app.command("book-split")
def book_split(book_file: Path, pattern: str = r"^\s*(Глава|ГЛАВА|Chapter|CHAPTER|Часть)\s+\d+\s*$",
               out_dir: Optional[Path] = None, clean: bool = True) -> None:
    """Split a whole book (plain text) into per-chapter files for one-by-one publishing.

    PDF page furniture is stripped first (--no-clean to skip): form feeds, standalone
    page numbers, the per-page running head/footer, decorative separator lines, and
    hyphenated line breaks — narration must never read a page number aloud.

    Heading lines must match --pattern on a line of their own (table-of-contents lines
    with dot leaders are ignored automatically). Writes chNN.txt + index.json next to
    the book (or into --out-dir). Feed each chapter to `studio storyboard`."""
    import json as _json
    text = book_file.read_text()
    if clean:
        from studio.textclean import clean_pdf_text
        text = clean_pdf_text(text)
    rx = re.compile(pattern)
    lines = text.splitlines()
    marks = [i for i, ln in enumerate(lines) if rx.match(ln.strip())]
    if not marks:
        console.print(f"[red]no headings matched[/] {pattern}")
        raise typer.Exit(1)
    out = out_dir or book_file.parent
    out.mkdir(parents=True, exist_ok=True)
    index = []
    bounds = marks + [len(lines)]
    for n, (a, b) in enumerate(zip(marks, bounds[1:]), 1):
        body = "\n".join(lines[a:b]).strip()
        f = out / f"ch{n:02d}.txt"
        f.write_text(body)
        index.append({"n": n, "title": lines[a].strip(), "file": f.name,
                      "chars": len(body)})
    (out / "index.json").write_text(_json.dumps(index, ensure_ascii=False, indent=1))
    console.print(f"[green]split[/] {len(index)} chapters -> {out}/ch01..ch{len(index):02d}.txt")


@app.command("characters-extract")
def characters_extract(name: str, story_file: Path, root: Path = Path("characters"),
                       provider: str = "gemini", age_shift: int = 0) -> None:
    """Build a TEXT-DERIVED card for a character with no reference images.

    Analyzes the WHOLE story once, extracts every physical characteristic the prose
    gives, invents committed era-consistent specifics for the gaps, and locks the
    result in card.json — so the character keeps one constant shape across every
    scene instead of being re-imagined per image. (Storyboard --discover does this
    automatically for unknown recurring characters.)"""
    from studio import characters as chars
    card = chars.build_card_from_text(root, name, story_file.read_text(), provider=provider,
                                      age_shift=age_shift)
    console.print(f"[green]card[/] {chars.card_path(root, name)}  ({card.note})")
    console.print(f"  descriptor: {card.descriptor[:200]}")


@app.command()
def storyboard(story_file: Path, run_id: Optional[str] = None, duration: int = 600,
               aspect: str = "16:9", style: str = "", provider: Optional[str] = None,
               characters_root: Path = Path("characters"),
               voice_name: str = "narrator", tone: str = "neutral",
               tier: str = "balanced", discover: bool = True) -> None:
    """Story mode — segment EXISTING prose (story/audiobook text) into a scene script.

    Creates the run + writes 01_script.json with `characters:[...]`-tagged beats from
    the cards under --characters-root. Recurring characters WITHOUT a card get a
    text-derived one automatically (whole-story analysis → locked descriptor;
    --no-discover skips). Continue with the normal pipeline, passing the
    same root to visuals:

        studio visuals <run_id> --characters-root characters/
        studio narrate <run_id> && studio clips <run_id> ... (or `studio run` per stage)
    """
    story = story_file.read_text()
    rid = run_id or f"{datetime.now():%Y%m%d_%H%M%S}_{_slug(story_file.stem)}"
    d = paths.run_dir(rid)
    d.mkdir(parents=True, exist_ok=True)
    m = manifest.Manifest(id=rid, idea=f"storyboard:{story_file.name}",
                          duration_s=duration, aspect=aspect, voice=True, style=style,
                          tier=tier)
    prov = provider or config.default_provider("script")
    script, latency = storyboard_stage.run(d, story, duration, aspect, style, prov,
                                           voice_name=voice_name, tone=tone,
                                           roster_root=characters_root, discover=discover)
    m.record("script", done=True, provider=f"storyboard:{prov}", latency_s=latency,
             note=f"{len(script.scenes)} beats from {story_file.name}")
    manifest.save(d, m)
    tagged = sum(1 for s in script.scenes if s.characters)
    console.print(f"[green]storyboard[/] {rid}: {len(script.scenes)} beats "
                  f"({tagged} with characters)")


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


def _print_verdict(v) -> None:
    """Render a CriticVerdict to the console."""
    head = "[green]PASS[/]" if v.passed else "[red]DECLINE[/]"
    console.print(f"[bold]critic[/] {head} — {v.summary}")
    for c in v.scores:
        mark = "[green]✓[/]" if c.passed else "[red]✗[/]"
        console.print(f"  {mark} {c.name} ({c.score}/5): {c.feedback}")
    if not v.passed and v.revision_notes:
        console.print(f"  [yellow]revision:[/] {v.revision_notes}")


@app.command()
def critic(run_id: str, provider: Optional[str] = None) -> None:
    """Stage 1.5 — score the current scenario for CONTENT (topic revealed · fact explained ·
    informative+interesting · emotional payoff) BEFORE spending on visuals/clips."""
    from studio.models import Script

    d, m = _load(run_id)
    prov = provider or config.default_provider("script")
    s = Script.model_validate_json(paths.script_json(d).read_text())
    v, lat, cost = critic_stage.run(d, s, prov)
    note = "pass" if v.passed else f"decline: {v.summary}"
    m.record("critic", done=v.passed, provider=prov, cost_usd=cost, latency_s=lat, note=note)
    manifest.save(d, m)
    _print_verdict(v)
    if not v.passed:
        raise typer.Exit(1)


def _script_with_critic(rid: str, sp: str, mode: str, retries: int,
                        critic_provider: Optional[str] = None):
    """script → critic gate → re-script with feedback, up to `retries` times.

    mode: "off" (skip the gate) · "on" (gate; on exhaustion KEEP the best attempt and proceed) ·
    "strict" (gate; on exhaustion ABORT the run). Returns the chosen CriticVerdict or None.
    Never loops unbounded — at most `retries`+1 script generations.
    """
    if mode == "off" or sp == "stub":
        script(rid, sp)
        return None
    cprov = critic_provider or sp
    d, m = _load(rid)
    s, lat, cost = script_stage.run(d, m.idea, m.duration_s, m.aspect, m.voice, m.style, sp)
    m.record("script", done=True, provider=sp, cost_usd=cost, latency_s=lat, n=len(s.scenes))
    manifest.save(d, m)
    console.print(f"[green]script[/] {len(s.scenes)} scenes via {sp}")

    best, best_script, best_attempt = None, None, None
    vlat = 0.0
    for attempt in range(retries + 1):
        v, vlat, vcost = critic_stage.run(d, s, cprov)
        _print_verdict(v)
        if best is None or v.total > best.total:  # snapshot the best-scoring attempt's script
            best, best_script, best_attempt = v, s, attempt + 1
        if v.passed:
            m.record("critic", done=True, provider=cprov, cost_usd=vcost, latency_s=vlat,
                     note=f"pass (attempt {attempt + 1})")
            manifest.save(d, m)
            return v
        if attempt < retries:  # rewrite addressing the feedback, then re-critique
            console.print(f"[yellow]» re-script (critic attempt {attempt + 2}/{retries + 1})[/]")
            s, lat, cost = script_stage.run(d, m.idea, m.duration_s, m.aspect, m.voice,
                                            m.style, sp, revision_notes=v.revision_notes)
            m.record("script", done=True, provider=sp, cost_usd=cost, latency_s=lat, n=len(s.scenes))
            manifest.save(d, m)

    # retries exhausted, still failing — the best attempt may not be the one on disk now
    if best_script is not None:
        paths.script_json(d).write_text(best_script.model_dump_json(indent=2))
    if mode == "strict":
        m.record("critic", done=False, provider=cprov, latency_s=vlat,
                 note=f"FAILED after {retries + 1} attempts: {best.summary}")
        manifest.save(d, m)
        console.print(f"[red]critic gate failed after {retries + 1} attempts — aborting "
                      f"(--critic strict).[/] Best was attempt {best_attempt} ({best.total}/20).")
        raise typer.Exit(1)
    console.print(f"[yellow]critic still failing after {retries + 1} attempts — proceeding with "
                  f"best (attempt {best_attempt}, {best.total}/20). Review the scenario.[/]")
    m.record("critic", done=False, provider=cprov, latency_s=vlat,
             note=f"proceed-best attempt {best_attempt} ({best.total}/20): {best.summary}")
    manifest.save(d, m)
    return best


@app.command()
def visuals(run_id: str, provider: Optional[str] = None,
            cheap_provider: Optional[str] = None,
            char_ref: Optional[Path] = None, force: bool = False,
            parallax_plates: bool = False, parallax_fg: bool = False,
            characters_root: Optional[Path] = None, verify_chars: bool = True) -> None:
    """Stage 2 — keyframe image per scene. Scenes with image_role="bg" use
    --cheap-provider (cheaper model for backgrounds/overlays); hero/character use
    --provider (quality + character ref).

    --parallax-plates: also generate a separate background plate (subject removed) for
    each animator:"parallax" scene → true layered 2.5D (no torn frame). +1 image/scene.
    --parallax-fg: also generate a separate FOREGROUND plate (subject on a flat bg, keyed
    to transparency) for a cleaner cutout than rembg-ing the busy still (Route 1).
    +1 image/scene; pair with --parallax-plates for fully purpose-built layers.

    --characters-root characters/: scenes tagged `characters:[...]` use each named
    card's canonical anchor image(s) + locked descriptor (story-illustrator mode);
    --no-verify-chars skips the per-scene vision drift check."""
    d, m = _load(run_id)
    prov = provider or config.default_provider("visuals")
    cheap = cheap_provider or config.default_provider("visuals_cheap")
    r = visuals_stage.run(d, prov, char_ref=char_ref, force=force, cheap_provider=cheap,
                          parallax_plates=parallax_plates, parallax_fg=parallax_fg,
                          characters_root=characters_root, verify_chars=verify_chars)
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
            tone: str = "", continuous: bool = False) -> None:
    """Pre-clips TTS: synth each scene, derive clip durations + aligned captions.

    --voice man|woman|cartoon|narrator  --tone neutral|serious|mystical|friendly|sad|excited
    (per-scene `tone` in the scenario overrides). See docs/30-animation/voices.md.
    """
    d, m = _load(run_id)
    prov = provider or config.default_provider("voice")
    r = narrate_stage.run(d, prov, voice_name=voice, tone=tone, continuous=continuous)
    m.record("narrate", done=True, provider=prov, cost_usd=r.cost_usd,
             latency_s=r.latency_s, note=r.note)
    manifest.save(d, m)
    console.print(f"[green]narrate[/] {r.note} via {prov}")


@app.command()
def clips(run_id: str, strategy: str = "auto", model: str = "kling",
          ai_scenes: Optional[str] = None, max_cost: float = 3.0,
          force: bool = False, video_provider: str = "fal-i2v") -> None:
    """Stage 3 — video clips. --strategy kenburns|all|hybrid|auto.

    kenburns=free, all=AI every scene, hybrid=--ai-scenes 1,7,15, auto=smart fill
    within --max-cost. Per-second AI cost is estimated and the stage ABORTS/trims so
    spend never exceeds --max-cost (0 disables). Preview with `studio estimate`.

    --video-provider local-i2v renders AI scenes FREE on a local ComfyUI server
    (slow; pair with --model wan-local|ltx-local). Default fal-i2v (hosted, paid).
    """
    d, m = _load(run_id)
    if ai_scenes:
        strategy = "hybrid"
    if video_provider == "local-i2v" and model not in ("wan-local", "ltx-local"):
        model = "wan-local"
    r = clips_stage.run(d, strategy=strategy, model=model,
                        ai_scene_ids=_parse_ids(ai_scenes), max_cost=max_cost or None,
                        force=force, ai_provider=video_provider)
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
          captions: str = "off", music: Optional[Path] = None) -> None:
    """Stage 5 — TTS voiceover, muxed over video. Captions OFF by default
    (YouTube auto-generates them); pass --captions burn to hard-burn them in."""
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


@app.command("unlist")
def unlist(video_id: str, channel: str = "", privacy: str = "unlisted") -> None:
    """Flip an existing YouTube video's privacy (default: unlisted) — retire an old version
    when a re-make replaces it. Needs the youtube.force-ssl scope; if the token predates it,
    the first run re-opens the browser consent. --channel uses token_<NAME>.json."""
    from studio.providers import publish as pub
    status = pub.set_privacy(video_id, privacy, channel)
    console.print(f"[green]{video_id}[/] → {status}")
    # propagate to marketing stats: unlisted/private videos must not count toward
    # percentiles, the bandit, or learning (SLO-39). Recompute over the public portfolio.
    from studio.marketing import journal as mj
    from studio.marketing import score as mscore
    j = mj.load(channel)
    e = next((x for x in j.entries if x.video_id == video_id), None)
    if e is not None:
        e.unlisted = privacy != "public"
        measured = j.measured()
        for x, p in zip(measured, mscore.relativize([x.virality for x in measured])):
            x.percentile = p
            x.outcome = mscore.outcome(p, j.in_cold_start)
        mj.save(j)
        console.print(f"[dim]journal {e.id}: unlisted={e.unlisted} → stats recomputed over "
                      f"{len(measured)} public videos[/]")


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
        video_provider: str = "fal-i2v",
        voice_provider: Optional[str] = None, captions: str = "off",
        voice_name: str = "", tone: str = "",
        sfx_provider: Optional[str] = None, music_provider: Optional[str] = None,
        transition: str = "cut", char_ref: Optional[Path] = None,
        ai_scenes: Optional[str] = None,
        publish_to: Optional[str] = None, privacy: str = "public", channel: str = "",
        from_stage: str = "script", to_stage: str = "save",
        run_id: Optional[str] = None, max_cost: float = 3.0,
        critic: str = "on", critic_retries: int = 2,
        critic_provider: Optional[str] = None) -> None:
    """Full pipeline idea -> master (+ optional publish), with resume.

    --tier free|cheap|balanced|premium sets all stage providers + video strategy;
    any --*-provider / --video-strategy / --video-model flag overrides the preset.
    Spend is capped by --max-cost (0 disables); the clips stage trims/aborts to fit.

    --critic on|off|strict gates the SCENARIO on content (topic revealed · fact explained ·
    informative+interesting · emotion) before any paid visuals/clips. "on" (default) reworks
    the script up to --critic-retries times, then proceeds with the best attempt; "strict"
    aborts if it still fails; "off" skips the gate. Cheap (LLM-only); --script-provider stub
    skips it. This is what stops the cron autopilot shipping uninformative videos.
    """
    p = tiers.preset(tier)
    # script falls through to the real-LLM default unless the tier pins it (free→stub).
    sp = script_provider or p.get("script") or config.default_provider("script")
    ip = image_provider or p["image"]
    icp = cheap_image_provider or p["image_cheap"]
    vp = voice_provider or p["voice"]
    sfxp = sfx_provider or p["sfx"]
    musicp = music_provider or p["music"]
    strat = "hybrid" if ai_scenes else (video_strategy or p["strategy"])
    vmodel = video_model or ("wan-local" if video_provider == "local-i2v"
                             else tiers.DEFAULT_MODEL_BY_TIER.get(tier, "kling"))

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
            _script_with_critic(rid, sp, critic, critic_retries, critic_provider)
        elif stage == "visuals":
            # balanced+ → generate separate fg (transparent subject) + bg (subject removed)
            # plates so parallax composites two REAL images (no inpaint, no torn frame);
            # cheap/free → single image (parallax = layered drift / clean pan).
            plates = tier in ("balanced", "premium")
            visuals(rid, ip, icp, char_ref, False, parallax_plates=plates, parallax_fg=plates)
        elif stage == "narrate":
            if with_voice:
                narrate(rid, vp, voice_name, tone)
            else:
                console.print("[dim]skip narrate (no voice)[/]")
        elif stage == "clips":
            # Budget is for the WHOLE video. Reserve the music bed (if paid) so the
            # clips stage leaves room for it. 0.0 == guard disabled; a tiny floor keeps
            # the guard ON (→ all kenburns).
            music_reserve = audio_costs.expected_music_cost(musicp) if with_voice else 0.0
            cap = 0.0 if not max_cost else max(0.0001, round(max_cost - m.total_cost_usd - music_reserve, 4))
            clips(rid, strat, vmodel, ai_scenes, cap, False, video_provider)
        elif stage == "stitch":
            stitch(rid, transition)
        elif stage == "audio":
            if with_voice:
                from studio.models import Script

                d, m = _load(rid)
                script = Script.model_validate_json(paths.script_json(d).read_text())

                # Count total SFX cues across all scenes
                total_sfx = sum(len(s.sfx) for s in script.scenes)
                # Estimate average SFX duration (conservative: 2.0s per cue)
                estimated_audio_cost = audio_costs.estimate_total_audio_cost(
                    sfxp, musicp, n_sfx=total_sfx, avg_sfx_seconds=2.0
                )
                remaining_budget = None if not max_cost else round(max_cost - m.total_cost_usd, 4)

                # Pre-spend gate: abort if budget insufficient
                if remaining_budget is not None and estimated_audio_cost > remaining_budget + 1e-9:
                    deficit = estimated_audio_cost - remaining_budget
                    ch_name = channel or "default"
                    raise RuntimeError(
                        f"audio budget gate — insufficient budget for audio stage\n"
                        f"  channel: {ch_name}\n"
                        f"  remaining budget: ${remaining_budget:.4f}\n"
                        f"  estimated cost ({total_sfx} SFX @ {sfxp}, {musicp}): ${estimated_audio_cost:.4f}\n"
                        f"  deficit: ${deficit:.4f}\n"
                        f"→ reduce SFX count, use free providers (freesound/local/silence), or increase budget cap"
                    )

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


# --------------------------------------------------------------------------- brand
@app.command()
def brand(spec: Path, provider: str = "fal-nanobanana") -> None:
    """Generate a channel BRAND KIT from a brand-spec JSON → runs/_brand/<slug>/.

    Produces banner.png (2560x1440 + exact wordmark), profile.png (1024²),
    logo.png + logo_512.png (transparent, watermark), and brand.md (keywords +
    description). The art is requested TEXT-FREE and the wordmark is composited in
    Pillow so spelling/placement are exact. ~$0.12 on fal (3 Nano Banana stills);
    use --provider stub for a free offline wiring test (writes to the spec's slug —
    use a throwaway slug so it doesn't overwrite a real kit).

    Part of the marketing-guru family — see the `youtube-branding` skill for how to
    author the spec (palette, emblem, banner scene) and review the output.
    """
    import json

    from studio.marketing import brand as brand_mod

    data = json.loads(spec.read_text())
    res = brand_mod.build_brand(data, provider=provider)
    console.print(f"[bold]brand kit[/] → {res['out']}   [dim](image spend ${res['cost_usd']})[/]")
    for name, path in res["assets"].items():
        console.print(f"  [green]{name}[/]  {path}")
    console.print(f"\n[bold]keywords:[/] {res['keywords']}")
    console.print(f"\n[bold]description:[/]\n{res['description']}")


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
                     explore=j.in_cold_start, playbook_version=j.playbook_version)
        j.entries.append(e)
        console.print(f"[green]{e.id}[/] {e.idea}")
        console.print(f"  [dim]hook:[/] {e.hook}")
        console.print(f"  [dim]assumption:[/] {e.assumption}  [dim]goal:[/] {e.goal}")
        console.print(f"  [cyan]deploy →[/] {_deploy_cmd(e, channel)}")
    mj.save(j)
    if j.in_cold_start:
        console.print(f"[yellow]cold start:[/] {j.deployed_count}/{j.bootstrap_target} "
                      f"deployed — exploring; relative virality unlocks at {j.bootstrap_target}.")


@marketing_app.command("add")
def m_add(idea: str, channel: str = "", hook: str = "", assumption: str = "",
          goal: str = "", theme: str = "", tags: str = "", exploit: bool = False) -> None:
    """Helper (NO LLM) — append ONE agent-authored bet to the backlog as a `planned` entry.

    Use when the AGENT did the ideation (skill-driven) and just needs to persist it safely
    (correct id, schema, journal.md re-render). `--tags` is comma-separated; `--exploit`
    marks an exploitation bet (default = exploration). Scripts are helpers; the thinking is
    the agent's."""
    from studio.marketing import journal as mj

    j = mj.load(channel)
    e = mj.Entry(id=j.next_id(), idea=idea, hook=hook, assumption=assumption, goal=goal,
                 theme=theme, tags=[t.strip() for t in tags.split(",") if t.strip()],
                 explore=not exploit, playbook_version=j.playbook_version)
    j.entries.append(e)
    mj.save(j)
    console.print(f"[green]{e.id}[/] queued (planned) — {e.idea}")
    console.print(f"  [cyan]deploy →[/] {_deploy_cmd(e, channel)}")


@marketing_app.command("backlog")
def m_backlog(channel: str = "") -> None:
    """Helper (NO LLM) — list the backlog (planned, not-yet-deployed bets) for the agent to
    pick from. Prioritization (the 60/40 explore/exploit pull) is the AGENT's decision — this
    only shows the queue + the current explore/exploit balance."""
    from studio.marketing import journal as mj

    j = mj.load(channel)
    planned = [e for e in j.entries if e.status == "planned"]
    if not planned:
        console.print("[dim](backlog empty — run ideate / marketing add)[/]")
        return
    n_expl = sum(1 for e in planned if e.explore)
    console.print(f"[bold]backlog[/] — {len(planned)} planned "
                  f"({n_expl} explore / {len(planned) - n_expl} exploit)")
    for e in planned:
        kind = "explore" if e.explore else "exploit"
        console.print(f"[green]{e.id}[/] [{kind}] {e.idea}  [dim]{e.theme}[/]")


@marketing_app.command("recall")
def m_recall(query: str, channel: str = "", k: int = 6) -> None:
    """Helper (NO LLM) — retrieve the past MEASURED bets most RELEVANT to `query` (episodic
    memory). Feed these lessons into agent-driven ideate/learn so the next bet reflects what
    actually worked, not just what's recent. Empty until videos are measured."""
    from studio.marketing import journal as mj
    from studio.marketing import memory

    j = mj.load(channel)
    block = memory.recall_block(j, query, k=k)
    console.print(block or "[dim](nothing measured yet — explore)[/]")


@marketing_app.command("exclude")
def m_exclude(entry_id: str, channel: str = "", restore: bool = typer.Option(False, "--restore"),
              deleted: bool = typer.Option(False, "--deleted")) -> None:
    """Exclude (or --restore) a bet from channel statistics (SLO-39).

    Use when a video is unlisted/private/removed on YouTube so its metrics must NOT skew
    percentiles, the bandit, or learning. Marks the journal entry `unlisted` (or `--deleted`
    to retire it), then recomputes percentiles over the remaining public portfolio. The
    `studio unlist` command does this automatically when you flip YouTube privacy."""
    from studio.marketing import journal as mj
    from studio.marketing import score as mscore

    j = mj.load(channel)
    e = j.get(entry_id)
    if e is None:
        console.print(f"[red]no entry {entry_id}[/]")
        raise typer.Exit(1)
    val = not restore
    if deleted:
        e.deleted = val
    else:
        e.unlisted = val
    measured = j.measured()
    for x, p in zip(measured, mscore.relativize([x.virality for x in measured])):
        x.percentile = p
        x.outcome = mscore.outcome(p, j.in_cold_start)
    mj.save(j)
    flag = "deleted" if deleted else "unlisted"
    console.print(f"[green]{entry_id}[/] {flag}={val} — stats recomputed over "
                  f"{len(measured)} public videos")


@marketing_app.command("strategy")
def m_strategy(channel: str = "", direction: str = "", winning: str = "", losing: str = "",
               seeds: str = "", niche: str = "", note: str = "") -> None:
    """Helper (NO LLM) — persist an AGENT's reflection into the journal's long-term strategy.

    The agent does the thinking (which assumptions held, what pattern wins) then records it
    here. Semicolon-separated lists for --winning/--losing/--seeds. `--note ENTRY_ID=text`
    files a per-bet learning. Only non-empty fields are written; omit to leave a field as-is."""
    from studio.marketing import journal as mj

    j = mj.load(channel)
    s = j.strategy
    if niche:
        s.niche = niche
    if direction:
        s.current_direction = direction
    if winning:
        s.winning_patterns = [x.strip() for x in winning.split(";") if x.strip()]
    if losing:
        s.losing_patterns = [x.strip() for x in losing.split(";") if x.strip()]
    if seeds:
        s.next_seeds = [x.strip() for x in seeds.split(";") if x.strip()]
    if direction or winning or losing or seeds or niche:
        s.updated_at = mj._now()
    if note and "=" in note:
        eid, _, text = note.partition("=")
        e = j.get(eid.strip())
        if e:
            e.learnings = text.strip()
        else:
            console.print(f"[yellow]no entry {eid.strip()} — note skipped[/]")
    mj.save(j)
    console.print(f"[green]strategy updated[/] — {channel or 'default'}")


@marketing_app.command("set-playbook-version")
def m_set_playbook_version(version: str, channel: str = "") -> None:
    """Record the current agent instruction version in the journal.

    Stamp this whenever Growth Lead or Screenwriter instructions change. New bets
    created after this call inherit the version; `learn` groups outcomes by version
    for A/B attribution so the CEO can compare instruction revisions head-to-head."""
    from studio.marketing import journal as mj

    j = mj.load(channel)
    j.playbook_version = version
    mj.save(j)
    console.print(f"[green]playbook version set[/] → {version!r} ({channel or 'default'})")


@marketing_app.command("drift")
def m_drift(channel: str = "", notify: bool = typer.Option(False, "--notify")) -> None:
    """Scan the journal for strategy drift (topic collapse / safety erosion).

    Prints any detected signals. Pass --notify to send a Telegram alert.
    Never modifies the strategy — flags for CEO review only."""
    from studio.marketing import drift as mdrift
    from studio.marketing import journal as mj

    j = mj.load(channel)
    signals = mdrift.detect(j)
    if not signals:
        console.print("[green]no drift detected[/]")
        return
    console.print("[yellow bold]drift signals:[/]")
    for s in signals:
        console.print(f"  [yellow]• {s}[/]")
    if notify:
        sent = mdrift.notify_drift(signals, channel)
        console.print("[dim]Telegram alert sent.[/]" if sent else "[dim]Telegram not configured.[/]")


@marketing_app.command("budget")
def m_budget(channel: str = "", per_video: Optional[float] = None,
             per_minute: Optional[float] = None, for_duration: float = 0.0,
             max_per_video: Optional[float] = None, daily: Optional[float] = None,
             slots: str = "") -> None:
    """Set / show the channel's per-video spend budget, or compute a video's --max-cost.

    Set ONE of: `--per-video 0.60` (flat cap per video) or `--per-minute 0.40` (rate × video
    length). `--for-duration 90` prints the --max-cost for a 90s video (pipe into `studio run`).
    No args → show the current budget + example caps."""
    from studio.marketing import journal as mj

    j = mj.load(channel)
    if per_video is not None and per_minute is not None:
        raise typer.BadParameter("set only one of --per-video / --per-minute")
    if per_video is not None:
        j.budget.mode, j.budget.amount = "per_video", round(per_video, 4)
        mj.save(j)
    elif per_minute is not None:
        j.budget.mode, j.budget.amount = "per_minute", round(per_minute, 4)
        mj.save(j)
    if max_per_video is not None:
        j.budget.max_per_video = round(max_per_video, 4)
        mj.save(j)
    if daily is not None:
        j.budget.daily_amount = round(daily, 4)
        mj.save(j)
    if slots:
        j.budget.slot_caps = [round(float(x.strip()), 4) for x in slots.split(",") if x.strip()]
        mj.save(j)

    if for_duration > 0:  # compute-and-print mode (for the deploy skill / driver)
        cap = j.budget.cap_for(for_duration)
        console.print(f"{cap:.4f}" if cap is not None else "[yellow](budget unset)[/]")
        return

    console.print(f"[bold]budget[/] ({channel or 'default'}): {j.budget.describe()}")
    if j.budget.mode:
        caps = "  ".join(f"{d}s→${j.budget.cap_for(d):.2f}" for d in (30, 60, 90, 150))
        console.print(f"  [dim]--max-cost by length:[/] {caps}")
    else:
        console.print("  [dim]set with[/] studio marketing budget --per-video 0.50  "
                      "[dim]or[/] --per-minute 0.40")


@marketing_app.command("bandit")
def m_bandit(channel: str = "", top: int = 12) -> None:
    """Show what the next-bet bandit has learned (T8): each theme/tag feature's win-probability
    (Beta posterior mean) from measured history, and how it would rank the current backlog."""
    from studio.marketing import bandit as mbandit
    from studio.marketing import journal as mj

    j = mj.load(channel)
    stats = mbandit.posteriors(j.measured(), j.loop.prior_strength)
    rows = sorted(((a / (a + b), n, a, b) for n, (a, b) in stats.items()),
                  key=lambda r: r[0], reverse=True)[:top]
    console.print(f"[bold]bandit[/] ({channel or 'default'}) — feature win-rates "
                  f"[dim](prior strength {j.loop.prior_strength})[/]")
    if not rows:
        console.print("  [dim](no measured signal yet — picks are exploratory)[/]")
    for mean, (dim, val), a, b in rows:
        console.print(f"  {mean:5.2f}  [cyan]{dim}[/]={val}  [dim]α={a:.0f} β={b:.0f}[/]")
    planned = [e for e in j.entries if e.status == "planned"]
    if planned:
        import random as _r
        order = mbandit.rank(planned, j.measured(), j.loop.prior_strength,
                             _r.Random(len(j.entries) * 1000 + len(j.measured())))
        console.print("  [dim]backlog rank →[/] " + " > ".join(e.id for e in order[:6]))


@marketing_app.command("tick")
def m_tick(channel: str = "", json_out: bool = typer.Option(False, "--json")) -> None:
    """Show the autonomous loop's NEXT due action (read-only decision; T1). The driver
    (`autopilot` / the marketing-autopilot skill / cron) acts on this, then ticks again."""
    from studio.marketing import journal as mj
    from studio.marketing import loop as mloop

    p = mloop.plan(mj.load(channel))
    if json_out:
        console.print_json(p.model_dump_json())
        return
    console.print(f"[bold]tick[/] ({channel or 'default'}) — phase={p.phase}")
    console.print(f"  next: [cyan]{p.next}[/] — {p.note}")
    if p.measure_due:
        console.print(f"  measure_due: {', '.join(p.measure_due)}")
    if p.next == "produce":
        cap = "?" if p.produce_max_cost is None else f"${p.produce_max_cost:.2f}"
        console.print(f"  → produce {p.produce_entry} (--duration {p.target_duration_s}, --max-cost {cap})")


@marketing_app.command("autopilot")
def m_autopilot(channel: str = "", provider: Optional[str] = None, produce: bool = False,
                tier: str = "balanced") -> None:
    """Run ONE tick of the autonomous loop: perform the single due action (measure | learn |
    ideate | produce | idle), then return. Schedule it (cron / the /loop skill /
    marketing-autopilot) to run the loop continuously — the deferred-measurement timing is
    handled by the engine. Producing spends money + publishes, so it is GATED behind --produce.

    Uses the SCRIPTED ideate/learn fallbacks; for smarter agent-driven steps use the
    marketing-autopilot skill instead."""
    import subprocess
    from datetime import datetime

    from studio.marketing import journal as mj
    from studio.marketing import loop as mloop

    j = mj.load(channel)
    p = mloop.plan(j)
    prov = provider or config.default_provider("script")
    console.print(f"[bold]autopilot[/] ({channel or 'default'}) → [cyan]{p.next}[/]: {p.note}")

    if p.next == "measure":
        m_measure(channel=channel)
    elif p.next == "learn":
        m_learn(channel=channel, provider=prov)
        j = mj.load(channel)
        j.last_learn_at = mj._now()
        mj.save(j)
    elif p.next == "ideate":
        m_ideate(channel=channel, provider=prov, n=3)
    elif p.next == "produce":
        e = j.get(p.produce_entry)
        cap = p.produce_max_cost if p.produce_max_cost is not None else 3.0
        ch = f" --channel {channel}" if channel else ""
        if not produce:
            console.print("[yellow]produce gated[/] — re-run with --produce, or run manually:")
            console.print(f'  studio run "{e.idea}" --duration {p.target_duration_s} --tier {tier} '
                          f'--max-cost {cap} --publish-to youtube --privacy public{ch}')
            console.print(f"  then: studio marketing link {e.id} <run_id>{ch}")
            return
        slug = re.sub(r"[^a-z0-9]+", "-", e.idea.lower())[:24].strip("-")
        rid = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug}"
        cmd = ["studio", "run", e.idea, "--duration", str(p.target_duration_s), "--tier", tier,
               "--max-cost", str(cap), "--publish-to", "youtube", "--privacy", "public",
               "--run-id", rid]
        if channel:
            cmd += ["--channel", channel]
        console.print(f"[dim]$ {' '.join(cmd)}[/]")
        r = subprocess.run(cmd, text=True)
        if r.returncode == 0:
            m_link(entry_id=e.id, run_id=rid, channel=channel)
        else:
            console.print(f"[red]produce failed[/] (exit {r.returncode}) — bet {e.id} left planned")


@marketing_app.command("link")
def m_link(entry_id: str, run_id: str, channel: str = "") -> None:
    """Step 2 — attach a produced run (and its YouTube id) to a journal bet.

    Also captures production telemetry (cost, duration, animators/fx/model, providers) from the
    run manifest into the bet — so `learn` can attribute success to the effects used (T3)."""
    from studio.marketing import journal as mj
    from studio.marketing import telemetry as mtel
    from studio.providers import analytics

    j = mj.load(channel)
    e = j.get(entry_id)
    if not e:
        raise typer.BadParameter(f"no entry {entry_id} in {channel or 'default'} journal")
    rd = paths.run_dir(run_id)
    e.run_id = run_id
    e.status = "deployed"
    if not e.published_at:
        e.published_at = mj._now()       # starts the maturation clock for the autopilot (T1)
    pj = paths.publish_json(rd)
    if pj.exists():
        import json as _json
        note = _json.loads(pj.read_text()).get("result", "")
        e.video_id = analytics.video_id_from_url(note)
        e.video_url = note.split()[0] if note else ""
    for k, v in mtel.from_run(rd).items():       # production telemetry (best-effort)
        setattr(e, k, v)
    mj.save(j)
    cost = f"${e.cost_usd:.2f}" if e.cost_usd else "?"
    console.print(f"[green]linked[/] {entry_id} → run {run_id}  video={e.video_id or '(none)'}  "
                  f"cost={cost} dur={e.duration_s:.0f}s model={e.video_model or '-'}")


@marketing_app.command("measure")
def m_measure(channel: str = "", comments_n: int = 60, force: bool = False) -> None:
    """Step 3 — fetch stats + comments for deployed bets, score virality RELATIVE
    to this channel's portfolio, and write results back to the journal.

    Videos younger than `loop.maturation_hours` are SKIPPED (their view/retention
    numbers haven't stabilized — measuring them early produces false verdicts that
    then poison `learn`). Pass `--force` to measure regardless of age."""
    import json as _json

    from studio.marketing import journal as mj
    from studio.marketing import score as mscore
    from studio.providers import analytics

    j = mj.load(channel)
    targets = [e for e in j.entries
               if e.video_id and e.status in ("deployed", "measured") and not e.deleted]
    if not targets:
        console.print("[yellow]nothing to measure[/] — link deployed runs first (`marketing link`).")
        return
    maturation_days = j.loop.maturation_hours / 24.0
    stats = analytics.video_stats([e.video_id for e in targets], channel)
    skipped = []
    for e in targets:
        st = stats.get(e.video_id)
        if not st:
            continue
        if not force and st["age_days"] < maturation_days:
            skipped.append((e.id, st["age_days"]))
            continue
        m = mj.Metrics(views=st["views"], likes=st["likes"], comments=st["comments"],
                       age_days=st["age_days"], fetched_at=mj._now())
        m.retention = analytics.retention(e.video_id, channel)
        m.subs_gained = analytics.subs_gained(e.video_id, channel)
        mscore.derive(m)
        e.metrics = m
        # append an age-bucketed snapshot so metrics form a time series (3d→7d→30d
        # growth curves, age-normalized velocity) instead of one overwritten number.
        # Re-measuring inside the same bucket replaces that bucket's snapshot.
        bucket = min((("1d", 1), ("3d", 3), ("7d", 7), ("14d", 14), ("30d", 30)),
                     key=lambda b: abs(st["age_days"] - b[1]))[0]
        snap = mj.MetricSnapshot(**m.model_dump(), bucket=bucket)
        e.snapshots = [s for s in e.snapshots if s.bucket != bucket] + [snap]
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
    if skipped:
        names = ", ".join(f"{eid} ({age:.1f}d)" for eid, age in skipped)
        console.print(f"[yellow]skipped {len(skipped)} too-young (< {maturation_days:.1f}d "
                      f"maturation)[/]: {names} — re-run after they age, or --force")
    _marketing_table(j)


@marketing_app.command("due-snapshots")
def m_due_snapshots(channel: str = "", buckets: str = "1,3,7,14,30") -> None:
    """Show which deployed/measured videos are due for age-bucket snapshots."""
    from studio.marketing import analytics_tools as mat
    from studio.marketing import journal as mj

    due = mat.due_entries(mj.load(channel), mat.parse_buckets(buckets))
    t = Table(title=f"due snapshots: {channel or 'default'}")
    for col in ("id", "video", "age", "due buckets"):
        t.add_column(col)
    for row in due:
        t.add_row(row["id"], row["video_id"], f"{row['age_days']:.1f}d", ", ".join(row["due"]))
    console.print(t)
    if not due:
        console.print("[green]no snapshot buckets due[/]")


@marketing_app.command("snapshots")
def m_snapshots(channel: str = "", buckets: str = "1,3,7,14,30", force: bool = False) -> None:
    """Fetch and persist post-publish age-bucket metric snapshots.

    Buckets default to 1d,3d,7d,14d,30d. A bucket is written once when a video is old enough;
    --force refreshes all eligible buckets. Latest metrics are also refreshed for compatibility.
    """
    from studio.marketing import analytics_tools as mat
    from studio.marketing import journal as mj
    from studio.marketing import score as mscore
    from studio.providers import analytics

    j = mj.load(channel)
    bucket_days = mat.parse_buckets(buckets)
    targets = [e for e in j.entries
               if e.video_id and e.status in ("deployed", "measured") and not e.deleted]
    stats = analytics.video_stats([e.video_id for e in targets], channel)
    written: list[tuple[str, list[str]]] = []
    for e in targets:
        st = stats.get(e.video_id)
        if not st:
            continue
        latest = mj.Metrics(views=st["views"], likes=st["likes"], comments=st["comments"],
                            age_days=st["age_days"], fetched_at=mj._now())
        latest.retention = analytics.retention(e.video_id, channel)
        latest.subs_gained = analytics.subs_gained(e.video_id, channel)
        mscore.derive(latest)
        e.metrics = latest
        e.published_at = e.published_at or st["published_at"]
        e.virality = mscore.virality(latest)
        e.status = "measured"
        due = [mat.bucket_name(b) for b in bucket_days if latest.age_days >= b] if force else (
            mat.buckets_to_write(e, latest.age_days, bucket_days)
        )
        for b in due:
            snap = mj.MetricSnapshot(bucket=b, **latest.model_dump())
            mat.upsert_snapshot(e, b, snap)
        if due:
            written.append((e.id, due))

    measured = j.measured()
    pcts = mscore.relativize([e.virality for e in measured])
    for e, p in zip(measured, pcts):
        e.percentile = p
        e.outcome = mscore.outcome(p, j.in_cold_start)
    mj.save(j)

    t = Table(title=f"snapshots written: {channel or 'default'}")
    for col in ("id", "buckets"):
        t.add_column(col)
    for eid, bs in written:
        t.add_row(eid, ", ".join(bs))
    console.print(t)
    if not written:
        console.print("[yellow]no eligible missing buckets[/]")


@marketing_app.command("slice")
def m_slice(channel: str = "", bucket: str = "latest", group_by: str = "theme",
            metric: str = "virality", min_n: int = 1, json_out: bool = typer.Option(False, "--json")) -> None:
    """Slice measured performance by theme/effects/animators/music/sfx/model/cost features."""
    from studio.marketing import analytics_tools as mat
    from studio.marketing import journal as mj

    j = mj.load(channel)
    groups = [g.strip() for g in group_by.split(",") if g.strip()]
    rows = [r for r in mat.slice_entries(j.entries, groups, metric, bucket) if r.n >= min_n]
    if json_out:
        console.print_json(mat.to_json([r.__dict__ for r in rows]))
        return
    t = Table(title=f"slice: {channel or 'default'} bucket={bucket} metric={metric}")
    for col in ("group", "n", "median", "mean", "win", "cpv", "v/$", "best", "worst"):
        t.add_column(col)
    for r in rows:
        warn = " *" if r.n < 5 else ""
        t.add_row(r.group + warn, str(r.n), f"{r.median:.4f}", f"{r.mean:.4f}",
                  f"{r.win_rate:.0%}", f"{r.cost_per_view:.5f}", f"{r.virality_per_dollar:.3f}",
                  ",".join(r.best), ",".join(r.worst))
    console.print(t)
    console.print("[dim]* low sample size; read as association, not causation.[/]")


@marketing_app.command("compare")
def m_compare(channel: str = "", feature: str = typer.Argument(...),
              bucket: str = "latest", metric: str = "virality",
              json_out: bool = typer.Option(False, "--json")) -> None:
    """Compare videos with a feature against videos without it, e.g. effects=glitch."""
    from studio.marketing import analytics_tools as mat
    from studio.marketing import journal as mj

    res = mat.compare_entries(mj.load(channel).entries, feature, bucket, metric)
    if json_out:
        console.print_json(mat.to_json(res))
        return
    t = Table(title=f"compare: {feature} bucket={bucket} metric={metric}")
    for col in ("cohort", "n", "median", "mean", "examples"):
        t.add_column(col)
    t.add_row("with", str(res["with"]["n"]), f"{res['with']['median']:.4f}",
              f"{res['with']['mean']:.4f}", ",".join(res["with"]["examples"]))
    t.add_row("without", str(res["without"]["n"]), f"{res['without']['median']:.4f}",
              f"{res['without']['mean']:.4f}", ",".join(res["without"]["examples"]))
    console.print(t)
    console.print(f"[bold]median lift:[/] {res['median_lift']:.1%}  "
                  f"[dim]confidence={res['confidence']} — association, not causation[/]")


@marketing_app.command("insights")
def m_insights(channel: str = "", json_out: bool = typer.Option(False, "--json")) -> None:
    """Emit a compact strategy insight pack for marketing-guru."""
    from studio.marketing import analytics_tools as mat
    from studio.marketing import journal as mj

    data = mat.insights(mj.load(channel))
    if json_out:
        console.print_json(mat.to_json(data))
        return
    console.print(f"[bold]insights[/] {data['channel']} — {data['phase']} "
                  f"({data['deployed_count']} deployed)")
    console.print(f"[bold]coverage:[/] {data['snapshot_coverage']}")
    for w in data["warnings"]:
        console.print(f"[yellow]warning:[/] {w}")
    for bucket, groups in data["top"].items():
        console.print(f"\n[bold]{bucket}[/]")
        for group, rows in groups.items():
            if not rows:
                continue
            best = rows[0]
            console.print(f"  [cyan]{group}[/] {best['group']} n={best['n']} "
                          f"median={best['median']:.4f} best={','.join(best['best'])}")


@marketing_app.command("export")
def m_export(channel: str = "", format: str = "csv", include_scenes: bool = False) -> None:
    """Export video-level marketing data for deeper analysis."""
    from studio.marketing import analytics_tools as mat
    from studio.marketing import journal as mj

    rows = mat.export_rows(mj.load(channel), include_scenes=include_scenes)
    if format == "json":
        console.print_json(mat.to_json(rows))
    else:
        console.print(mat.to_csv(rows))


@marketing_app.command("learn")
def m_learn(channel: str = "", provider: Optional[str] = None) -> None:
    """Step 3b — reflect on measured bets → update strategy + next idea seeds.

    Also runs drift detection (topic collapse / safety erosion) and sends a
    Telegram alert if signals are found — for CEO review, not autonomous action."""
    from studio.marketing import drift as mdrift
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
    if j.strategy.playbook_attributions:
        console.print("[bold]playbook attribution:[/]")
        for v, stats in j.strategy.playbook_attributions.items():
            console.print(f"  {v}: n={stats['n']} wins={stats['wins']} "
                          f"win_rate={stats['win_rate']:.0%} "
                          f"median_virality={stats['median_virality']:.4f}")
    signals = mdrift.detect(j)
    if signals:
        console.print("[yellow bold]drift detected:[/]")
        for s in signals:
            console.print(f"  [yellow]• {s}[/]")
        sent = mdrift.notify_drift(signals, channel)
        if sent:
            console.print("[dim]Telegram alert sent.[/]")


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


# ======================================================= guerrilla-marketing loop

def _guerrilla_published_timestamps(channel: str) -> list[str]:
    """Raw `published_at` ISO timestamps from the marketing journal, one per bet that has
    shipped a video. Shared by `rollup` (which needs `YYYY-MM-DD` day strings) and `approve`
    (which needs full timestamps for the publish-blackout check) so the journal-loading logic
    lives in exactly one place."""
    from studio.marketing import journal as mj

    return [e.published_at for e in mj.load(channel).entries if getattr(e, "published_at", "")]


@watchlist_app.command("add")
def guerrilla_watchlist_add(
    channel_id: str = typer.Argument(..., help="Target YouTube channel id (UC...)"),
    channel: str = typer.Option(..., "--channel", help="Our channel token"),
    title: str = typer.Option("", "--title"),
    median_views: int = typer.Option(0, "--median-views"),
    topic_tags: str = typer.Option("", "--tags"),
):
    """Add a target channel to the watchlist."""
    from studio.guerrilla import db as gdb
    from studio.guerrilla import watchlist as gwl

    conn = gdb.connect(channel)
    gwl.add(conn, channel_id, title=title, median_views=median_views,
            topic_tags=topic_tags, added_by="manual")
    console.print(f"[green]added[/] {channel_id} to {channel} watchlist")


@watchlist_app.command("list")
def guerrilla_watchlist_list(
    channel: str = typer.Option(..., "--channel"),
    show_all: bool = typer.Option(False, "--all",
                                  help="Include paused/banned/rejected channels."),
):
    """List target channels (active only, unless --all)."""
    from studio.guerrilla import db as gdb
    from studio.guerrilla import watchlist as gwl

    conn = gdb.connect(channel)
    rows = gwl.all_channels(conn) if show_all else gwl.active(conn)
    if not rows:
        console.print("[dim](watchlist empty — guerrilla watchlist add <UC...>)[/]")
        return
    for r in rows:
        status_tag = "" if r["status"] == "active" else f"  [yellow]\\[{r['status']}][/]"
        console.print(f"{r['channel_id']}  {r['title'] or '(untitled)'}  "
                      f"median_views={r['median_views']}  last={r['last_commented_at'] or '-'}"
                      f"{status_tag}")


@watchlist_app.command("resume")
def guerrilla_watchlist_resume(
    channel_id: str = typer.Argument(..., help="Target YouTube channel id (UC...) to un-pause"),
    channel: str = typer.Option(..., "--channel", help="Our channel token"),
):
    """Un-pause a watchlist channel — e.g. after a transient discovery error paused
    it, or after confirming a channel that looked gone is actually back."""
    from studio.guerrilla import db as gdb
    from studio.guerrilla import watchlist as gwl

    conn = gdb.connect(channel)
    gwl.set_status(conn, channel_id, "active")
    console.print(f"[green]resumed[/] {channel_id}")


@guerrilla_app.command("tick")
def guerrilla_tick(
    channel: str = typer.Option(..., "--channel"),
    daily_cap: int = typer.Option(12, "--cap", min=10, max=25),
    dry_run: bool = typer.Option(False, "--dry-run",
                                 help="Do everything except post. Read the output first."),
    provider: str = typer.Option("", "--provider"),
    experiment_start: str = typer.Option(
        "", "--experiment-start",
        help="YYYY-MM-DD. Enables switchback gating (tick suppressed on OFF days). "
             "Omit to run every tick regardless of the switchback calendar."),
    cite_timestamps: bool = typer.Option(
        False, "--cite-timestamps",
        help="Opt-in: let posted comments cite a video timestamp. Off by default — "
             "the highlight stage's timestamps are unreliable and the citation phrasing "
             "is bot-detectable; the composed comment still reacts to the found moment "
             "either way, it just won't name a time."),
    max_age_min: float = typer.Option(
        90.0, "--max-age-min",
        help="Only comment on videos younger than this many minutes (default 90 — early "
             "enough to hold a top slot). Raise (e.g. 1440 for 24h) to widen the pool; the "
             "max-comments gate still skips videos that have grown crowded."),
):
    """Run one discover -> rank -> transcript -> classify -> highlight -> compose -> gate -> post cycle."""
    from datetime import date as _date
    from datetime import datetime, timezone

    from studio.guerrilla import client as gclient
    from studio.guerrilla import db as gdb
    from studio.guerrilla import loop as gloop
    from studio.guerrilla import rank as grank

    conn = gdb.connect(channel)
    cfg = gloop.Config(
        daily_cap=daily_cap,
        dry_run=dry_run,
        provider=provider,
        gates=grank.Gates(max_age_min=max_age_min),
        # Same helper `approve` uses for the blackout check — without this, `in_blackout`
        # is always evaluated against an empty list and the rail is a no-op.
        publish_times=_guerrilla_published_timestamps(channel),
        experiment_start=_date.fromisoformat(experiment_start) if experiment_start else None,
        # Only spent lazily, inside `post.post_comment`'s ghost-post read-back,
        # to resolve our own channel id (`channel_info`) — never on a normal tick.
        channel=channel,
        cite_timestamps=cite_timestamps,
    )
    res = gloop.tick(conn, gclient.build(channel), cfg, datetime.now(timezone.utc))
    if res.paused:
        console.print("[red]PAUSED[/] — circuit breaker tripped, see the Telegram alert")
        raise typer.Exit(1)
    if dry_run and res.proposed:
        console.print(f"[bold]{len(res.proposed)} comment(s) would post — read every one:[/]\n")
        for p in res.proposed:
            console.print(f"[dim]{p['video_id']}[/]  [bold]{p['title']}[/]  "
                          f"[cyan]{p['style_tag']}[/]  [dim]score={p['score']}[/]")
            console.print(f"  [green]“{p['text']}”[/]\n")
    console.print(f"discovered={res.discovered} considered={res.considered} "
                  f"posted={res.posted} queued={res.queued}")
    if res.skipped:
        console.print(f"[dim]skipped: {dict(res.skipped)}[/]")
    if res.blocked:
        console.print(f"[dim]blocked: {dict(res.blocked)}[/]")


@guerrilla_app.command("track")
def guerrilla_track(channel: str = typer.Option(..., "--channel")):
    """Refresh likes/replies/survival for recent comments; check the breaker."""
    from studio.guerrilla import client as gclient
    from studio.guerrilla import db as gdb
    from studio.guerrilla import track as gtrack

    conn = gdb.connect(channel)
    n = gtrack.refresh(conn, gclient.build(channel))
    rate = gtrack.survival_rate(conn)
    console.print(f"checked {n} comments — survival {rate:.1%}")
    if gtrack.check_breaker(conn):
        console.print("[red]breaker tripped — loop should stay paused[/]")
        raise typer.Exit(1)


@guerrilla_app.command("resume")
def guerrilla_resume(channel: str = typer.Option(..., "--channel")):
    """Clear a tripped circuit breaker. Manual by design — only run this after
    investigating the possible shadowban that tripped it."""
    from studio.guerrilla import db as gdb
    from studio.guerrilla import track as gtrack

    conn = gdb.connect(channel)
    gtrack.resume(conn)
    console.print("[green]breaker cleared[/] — tick and approve will resume posting")


@guerrilla_app.command("report")
def guerrilla_report(channel: str = typer.Option(..., "--channel"),
                     write: bool = typer.Option(False, "--write")):
    """Effectiveness by style tag, skip reasons, and the switchback readout."""
    from studio import paths
    from studio.guerrilla import db as gdb
    from studio.guerrilla import report as greport

    conn = gdb.connect(channel)
    md = greport.render(conn)
    console.print(md)
    if write:
        out = paths.guerrilla_dir(channel) / "report.md"
        out.write_text(md)
        console.print(f"[green]wrote[/] {out}")


@guerrilla_app.command("rollup")
def guerrilla_rollup(
    channel: str = typer.Option(..., "--channel"),
    channel_id: str = typer.Option(..., "--channel-id", help="Our own UC... id"),
    start: str = typer.Option(..., "--start", help="YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", help="YYYY-MM-DD"),
    experiment_start: str = typer.Option(..., "--experiment-start", help="YYYY-MM-DD"),
):
    """Pull daily subs/views into channel_daily so the switchback can be read."""
    from datetime import date as _date

    from studio.guerrilla import db as gdb
    from studio.guerrilla import rollup as grollup

    conn = gdb.connect(channel)
    published = {ts[:10] for ts in _guerrilla_published_timestamps(channel)}
    n = grollup.run(conn, grollup.build(channel), channel_id,
                    _date.fromisoformat(start), _date.fromisoformat(end),
                    _date.fromisoformat(experiment_start), published)
    console.print(f"[green]wrote[/] {n} days into channel_daily")


@guerrilla_app.command("queue")
def guerrilla_queue(channel: str = typer.Option(..., "--channel")):
    """Comments awaiting your approval."""
    from studio.guerrilla import db as gdb

    rows = list(gdb.connect(channel).execute(
        "SELECT video_id, title, skip_reason FROM videos WHERE decision = 'queued'"))
    if not rows:
        console.print("[dim](nothing queued)[/]")
        return
    for r in rows:
        console.print(f"[bold]{r['video_id']}[/]  {r['title']}\n  {r['skip_reason']}\n")


@guerrilla_app.command("approve")
def guerrilla_approve(video_id: str = typer.Argument(...),
                      channel: str = typer.Option(..., "--channel"),
                      cap: int = typer.Option(12, "--cap", min=10, max=25)):
    """Post a queued comment."""
    from datetime import datetime, timezone

    from studio.guerrilla import client as gclient
    from studio.guerrilla import critic as gcritic
    from studio.guerrilla import db as gdb
    from studio.guerrilla import post as gpost
    from studio.guerrilla import track as gtrack

    conn = gdb.connect(channel)
    if gtrack.is_tripped(conn):
        console.print("[red]circuit breaker is tripped[/] — refusing to hand-post through a "
                      "suspected shadowban. Investigate, then `guerrilla resume` to clear it.")
        raise typer.Exit(1)
    row = conn.execute(
        "SELECT skip_reason FROM videos WHERE video_id = ? AND decision = 'queued'",
        (video_id,)).fetchone()
    if not row:
        console.print(f"[red]{video_id} is not queued[/]")
        raise typer.Exit(1)
    verdict = gcritic.Verdict(score=gcritic.QUEUE, breakdown={}, decision="queue")
    publish_times = _guerrilla_published_timestamps(channel)
    try:
        gpost.post_comment(conn, gclient.build(channel), video_id, row["skip_reason"],
                           "approved", verdict, 0, datetime.now(timezone.utc),
                           {"daily_cap": cap, "publish_times": publish_times, "channel": channel})
        console.print("[green]posted[/]")
    except gpost.PostBlocked as e:
        console.print(f"[yellow]blocked:[/] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
