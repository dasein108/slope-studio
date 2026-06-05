"""Stage 5 — assemble narration audio + captions, mux over the stitched video.

If the `narrate` stage ran (per-scene audio + timing + captions present), this just
concatenates the scene audio (already length-matched to the clips) and burns the
prebuilt, aligned captions. Otherwise it falls back to one-shot TTS of the full text.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from studio import canvas, ffmpeg, paths
from studio.models import Script
from studio.providers import tts
from studio.providers.base import GenResult


def run(run_dir: Path, provider: str, voice: str = "", captions: str = "off",
        music: Path | None = None) -> GenResult:
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    canvas.set_from_aspect(script.aspect)
    stitched = paths.stitched(run_dir)
    final = paths.final_with_audio(run_dir)
    srt = paths.captions_srt(run_dir)
    paths.voice_dir(run_dir).mkdir(parents=True, exist_ok=True)

    narration = " ".join(s.narration for s in script.scenes if s.narration).strip()
    if not script.voice or not narration:
        shutil.copy(stitched, final)
        return GenResult(path=final, provider="none", note="no voiceover")

    mp3 = paths.narration_mp3(run_dir)
    cost = 0.0
    scene_audios = [paths.scene_audio(run_dir, s.id) for s in script.scenes]
    if paths.timing_json(run_dir).exists() and all(p.exists() for p in scene_audios):
        # narrate stage already synthesized per-scene audio aligned to the clips.
        ffmpeg.concat_audio(scene_audios, mp3)
    else:
        # fallback: synth the whole script at once (legacy path)
        res = tts.synth(provider, narration, mp3, srt=srt,
                        voice_name=voice or script.voice_name, tone=script.tone)
        cost = res.cost_usd

    audio_notes: list[str] = []

    # lay sound effects (from the `audio` stage) over the narration at their cues.
    placements_p = paths.sfx_placements_json(run_dir)
    if placements_p.exists():
        cues = [(Path(p), float(at), float(g))
                for p, at, g in json.loads(placements_p.read_text()) if Path(p).exists()]
        if cues:
            withsfx = paths.voice_dir(run_dir) / "narration_sfx.mp3"
            ffmpeg.overlay_sfx(mp3, cues, withsfx)
            mp3 = withsfx
            audio_notes.append(f"{len(cues)} sfx")

    # duck a music bed under the narration (sidechain). An explicit --music file
    # wins over the bed produced by the audio stage.
    bed = music if music is not None else paths.music_track(run_dir)
    if bed is not None and bed.exists():
        mixed = paths.voice_dir(run_dir) / "narration_mix.mp3"
        ffmpeg.duck_music(mp3, bed, mixed)
        mp3 = mixed
        audio_notes.append("music ducked")

    muxed = paths.voice_dir(run_dir) / "_muxed.mp4"
    ffmpeg.mux_audio(stitched, mp3, muxed)  # music (if any) is already mixed into mp3

    if captions == "burn" and srt.exists() and srt.read_text().strip():
        ffmpeg.burn_subs(muxed, srt, final)
        muxed.unlink(missing_ok=True)
        cap_note = "captions burned"
    else:
        muxed.replace(final)
        cap_note = ("captions skipped: no srt" if captions == "burn"
                    else f"captions={captions}")

    note = "; ".join([cap_note, *audio_notes])
    return GenResult(path=final, cost_usd=cost, provider=provider, note=note)
