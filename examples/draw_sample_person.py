"""Draw a simple flat upright character with separable arms → examples/assets/sample_person.png.
A clean test subject for the puppet LIMB demo (raise / wave a clearly-located arm).

    python examples/draw_sample_person.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

W, H = 1080, 1920
OUT = Path(__file__).resolve().parent / "assets" / "sample_person.png"

SKIN = (245, 205, 170)
SHIRT = (70, 120, 200)
PANTS = (60, 64, 80)


def _rrect(d: ImageDraw.ImageDraw, box, r, fill) -> None:
    d.rounded_rectangle(box, radius=r, fill=fill)


def main() -> None:
    img = Image.new("RGB", (W, H), (232, 236, 242))   # plain bg so rembg cuts cleanly
    d = ImageDraw.Draw(img)
    cx = W // 2

    # legs
    _rrect(d, [cx - 70, 1180, cx - 15, 1640], 26, PANTS)
    _rrect(d, [cx + 15, 1180, cx + 70, 1640], 26, PANTS)
    # torso
    _rrect(d, [cx - 110, 600, cx + 110, 1200], 60, SHIRT)
    # RIGHT arm (viewer-left) — the one we'll RAISE. Hangs straight down from the shoulder,
    # held slightly off the torso so a tight box can isolate it. Shoulder ≈ (cx-95, 640).
    _rrect(d, [cx - 150, 630, cx - 92, 1080], 28, SHIRT)        # upper+fore arm as one bar
    d.ellipse([cx - 156, 1050, cx - 86, 1120], fill=SKIN)       # hand
    # LEFT arm (viewer-right) — static, at the side
    _rrect(d, [cx + 92, 630, cx + 150, 1080], 28, SHIRT)
    d.ellipse([cx + 86, 1050, cx + 156, 1120], fill=SKIN)
    # head + neck
    _rrect(d, [cx - 26, 540, cx + 26, 610], 18, SKIN)
    d.ellipse([cx - 120, 300, cx + 120, 560], fill=SKIN)
    d.ellipse([cx - 55, 410, cx - 25, 450], fill=(40, 40, 50))  # eyes
    d.ellipse([cx + 25, 410, cx + 55, 450], fill=(40, 40, 50))
    d.arc([cx - 45, 450, cx + 45, 510], 20, 160, fill=(120, 70, 70), width=6)  # smile

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    # the raise-arm box (fractions) for reference in the limb demo:
    print(f"wrote {OUT}")
    print("raise-arm box≈[0.36,0.33,0.47,0.59] pivot≈[0.41,0.34] (shoulder)")


if __name__ == "__main__":
    main()
