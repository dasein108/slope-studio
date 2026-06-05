"""Extract per-video production telemetry from a finished run, for the journal.

T3: when a bet is linked to its produced run, we copy the *production facts* — cost, duration,
and the video technologies actually used (animators, effects, model, per-stage providers) — out
of the run manifest (`project.json`) and script (`01_script.json`) into the journal Entry. That
is what lets `learn` attribute success not just to a theme but to the EFFECTS underneath it.

Best-effort: a partial/missing run never raises — unknown fields stay at their defaults.
"""

from __future__ import annotations

from pathlib import Path

from studio import ffmpeg, manifest, models, paths


def _duration(run_dir: Path, fallback: float) -> float:
    """Real length of the finished video, best-effort (master → voiced → stitched)."""
    for p in (paths.master(run_dir), paths.final_with_audio(run_dir), paths.stitched(run_dir)):
        if p.exists():
            try:
                d = ffmpeg.probe_duration(p)
                if d > 0:
                    return round(d, 2)
            except Exception:
                continue
    return float(fallback)


def from_run(run_dir: Path) -> dict:
    """Production telemetry for one run. Returns {} if there's no manifest to read."""
    try:
        m = manifest.load(run_dir)
    except Exception:
        return {}

    out: dict = {
        "cost_usd": m.total_cost_usd,
        "tier": m.tier,
        "duration_s": _duration(run_dir, m.duration_s),
        "providers": {stage: r.provider for stage, r in m.stages.items() if r.provider},
        "video_model": "",
        "animators": [],
        "effects": [],
        "n_scenes": 0,
    }

    # video model: the clips stage records provider as "strategy:model" (e.g. "auto:kling")
    clips = m.stages.get("clips")
    if clips and clips.provider:
        out["video_model"] = clips.provider.split(":")[-1]

    # animators + effects come from the authored scenes
    sp = paths.script_json(run_dir)
    if sp.exists():
        try:
            script = models.Script.model_validate_json(sp.read_text())
            out["n_scenes"] = len(script.scenes)
            animators, effects = [], []
            for sc in script.scenes:
                a = sc.animator or "kenburns"
                if a not in animators:
                    animators.append(a)
                for fx in sc.fx:
                    if fx and fx not in effects:
                        effects.append(fx)
                if sc.atmosphere and sc.atmosphere not in effects:
                    effects.append(sc.atmosphere)
            out["animators"] = animators
            out["effects"] = effects
        except Exception:
            pass
    return out
