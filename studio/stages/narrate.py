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


def _scene_spans(texts: list[str], cues: list[tuple[float, float, str]],
                 total: float) -> list[float]:
    """Map one continuous narration's word cues back onto per-scene durations.

    Matching is by cumulative CHARACTER share (robust to tokenizer differences
    between our .split() and the TTS engine's word boundaries). Durations sum to
    `total`, so clips cut to them align exactly with the single audio track."""
    targets, acc = [], 0
    for t in texts:
        acc += len(t) + 1
        targets.append(acc)
    starts: list[float] = []
    ci, consumed = 0, 0
    for si, tgt in enumerate(targets):
        starts.append(cues[ci][0] if ci < len(cues) else total)
        while ci < len(cues) and consumed < tgt:
            consumed += len(cues[ci][2]) + 1
            ci += 1
    durs = []
    for si in range(len(starts)):
        end = starts[si + 1] if si + 1 < len(starts) else total
        durs.append(max(0.5, round(end - starts[si], 3)))
    return durs


def _continuous(run_dir: Path, script: Script, provider: str, vname: str,
                base_tone: str) -> GenResult:
    """ONE fluent TTS pass over the whole narration — natural prosody, no per-scene
    micro-pauses. Scene timings are derived FROM the speech, not imposed on it."""
    texts = [s.narration.strip() for s in script.scenes]
    full = " ".join(texts)
    mp3 = paths.narration_mp3(run_dir)
    mp3.parent.mkdir(parents=True, exist_ok=True)
    cues = tts.synth_scene(provider, full, mp3, voice_name=vname, tone=base_tone)
    total = ffmpeg.probe_duration(mp3)
    durs = _scene_spans(texts, cues, total)
    timing = {str(s.id): d for s, d in zip(script.scenes, durs)}
    paths.timing_json(run_dir).write_text(json.dumps(timing, indent=2))
    # stale per-scene audios would make the voice stage concat them (torn speech
    # again) — remove so voice muxes the continuous track
    for p in paths.scene_audio_dir(run_dir).glob("scene_*.mp3"):
        p.unlink()
    srt_blocks = [f"{i}\n{_ts(s)} --> {_ts(e)}\n{txt}\n"
                  for i, (s, e, txt) in enumerate(cues, 1)]
    paths.captions_srt(run_dir).write_text("\n".join(srt_blocks))
    return GenResult(path=mp3, cost_usd=0.0, provider=provider,
                     note=f"{len(timing)} scenes, {round(total, 1)}s continuous, "
                          f"{vname}/{base_tone}")


def run(run_dir: Path, provider: str, voice_name: str = "", tone: str = "",
        force: bool = False, continuous: bool = False) -> GenResult:
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    paths.scene_audio_dir(run_dir).mkdir(parents=True, exist_ok=True)
    vname = voice_name or script.voice_name
    base_tone = tone or script.tone

    if continuous:
        if all(s.narration.strip() for s in script.scenes):
            return _continuous(run_dir, script, provider, vname, base_tone)
        # silent scenes need per-scene silence tracks — continuous can't place them
        # (falls through to per-scene mode)

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
