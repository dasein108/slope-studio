"""Thin ffmpeg/ffprobe helpers. All shelling out is centralized here."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from studio import canvas


def _run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(args)}\n{proc.stderr[-2000:]}")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def grab_frame(video: Path, dst: Path, at: float = 0.0) -> None:
    """Extract a single still frame from `video` at `at` seconds (for thumbnails)."""
    _run(["ffmpeg", "-y", "-ss", f"{max(0.0, at):.3f}", "-i", str(video),
          "-frames:v", "1", "-q:v", "2", str(dst)])


def normalize(src: Path, dst: Path, w: int = 0, h: int = 0, fps: int = 30,
              target_dur: float | None = None) -> None:
    """Scale+pad any clip/image-video to target canvas, fixed fps, yuv420p.

    If target_dur is given, fit the clip to exactly that length: hold the last frame
    to extend a short clip, or trim a long one. Keeps clips synced to narration.
    """
    w, h = w or canvas.W, h or canvas.H
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}"
    )
    args = ["ffmpeg", "-y", "-i", str(src), "-vf", vf, "-pix_fmt", "yuv420p",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    if target_dur is not None:
        vf += f",tpad=stop_mode=clone:stop_duration={max(0.0, target_dur):.3f}"
        args[args.index("-vf") + 1] = vf
        args += ["-t", f"{target_dur:.3f}"]
    args.append(str(dst))
    _run(args)


def to_wav(src: Path, dst: Path, rate: int = 44100) -> None:
    """Decode any audio to mono PCM WAV (what Rhubarb Lip-Sync ingests)."""
    _run(["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", str(rate), str(dst)])


def frames_to_video(pattern: str, dst: Path, fps: int = 30) -> None:
    """Encode a zero-padded PNG frame sequence (e.g. dir/f_%05d.png) to a silent mp4.
    Used by the talking-head animator, which composites mouth sprites per frame."""
    _run(["ffmpeg", "-y", "-framerate", str(fps), "-i", pattern,
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-an", str(dst)])


def silence(dst: Path, dur: float) -> None:
    """Generate a silent mp3 of `dur` seconds (for scenes with no narration)."""
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
          "-t", f"{dur:.3f}", "-c:a", "libmp3lame", "-q:a", "4", str(dst)])


def placeholder_image(dst: Path, label: str, color: str = "teal",
                      w: int = 0, h: int = 0) -> None:
    """Generate a solid-color keyframe (offline stub, no network/API).

    Plain color fill — drawtext is omitted because some ffmpeg builds lack
    libfreetype. `label` is kept in the signature for callers/future use.
    """
    w, h = w or canvas.W, h or canvas.H
    _ = label
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}",
          "-frames:v", "1", str(dst)])


def ken_burns(image: Path, dst: Path, seconds: float, w: int = 0, h: int = 0,
              fps: int = 30) -> None:
    """Animate a still with a slow zoom/pan — the free 'no AI video' fallback."""
    w, h = w or canvas.W, h or canvas.H
    frames = max(1, int(seconds * fps))
    # zoom from 1.0 -> 1.12 over the clip, centered.
    vf = (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='min(zoom+0.0012,1.12)':d={frames}:s={w}x{h}:fps={fps}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
        f"setsar=1"
    )
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-vf", vf,
          "-t", f"{seconds}", "-pix_fmt", "yuv420p", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", "-an", str(dst)])


def still(image: Path, dst: Path, seconds: float, w: int = 0, h: int = 0,
          fps: int = 30) -> None:
    """Hold a still with NO motion (the `static` animator). A deliberate static beat
    reads better than a twitchy zoom for calm/severe moments — see the operator's
    no-zoom preference in film-maker-guides.md."""
    w, h = w or canvas.W, h or canvas.H
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}")
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-vf", vf,
          "-t", f"{seconds}", "-pix_fmt", "yuv420p", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", "-an", str(dst)])


# xfade transition types we expose (subset of ffmpeg's, plus 'cut'). See
# docs/30-animation/transitions.md for the when-to-use guide.
TRANSITIONS = {
    "cut", "fade", "fadeblack", "fadewhite", "dissolve", "pixelize", "radial",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "circleopen", "circleclose", "circlecrop", "rectcrop",
    "horzopen", "vertopen", "zoomin", "squeezeh", "squeezev",
}

# zoompan (z, x, y) expression presets. {N} = total frames. See docs/30-animation/motion.md
_MOTION = {
    "kenburns": ("min(zoom+0.0010,1.12)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "zoomin":   ("min(zoom+0.0014,1.18)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "zoomout":  ("max(1.18-0.0014*on,1.0)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "pulse":    ("1.06+0.035*sin(on/11)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "driftright": ("1.12", "(iw-iw/zoom)*on/{N}", "ih/2-(ih/zoom/2)"),
    "driftleft":  ("1.12", "(iw-iw/zoom)*(1-on/{N})", "ih/2-(ih/zoom/2)"),
    "driftup":    ("1.12", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/{N})"),
    "driftdown":  ("1.12", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*on/{N}"),
}


def motion(image: Path, dst: Path, seconds: float, preset: str = "kenburns",
           w: int = 0, h: int = 0, fps: int = 30) -> None:
    """Animate a still with a motion preset (free pseudo-animation). Falls back to
    kenburns for an unknown preset. See docs/30-animation/motion.md."""
    w, h = w or canvas.W, h or canvas.H
    frames = max(1, int(seconds * fps))
    z, x, y = _MOTION.get(preset, _MOTION["kenburns"])
    z, x, y = (e.format(N=frames) for e in (z, x, y))
    vf = (
        f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
        f"zoompan=z='{z}':d={frames}:s={w}x{h}:fps={fps}:x='{x}':y='{y}',setsar=1"
    )
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-vf", vf,
          "-t", f"{seconds}", "-pix_fmt", "yuv420p", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", "-an", str(dst)])


def concat_xfade_seq(clips: list[Path], durations: list[float],
                     transitions: list[tuple[str, float]], dst: Path, fps: int = 30) -> None:
    """Concat with a DIFFERENT transition between each pair, compensated so the output
    length == sum(durations) (keeps per-scene audio sync). `transitions[i]` is the
    (type, dur) used between clip i and i+1; len == len(clips)-1. See transitions.md."""
    n = len(clips)
    if n == 1:
        normalize(clips[0], dst, fps=fps, target_dur=durations[0])
        return
    # normalize cut -> 1-frame fade; clamp dur to < clip lengths.
    eff: list[tuple[str, float]] = []
    for i, (ttype, tdur) in enumerate(transitions):
        t = ttype if ttype in TRANSITIONS and ttype != "cut" else "fade"
        d = (1.0 / fps) if ttype == "cut" or tdur <= 0 else float(tdur)
        d = min(d, durations[i] - 0.05, durations[i + 1] - 0.05, 1.5)
        eff.append((t, max(1.0 / fps, d)))

    inputs: list[str] = []
    for c in clips:
        inputs += ["-i", str(c)]
    # pre-extend each non-last clip by its outgoing transition dur (hold last frame),
    # so the overlap consumed by xfade is recovered → total == sum(durations).
    # The extension carries an extra SLACK beyond the transition: each xfade's
    # offset+duration must land STRICTLY before its first input's end, else ffmpeg's
    # xfade silently drops the second input and the whole tail of the chain collapses
    # (manifested as a many-clip video stitching to a few seconds). The slack frames
    # are always consumed by the next xfade, so the output length is unaffected — only
    # the LAST clip is unextended, which fixes total == sum(durations). Without slack
    # the boundary is exact and floating-point error trips it on long (40+ clip) videos.
    slack = 0.5
    parts: list[str] = []
    labels: list[str] = []
    for i in range(n):
        if i < n - 1:
            parts.append(f"[{i}:v]tpad=stop_mode=clone:stop_duration={eff[i][1] + slack:.3f},"
                         f"setsar=1[c{i}]")
        else:
            parts.append(f"[{i}:v]setsar=1[c{i}]")
        labels.append(f"[c{i}]")

    prev = labels[0]
    cum = durations[0]
    for i in range(1, n):
        ttype, tdur = eff[i - 1]
        out = f"[v{i}]"
        parts.append(f"{prev}{labels[i]}xfade=transition={ttype}:duration={tdur:.3f}:"
                     f"offset={cum:.3f}{out}")
        prev = out
        cum += durations[i]
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts),
          "-map", prev, "-r", str(fps), "-pix_fmt", "yuv420p", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", str(dst)])


def kinetic(image: Path, headline_png: Path, dst: Path, seconds: float,
            preset: str = "pulse", w: int = 0, h: int = 0, fps: int = 30) -> None:
    """Motion-graphics clip: cover-filled still + a headline that slides up & fades in.

    The background is **cover-cropped** to the frame (full image fills it, no white/empty
    bars) and only ever zooms IN — at the start the WHOLE image is visible (zoom=1.0), then
    a slow push to ~1.08. It never zooms out past the full image (which would expose the
    background). NOT the twitchy `pulse`. `preset` is accepted but ignored. See the zoom-fill
    rule in film-maker SKILL.md / film-maker-guides.md."""
    _ = preset
    w, h = w or canvas.W, h or canvas.H
    frames = max(1, int(seconds * fps))
    # zoom-in-from-full: z starts at 1.0 (whole image covers the frame), pushes to 1.08,
    # centered. Cover-crop (increase+crop) guarantees no empty edges at any zoom.
    z = "min(1+0.0007*on,1.08)"
    x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    base = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,"
            f"zoompan=z='{z}':d={frames}:s={w}x{h}:fps={fps}:x='{x}':y='{y}',setsar=1[bg]")
    # headline: fade in over 0.6s, slide up 50px, sit at ~22% height.
    txt = "[1:v]format=rgba,fade=in:st=0:d=0.6:alpha=1[t]"
    over = "[bg][t]overlay=x=(W-w)/2:y='H*0.18 - 50*min(t/0.6,1)':format=auto[v]"
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-loop", "1", "-i", str(headline_png),
          "-filter_complex", f"{base};{txt};{over}", "-map", "[v]", "-t", f"{seconds}",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-an", str(dst)])


def parallax(bg: Path, fg_png: Path, dst: Path, seconds: float,
             w: int = 0, h: int = 0, fps: int = 30, direction: str = "both") -> None:
    """2.5D parallax: the cut-out foreground subject stays STATIC and centered while
    the background slides horizontally behind it — the differential reads as depth.

    `direction`: 'left' | 'right' | 'both' (slow sine sweep). The background is
    scaled ~1.5× the frame width to give pan room; the subject never moves.
    See docs/30-animation/parallax.md.
    """
    w, h = w or canvas.W, h or canvas.H
    bw = int(w * 1.5)                       # background widened to leave pan room
    span = "(iw-ow)"                        # crop x-travel available, in source px
    if direction == "right":
        panx = f"{span}*t/{seconds:.3f}"
    elif direction == "left":
        panx = f"{span}*(1-t/{seconds:.3f})"
    else:                                   # 'both' — ease back and forth once
        period = max(2.0, 2.0 * seconds)
        panx = f"{span}/2+{span}/2*sin(t*2*PI/{period:.3f})"
    # Background is blurred + slightly enlarged: the still already contains the
    # subject, so a sharp pan would show a "ghost twin" of the cut-out. Blurring
    # turns the duplicate into a soft out-of-focus backdrop (anime depth-of-field)
    # and hides rembg cut edges; the crisp static foreground pops in front.
    bgf = (f"[0:v]scale={bw}:{h}:force_original_aspect_ratio=increase,setsar=1,"
           f"crop={w}:{h}:x='{panx}':y='(ih-{h})/2',gblur=sigma=22[bg]")
    # foreground subject: contained whole, centered, fixed (no drift, no zoom)
    fgf = f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[fgs]"
    over = "[bg][fgs]overlay=x=(W-w)/2:y=(H-h)/2:format=auto[v]"
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(bg), "-loop", "1", "-i", str(fg_png),
          "-filter_complex", f"{bgf};{fgf};{over}", "-map", "[v]", "-t", f"{seconds}",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-an", str(dst)])


def parallax_drift(bg: Path, fg_png: Path, dst: Path, seconds: float,
                   w: int = 0, h: int = 0, fps: int = 30, direction: str = "right",
                   depth: float = 0.25) -> None:
    """TRUE parallax: a SHARP background (subject already inpainted out) drifts steadily
    while the static cut-out foreground sits on top, fixed and centered. `direction`:
    right|left (horizontal) or up|down (vertical). `depth` = how much wider/taller the bg
    is scaled (pan room → drift distance). No blur. See docs/30-animation/parallax.md."""
    w, h = w or canvas.W, h or canvas.H
    horiz = direction in ("right", "left")
    if horiz:
        bw, bh, span = int(w * (1 + depth)), h, "(iw-ow)"
        cx = f"{span}*t/{seconds:.3f}" if direction == "right" else f"{span}*(1-t/{seconds:.3f})"
        cy = "(ih-oh)/2"
    else:
        bw, bh, span = w, int(h * (1 + depth)), "(ih-oh)"
        cy = f"{span}*t/{seconds:.3f}" if direction == "down" else f"{span}*(1-t/{seconds:.3f})"
        cx = "(iw-ow)/2"
    bgf = (f"[0:v]scale={bw}:{bh}:force_original_aspect_ratio=increase,setsar=1,"
           f"crop={w}:{h}:x='{cx}':y='{cy}'[bg]")
    fgf = f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[fgs]"
    over = "[bg][fgs]overlay=x=(W-w)/2:y=(H-h)/2:format=auto[v]"
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(bg), "-loop", "1", "-i", str(fg_png),
          "-filter_complex", f"{bgf};{fgf};{over}", "-map", "[v]", "-t", f"{seconds}",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-an", str(dst)])


def diag_slice(half_a: Path, half_b: Path, dst: Path, seconds: float,
               w: int = 0, h: int = 0, fps: int = 30,
               split_dur: float = 0.7, offset: int = 160,
               axis: str = "diag", red_flash: bool = False) -> None:
    """`slice` animator: the still is cut into two complementary halves (built by
    cardgen.split_halves) that start offset apart and slide together over
    `split_dur`, then hold — a dramatic cut/reveal. Free. See docs/30-animation/slice.md.

    `axis`: 'diag' (sword-cut reveal) | 'horizontal' (top/bottom split — the
    beheading) | 'vertical'. `red_flash`: pulse a red overlay at the cut moment.
    """
    w, h = w or canvas.W, h or canvas.H
    d = max(0.1, min(split_dur, seconds - 0.05))
    k = f"(1-min(t/{d:.3f}\\,1))"           # 1 → 0 over split_dur, then 0 (joined)
    if axis == "horizontal":               # A=top → up, B=bottom → down
        ax, ay, bx, by = "0", f"-{offset}*{k}", "0", f"{offset}*{k}"
    elif axis == "vertical":               # A=left → left, B=right → right
        ax, ay, bx, by = f"-{offset}*{k}", "0", f"{offset}*{k}", "0"
    else:                                  # diag — perpendicular offsets
        ax, ay, bx, by = f"{offset}*{k}", f"-{offset}*{k}", f"-{offset}*{k}", f"{offset}*{k}"
    bg = f"color=c=#0a0a12:s={w}x{h}:r={fps}:d={seconds:.3f}[bg]"
    fa = f"[0:v]scale={w}:{h},setsar=1[a]"
    fb = f"[1:v]scale={w}:{h},setsar=1[b]"
    o1 = f"[bg][a]overlay=x='{ax}':y='{ay}':format=auto[t1]"
    o2 = f"[t1][b]overlay=x='{bx}':y='{by}':format=auto[{'pre' if red_flash else 'v'}]"
    parts = [bg, fa, fb, o1, o2]
    if red_flash:
        # red full-frame layer flashing at the cut: alpha 0→peak→0 over ~0.45s
        parts += [
            f"color=c=#cc1515:s={w}x{h}:r={fps}:d={seconds:.3f}[r0]",
            "[r0]format=rgba,fade=t=in:st=0:d=0.06:alpha=1,"
            "fade=t=out:st=0.12:d=0.38:alpha=1,colorchannelmixer=aa=0.55[red]",
            "[pre][red]overlay=0:0:format=auto[v]",
        ]
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(half_a), "-loop", "1", "-i", str(half_b),
          "-filter_complex", ";".join(parts), "-map", "[v]", "-t", f"{seconds}",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-an", str(dst)])


def parallax_layers(top_png: Path, bottom_png: Path, fg_png: Path, dst: Path, seconds: float,
                    w: int = 0, h: int = 0, fps: int = 30) -> None:
    """Multi-layer 2.5D parallax: a static sharp foreground cut-out in front of TWO
    background depth planes (built by cardgen.depth_bands) that pan in OPPOSITE
    directions — sky/far drifts one way, ground/mountains/near the other (faster) —
    for true perspective. All free. See docs/30-animation/parallax.md.
    """
    w, h = w or canvas.W, h or canvas.H
    bw1, bw2 = int(w * 1.35), int(w * 1.55)        # near plane wider → moves more
    period = max(2.0, 2.4 * seconds)
    skyx = f"(iw-{w})/2-(iw-{w})/2*sin(t*2*PI/{period:.3f})"     # far: drifts left-ish
    earthx = f"(iw-{w})/2+(iw-{w})/2*sin(t*2*PI/{period:.3f})"   # near: opposite, wider
    base = f"color=c=#0a0a12:s={w}x{h}:r={fps}:d={seconds:.3f}[base]"
    sky = (f"[0:v]scale={bw1}:{h}:force_original_aspect_ratio=increase,setsar=1,"
           f"crop={w}:{h}:x='{skyx}':y='(ih-{h})/2',gblur=sigma=8[sky]")
    earth = (f"[1:v]scale={bw2}:{h}:force_original_aspect_ratio=increase,setsar=1,"
             f"crop={w}:{h}:x='{earthx}':y='(ih-{h})/2',gblur=sigma=5[earth]")
    fg = f"[2:v]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[fg]"
    o1 = "[base][sky]overlay=0:0:format=auto[t1]"
    o2 = "[t1][earth]overlay=0:0:format=auto[t2]"
    o3 = "[t2][fg]overlay=x=(W-w)/2:y=(H-h)/2:format=auto[v]"
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(top_png), "-loop", "1", "-i", str(bottom_png),
          "-loop", "1", "-i", str(fg_png),
          "-filter_complex", ";".join([base, sky, earth, fg, o1, o2, o3]),
          "-map", "[v]", "-t", f"{seconds}", "-pix_fmt", "yuv420p", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", "-an", str(dst)])


# atmosphere overlay: per-kind scroll speed (px/s), rise vs fall, sideways sway (px).
_ATMO = {
    "rain":   (660, False, 14),
    "snow":   (130, False, 36),
    "embers": (220, True, 26),
    "sparks": (280, True, 30),
    "blood":  (430, False, 10),
    "petals": (150, False, 70),
    "wind":   (150, False, 130),
    "leaves": (175, False, 90),
    "fog":    (38,  False, 60),
}


def atmosphere(clip: Path, layer_png: Path, dst: Path, kind: str, seconds: float,
               w: int = 0, h: int = 0, fps: int = 30, opacity: float = 0.85) -> None:
    """Composite a transparent particle/weather LAYER (cardgen.particle_layer) onto an
    already-rendered clip — the free atmosphere post-pass. The layer (2× tall, wider
    than the frame) scrolls vertically and sways sideways; `overlay` keeps it
    alpha-correct so only the particles land (no frame wash). Works on ANY animator's
    clip. See docs/30-animation/atmosphere.md.
    """
    w, h = w or canvas.W, h or canvas.H
    speed, rise, amp = _ATMO.get((kind or "").lower(), (200, False, 16))
    yoff = f"-mod(t*{speed}\\,{h})" if rise else f"-{h}+mod(t*{speed}\\,{h})"
    xoff = f"-160+{amp}*sin(t/1.6)"
    op = max(0.0, min(1.0, opacity))
    lay = f"[1:v]format=rgba,colorchannelmixer=aa={op:.2f},setsar=1[lay]"
    over = f"[0:v][lay]overlay=x='{xoff}':y='{yoff}':eval=frame:format=auto[v]"
    _run(["ffmpeg", "-y", "-i", str(clip), "-loop", "1", "-i", str(layer_png),
          "-filter_complex", f"{lay};{over}", "-map", "[v]", "-t", f"{seconds}",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-an", str(dst)])


def post_fx(src: Path, dst: Path, name: str, seconds: float, w: int = 0, h: int = 0) -> None:
    """Apply a free 'look' post-pass filter to a rendered clip (in place; supports
    src==dst). Names: grain · vignette · chroma · glitch · sunrise · sunset · godrays ·
    flash[-white|-yellow|-red|-black] (impact colour punch that fades back to normal).
    Verified on this ffmpeg build (no drawtext/libass needed). effects/ffmpeg-recipes.md."""
    w, h = w or canvas.W, h or canvas.H
    n = (name or "").lower()
    d = max(0.1, seconds)
    # impact flash: a full-frame colour layer punches in (~0.05s), holds, then fades back
    # over `fade` — white/black = quick hit; red/yellow hold longer (a brief palette shift).
    if n.startswith("flash") or n.startswith("palette"):
        color = n.split("-", 1)[1] if "-" in n else "white"
        spec = {  # color: (hex, peak alpha, hold s, fade s)
            "white":  ("#ffffff", 0.88, 0.07, 0.45),
            "yellow": ("#ffd200", 0.70, 0.30, 0.65),
            "red":    ("#d11414", 0.62, 0.40, 0.75),
            "black":  ("#000000", 0.92, 0.06, 0.40),
        }.get(color, ("#ffffff", 0.88, 0.07, 0.45))
        hexv, peak, hold, fade = spec
        st = 0.08                                   # when the hit lands
        fade = min(fade, max(0.2, d - st - hold - 0.05))   # keep inside the clip
        fc = (f"color=c={hexv}:s={w}x{h}:r=30:d={d:.3f}[c];"
              f"[c]format=rgba,fade=t=in:st={st:.3f}:d=0.05:alpha=1,"
              f"fade=t=out:st={st + hold:.3f}:d={fade:.3f}:alpha=1,"
              f"colorchannelmixer=aa={peak}[fl];"
              f"[0:v][fl]overlay=0:0:format=auto[v]")
        tmp = dst.with_name(dst.stem + "_fx.mp4")
        _run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", fc, "-map", "[v]",
              "-t", f"{seconds:.3f}", "-pix_fmt", "yuv420p", "-c:v", "libx264",
              "-preset", "veryfast", "-crf", "20", "-an", str(tmp)])
        tmp.replace(dst)
        return
    simple = {
        "grain": "noise=alls=16:allf=t",
        "vignette": "vignette=PI/5",
        "chroma": "rgbashift=rh=6:bh=-6",
        "aberration": "rgbashift=rh=6:bh=-6",
        "glitch": "rgbashift=rh=10:bh=-10,noise=alls=44:allf=t",
    }
    if n in simple:
        fc = f"[0:v]{simple[n]}[v]"
    elif n in ("sunrise", "golden", "sunset"):
        ramp = f"0.08-0.06*t/{d:.3f}" if n == "sunset" else f"0.02+0.06*t/{d:.3f}"
        fc = (f"[0:v]colorbalance=rs=0.1:gs=0.02:bs=-0.12:rm=0.15:bm=-0.1,"
              f"eq=brightness='{ramp}':saturation='1.0+0.25*t/{d:.3f}',vignette=PI/6[v]")
    elif n in ("godrays", "lightrays"):
        # build neutral-white shafts on a GRAY plane, convert to RGB, screen-blend in RGB
        # (screen in yuv420p shifts the chroma planes → colour cast).
        ox, oy = w // 2, int(h * 0.08)
        # distinct radial SHAFTS = sharp angular stripes (sin(angle*n)^k), windowed to a
        # downward cone and faded with distance; gray→rgb, screen-blended subtly in RGB.
        ray = (f"190*pow(max(0\\,sin((atan2(Y-{oy}\\,X-{ox})+0.04*sin(T))*22))\\,6)"
               f"*pow(max(0\\,cos(atan2(Y-{oy}\\,X-{ox})-1.571))\\,2)")
        fc = (f"[0:v]split[a][b];[a]format=rgb24[base];"
              f"[b]format=gray,geq=lum='{ray}',gblur=sigma=6,format=rgb24[r];"
              f"[base][r]blend=all_mode=screen:all_opacity=0.42[v]")
    else:
        import shutil
        if src != dst:
            shutil.copy(src, dst)
        return
    tmp = dst.with_name(dst.stem + "_fx.mp4")
    _run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", fc, "-map", "[v]",
          "-t", f"{seconds:.3f}", "-pix_fmt", "yuv420p", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", "-an", str(tmp)])
    tmp.replace(dst)


def concat(clips: list[Path], dst: Path) -> None:
    """Fast concat (no transition) via the concat demuxer. Clips must be normalized."""
    listfile = dst.with_suffix(".txt")
    listfile.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
          "-c", "copy", str(dst)])
    listfile.unlink(missing_ok=True)


def concat_xfade(clips: list[Path], durations: list[float], dst: Path,
                 transition: str = "fade", t: float = 0.4) -> None:
    """Concat with crossfade transitions between every pair (clips normalized)."""
    if len(clips) == 1:
        normalize(clips[0], dst)
        return
    inputs: list[str] = []
    for c in clips:
        inputs += ["-i", str(c)]
    # chain xfade: each xfade offsets by cumulative duration minus transition overlaps.
    filt = []
    prev = "[0:v]"
    offset = 0.0
    for i in range(1, len(clips)):
        offset += durations[i - 1] - t
        out = f"[v{i}]"
        filt.append(
            f"{prev}[{i}:v]xfade=transition={transition}:duration={t}:offset={offset:.3f}{out}"
        )
        prev = out
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt),
          "-map", prev, "-pix_fmt", "yuv420p", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", str(dst)])


def pad_audio(src: Path, dst: Path, dur: float) -> None:
    """Pad an audio clip with trailing silence to exactly `dur` seconds.

    ffmpeg can't edit in-place, so write to a temp file then move (supports src==dst).
    """
    tmp = dst.with_name(dst.stem + "_pad.mp3")
    _run(["ffmpeg", "-y", "-i", str(src), "-af", f"apad=whole_dur={dur:.3f}",
          "-t", f"{dur:.3f}", "-c:a", "libmp3lame", "-q:a", "4", str(tmp)])
    tmp.replace(dst)


def concat_audio(clips: list[Path], dst: Path) -> None:
    """Concatenate audio clips (re-encoded for safety) in order."""
    listfile = dst.with_suffix(".txt")
    listfile.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
          "-c:a", "libmp3lame", "-q:a", "4", str(dst)])
    listfile.unlink(missing_ok=True)


def mux_audio(video: Path, audio: Path, dst: Path, music: Path | None = None,
              tail_s: float = 0.6) -> None:
    """Mux narration (and optional ducked music) over video; loudness-normalize."""
    # NEVER truncate narration. Target = max(video, audio) + tail; hold the last
    # video frame (tpad) to cover any audio overhang, and pad audio with silence.
    v, a = probe_duration(video), probe_duration(audio)
    target = max(v, a) + tail_s
    vpad = max(0.0, round(target - v, 3))
    vfilt = f"[0:v]tpad=stop_mode=clone:stop_duration={vpad}[vo]"
    if music:
        afilt = ("[2:a]volume=0.15[m];[1:a][m]amix=inputs=2:duration=first[mix];"
                 "[mix]loudnorm=I=-14:TP=-1.5:LRA=11,apad[ao]")
        inputs = ["-i", str(video), "-i", str(audio), "-i", str(music)]
    else:
        afilt = "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,apad[ao]"
        inputs = ["-i", str(video), "-i", str(audio)]
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", f"{vfilt};{afilt}",
          "-map", "[vo]", "-map", "[ao]", "-t", f"{target:.3f}",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(dst)])


def loudnorm(src: Path, dst: Path, i: float = -14.0, tp: float = -1.5,
             lra: float = 11.0) -> None:
    """Loudness-normalize an audio file to a platform target (default -14 LUFS,
    the YouTube/TikTok reference). Single-pass EBU R128; good enough for short beds.

    ffmpeg can't edit in place, so write a temp then move (supports src==dst).
    """
    tmp = dst.with_name(dst.stem + "_ln.mp3")
    _run(["ffmpeg", "-y", "-i", str(src),
          "-af", f"loudnorm=I={i}:TP={tp}:LRA={lra}",
          "-c:a", "libmp3lame", "-q:a", "2", "-ar", "48000", str(tmp)])
    tmp.replace(dst)


def duck_music(voice: Path, music: Path, dst: Path, music_db: float = -24.0,
               threshold: float = 0.03, ratio: float = 12.0, attack: float = 10.0,
               release: float = 300.0, i: float = -14.0, tp: float = -1.5,
               lra: float = 11.0) -> None:
    """Mix narration over a music bed with sidechain ducking: the voice keys a
    compressor on the music so the bed drops while words play and swells in the gaps.

    `music` is looped to cover the full narration, then the mix is trimmed to the
    voice length and loudness-normalized to `i` LUFS. Output is mp3.
    Tune threshold/ratio/attack/release for cleaner ducking; the defaults are a
    safe voice-over starting point.
    """
    vdur = probe_duration(voice)
    # voice is needed twice (sidechain control + mix), so asplit it.
    fc = (
        f"[0:a]asplit=2[v1][v2];"
        f"[1:a]volume={music_db}dB[m];"
        f"[m][v2]sidechaincompress=threshold={threshold}:ratio={ratio}:"
        f"attack={attack}:release={release}[duck];"
        f"[v1][duck]amix=inputs=2:duration=first:dropout_transition=0[mix];"
        f"[mix]loudnorm=I={i}:TP={tp}:LRA={lra}[out]"
    )
    _run(["ffmpeg", "-y", "-i", str(voice), "-stream_loop", "-1", "-i", str(music),
          "-filter_complex", fc, "-map", "[out]", "-t", f"{vdur:.3f}",
          "-c:a", "libmp3lame", "-q:a", "2", "-ar", "48000", str(dst)])


def overlay_sfx(base: Path, sfx: list[tuple], dst: Path, sfx_db: float = -3.0) -> None:
    """Overlay one-shot sound effects onto a base audio track at given start offsets.

    `sfx` = [(path, start_s) | (path, start_s, gain_db), ...]. Each effect is delayed
    to its cue and amix'd over the base; the base sets the output length
    (duration=first). Per-cue gain falls back to `sfx_db`. Output mp3.
    """
    if not sfx:
        import shutil
        shutil.copy(base, dst)
        return
    inputs: list[str] = ["-i", str(base)]
    for item in sfx:
        inputs += ["-i", str(item[0])]
    parts: list[str] = []
    labels: list[str] = ["[0:a]"]
    for idx, item in enumerate(sfx, start=1):
        start = item[1]
        gain = item[2] if len(item) > 2 else sfx_db
        ms = int(max(0.0, start) * 1000)
        # adelay needs a value per channel; all=1 applies the delay to every channel.
        parts.append(f"[{idx}:a]adelay={ms}:all=1,volume={gain}dB[s{idx}]")
        labels.append(f"[s{idx}]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:"
                 f"dropout_transition=0[out]")
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts),
          "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", "-ar", "48000", str(dst)])


def _parse_srt(srt: Path) -> list[tuple[float, float, str]]:
    """Return [(start_s, end_s, text)] from an SRT file."""
    def to_s(ts: str) -> float:
        h, m, rest = ts.split(":")
        s, ms = rest.replace(".", ",").split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    cues, block = [], srt.read_text().strip().split("\n\n")
    for b in block:
        lines = [ln for ln in b.splitlines() if ln.strip()]
        ts_line = next((ln for ln in lines if "-->" in ln), None)
        if not ts_line:
            continue
        start, end = (p.strip() for p in ts_line.split("-->"))
        text = " ".join(lines[lines.index(ts_line) + 1:])
        if text:
            cues.append((to_s(start), to_s(end), text))
    return cues


def burn_subs(video: Path, srt: Path, dst: Path) -> None:
    """Burn SRT captions by overlaying Pillow-rendered PNGs (no libass/drawtext needed)."""
    import shutil

    from studio.providers import cardgen

    cues = _parse_srt(srt)
    if not cues:
        shutil.copy(video, dst)
        return

    tmp = dst.parent / "_cap"
    tmp.mkdir(exist_ok=True)
    pngs: list[tuple[Path, float, float]] = []
    for i, (s, e, text) in enumerate(cues):
        p = tmp / f"cap_{i:03d}.png"
        cardgen.caption_strip(text, p)
        pngs.append((p, s, e))

    inputs: list[str] = ["-i", str(video)]
    for p, _, _ in pngs:
        inputs += ["-i", str(p)]
    # Bottom safe-area margin scales with the canvas height: ~11.5% clears the
    # TikTok/Shorts action bar on vertical (1920→~221px) and stays a tasteful lower-
    # third margin on landscape (1080→~124px). The strip is tight-fit, so the whole
    # caption block is always on-frame in any aspect. See docs/30-animation/captions.md.
    margin = round(canvas.H * 0.115)
    parts, prev = [], "[0:v]"
    for i, (_, s, e) in enumerate(pngs, start=1):
        out = f"[v{i}]"
        parts.append(f"{prev}[{i}:v]overlay=(W-w)/2:H-h-{margin}:"
                     f"enable='between(t,{s:.3f},{e:.3f})'{out}")
        prev = out
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts),
          "-map", prev, "-map", "0:a?", "-c:a", "copy", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(dst)])
    shutil.rmtree(tmp, ignore_errors=True)


def encode_master(src: Path, dst: Path, w: int = 0, h: int = 0, fps: int = 30) -> None:
    """Final platform-correct H.264 master with faststart."""
    w, h = w or canvas.W, h or canvas.H
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    _run(["ffmpeg", "-y", "-i", str(src), "-vf", vf, "-r", str(fps),
          "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "20",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
          "-movflags", "+faststart", str(dst)])
