"""Extract per-video production telemetry from a finished run, for the journal.

T3: when a bet is linked to its produced run, we copy the *production facts* — cost, duration,
and the video technologies actually used (animators, effects, model, per-stage providers) — out
of the run manifest (`project.json`) and script (`01_script.json`) into the journal Entry. That
is what lets `learn` attribute success not just to a theme but to the EFFECTS underneath it.

Best-effort: a partial/missing run never raises — unknown fields stay at their defaults.
"""

from __future__ import annotations

import re
from pathlib import Path

from studio import ffmpeg, manifest, models, paths


def _inc(d: dict[str, int], key: str) -> None:
    if key:
        d[key] = d.get(key, 0) + 1


def _provider_stage(provider: str, idx: int, default: str = "") -> str:
    parts = (provider or "").split("+")
    return parts[idx] if len(parts) > idx and parts[idx] else default


def _cost(m: manifest.Manifest, stage: str) -> float:
    r = m.stages.get(stage)
    return round(r.cost_usd, 4) if r else 0.0


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
        "cost_per_minute": 0.0,
        "image_cost_usd": _cost(m, "visuals"),
        "video_cost_usd": _cost(m, "clips"),
        "audio_cost_usd": round(_cost(m, "audio") + _cost(m, "voice") + _cost(m, "narrate"), 4),
        "voice_provider": "",
        "voice_name": "",
        "tone": "",
        "music": "",
        "music_provider": "",
        "sfx_provider": "",
        "sfx_count": 0,
        "sfx_keywords": [],
        "transitions": [],
        "animator_counts": {},
        "effect_counts": {},
        "atmosphere_counts": {},
        "transition_counts": {},
        "ai_scene_count": 0,
        "kenburns_scene_count": 0,
    }
    if out["duration_s"] > 0:
        out["cost_per_minute"] = round(out["cost_usd"] / (out["duration_s"] / 60.0), 4)

    # video model: the clips stage records provider as "strategy:model" (e.g. "auto:kling")
    clips = m.stages.get("clips")
    if clips and clips.provider:
        out["video_model"] = clips.provider.split(":")[-1]
        match = re.search(r"\((\d+)\s+AI\b", clips.note)
        if match:
            out["ai_scene_count"] = int(match.group(1))

    voice = m.stages.get("voice") or m.stages.get("narrate")
    if voice and voice.provider:
        out["voice_provider"] = voice.provider

    audio = m.stages.get("audio")
    if audio and audio.provider:
        out["sfx_provider"] = _provider_stage(audio.provider, 0)
        out["music_provider"] = _provider_stage(audio.provider, 1)

    # animators + effects come from the authored scenes
    sp = paths.script_json(run_dir)
    if sp.exists():
        try:
            script = models.Script.model_validate_json(sp.read_text())
            out["n_scenes"] = len(script.scenes)
            out["voice_name"] = script.voice_name
            out["tone"] = script.tone
            out["music"] = script.music
            animators, effects, transitions, sfx_keywords = [], [], [], []
            animator_counts: dict[str, int] = {}
            effect_counts: dict[str, int] = {}
            atmosphere_counts: dict[str, int] = {}
            transition_counts: dict[str, int] = {}
            sfx_count = 0
            for sc in script.scenes:
                a = sc.animator or "kenburns"
                if a not in animators:
                    animators.append(a)
                _inc(animator_counts, a)
                if a == "kenburns":
                    out["kenburns_scene_count"] += 1
                for fx in sc.fx:
                    if fx and fx not in effects:
                        effects.append(fx)
                    _inc(effect_counts, fx)
                if sc.atmosphere and sc.atmosphere not in effects:
                    effects.append(sc.atmosphere)
                _inc(atmosphere_counts, sc.atmosphere)
                if sc.transition and sc.transition not in transitions:
                    transitions.append(sc.transition)
                _inc(transition_counts, sc.transition)
                for cue in sc.sfx:
                    sfx_count += 1
                    words = [w.strip(" ,.;:!?()[]{}").lower() for w in cue.prompt.split()]
                    for w in words:
                        if len(w) >= 4 and w not in sfx_keywords:
                            sfx_keywords.append(w)
            out["animators"] = animators
            out["effects"] = effects
            out["transitions"] = transitions
            out["sfx_count"] = sfx_count
            out["sfx_keywords"] = sfx_keywords[:40]
            out["animator_counts"] = animator_counts
            out["effect_counts"] = effect_counts
            out["atmosphere_counts"] = atmosphere_counts
            out["transition_counts"] = transition_counts
            out["ai_scene_count"] = max(0, len(script.scenes) - out["kenburns_scene_count"])
        except Exception:
            pass
    return out
