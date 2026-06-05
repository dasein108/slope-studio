"""Stage 4 — glue clips into one video track using per-scene transitions.

Each scene may set `transition` (into it) + `transition_dur`; otherwise the global
default is used. Transitions are overlap-compensated so the output length equals the
sum of clip durations (keeps audio in sync). See docs/30-animation/transitions.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from studio import canvas, ffmpeg, paths
from studio.models import Script
from studio.providers.base import GenResult


def run(run_dir: Path, transition: str = "cut", transition_s: float = 0.4) -> GenResult:
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    canvas.set_from_aspect(script.aspect)
    clips = [paths.scene_clip(run_dir, s.id) for s in script.scenes]
    missing = [c for c in clips if not c.exists()]
    if missing:
        raise FileNotFoundError(f"missing clips: {[c.name for c in missing]}")

    dst = paths.stitched(run_dir)
    # per-scene clip durations (narration-driven if narrate ran, else planned).
    timing: dict[str, float] = {}
    if paths.timing_json(run_dir).exists():
        timing = json.loads(paths.timing_json(run_dir).read_text())
    durations = [float(timing.get(str(s.id), s.duration_s)) for s in script.scenes]

    if len(clips) == 1:
        ffmpeg.normalize(clips[0], dst, target_dur=durations[0])
        kinds = {transition}
    else:
        # transition BETWEEN scene i and i+1 comes from scene i+1's fields.
        transitions: list[tuple[str, float]] = []
        for s in script.scenes[1:]:
            ttype = s.transition or transition
            tdur = s.transition_dur or transition_s
            transitions.append((ttype, tdur))
        ffmpeg.concat_xfade_seq(clips, durations, transitions, dst)
        kinds = {t for t, _ in transitions}

    return GenResult(path=dst, provider="ffmpeg",
                     note=f"{len(clips)} clips, transitions: {','.join(sorted(kinds))}")
