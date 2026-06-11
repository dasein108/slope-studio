"""Stage 5b — generate sound effects + a background-music bed (license-safe).

SFX come from per-scene `Scene.sfx` cues; their GLOBAL trigger times are computed
from the narration-driven `timing.json` (falling back to planned scene durations) so
they land on the right frame. A single music bed is generated from `Script.music`.

This stage only PRODUCES assets + a placements manifest — the `voice` stage overlays
the SFX onto the narration and ducks the music under it (ffmpeg.duck_music). All
sources must be safe for monetized video; see providers/audio.py for licensing.
"""

from __future__ import annotations

import json
from pathlib import Path

from studio import paths
from studio.models import Script
from studio.providers import audio
from studio.providers.base import GenResult

SFX_FAMILY_COOLDOWN_S = 30.0


def _scene_offsets(run_dir: Path, script: Script) -> tuple[dict[int, float], float]:
    """Return ({scene_id: global_start_s}, total_s), preferring narration timing."""
    tj = paths.timing_json(run_dir)
    durs: dict[int, float] = {}
    if tj.exists():
        durs = {int(k): float(v) for k, v in json.loads(tj.read_text()).items()}
    offsets: dict[int, float] = {}
    cursor = 0.0
    for s in script.scenes:
        offsets[s.id] = cursor
        cursor += durs.get(s.id, s.duration_s)
    return offsets, cursor


def run(run_dir: Path, sfx_provider: str, music_provider: str,
        force: bool = False) -> GenResult:
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    offsets, total_s = _scene_offsets(run_dir, script)
    cost = lat = 0.0
    notes: list[str] = []

    # --- sound effects ---------------------------------------------------------
    paths.sfx_dir(run_dir).mkdir(parents=True, exist_ok=True)
    placements: list[tuple[str, float, float]] = []
    n_sfx = 0
    suppressed_sfx = 0
    family_last_at: dict[str, float] = {}
    for scene in script.scenes:
        for j, cue in enumerate(scene.sfx):
            dst = paths.sfx_dir(run_dir) / f"scene_{scene.id:02d}_{j}.mp3"
            global_at = offsets[scene.id] + cue.at
            family = audio.sfx_family(cue.prompt)
            previous_at = family_last_at.get(family)
            if previous_at is not None and global_at - previous_at < SFX_FAMILY_COOLDOWN_S:
                dst.unlink(missing_ok=True)
                suppressed_sfx += 1
                continue
            if force or not dst.exists():
                r = audio.generate_sfx(sfx_provider, cue.prompt, cue.dur, dst)
                cost += r.cost_usd
                lat += r.latency_s
            placements.append((str(dst), round(global_at, 3), cue.gain_db))
            family_last_at[family] = global_at
            n_sfx += 1
    paths.sfx_placements_json(run_dir).write_text(json.dumps(placements, indent=2))
    if n_sfx:
        notes.append(f"{n_sfx} sfx/{sfx_provider}")
    if suppressed_sfx:
        notes.append(f"{suppressed_sfx} repetitive sfx suppressed (<{SFX_FAMILY_COOLDOWN_S:.0f}s)")

    # --- music bed -------------------------------------------------------------
    if script.music.strip():
        bed = paths.music_track(run_dir)
        if force or not bed.exists():
            r = audio.generate_music(music_provider, script.music, total_s or 30.0, bed)
            cost += r.cost_usd
            lat += r.latency_s
            notes.append(r.note)
        else:
            notes.append(f"music/{music_provider} (cached)")
    else:
        paths.music_track(run_dir).unlink(missing_ok=True)  # drop a stale bed

    return GenResult(path=paths.sfx_dir(run_dir), cost_usd=round(cost, 4),
                     latency_s=round(lat, 2),
                     provider=f"{sfx_provider}+{music_provider}",
                     note="; ".join(notes) or "no audio cues")
