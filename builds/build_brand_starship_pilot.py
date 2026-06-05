"""Brand kit for the 'Starship Pilot' YouTube channel (slogan: 'unusual knowledge').

One-off generator (not a per-video 01_script.json, but a one-off asset script → lives
in builds/ per the repo convention). Produces, into runs/_brand/starship-pilot/:

  logo.png         transparent square emblem (rembg-cut)        — channel/branding
  logo_512.png     transparent 512px watermark                  — overlay ON VIDEOS
  profile.png      1024x1024 filled cosmic badge                — channel avatar
  banner.png       2560x1440 channel art, EXACT text overlaid   — channel banner

Aesthetic: retro-futurist cosmic-explorer. Deep indigo space, warm amber-gold accent,
cyan highlight. The art is generated text-free (Nano Banana) and the wordmark is
composited with Pillow so the spelling/placement are exact and sit in YouTube's
safe area. Brand text (keywords/description) is printed at the end for copy-paste.

Run from repo root:  python builds/build_brand_starship_pilot.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from studio.providers.image import generate

# ---------------------------------------------------------------- brand tokens
NAME = "STARSHIP PILOT"
SLOGAN = "UNUSUAL KNOWLEDGE"
INDIGO = (11, 16, 38)
AMBER = (255, 200, 87)
CYAN = (69, 230, 208)
WHITE = (244, 247, 255)

STYLE = (
    "retro-futurist cosmic explorer aesthetic, deep indigo and navy space, "
    "warm amber-gold accent light, cyan-teal highlights, cinematic, high contrast, "
    "clean modern, premium, no text, no letters, no words, no watermark"
)

OUT = Path("runs/_brand/starship-pilot")
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- font loader
_FONT_FILES = [
    "/System/Library/Fonts/Supplemental/Avenir Next Condensed.ttc",
    "/System/Library/Fonts/Supplemental/Futura.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def load_font(size: int, want=("Heavy", "Bold")) -> ImageFont.FreeTypeFont:
    """Pick the boldest available face from the candidate files."""
    best = None
    for path in _FONT_FILES:
        if not Path(path).exists():
            continue
        for idx in range(12):
            try:
                f = ImageFont.truetype(path, size, index=idx)
            except Exception:
                break
            try:
                style = f.getname()[1]
            except Exception:
                style = ""
            score = sum(2 if w == "Heavy" else 1 for w in want if w in style)
            if "Condensed" in style:
                score += 1
            if best is None or score > best[0]:
                best = (score, f)
            if score >= 3:
                return f
    return best[1] if best else ImageFont.load_default(size)


# ---------------------------------------------------------------- image helpers
def cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Scale-to-cover then center-crop to exactly w x h."""
    src_w, src_h = img.size
    s = max(w / src_w, h / src_h)
    img = img.resize((round(src_w * s), round(src_h * s)), Image.LANCZOS)
    x = (img.size[0] - w) // 2
    y = (img.size[1] - h) // 2
    return img.crop((x, y, x + w, y + h))


def text_tracked(draw, xy, text, font, fill, track=0, anchor_center_x=None):
    """Draw text with letter-spacing; optionally center on anchor_center_x."""
    widths = [draw.textlength(c, font=font) for c in text]
    total = sum(widths) + track * (len(text) - 1)
    x = (anchor_center_x - total / 2) if anchor_center_x is not None else xy[0]
    y = xy[1]
    for c, cw in zip(text, widths):
        draw.text((x, y), c, font=font, fill=fill)
        x += cw + track
    return total


# ---------------------------------------------------------------- 1. generate art
PROMPTS = {
    "logo_raw": (
        f"{STYLE}. A minimalist flat vector EMBLEM: a sleek astronaut / starship "
        "pilot helmet seen front-on, a single bright star and a small ringed planet "
        "reflected in the curved visor, enclosed in a thin circular badge ring with "
        "tiny stars. Bold, simple, iconic, readable at small size, symmetrical, "
        "centered on a plain solid flat light-grey background, sticker style."
    ),
    "profile_raw": (
        f"{STYLE}. A circular channel-avatar badge: the same starship pilot helmet "
        "front-on with a star and ringed planet glowing in the visor, rich glowing "
        "indigo cosmic background filling the whole square frame, amber rim light, "
        "bold and centered, instantly readable even when tiny."
    ),
    "banner_raw": (
        f"{STYLE}, cinematic ultra-wide 16:9 composition. A lone starship pilot in "
        "silhouette inside a cockpit, seen from behind, gazing through a vast curved "
        "window at a strange luminous cosmic phenomenon — impossible glowing geometry "
        "and a swirling amber-and-cyan nebula in deep space. Wide empty darker negative "
        "space across the CENTER of the frame for a title, detail pushed to the left and "
        "right edges, atmospheric, awe, curiosity."
    ),
}

raw = {}
for key, prompt in PROMPTS.items():
    dst = OUT / f"_{key}.png"
    aspect = "16:9" if key == "banner_raw" else "1:1"
    print(f"generating {key} ({aspect}) …")
    res = generate("fal-nanobanana", prompt, dst, aspect=aspect)
    raw[key] = dst
    print(f"  -> {dst}  ${res.cost_usd:.3f}  {res.latency_s}s")

# ---------------------------------------------------------------- 2. transparent logo
print("cutting transparent logo (rembg) …")
from rembg import remove  # noqa: E402

src = Image.open(raw["logo_raw"]).convert("RGBA")
cut = remove(src)
# trim to content bbox, pad to a centered square, export 1024 + 512 watermark
bbox = cut.getbbox()
if bbox:
    cut = cut.crop(bbox)
side = max(cut.size) + 80
canvas_sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas_sq.paste(cut, ((side - cut.size[0]) // 2, (side - cut.size[1]) // 2), cut)
logo = canvas_sq.resize((1024, 1024), Image.LANCZOS)
logo.save(OUT / "logo.png")
logo.resize((512, 512), Image.LANCZOS).save(OUT / "logo_512.png")
print(f"  -> {OUT/'logo.png'} + logo_512.png (transparent)")

# ---------------------------------------------------------------- 3. profile avatar
print("finishing profile avatar …")
prof = cover(Image.open(raw["profile_raw"]).convert("RGB"), 1024, 1024)
prof.save(OUT / "profile.png")
print(f"  -> {OUT/'profile.png'} (1024x1024)")

# ---------------------------------------------------------------- 4. banner + wordmark
print("compositing banner wordmark …")
W, H = 2560, 1440
banner = cover(Image.open(raw["banner_raw"]).convert("RGB"), W, H).convert("RGBA")

# central scrim so the wordmark always reads over the art
scrim = Image.new("L", (W, H), 0)
sd = ImageDraw.Draw(scrim)
sd.ellipse([W * 0.18, H * 0.20, W * 0.82, H * 0.80], fill=150)
scrim = scrim.filter(ImageFilter.GaussianBlur(120))
dark = Image.new("RGBA", (W, H), (*INDIGO, 255))
banner = Image.composite(dark, banner, scrim)

d = ImageDraw.Draw(banner)
cx = W // 2
title_f = load_font(190)
slog_f = load_font(58, want=("Medium", "Regular"))

# title with a soft amber glow
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
text_tracked(gd, (0, H * 0.40), NAME, title_f, (*AMBER, 230), track=10, anchor_center_x=cx)
banner.alpha_composite(glow.filter(ImageFilter.GaussianBlur(22)))
text_tracked(d, (0, H * 0.40), NAME, title_f, WHITE, track=10, anchor_center_x=cx)

# amber divider rule
rule_w = 360
d.line([(cx - rule_w // 2, H * 0.585), (cx + rule_w // 2, H * 0.585)], fill=(*AMBER, 255), width=5)

# slogan, tracked, in cyan
text_tracked(d, (0, H * 0.612), SLOGAN, slog_f, CYAN, track=26, anchor_center_x=cx)

banner.convert("RGB").save(OUT / "banner.png")
print(f"  -> {OUT/'banner.png'} ({W}x{H}, safe-area text)")

# ---------------------------------------------------------------- 5. brand copy
KEYWORDS = [
    "starship pilot", "unusual knowledge", "unusual facts", "did you know",
    "space facts", "science facts", "weird history", "mind blowing facts",
    "curiosity", "educational shorts", "learn something new", "interesting facts",
    "the universe", "obscure knowledge", "trivia", "fun facts", "explained",
    "cosmos", "knowledge shorts", "today i learned",
]
DESCRIPTION = (
    "STARSHIP PILOT — unusual knowledge.\n\n"
    "Strap in. Every video is a short flight to the strangest, most fascinating "
    "corners of what we know — the facts that sound impossible, the history nobody "
    "taught you, the science that rewires how you see the world.\n\n"
    "Unusual knowledge, in under a minute. Subscribe and ride along.\n\n"
    "New shorts regularly. #unusualknowledge #didyouknow #shorts"
)

print("\n" + "=" * 64)
print("BRAND ASSETS  ->", OUT)
for f in ("logo.png", "logo_512.png", "profile.png", "banner.png"):
    print("  -", OUT / f)
print("\nCHANNEL KEYWORDS (Settings → Channel → Basic info):")
print("  " + ", ".join(KEYWORDS))
print("\nCHANNEL DESCRIPTION:\n")
print(DESCRIPTION)
print("=" * 64)
