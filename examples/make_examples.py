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

# literal vector animations — core mobjects only (no MathTex/LaTeX needed).
_MORPH = """shape = Circle(radius=2.2, color=BLUE, stroke_width=10)
self.play(Create(shape), run_time=0.9)
self.play(Transform(shape, Square(side_length=4, color=GREEN, stroke_width=10)), run_time=0.9)
self.play(Transform(shape, Triangle(color=YELLOW, stroke_width=10).scale(2.4)), run_time=0.9)
self.play(shape.animate.rotate(PI), run_time=0.8)"""

_SINE = """ax = Axes(x_range=[0, 7, 1], y_range=[-2, 2, 1], x_length=11, y_length=5.5)
curve = ax.plot(lambda x: 1.6 * np.sin(x), color=YELLOW, stroke_width=8)
self.play(Create(ax), run_time=1.0)
self.play(Create(curve), run_time=2.2)
self.wait(0.3)"""

_ORBIT = """sun = Dot(color=YELLOW, radius=0.45)
earth = Dot(color=BLUE, radius=0.22).shift(RIGHT * 3)
moon = Dot(color=GRAY_B, radius=0.12).shift(RIGHT * 4)
self.add(sun, earth, moon)
self.play(Rotate(VGroup(earth, moon), angle=2 * PI, about_point=ORIGIN), run_time=3.2, rate_func=linear)"""

_BARS = """heights = [2.2, 3.6, 1.4, 4.2, 2.8]
bars = VGroup()
for i, hgt in enumerate(heights):
    bar = Rectangle(width=0.8, height=hgt, fill_color=TEAL, fill_opacity=0.95, stroke_width=0)
    bar.move_to([i * 1.15 - 2.3, hgt / 2 - 2.2, 0])
    bars.add(bar)
self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in bars], lag_ratio=0.25), run_time=2.6)"""

_SPIRAL = """spiral = ParametricFunction(
    lambda t: np.array([0.16 * t * np.cos(t), 0.16 * t * np.sin(t), 0]),
    t_range=[0, 6 * PI], color=PINK, stroke_width=8)
self.play(Create(spiral), run_time=3.0)
self.play(spiral.animate.rotate(PI / 2), run_time=0.6)"""

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
    # look post-passes (apply on any clip via Scene.fx). Demo over a Ken-Burns base so the
    # motion is obvious — the temporal parts (grain shimmer, oldfilm flicker, glitch noise,
    # godrays sway) read much better against a slowly moving frame than a frozen one.
    "fx": [(k, "kenburns", {"fx": [k]}) for k in
           ("grain", "vignette", "chroma", "glitch", "sunrise", "godrays", "oldfilm",
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
    "kinetic": [
        ("headline", "kinetic", {"on_screen_text": "WATCH THIS"}),
        ("stat", "kinetic", {"on_screen_text": "50x MORE VIEWS"}),
    ],
    "static": [("hold", "static", {})],
    "manim": [
        ("sunrise", "manim", {"manim_code": _SUN}),
        ("morph", "manim", {"manim_code": _MORPH}),
        ("sine", "manim", {"manim_code": _SINE}),
        ("orbit", "manim", {"manim_code": _ORBIT}),
        ("bars", "manim", {"manim_code": _BARS}),
        ("spiral", "manim", {"manim_code": _SPIRAL}),
    ],
    # one clean portrait demo. mouth_xy 3rd value scales the sprite; a big, clearly-visible
    # mouth reads best on this small-headed figure. (Auto-detect + other faces exist in code;
    # lip-sync is most reliable on a clear closed-mouth portrait, so we keep the demo to that.)
    "talkinghead": [
        ("lipsync", "talkinghead", {"__src__": "sample_person.png", "mouth_xy": [0.5, 0.27, 0.13]},
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
