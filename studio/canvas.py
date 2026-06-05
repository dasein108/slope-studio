"""Current render canvas (W×H pixels).

The studio was vertical-first (1080×1920). To also support classic landscape
YouTube videos (1920×1080) — and square/portrait variants — stages set the canvas
from the script's `aspect` once, and every ffmpeg/cardgen/image helper defaults its
`w`/`h` to `canvas.W`/`canvas.H`. That means dimensions flow from a single source
without threading `w, h` through every call site (e.g. `animate.render`).

Backward-compatible: the module default is 1080×1920, so any code path that never
calls `set_from_aspect` renders vertical exactly as before.
"""

from __future__ import annotations

# Live canvas — mutated by set_from_aspect() at the start of each rendering stage.
W = 1080
H = 1920

# aspect string -> (w, h). 1080p on the short side; even dimensions (H.264-safe).
_DIMS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),   # classic / landscape YouTube
    "9:16": (1080, 1920),   # vertical Shorts / TikTok (default)
    "1:1": (1080, 1080),    # square
    "4:5": (1080, 1350),    # portrait feed
    "4:3": (1440, 1080),    # classic TV
    "21:9": (2560, 1080),   # cinematic ultrawide
}


def dims(aspect: str) -> tuple[int, int]:
    """Pixel (w, h) for an aspect string; unknown/empty → vertical 1080×1920."""
    return _DIMS.get((aspect or "").strip(), (1080, 1920))


def set_from_aspect(aspect: str) -> None:
    """Point the live canvas at the given aspect. Call once per rendering stage."""
    global W, H
    W, H = dims(aspect)
