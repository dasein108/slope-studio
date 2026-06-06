"""Offline typographic scene cards (Pillow). The free, no-API image path.

Produces a clean gradient background with the scene's headline text — a legit
kinetic-typography style for faceless Shorts. $0, no network, no GPU.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from studio import canvas

# warm/cool palette pairs (top, bottom) cycled per scene for visual variety.
PALETTES = [
    ((255, 196, 61), (255, 107, 107)),   # yellow -> coral
    ((38, 198, 218), (94, 53, 177)),     # teal -> indigo
    ((255, 138, 101), (191, 54, 12)),    # orange -> deep red
    ((38, 166, 154), (0, 77, 64)),       # teal -> dark green
    ((126, 87, 194), (49, 27, 146)),     # purple -> deep purple
    ((255, 167, 38), (216, 67, 21)),     # amber -> burnt orange
]

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    base = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(base)
    for y in range(h):
        t = y / h
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=col)
    return base


def caption_strip(text: str, dst: Path, w: int = 0, max_h: int = 0) -> None:
    """Transparent PNG sized to fit a wrapped caption (white text, black stroke),
    guaranteed to stay inside a compact lower-third band — it can NEVER clip a line
    off-frame top or bottom.

    Used to burn captions via ffmpeg `overlay` when the ffmpeg build lacks
    libass/libfreetype (so `subtitles`/`drawtext` filters are unavailable).

    Two guarantees keep long sentence-level cues tidy:
    1. Each line is wrapped to FILL the usable width (chars-per-line derived from the
       font's measured average glyph width) → the fewest possible lines → shortest block.
    2. The font shrinks until the block fits a tight height budget (~22% of canvas H),
       and the PNG height is HARD-CAPPED at that budget. Combined with burn_subs'
       bottom margin, the whole caption is always on-frame in any aspect.
    """
    w = w or canvas.W
    max_h = max_h or round(canvas.H * 0.22)   # ~422px vertical, ~238px landscape
    pad, spacing, stroke = 24, 10, 6
    max_w = w - 120
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    txt = text.strip() or " "

    def layout(size: int) -> tuple[str, int, int]:
        font = _font(size)
        # chars/line that fill the usable width → fewest lines → shortest block
        avg = max(1.0, probe.textlength("abcdefghijklmnopqrstuvwxyz ", font=font) / 27)
        wrap_chars = max(10, int((max_w - 2 * stroke) / avg))
        wrapped = textwrap.fill(txt, width=wrap_chars) or " "
        lines = wrapped.split("\n")
        # REAL rendered height from font metrics (the glyph bbox under-reports
        # multiline advance + stroke, which used to clip the block). Width is the
        # widest stroked line.
        asc, desc = font.getmetrics()
        line_h = asc + desc + 2 * stroke
        th = len(lines) * line_h + (len(lines) - 1) * spacing
        tw = max(probe.textlength(ln, font=font) for ln in lines) + 2 * stroke
        return wrapped, int(tw), int(th)

    size = 56
    wrapped, tw, th = layout(size)
    # shrink until the block fits BOTH the usable width and the height budget
    while size > 20 and (tw > max_w or th > max_h - 2 * pad):
        size -= 3
        wrapped, tw, th = layout(size)

    cw, ch = w, int(th + 2 * pad)   # sized to the true text height — never clips
    font = _font(size)
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.multiline_text((cw / 2, ch / 2), wrapped, font=font, fill=(255, 255, 255),
                        spacing=spacing, align="center", anchor="mm",
                        stroke_width=stroke, stroke_fill=(0, 0, 0))
    img.save(dst)


def split_halves(src: Path, out_a: Path, out_b: Path, axis: str = "diag",
                 w: int = 0, h: int = 0) -> None:
    """Split a still into two complementary masked PNGs for the `slice` animator.

    `axis`:
      - `diag`       — half A = upper-right triangle, half B = lower-left
                       (cut along the top-left→bottom-right diagonal).
      - `horizontal` — half A = TOP half, half B = BOTTOM half (the beheading cut).
      - `vertical`   — half A = LEFT half, half B = RIGHT half.

    ffmpeg.diag_slice offsets the halves apart and slides them back together.
    """
    from PIL import ImageOps

    w, h = w or canvas.W, h or canvas.H
    img = ImageOps.fit(Image.open(src).convert("RGBA"), (w, h))
    mask_a = Image.new("L", (w, h), 0)
    mask_b = Image.new("L", (w, h), 0)
    da, db = ImageDraw.Draw(mask_a), ImageDraw.Draw(mask_b)
    if axis == "horizontal":
        da.rectangle([0, 0, w, h // 2], fill=255)          # top
        db.rectangle([0, h // 2, w, h], fill=255)          # bottom
    elif axis == "vertical":
        da.rectangle([0, 0, w // 2, h], fill=255)          # left
        db.rectangle([w // 2, 0, w, h], fill=255)          # right
    else:                                                   # diag
        da.polygon([(0, 0), (w, 0), (w, h)], fill=255)     # upper-right
        db.polygon([(0, 0), (0, h), (w, h)], fill=255)     # lower-left
    a, b = img.copy(), img.copy()
    a.putalpha(mask_a)
    b.putalpha(mask_b)
    a.save(out_a)
    b.save(out_b)


def depth_bands(src: Path, out_top: Path, out_bottom: Path,
                w: int = 0, h: int = 0, seam: float = 0.52, feather: int = 200) -> None:
    """Split a still into two **complementary feathered depth layers** for multi-layer
    parallax: a TOP layer (sky/far — opaque above the seam, faded to transparent
    below) and a BOTTOM layer (ground/mountains/near — opaque below, faded above).
    They overlap+blend across the feather zone, so panning them in OPPOSITE
    directions reads as real 2.5D depth (sky one way, mountains the other).

    `seam` = horizon as a fraction of height; `feather` = blend-zone height in px.
    """
    from PIL import ImageChops, ImageOps

    w, h = w or canvas.W, h or canvas.H
    img = ImageOps.fit(Image.open(src).convert("RGBA"), (w, h))
    seam_y = int(h * seam)
    grad = Image.new("L", (w, h), 0)                        # TOP-layer alpha
    draw = ImageDraw.Draw(grad)
    for y in range(h):
        if y <= seam_y - feather:
            a = 255
        elif y >= seam_y + feather:
            a = 0
        else:
            a = int(255 * (1 - (y - (seam_y - feather)) / (2 * feather)))
        draw.line([(0, y), (w, y)], fill=a)
    top, bottom = img.copy(), img.copy()
    top.putalpha(grad)
    bottom.putalpha(ImageChops.invert(grad))
    top.save(out_top)
    bottom.save(out_bottom)


def particle_layer(kind: str, dst: Path, w: int = 0, h: int = 0, seed: int = 0) -> None:
    """Draw a TRANSPARENT particle/weather layer for the atmosphere post-pass.

    The layer is drawn on a fully transparent canvas (sparse opaque marks only) and
    is 2× the frame height + wider than the frame, so ffmpeg.atmosphere can scroll it
    seamlessly and sway it sideways. Because the layer carries real alpha, it's
    composited with `overlay` (alpha-correct) — NOT a screen-blend of a noise field,
    which washes the whole frame. Deterministic per `seed`. See docs/30-animation/atmosphere.md.
    """
    import random

    from PIL import ImageFilter

    w, h = w or canvas.W, h or canvas.H
    rnd = random.Random(seed)
    lw, lh = w + 320, h * 2                      # wider + taller → seamless scroll/sway room
    img = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = (kind or "").lower()

    if k == "rain":
        for _ in range(900):                          # dense enough to read on any bg
            x, y, ln = rnd.randint(0, lw), rnd.randint(0, lh), rnd.randint(22, 54)
            d.line([(x, y), (x - 6, y + ln)], fill=(215, 228, 255, rnd.randint(110, 205)),
                   width=rnd.randint(2, 3))
    elif k == "snow":
        for _ in range(420):
            x, y, r = rnd.randint(0, lw), rnd.randint(0, lh), rnd.randint(3, 8)
            d.ellipse([x, y, x + r, y + r], fill=(255, 255, 255, rnd.randint(150, 240)))
    elif k in ("embers", "sparks"):
        for _ in range(170):
            x, y, r = rnd.randint(0, lw), rnd.randint(0, lh), rnd.randint(2, 5)
            col = rnd.choice([(255, 160, 60), (255, 95, 40), (255, 210, 130)])
            d.ellipse([x, y, x + r, y + r], fill=col + (rnd.randint(120, 235),))
    elif k == "blood":
        for _ in range(80):
            x, y, r = rnd.randint(0, lw), rnd.randint(0, lh), rnd.randint(3, 9)
            d.ellipse([x, y, x + r, y + int(r * 1.7)], fill=(155, 16, 16, rnd.randint(150, 235)))
    elif k in ("petals", "wind", "leaves"):
        leaf = k == "leaves"
        for _ in range(130):
            x, y, r = rnd.randint(0, lw), rnd.randint(0, lh), rnd.randint(4, 10)
            col = (170, 120, 60) if leaf else rnd.choice([(232, 150, 172), (220, 212, 226), (200, 120, 142)])
            d.ellipse([x, y, x + r, y + int(r * 0.6)], fill=col + (rnd.randint(120, 210),))
    elif k == "fog":
        for _ in range(48):
            x, y = rnd.randint(-200, lw), rnd.randint(0, lh)
            rw, rh = rnd.randint(220, 540), rnd.randint(70, 180)
            d.ellipse([x, y, x + rw, y + rh], fill=(205, 210, 220, rnd.randint(10, 30)))
        img = img.filter(ImageFilter.GaussianBlur(44))
    else:
        raise ValueError(f"unknown atmosphere kind: {kind}")
    img.save(dst)


# Rhubarb mouth shapes → (width_frac, height_frac, teeth, tongue) of the sprite box.
# A/X = closed (rest), D = wide-open, F = puckered. Drawn cartoon fallback when no
# real sprite set is supplied. See docs/30-animation/effects/talking-head.md.
_MOUTH_SHAPES = {
    "A": (0.46, 0.05, False, False),   # closed (M/B/P)
    "X": (0.44, 0.05, False, False),   # idle/rest
    "B": (0.48, 0.16, True, False),    # slightly open, teeth (many consonants/EE)
    "C": (0.58, 0.34, False, False),   # open (EH/AE)
    "D": (0.56, 0.62, False, True),    # wide open + tongue (AA)
    "E": (0.46, 0.40, False, False),   # rounded (AO/ER)
    "F": (0.30, 0.30, False, False),   # puckered small round (UW/OW/W)
    "G": (0.46, 0.18, True, False),    # upper teeth on lower lip (F/V)
    "H": (0.50, 0.42, False, True),    # L (tongue)
}


def mouth_sprite_image(shape: str, w: int = 260, h: int = 180):
    """Draw a cartoon mouth sprite (transparent RGBA Image) for a Rhubarb mouth shape.
    The drawn fallback when assets/mouths/<set>/<SHAPE>.png is absent — legible 'Flash'
    tier; drop in matching sprites for an art-consistent look."""
    cfg = _MOUTH_SHAPES.get((shape or "X").upper(), _MOUTH_SHAPES["X"])
    wf, hf, teeth, tongue = cfg
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    mw, mh = int(w * wf), max(5, int(h * hf))
    cx, cy = w // 2, h // 2
    box = [cx - mw // 2, cy - mh // 2, cx + mw // 2, cy + mh // 2]
    d.ellipse(box, fill=(74, 32, 36, 255), outline=(38, 14, 16, 255), width=6)
    if teeth:
        d.rectangle([cx - mw // 2 + 10, cy - mh // 2, cx + mw // 2 - 10,
                     cy - mh // 2 + max(6, mh // 4)], fill=(244, 244, 234, 255))
    if tongue:
        d.ellipse([cx - mw // 4, cy, cx + mw // 4, cy + mh // 2], fill=(204, 92, 98, 255))
    return img


def headline_png(text: str, dst: Path, w: int = 0, h: int = 0) -> None:
    """Transparent PNG of a big centered headline for kinetic-text overlays.

    Fits ANY length and CANNOT clip: the PNG auto-sizes to the text, the line wrap
    fills the usable width (fewest lines), and the font shrinks until the block fits
    both the width AND a height budget — all measured from FONT METRICS + stroke (the
    glyph bbox under-reports multiline+stroke height, which is what used to clip long
    headlines like a 4-line on_screen_text). Same guarantee as cardgen.caption_strip."""
    w = w or canvas.W
    budget = h or round(canvas.H * 0.30)   # max headline-block height (kinetic sits at ~18% H)
    pad, spacing, stroke = 20, 14, 9
    max_w = w - 110
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    txt = (text or " ").upper().strip() or " "

    def layout(size: int) -> tuple[str, int, int]:
        font = _font(size)
        avg = max(1.0, probe.textlength("ABCDEFGHIJKLMNOPQRSTUVWXYZ ", font=font) / 27)
        wrap_chars = max(8, int((max_w - 2 * stroke) / avg))
        wrapped = textwrap.fill(txt, width=wrap_chars) or " "
        lines = wrapped.split("\n")
        asc, desc = font.getmetrics()
        line_h = asc + desc + 2 * stroke
        th = len(lines) * line_h + (len(lines) - 1) * spacing
        tw = max(probe.textlength(ln, font=font) for ln in lines) + 2 * stroke
        return wrapped, int(tw), int(th)

    size = 104
    wrapped, tw, th = layout(size)
    while size > 40 and (tw > max_w or th > budget - 2 * pad):
        size -= 6
        wrapped, tw, th = layout(size)

    font = _font(size)
    ch = int(th + 2 * pad)   # PNG sized to the text — no fixed height to clip against
    img = Image.new("RGBA", (w, ch), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.multiline_text((w / 2, ch / 2), wrapped, font=font, fill=(255, 255, 255),
                        spacing=spacing, align="center", anchor="mm",
                        stroke_width=stroke, stroke_fill=(0, 0, 0))
    img.save(dst)


def render(text: str, dst: Path, index: int = 0, w: int = 0, h: int = 0,
           subtitle: str = "") -> None:
    w, h = w or canvas.W, h or canvas.H
    top, bottom = PALETTES[index % len(PALETTES)]
    img = _gradient(w, h, top, bottom)
    draw = ImageDraw.Draw(img)

    # decorative accent circle
    r = int(w * 0.42)
    draw.ellipse([w - r, -r // 2, w + r, r // 2 + r], fill=None,
                 outline=(255, 255, 255), width=6)

    headline = (text or subtitle or "").upper()
    font = _font(120)
    wrapped = textwrap.fill(headline, width=14) or " "
    # shrink until it fits BOTH the usable width and ~70% of frame height
    max_h = int(h * 0.7)
    while font.size > 44:
        lines = wrapped.splitlines() or [" "]
        widest = max((draw.textbbox((0, 0), ln, font=font)[2] for ln in lines), default=0)
        asc, desc = font.getmetrics()
        block_h = len(lines) * (asc + desc) + (len(lines) - 1) * 18
        if widest <= w - 140 and block_h <= max_h:
            break
        font = _font(font.size - 8)

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=18, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (w - tw) / 2, (h - th) / 2
    # drop shadow + white text for contrast on any gradient
    draw.multiline_text((x + 5, y + 5), wrapped, font=font, fill=(0, 0, 0),
                        spacing=18, align="center")
    draw.multiline_text((x, y), wrapped, font=font, fill=(255, 255, 255),
                        spacing=18, align="center")
    img.save(dst)


def _fit_font(draw, text, max_w, start, floor=40, step=4):
    """Largest font (<= start px) whose single line fits max_w, down to floor."""
    f = _font(start)
    while f.size > floor and draw.textlength(text, font=f) > max_w:
        f = _font(f.size - step)
    return f


def thumbnail(bg_frame: Path, dst: Path, title: str, author: str = "", hook: str = "",
              w: int = 1280, h: int = 720) -> None:
    """Build a YouTube preview/thumbnail (default 1280×720) from a hero video frame.

    A 'balanced preview with hook': the frame fills the canvas (cover-cropped), a dark
    bottom-up scrim keeps text legible, a warm-yellow accent bar sits under the title,
    the AUTHOR/name renders in yellow above the big white TITLE, and an optional HOOK
    line sits top-left in a translucent band. Free (Pillow). Used for the YouTube upload
    thumbnail — see the film-maker landscape rule.
    """
    from PIL import ImageOps

    base = ImageOps.fit(Image.open(bg_frame).convert("RGB"), (w, h))
    # bottom-up dark scrim for text contrast (and a light top scrim for the hook)
    scrim = Image.new("L", (1, h), 0)
    for y in range(h):
        top_fade = max(0, int(150 * (1 - y / (h * 0.34)))) if y < h * 0.34 else 0
        bot_fade = max(0, int(225 * ((y - h * 0.4) / (h * 0.6)))) if y > h * 0.4 else 0
        scrim.putpixel((0, y), min(235, max(top_fade, bot_fade)))
    scrim = scrim.resize((w, h))
    black = Image.new("RGB", (w, h), (0, 0, 0))
    base = Image.composite(black, base, scrim)
    draw = ImageDraw.Draw(base)
    margin = 64
    yellow = (255, 196, 61)

    # TITLE — big, bold, may wrap to 2 lines; sits in the lower third.
    title = (title or "").upper().strip()
    tf = _fit_font(draw, title, w - 2 * margin, start=148, floor=60)
    if draw.textlength(title, font=tf) > w - 2 * margin:  # still too wide → wrap to 2 lines
        words = title.split()
        mid = len(words) // 2
        title = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
        tf = _fit_font(draw, max(title.split("\n"), key=len), w - 2 * margin, start=120, floor=54)
    tb = draw.multiline_textbbox((0, 0), title, font=tf, spacing=8)
    th = tb[3] - tb[1]
    ty = h - margin - th
    # AUTHOR — yellow, above the title.
    ay = ty
    if author:
        af = _fit_font(draw, author.upper(), w - 2 * margin, start=64, floor=34)
        ah = af.size + 14
        ay = ty - ah
        draw.text((margin, ay), author.upper(), font=af, fill=yellow,
                  stroke_width=4, stroke_fill=(0, 0, 0))
    # yellow accent bar between author and title
    draw.rectangle([margin, ty - 10, margin + 220, ty - 4], fill=yellow)
    draw.multiline_text((margin, ty), title, font=tf, fill=(255, 255, 255),
                        spacing=8, stroke_width=6, stroke_fill=(0, 0, 0))

    # HOOK — top-left curiosity line in a translucent band.
    if hook:
        hf = _fit_font(draw, hook, w - 2 * margin, start=58, floor=34)
        draw.text((margin, margin), hook, font=hf, fill=(240, 240, 240),
                  stroke_width=5, stroke_fill=(0, 0, 0))
    base.save(dst)
