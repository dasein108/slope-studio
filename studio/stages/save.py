"""Stage 6 — encode the platform-correct master + write metadata sidecar."""

from __future__ import annotations

import json
from pathlib import Path

from studio import canvas, ffmpeg, paths
from studio.models import Script
from studio.providers.base import GenResult


def run(run_dir: Path) -> GenResult:
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    canvas.set_from_aspect(script.aspect)
    src = paths.final_with_audio(run_dir)
    if not src.exists():
        # voice stage may have been skipped; fall back to stitched
        src = paths.stitched(run_dir)
    dst = paths.master(run_dir)
    ffmpeg.encode_master(src, dst)

    paths.meta_json(run_dir).write_text(json.dumps({
        "title": script.title or script.topic,
        "description": script.description,
        "hashtags": script.hashtags,
    }, indent=2))
    return GenResult(path=dst, provider="ffmpeg", note="master encoded")
