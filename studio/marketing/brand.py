"""Channel brand-kit generator — banner, profile, transparent logo + copy.

Part of the marketing-guru family (driven by the `youtube-branding` skill and the
`studio brand` CLI command). The AGENT authors the creative as a brand-spec dict;
this module does the deterministic, error-prone pipeline:

  1. request the art TEXT-FREE from an image provider (Nano Banana),
  2. cut the logo to transparency with rembg,
  3. cover-crop everything to exact YouTube upload sizes,
  4. composite the EXACT wordmark with Pillow inside YouTube's safe area
     (never trust the image model to spell), and
  5. write the keywords + description to brand.md.

Outputs land in runs/_brand/<slug>/. See docs via the `youtube-branding` skill.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from studio import paths
from studio.providers.image import generate

REQUIRED = ("name", "slogan", "slug", "style", "logo_prompt", "profile_prompt",
            "banner_prompt", "palette", "keywords", "description")

BANNER_W, BANNER_H = 2560, 1440  # YouTube channel art master

_FONT_FILES = [
    "/System/Library/Fonts/Supplemental/Avenir Next Condensed.ttc",
    "/System/Library/Fonts/Supplemental/Futura.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int, want: tuple[str, ...] = ("Heavy", "Bold")) -> ImageFont.FreeTypeFont:
    """Pick the boldest available face across the candidate files."""
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
            score += 1 if "Condensed" in style else 0
            if best is None or score > best[0]:
                best = (score, f)
            if score >= 3:
                return f
    return best[1] if best else ImageFont.load_default(size)


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Scale-to-cover then center-crop to exactly w x h (never letterbox)."""
    sw, sh = img.size
    s = max(w / sw, h / sh)
    img = img.resize((round(sw * s), round(sh * s)), Image.LANCZOS)
    x, y = (img.size[0] - w) // 2, (img.size[1] - h) // 2
    return img.crop((x, y, x + w, y + h))


def _tracked(draw, y: float, text: str, font, fill, track: int = 0, cx: float | None = None) -> None:
    """Draw text with letter-spacing, optionally centered on cx."""
    widths = [draw.textlength(c, font=font) for c in text]
    total = sum(widths) + track * (len(text) - 1)
    x = (cx - total / 2) if cx is not None else 0.0
    for c, cw in zip(text, widths):
        draw.text((x, y), c, font=font, fill=fill)
        x += cw + track


def build_brand(spec: dict, provider: str = "fal-nanobanana") -> dict:
    """Generate the full brand kit for `spec`. Returns {out, assets, cost_usd}."""
    missing = [k for k in REQUIRED if not spec.get(k)]
    if missing:
        raise ValueError(f"brand spec missing required field(s): {', '.join(missing)}")

    pal = spec["palette"]
    primary = tuple(pal["primary"])
    accent = tuple(pal["accent"])
    highlight = tuple(pal["highlight"])
    text_col = tuple(pal["text"])
    style = spec["style"]

    out = paths.brand_dir(spec["slug"])
    out.mkdir(parents=True, exist_ok=True)

    # --- 1. generate text-free art ---------------------------------------
    jobs = {  # key: (prompt, aspect, w, h)  — w,h only used by the offline stub provider
        "logo_raw": (spec["logo_prompt"], "1:1", 1024, 1024),
        "profile_raw": (spec["profile_prompt"], "1:1", 1024, 1024),
        "banner_raw": (spec["banner_prompt"], "16:9", 1920, 1080),
    }
    raw: dict[str, Path] = {}
    cost = 0.0
    for key, (prompt, aspect, w, h) in jobs.items():
        dst = out / f"_{key}.png"
        res = generate(provider, f"{style}. {prompt}", dst, aspect=aspect, w=w, h=h)
        raw[key] = dst
        cost += res.cost_usd

    # --- 2. transparent logo (rembg) -------------------------------------
    from rembg import remove

    cut = remove(Image.open(raw["logo_raw"]).convert("RGBA"))
    bbox = cut.getbbox()
    if bbox:
        cut = cut.crop(bbox)
    side = max(cut.size) + 80
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(cut, ((side - cut.size[0]) // 2, (side - cut.size[1]) // 2), cut)
    logo = sq.resize((1024, 1024), Image.LANCZOS)
    logo.save(out / "logo.png")
    logo.resize((512, 512), Image.LANCZOS).save(out / "logo_512.png")

    # --- 3. profile avatar -----------------------------------------------
    _cover(Image.open(raw["profile_raw"]).convert("RGB"), 1024, 1024).save(out / "profile.png")

    # --- 4. banner + safe-area wordmark ----------------------------------
    W, H = BANNER_W, BANNER_H
    banner = _cover(Image.open(raw["banner_raw"]).convert("RGB"), W, H).convert("RGBA")

    scrim = Image.new("L", (W, H), 0)
    ImageDraw.Draw(scrim).ellipse([W * 0.18, H * 0.20, W * 0.82, H * 0.80], fill=150)
    scrim = scrim.filter(ImageFilter.GaussianBlur(120))
    banner = Image.composite(Image.new("RGBA", (W, H), (*primary, 255)), banner, scrim)

    d = ImageDraw.Draw(banner)
    cx = W // 2
    title_f = _font(190)
    slog_f = _font(58, want=("Medium", "Regular"))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _tracked(ImageDraw.Draw(glow), H * 0.40, spec["name"], title_f, (*accent, 230), track=10, cx=cx)
    banner.alpha_composite(glow.filter(ImageFilter.GaussianBlur(22)))
    _tracked(d, H * 0.40, spec["name"], title_f, text_col, track=10, cx=cx)

    d.line([(cx - 180, H * 0.585), (cx + 180, H * 0.585)], fill=(*accent, 255), width=5)
    _tracked(d, H * 0.612, spec["slogan"], slog_f, highlight, track=26, cx=cx)

    banner.convert("RGB").save(out / "banner.png")

    # --- 5. brand copy ----------------------------------------------------
    kw = ", ".join(spec["keywords"])
    (out / "brand.md").write_text(
        f"# {spec['name']} — brand kit\n\n"
        f"## Channel keywords (Settings → Channel → Basic info)\n\n{kw}\n\n"
        f"## Channel description\n\n{spec['description']}\n"
    )

    assets = {n: out / n for n in
              ("banner.png", "profile.png", "logo.png", "logo_512.png", "brand.md")}
    return {"out": out, "assets": assets, "cost_usd": round(cost, 3),
            "keywords": kw, "description": spec["description"]}
