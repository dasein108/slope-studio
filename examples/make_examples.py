"""Render sample clips for each animator/effect into examples/out/ so you can eyeball
them and polish the effects for production.

    python examples/make_examples.py puppet                 # one effect, all variants
    python examples/make_examples.py                        # every registered effect
    python examples/make_examples.py puppet --src path.png --seconds 3
    python examples/make_examples.py puppet --frames        # also dump 3 preview PNGs/clip

Reuses studio.animate with a real source still (examples/assets/sample_figure.png by
default — a clear figure on a simple background, best for cutout/parallax). Output mp4s
and preview frames land in examples/out/ (gitignored media). Re-run after tweaking an
animator to see the change.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from studio import animate, ffmpeg  # noqa: E402
from studio.models import Scene  # noqa: E402

OUT = ROOT / "examples" / "out"
DEFAULT_SRC = ROOT / "examples" / "assets" / "sample_figure.png"

_SUN = """sky = Rectangle(width=16, height=18, fill_color=BLUE, fill_opacity=0.35, stroke_width=0)
self.add(sky)
sun = Circle(radius=1.3, color=YELLOW, fill_opacity=1).move_to([0, -7, 0])
self.play(sun.animate.move_to([0, 3, 0]), run_time=2.5, rate_func=smooth)
self.wait(0.4)"""

# effect -> list of variants. A variant is (label, animator, scene_kwargs[, narration]).
# A 4th element (str) means "needs narration audio" (talkinghead) and is TTS-synthed.
EFFECTS: dict[str, list[tuple]] = {
    "puppet": [
        ("idle", "puppet", {"motion_hint": ""}),
        ("hop", "puppet", {"motion_hint": "hop"}),
        ("shake", "puppet", {"motion_hint": "shake head no"}),
        ("nod", "puppet", {"motion_hint": "nod yes"}),
        # per-limb (hand up / wave) — uses the drawn person; box/pivot in FRACTIONS
        ("raise", "puppet", {"__src__": "sample_person.png", "limbs": [
            {"box": [0.353, 0.32, 0.422, 0.60], "pivot": [0.388, 0.34], "move": "raise",
             "amp": 120, "period": 0.8}]}),
        ("wave", "puppet", {"__src__": "sample_person.png", "limbs": [
            {"box": [0.353, 0.32, 0.422, 0.60], "pivot": [0.388, 0.34], "move": "wave",
             "amp": 32, "period": 0.5, "phase": 0.0}]}),
    ],
    "atmosphere": [(k, "kenburns", {"atmosphere": k}) for k in
                   ("rain", "snow", "embers", "fog", "blood", "petals", "leaves", "wind")],
    # look post-passes (apply on any clip via Scene.fx)
    "fx": [(k, "static", {"fx": [k]}) for k in
           ("grain", "vignette", "chroma", "glitch", "sunrise", "godrays",
            "flash-white", "flash-yellow", "flash-red", "flash-black")],
    "slice": [
        ("diag", "slice", {"motion_hint": ""}),
        ("horizontal", "slice", {"motion_hint": "horizontal red flash"}),
        ("vertical", "slice", {"motion_hint": "vertical"}),
    ],
    # parallax = static sharp subject + REAL background drifting (subject inpainted out →
    # no ghost). blurred-parallax = the old soft-backdrop version (blurred panning planes).
    "parallax": [(f"drift{d}", "parallax", {"motion_hint": d})
                 for d in ("right", "left", "up", "down")],
    "blurred-parallax": [
        ("layers", "blurred-parallax", {"__src__": "sample_scene.png", "motion_hint": ""}),
        ("single", "blurred-parallax", {"__src__": "sample_scene.png", "motion_hint": "single right"})],
    "motion": [(f"{p}", f"motion-{p}", {}) for p in
               ("driftright", "driftleft", "driftup", "driftdown", "zoomin", "zoomout")],
    "kinetic": [("headline", "kinetic", {"on_screen_text": "WATCH THIS"})],
    "static": [("hold", "static", {})],
    "manim": [("sunrise", "manim", {"manim_code": _SUN})],
    "talkinghead": [
        ("lipsync", "talkinghead", {"__src__": "sample_person.png", "mouth_xy": [0.5, 0.26]},
         "Hey! Watch how my mouth moves while I talk to you."),
    ],
    # scene-to-scene transitions (rendered specially: two stills xfaded — see __transition__)
    "transitions": [(t, "__transition__", {"transition": t}) for t in
                    ("fade", "fadeblack", "dissolve", "wipeleft", "slideup", "smoothright",
                     "circleopen", "pixelize", "radial")],
}


def _tts(text: str, dst: Path) -> Path:
    import edge_tts

    async def go() -> None:
        await edge_tts.Communicate(text, "en-US-AriaNeural").save(str(dst))

    asyncio.run(go())
    return dst


def _render_transition(label: str, transition: str, src: Path, dst: Path) -> str:
    """Two distinct stills (the cat then the person) joined with one xfade transition."""
    a, b = OUT / "_xa.mp4", OUT / "_xb.mp4"
    ffmpeg.still(src, a, 1.6)                              # clip A = the default figure
    ffmpeg.still(src.parent / "sample_person.png", b, 1.6)  # clip B = the drawn person
    ffmpeg.concat_xfade([a, b], [1.6, 1.6], dst, transition=transition, t=0.7)
    a.unlink(missing_ok=True)
    b.unlink(missing_ok=True)
    return f"xfade:{transition}"


def render_effect(name: str, src: Path, seconds: float, frames: bool) -> None:
    variants = EFFECTS[name]
    OUT.mkdir(parents=True, exist_ok=True)
    for v in variants:
        label, animator, kwargs = v[0], v[1], dict(v[2])
        dst = OUT / f"{name}_{label}.mp4"
        if animator == "__transition__":                  # special render path
            note = _render_transition(label, kwargs["transition"], src, dst)
            print(f"  {name}/{label:11} -> {dst.name}  [{note}]")
            continue
        narration = v[3] if len(v) > 3 else None
        vsrc = src.parent / kwargs.pop("__src__") if "__src__" in kwargs else src
        scene = Scene(id=1, start_s=0, end_s=seconds, visual_prompt="demo",
                      narration=narration or "", animator=animator, **kwargs)
        audio = _tts(narration, OUT / f"_{name}_{label}.mp3") if narration else None
        note = animate.render(animator, scene, vsrc, dst, seconds, audio=audio)
        dur = ffmpeg.probe_duration(dst)
        print(f"  {name}/{label:11} -> {dst.name}  ({dur:.1f}s)  [{note}]")
        if frames:
            _dump_frames(dst, name, label, dur)


def _dump_frames(clip: Path, name: str, label: str, dur: float) -> None:
    """Pull 3 preview PNGs (start / mid / late) so motion is visible in stills."""
    import subprocess

    for tag, t in (("a", 0.05), ("b", dur / 2), ("c", max(0.0, dur - 0.1))):
        subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(clip),
                        "-frames:v", "1", str(OUT / f"{name}_{label}_{tag}.png")],
                       capture_output=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render effect sample clips into examples/out/")
    ap.add_argument("effect", nargs="?", help="effect name (omit = all). Options: "
                    + ", ".join(EFFECTS))
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="source still")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--frames", action="store_true", help="also dump 3 preview PNGs per clip")
    args = ap.parse_args()

    if not args.src.exists():
        sys.exit(f"source image not found: {args.src}")
    names = [args.effect] if args.effect else list(EFFECTS)
    for name in names:
        if name not in EFFECTS:
            sys.exit(f"unknown effect {name!r}. Options: {', '.join(EFFECTS)}")
        print(f"[{name}]  src={args.src.name}  {args.seconds}s")
        render_effect(name, args.src, args.seconds, args.frames)
    print(f"\ndone → {OUT}")


if __name__ == "__main__":
    main()
