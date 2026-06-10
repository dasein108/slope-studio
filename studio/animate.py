"""Free pseudo-animation for the clips stage. Dispatch on Scene.animator.

  kenburns        slow pan/zoom on the still (default)
  motion-<preset> ffmpeg motion preset (drift*/pulse/zoomin/zoomout) — motion.md
  kinetic         animated still + slide/fade headline (motion-graphics) — kinetic.md
  parallax        rembg cut-out subject drifts over a zooming background — parallax.md
  manim           true vector animation rendered by Manim — manim.md

Heavy animators (parallax/manim) need optional deps; any failure falls back to
kenburns and returns a note. None of these call paid APIs ($0).
See docs/30-animation/README.md.
"""

from __future__ import annotations

from pathlib import Path

from studio import canvas, ffmpeg
from studio.models import Scene


def render(animator: str, scene: Scene, image: Path, dst: Path, seconds: float,
           audio: Path | None = None) -> str:
    """Produce a clip for one scene, then apply an optional atmosphere overlay
    (rain/snow/embers/blood/petals/wind/fog) as a free post-pass. Returns the note.

    `audio` = the scene's narration mp3 (from narrate), used by the talkinghead
    animator for lip-sync; ignored by the others."""
    note = _base_render(animator, scene, image, dst, seconds, audio)
    atmo = (getattr(scene, "atmosphere", "") or "").strip().lower()
    if atmo and atmo not in ("none", ""):
        try:
            _apply_atmosphere(scene, dst, seconds, atmo)
            note = f"{note} +{atmo}"
        except Exception as e:  # atmosphere is optional — never break the clip
            note = f"{note} (atmo {atmo} skipped: {str(e)[:40]})"
    for fx in (getattr(scene, "fx", None) or []):       # look post-passes (grain/vignette/…)
        fx = (fx or "").strip().lower()
        if not fx:
            continue
        try:
            ffmpeg.post_fx(dst, dst, fx, seconds)
            note = f"{note} +fx:{fx}"
        except Exception as e:                          # fx is optional — never break the clip
            note = f"{note} (fx {fx} skipped: {str(e)[:40]})"
    return note


def _apply_atmosphere(scene: Scene, dst: Path, seconds: float, kind: str) -> None:
    from studio.providers import cardgen

    layer = dst.with_name(dst.stem + "_atmo.png")
    pre = dst.with_name(dst.stem + "_pre.mp4")
    cardgen.particle_layer(kind, layer, seed=scene.id * 7 + len(kind))
    dst.replace(pre)
    try:
        ffmpeg.atmosphere(pre, layer, dst, kind, seconds)
    finally:
        pre.unlink(missing_ok=True)
        layer.unlink(missing_ok=True)


def _base_render(animator: str, scene: Scene, image: Path, dst: Path, seconds: float,
                 audio: Path | None = None) -> str:
    """Produce a clip for one scene. Returns a manifest note (records fallbacks)."""
    a = (animator or "kenburns").strip()
    try:
        if a in ("static", "none", "hold"):
            ffmpeg.still(image, dst, seconds)
            return "static"
        if a == "kenburns" or a == "":
            ffmpeg.ken_burns(image, dst, seconds)
            return "kenburns"
        if a.startswith("motion-"):
            ffmpeg.motion(image, dst, seconds, preset=a.split("-", 1)[1])
            return a
        if a == "kinetic":
            return _kinetic(scene, image, dst, seconds)
        if a == "parallax":
            return _parallax(scene, image, dst, seconds)
        if a in ("blurred-parallax", "blurred_parallax", "blurredparallax"):
            return _blurred_parallax(scene, image, dst, seconds)
        if a == "slice":
            return _slice(scene, image, dst, seconds)
        if a in ("puppet", "cutout"):
            return _puppet(scene, image, dst, seconds)
        if a in ("talkinghead", "talk", "lipsync"):
            return _talkinghead(scene, image, dst, seconds, audio)
        if a == "manim":
            return _manim(scene, dst, seconds)
    except Exception as e:  # never break the pipeline on an animator
        ffmpeg.ken_burns(image, dst, seconds)
        return f"{a}->kenburns (fallback: {str(e)[:80]})"
    # unknown animator
    ffmpeg.ken_burns(image, dst, seconds)
    return f"{a}->kenburns (unknown)"


def _kinetic(scene: Scene, image: Path, dst: Path, seconds: float) -> str:
    from studio.providers import cardgen

    head = dst.with_name(dst.stem + "_head.png")
    cardgen.headline_png(scene.on_screen_text or scene.narration[:40], head)
    ffmpeg.kinetic(image, head, dst, seconds, preset="pulse")
    head.unlink(missing_ok=True)
    return "kinetic"


def _inpaint_subject(image: Path, mask, iters: int = 18, radius: int = 28):
    """Erase the cut-out subject from the background by blur-diffusion (no OpenCV):
    repeatedly blur, then restamp the KNOWN (non-subject) pixels, so the subject hole
    fills with diffused surrounding colours. Great for smooth backgrounds (sky/clouds);
    approximate for busy ones. Returns a PIL RGB Image with the subject removed."""
    import numpy as np
    from PIL import Image, ImageFilter

    rgb = np.asarray(Image.open(image).convert("RGB"), dtype=np.float32)
    hole = np.asarray(mask.filter(ImageFilter.MaxFilter(15)), dtype=np.uint8) > 12  # dilated
    known = ~hole
    cur = rgb.copy()
    if known.any():                               # seed hole with the mean known colour
        cur[hole] = rgb[known].mean(axis=0)
    img = Image.fromarray(cur.astype(np.uint8))
    for _ in range(iters):
        blur = np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
        cur[hole] = blur[hole]
        cur[known] = rgb[known]                   # keep the real background fixed
        img = Image.fromarray(cur.astype(np.uint8))
    return img


def _clean_subject(alpha) -> bool:
    """Is this rembg alpha a SINGLE compact foreground subject worth holding static while
    the background drifts? Rejects the masks that produce torn frames when inpainted:
      • thin verticals (minarets/poles) — a tall sliver the blur-diffusion can't fill;
      • edge-hugging masks touching 3+ frame borders — that's background, not a subject;
      • scattered/fragmented masks (low fill inside their bbox).
    Scenery skylines trip every one of these, so they fall through to layered drift."""
    import numpy as np

    a = np.asarray(alpha, dtype=np.uint8) > 32
    cov = float(a.mean())
    if not (0.06 <= cov <= 0.55):
        return False
    ys, xs = np.where(a)
    if xs.size == 0:
        return False
    hh, ww = a.shape
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    bw, bh = (x1 - x0 + 1) / ww, (y1 - y0 + 1) / hh
    if bw < 0.22 and bh > 0.55:                            # thin vertical sliver (minaret)
        return False
    edges = (x0 <= 2) + (x1 >= ww - 3) + (y0 <= 2) + (y1 >= hh - 3)
    if edges >= 3:                                         # hugs the frame = background
        return False
    if cov / max(bw * bh, 1e-6) < 0.30:                    # fragmented inside its bbox
        return False
    return True


def _parallax(scene: Scene, image: Path, dst: Path, seconds: float) -> str:
    """TRUE 2.5D parallax: a STATIC + sharp foreground subject held in front while a
    background plane DRIFTS behind it. Layers come from the best source available:

    1. **Two purpose-built plates** (gold) — a transparent `scene_NN_fg.png` subject over a
       separate clean `scene_NN_bg.png` (subject re-rendered out). Two REAL images, zero
       inpaint, zero tear. Made on balanced+ via `studio visuals --parallax-plates
       --parallax-fg`.
    2. **Clean cut + auto-inpaint** (no plates) — only when rembg finds a single compact
       subject (`_clean_subject`): cut it out, erase its hole from the background by
       blur-diffusion (`_inpaint_subject`), drift the filled plane behind it.

    Scenery (no separable subject — skylines, landscapes, cosmos) routes to a SHARP 2-plane
    DEPTH split (`ffmpeg.parallax_scenery`): the still is cut into two feathered depth bands
    that pan in opposite directions at different speeds → real visible 2.5D depth, kept crisp
    (NOT a flat full-frame pan, which reads as plain drift). A still that fails the clean-subject
    gate falls to a sharp full-frame drift as a last resort. `motion_hint` sets direction.
    See docs/30-animation/parallax.md and the parallax rule in film-maker-guides.md."""
    w, h = canvas.W, canvas.H
    hint = (scene.motion_hint or "").lower()
    direction = ("left" if "left" in hint else "up" if "up" in hint
                 else "down" if "down" in hint else "right")
    pan = {"left": "driftleft", "right": "driftright", "up": "driftup", "down": "driftdown"}[direction]

    fg_plate = image.with_name(image.stem + "_fg.png")     # optional transparent fg plate
    bg_plate = image.with_name(image.stem + "_bg.png")     # optional clean bg plate

    # --- Route 1: two real plates → composite directly, no inpaint, no tear. ---
    if fg_plate.exists() and bg_plate.exists():
        try:
            ffmpeg.parallax_drift(bg_plate, fg_plate, dst, seconds, direction=direction)
            return "parallax (fg-plate+bg-plate)"
        except Exception:
            pass  # plate composite failed → fall through to the gated cut below

    # Scenery has no subject to hold static → split it into two feathered DEPTH BANDS and
    # pan them at different speeds (sharp) for REAL visible 2.5D depth — not a flat full-frame
    # pan (which reads as plain drift). Never subject-inpaint a skyline.
    if (scene.image_role or "").lower() == "bg":
        from studio.providers import cardgen
        top = dst.with_name(dst.stem + "_ptop.png")
        bot = dst.with_name(dst.stem + "_pbot.png")
        try:
            cardgen.depth_bands(image, top, bot)
            ffmpeg.parallax_scenery(top, bot, dst, seconds)
            return "parallax (sharp 2-plane depth, scenery)"
        except Exception:
            ffmpeg.motion(image, dst, seconds, preset=pan)   # last-resort flat drift
            return f"parallax->drift ({direction}, scenery)"

    # --- Route 2: cut the subject from the still, but ONLY if it's a clean one. ---
    tmp: list = []
    try:
        import numpy as np
        from PIL import Image, ImageOps
        from rembg import remove

        cut = remove(ImageOps.fit(Image.open(image).convert("RGBA"), (w, h)))
        alpha = cut.split()[-1]
        if not _clean_subject(alpha):                      # thin/edge/scattered → not a subject
            raise ValueError("no clean separable subject")
        cov = float((np.asarray(alpha, dtype=np.uint8) > 32).mean())
        fg = dst.with_name(dst.stem + "_fg.png")
        cut.save(fg)
        tmp.append(fg)

        if bg_plate.exists():
            bg = bg_plate
            src_tag = "bg-plate"
        else:
            fitted = dst.with_name(dst.stem + "_fit.png")
            ImageOps.fit(Image.open(image).convert("RGB"), (w, h)).save(fitted)
            tmp.append(fitted)
            bg = dst.with_name(dst.stem + "_bg.png")
            _inpaint_subject(fitted, alpha).save(bg)
            tmp.append(bg)
            src_tag = "auto-inpaint"

        ffmpeg.parallax_drift(bg, fg, dst, seconds, direction=direction)
        for t in tmp:
            t.unlink(missing_ok=True)
        return f"parallax ({src_tag}; subject {cov:.0%})"
    except Exception:
        for t in tmp:
            t.unlink(missing_ok=True)

    # Last resort: a clean sharp drift — bulletproof, never holes/tears.
    ffmpeg.motion(image, dst, seconds, preset=pan)
    return f"parallax->drift ({direction})"


def _blurred_parallax(scene: Scene, image: Path, dst: Path, seconds: float) -> str:
    """Multi-layer 2.5D parallax over a BLURRED copy of the still (the original behavior):
    static cut-out in front of two blurred depth planes panning in opposite directions
    (sky vs ground). `motion_hint` with 'single'/'flat' forces a single blurred plane.
    Use when there's no clean background to inpaint; the blur hides the ghost twin."""
    from rembg import remove  # optional dep: pip install rembg onnxruntime
    from PIL import Image
    from studio.providers import cardgen

    hint = (scene.motion_hint or "").lower()
    fg = dst.with_name(dst.stem + "_fg.png")
    remove(Image.open(image).convert("RGBA")).save(fg)
    if "single" in hint or "flat" in hint:        # single blurred plane
        direction = "left" if "left" in hint else "right" if "right" in hint else "both"
        ffmpeg.parallax(image, fg, dst, seconds, direction=direction)
        note = f"blurred-parallax-single ({direction})"
    else:                                         # multi-layer (sky/ground)
        top = dst.with_name(dst.stem + "_top.png")
        bot = dst.with_name(dst.stem + "_bot.png")
        cardgen.depth_bands(image, top, bot)
        ffmpeg.parallax_layers(top, bot, fg, dst, seconds)
        top.unlink(missing_ok=True)
        bot.unlink(missing_ok=True)
        note = "blurred-parallax-layers (sky/ground opposite pan)"
    fg.unlink(missing_ok=True)
    return note


def _slice(scene: Scene, image: Path, dst: Path, seconds: float) -> str:
    """Slice/cut reveal. `motion_hint` keywords pick the cut: 'horizontal' (top/
    bottom — the beheading), 'vertical' (left/right), else diagonal; 'flash'/'red'
    adds a red flash at the cut."""
    from studio.providers import cardgen

    hint = (scene.motion_hint or "").lower()
    axis = "horizontal" if "horizontal" in hint else "vertical" if "vertical" in hint else "diag"
    red = ("flash" in hint) or ("red" in hint)
    a = dst.with_name(dst.stem + "_ha.png")
    b = dst.with_name(dst.stem + "_hb.png")
    cardgen.split_halves(image, a, b, axis=axis)
    ffmpeg.diag_slice(a, b, dst, seconds, axis=axis, red_flash=red)
    a.unlink(missing_ok=True)
    b.unlink(missing_ok=True)
    return f"slice ({axis}{'+flash' if red else ''})"


_MOUTH_SHAPES = ["A", "B", "C", "D", "E", "F", "G", "H", "X"]


def _load_mouth_sprites(set_name: str):
    """{shape: RGBA Image} — real PNGs from assets/mouths/<set>/ when present, else
    cardgen-drawn cartoon mouths. Missing individual shapes fall back to drawn."""
    from PIL import Image

    from studio import paths
    from studio.providers import cardgen

    d = paths.mouth_library_dir(set_name)
    out = {}
    for s in _MOUTH_SHAPES:
        p = d / f"{s}.png"
        out[s] = Image.open(p).convert("RGBA") if p.exists() else cardgen.mouth_sprite_image(s)
    return out


def _limb_angle(lb, t: float) -> float:
    """Rotation (deg) for a limb at time t. wave/swing = oscillate; raise/point =
    smooth ramp 0→amp over `period`, then hold."""
    import math

    move = (lb.move or "wave").lower()
    if move in ("raise", "point", "lift"):
        p = min(1.0, max(0.0, (t - lb.phase) / max(0.05, lb.period)))
        ease = p * p * (3 - 2 * p)                       # smoothstep
        return lb.amp * ease
    return lb.amp * math.sin(2 * math.pi * (t - lb.phase) / max(0.05, lb.period))


def _puppet(scene: Scene, image: Path, dst: Path, seconds: float) -> str:
    """Free cutout-puppet animation: rembg cuts the figure out, then we move it over a
    heavily blurred + desaturated copy of the still (so the static 'ghost twin' recedes).
    The naive, deterministic 'paper puppet' look. Mode from `motion_hint` keywords:

      idle  (default)  gentle bob + sway + breathe — keeps a figure alive
      hop / jump       bounce up & down (with squash/stretch)
      shake / 'no'     HEAD region swings left-right around the neck (shake the head)
      nod / 'yes'      HEAD region bobs + tilts (nod)

    shake/nod assume an UPRIGHT figure (head at top); add 'headbottom'/'inverted' to the
    hint for an upside-down subject. Per-limb moves (hand up, point) need a joint schema —
    backlog; use i2v for those. Needs the parallax extra (rembg).
    See docs/30-animation/effects/puppet.md."""
    import math
    import shutil
    import tempfile

    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    from rembg import remove  # optional dep: pip install -e ".[parallax]"

    fps = 30
    w, h = canvas.W, canvas.H
    hint = (scene.motion_hint or "").lower()
    mode = ("shake" if ("shake" in hint or "no " in hint) else
            "nod" if ("nod" in hint or "yes" in hint) else
            "hop" if any(k in hint for k in ("hop", "jump", "bounce")) else "idle")
    head_at_bottom = any(k in hint for k in ("headbottom", "inverted", "upside"))

    def _pose(layer: Image.Image, dx: int, dy: int, ang: float, pivot, scale: float = 1.0):
        """Place a layer onto a fresh transparent canvas with rotate+scale about a pivot."""
        out = layer
        if scale != 1.0:
            out = ImageOps.scale(out, scale, resample=Image.BICUBIC)
        if ang:
            out = out.rotate(ang, resample=Image.BICUBIC, center=pivot)
        canv = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        # keep size constant: scaled layer may differ — paste centered on the same pivot
        ox = dx - (out.width - layer.width) // 2
        oy = dy - (out.height - layer.height) // 2
        canv.alpha_composite(out, (ox, oy))
        return canv

    work = Path(tempfile.mkdtemp())
    try:
        src = ImageOps.fit(Image.open(image).convert("RGBA"), (w, h))
        cut = remove(src)                                   # transparent-bg figure
        # background: strong blur + desaturate + darken so the static twin truly recedes
        bg = src.convert("RGB").filter(ImageFilter.GaussianBlur(28))
        bg = ImageEnhance.Color(bg).enhance(0.55)
        bg = ImageEnhance.Brightness(bg).enhance(0.74).convert("RGBA")
        x0, y0, x1, y1 = cut.getbbox() or (0, 0, w, h)
        cx, fh = (x0 + x1) // 2, max(1, y1 - y0)
        # neck pivot: 42% down from the head end (top by default, bottom if inverted)
        neck_y = int(y1 - 0.42 * fh) if head_at_bottom else int(y0 + 0.42 * fh)
        if head_at_bottom:
            head, body = cut.crop((0, neck_y, w, h)), cut.crop((0, 0, w, neck_y))
            head_origin = (0, neck_y)
        else:
            head, body = cut.crop((0, 0, w, neck_y)), cut.crop((0, neck_y, w, h))
            head_origin = (0, 0)
        # per-limb articulation (hand up / wave): rotate limb regions around their joints
        # over a static body (the limbs are erased from the body so they don't ghost).
        limbs = getattr(scene, "limbs", None) or []
        if limbs:
            n = max(1, int(round(seconds * fps)))
            specs = []
            body = cut.copy()
            for lb in limbs:
                bx = [int(lb.box[0] * w), int(lb.box[1] * h), int(lb.box[2] * w), int(lb.box[3] * h)]
                limb_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                limb_layer.paste(cut.crop(tuple(bx)), (bx[0], bx[1]))   # limb on full canvas
                body.paste((0, 0, 0, 0), tuple(bx))                     # erase from body
                specs.append((limb_layer, (int(lb.pivot[0] * w), int(lb.pivot[1] * h)), lb))
            for i in range(n):
                t = i / fps
                frame = bg.copy()
                frame.alpha_composite(body)
                for limb_layer, piv, lb in specs:
                    ang = _limb_angle(lb, t)
                    frame.alpha_composite(limb_layer.rotate(ang, resample=Image.BICUBIC, center=piv))
                frame.convert("RGB").save(work / f"f_{i:05d}.png")
            ffmpeg.frames_to_video(str(work / "f_%05d.png"), dst, fps=fps)
            return f"puppet (limbs x{len(limbs)})"

        n = max(1, int(round(seconds * fps)))
        for i in range(n):
            t = i / fps
            frame = bg.copy()
            if mode in ("shake", "nod"):
                frame.alpha_composite(body, (0, 0 if head_at_bottom else neck_y))
                if mode == "shake":
                    ang, dy = 7 * math.sin(2 * math.pi * t / 0.5), 0
                else:
                    ang = 4 * math.sin(2 * math.pi * t / 0.6)
                    dy = int(10 * math.sin(2 * math.pi * t / 0.6))
                rot = head.rotate(ang, resample=Image.BICUBIC, center=(cx, neck_y - head_origin[1]))
                frame.alpha_composite(rot, (head_origin[0], head_origin[1] + dy))
            elif mode == "hop":
                dy = -abs(int(34 * math.sin(2 * math.pi * t / 0.8)))
                sq = 1.0 + 0.05 * math.cos(2 * math.pi * t / 0.8)   # squash/stretch
                frame.alpha_composite(_pose(cut, 0, dy, 0.0, (cx, y1), sq))
            else:                                           # idle: bob + sway + tilt + breathe
                dx = int(10 * math.sin(2 * math.pi * t / 3.0))
                dy = int(12 * math.sin(2 * math.pi * t / 2.0))
                ang = 1.5 * math.sin(2 * math.pi * t / 3.0)
                breathe = 1.0 + 0.012 * math.sin(2 * math.pi * t / 2.0)
                frame.alpha_composite(_pose(cut, dx, dy, ang, (cx, y1), breathe))
            frame.convert("RGB").save(work / f"f_{i:05d}.png")
        ffmpeg.frames_to_video(str(work / "f_%05d.png"), dst, fps=fps)
        return f"puppet ({mode})"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _detect_mouth(image: Path) -> dict | None:
    """LLM-vision mouth locator → {cx, cy, w} as fractions of the image (mouth center +
    width), or None if unavailable. Works on human, cartoon, or animal faces — the model
    is told to find "the mouth" regardless. Any failure (no key, bad JSON, network) returns
    None so the caller falls back to an explicit anchor or a sane default; lip-sync never
    breaks just because detection is offline."""
    import json as _json

    try:
        from studio.providers import llm
        system = "You locate a single face's mouth so a lip-sync mouth sprite can be overlaid."
        user = (
            "Find THE MOUTH in this image (human, cartoon, or animal — whichever face is "
            "present). Respond with ONLY JSON: "
            '{"cx": <mouth center x, 0-1 of width>, "cy": <mouth center y, 0-1 of height>, '
            '"w": <mouth width as a fraction of image width, 0-1>}.')
        d = _json.loads(llm.vision_json(image, system, user))
        cx, cy, w = float(d["cx"]), float(d["cy"]), float(d["w"])
        if 0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0 and 0.02 <= w <= 0.9:
            return {"cx": cx, "cy": cy, "w": w}
    except Exception:
        return None
    return None


def _talkinghead(scene: Scene, image: Path, dst: Path, seconds: float,
                 audio: Path | None) -> str:
    """Tier-2 2D lip-sync: Rhubarb turns the scene narration into a mouth-shape
    timeline; we composite the matching mouth sprite onto the STATIC face per frame.
    Free, headless, deterministic. Falls back (via the caller) to kenburns if the
    narration audio or the `rhubarb` binary is missing. See
    docs/30-animation/effects/talking-head.md."""
    import json
    import shutil
    import subprocess
    import tempfile

    from PIL import Image, ImageOps

    if audio is None or not Path(audio).exists():
        raise RuntimeError("talkinghead needs scene narration audio (run narrate first)")
    if not shutil.which("rhubarb"):
        raise RuntimeError("rhubarb not installed — see docs/30-animation/effects/talking-head.md")

    fps, w, h = 30, 1080, 1920
    work = Path(tempfile.mkdtemp())
    try:
        wav = work / "a.wav"
        ffmpeg.to_wav(audio, wav)
        cues_path = work / "cues.json"
        cmd = ["rhubarb", "-f", "json", "-o", str(cues_path)]
        if (scene.narration or "").strip():
            dlg = work / "dialog.txt"
            dlg.write_text(scene.narration.strip())
            cmd += ["-d", str(dlg)]                       # dialog text → better accuracy
        cmd.append(str(wav))
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
        cues = json.loads(cues_path.read_text()).get("mouthCues", [])

        face = ImageOps.fit(Image.open(image).convert("RGBA"), (w, h))

        # Mouth placement + SIZE. Explicit scene.mouth_xy wins (3rd element = width frac);
        # any unset field is auto-detected by an LLM looking at the actual fitted face, so
        # the sprite lands on the real mouth at the right scale instead of a guessed anchor.
        mx = scene.mouth_xy or []
        ax = mx[0] if len(mx) >= 1 else None
        ay = mx[1] if len(mx) >= 2 else None
        mw = mx[2] if len(mx) >= 3 else None
        det_note = ""
        if ax is None or ay is None or mw is None:
            probe = work / "face_probe.png"
            face.convert("RGB").save(probe)
            det = _detect_mouth(probe)
            if det:
                ax = det["cx"] if ax is None else ax
                ay = det["cy"] if ay is None else ay
                mw = det["w"] if mw is None else mw
                det_note = " +llm-mouth"
        ax = 0.5 if ax is None else ax
        ay = 0.6 if ay is None else ay
        mw = 0.18 if mw is None else mw

        sprites = _load_mouth_sprites(scene.mouth_set or "default")
        target_w = max(8, int(round(mw * w)))            # mouth width relative to the image
        def _scale(sp):
            th = max(1, round(sp.height * target_w / sp.width))
            return sp.resize((target_w, th), Image.LANCZOS)
        sprites = {k: _scale(v) for k, v in sprites.items()}

        def shape_at(t: float) -> str:
            for c in cues:
                if c["start"] <= t < c["end"]:
                    return c["value"]
            return "X"

        nframes = max(1, int(round(seconds * fps)))
        for i in range(nframes):
            sp = sprites.get(shape_at(i / fps)) or sprites["X"]
            frame = face.copy()
            frame.alpha_composite(sp, (int(ax * w - sp.width / 2), int(ay * h - sp.height / 2)))
            frame.convert("RGB").save(work / f"f_{i:05d}.png")
        ffmpeg.frames_to_video(str(work / "f_%05d.png"), dst, fps=fps)
        return f"talkinghead ({len(cues)} cues, set={scene.mouth_set or 'default'}{det_note})"
    finally:
        shutil.rmtree(work, ignore_errors=True)


_MANIM_TEMPLATE = '''from manim import *

class StudioScene(Scene):
    def construct(self):
{body}
'''

_MANIM_DEFAULT = '''        title = Text({title!r}, font_size=56, weight=BOLD).to_edge(UP)
        self.play(Write(title), run_time=1.2)
        dot = Dot(color=YELLOW).scale(2)
        self.play(GrowFromCenter(dot))
        self.play(dot.animate.shift(RIGHT * 3), run_time=1.0)
        self.play(dot.animate.shift(LEFT * 6), run_time=1.0)
        self.play(FadeOut(dot), run_time=0.6)
        self.wait(0.5)'''


def _manim(scene: Scene, dst: Path, seconds: float) -> str:
    import importlib.util
    import shutil
    import subprocess
    import sys
    import tempfile

    import textwrap

    # Prefer the importable package (resolves inside a venv regardless of PATH), invoked
    # as `python -m manim`; fall back to a `manim` CLI on PATH. This is why the demo could
    # render manim with the package pip-installed but no `manim` binary on PATH.
    if importlib.util.find_spec("manim") is not None:
        manim_cmd = [sys.executable, "-m", "manim"]
    elif shutil.which("manim"):
        manim_cmd = ["manim"]
    else:
        raise RuntimeError("manim not installed (pip install manim)")
    raw = scene.manim_code if scene.manim_code else \
        _MANIM_DEFAULT.format(title=(scene.on_screen_text or "")[:40])
    # Normalize indentation regardless of how manim_code was authored: dedent any
    # common leading whitespace, then re-indent uniformly to the construct() body
    # level. Robust to flush-left OR pre-indented code (no more IndentationError
    # fallbacks from mixed indentation).
    body = textwrap.indent(textwrap.dedent(raw).strip("\n"), "        ")
    src = Path(tempfile.mkdtemp()) / "scene.py"
    src.write_text(_MANIM_TEMPLATE.format(body=body))
    media = src.parent / "media"
    subprocess.run(
        [*manim_cmd, "render", "-qm", "--format", "mp4", "--fps", "30",
         "--resolution", f"{canvas.W},{canvas.H}", "--media_dir", str(media), str(src),
         "StudioScene"],
        capture_output=True, text=True, check=True, timeout=600,
    )
    out = next(media.rglob("StudioScene.mp4"), None)
    if not out:
        raise RuntimeError("manim produced no mp4")
    import shutil as _sh
    _sh.copy(out, dst)
    return "manim"
