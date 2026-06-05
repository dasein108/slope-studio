"""Pre-clips narration stage: TTS each scene, derive per-scene clip durations, and
build a caption track aligned to those durations.

Running this BEFORE clips lets each clip last exactly as long as its narration, so
the final video length follows the speech (no truncation, no long freezes) and the
total naturally lands near the target ±tolerance.
"""

from __future__ import annotations

import json
from pathlib import Path

from studio import ffmpeg, paths
from studio.models import Script
from studio.providers import tts
from studio.providers.base import GenResult

PAD_S = 0.2  # breathing room of silence after each scene's narration


def _ts(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def run(run_dir: Path, provider: str, voice_name: str = "", tone: str = "",
        force: bool = False) -> GenResult:
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    paths.scene_audio_dir(run_dir).mkdir(parents=True, exist_ok=True)
    vname = voice_name or script.voice_name
    base_tone = tone or script.tone

    timing: dict[str, float] = {}
    srt_blocks: list[str] = []
    cursor = 0.0
    idx = 1
    cost = lat = 0.0
    for scene in script.scenes:
        mp3 = paths.scene_audio(run_dir, scene.id)
        text = scene.narration.strip()
        if not text:
            # silent scene: keep its planned duration, emit silence
            dur = scene.duration_s
            ffmpeg.silence(mp3, dur)
            timing[str(scene.id)] = dur
            cursor += dur
            continue
        scene_tone = scene.tone or base_tone
        cues = tts.synth_scene(provider, text, mp3, voice_name=vname, tone=scene_tone)
        spoken = ffmpeg.probe_duration(mp3)
        clip_dur = round(spoken + PAD_S, 3)
        ffmpeg.pad_audio(mp3, mp3, clip_dur)  # pad silence to exact clip length
        timing[str(scene.id)] = clip_dur
        # caption cues offset into the global timeline
        if cues:
            for s, e, txt in cues:
                srt_blocks.append(f"{idx}\n{_ts(cursor + s)} --> {_ts(cursor + e)}\n{txt}\n")
                idx += 1
        else:  # no word timing: one caption spanning the scene
            srt_blocks.append(f"{idx}\n{_ts(cursor)} --> {_ts(cursor + spoken)}\n{text}\n")
            idx += 1
        cursor += clip_dur

    paths.timing_json(run_dir).write_text(json.dumps(timing, indent=2))
    paths.captions_srt(run_dir).write_text("\n".join(srt_blocks))
    return GenResult(path=paths.scene_audio_dir(run_dir), cost_usd=round(cost, 4),
                     latency_s=round(lat, 2), provider=provider,
                     note=f"{len(timing)} scenes, {round(cursor, 1)}s, {vname}/{base_tone}")
