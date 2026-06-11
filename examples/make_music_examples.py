"""Render short free-music samples into examples/out/.

    python examples/make_music_examples.py

The demos use the built-in `synth` music provider, so they require no network, no API key,
and no local music library. Output mp3s are referenced by examples/build_index.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from studio.providers.audio import generate_music  # noqa: E402

OUT = ROOT / "examples" / "out"

# label, prompt, description
MUSIC_DEMOS: list[tuple[str, str, str]] = [
    (
        "cosmic-dread",
        "deep cosmic drone, awe and dread, sparse",
        "Low, dark, minor drone for space, black holes, vast scale, dread, and awe.",
    ),
    (
        "mournful",
        "slow mournful strings, tragic elegiac lament",
        "Soft darker bed for tragic history, loss, grief, and solemn reflection.",
    ),
    (
        "tense-mystery",
        "tense mystery, eerie unease, suspense",
        "Suspenseful drone for puzzles, paradoxes, reveals, and unsettling facts.",
    ),
    (
        "ancient-lyre",
        "gentle ancient Greek lyre, warm, wry, sunlit, philosophical",
        "Brighter ancient/folk color for philosophy, myth, classical scenes, and warm irony.",
    ),
    (
        "bright-hopeful",
        "bright hopeful warm major ambient, playful and calm",
        "Major, warmer bed for optimistic, curious, playful, or light explanatory shorts.",
    ),
    (
        "neutral-ambient",
        "calm cinematic ambient background, instrumental",
        "Middle-ground fallback when no strong mood is specified.",
    ),
]


def render(seconds: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for label, prompt, _desc in MUSIC_DEMOS:
        dst = OUT / f"music_synth_{label}.mp3"
        result = generate_music("synth", prompt, seconds, dst)
        print(f"{label:15} -> {dst.relative_to(ROOT)}  [{result.note}]")


def main() -> None:
    ap = argparse.ArgumentParser(description="Render 5-second free synth music demos")
    ap.add_argument("--seconds", type=float, default=5.0)
    args = ap.parse_args()
    render(args.seconds)


if __name__ == "__main__":
    main()
