"""Telemetry must record what actually rendered — not what was merely configured."""

from __future__ import annotations

from studio import manifest, paths
from studio.marketing import telemetry
from studio.models import Scene, Script


def _run(tmp_path, provider, note, extra_stages=()):
    d = tmp_path / "run"
    d.mkdir()
    m = manifest.Manifest(id="r", idea="i")
    m.record("clips", done=True, provider=provider, cost_usd=0.0, note=note)
    for stage, prov, cost in extra_stages:
        m.record(stage, done=True, provider=prov, cost_usd=cost)
    manifest.save(d, m)
    return d


def test_configured_but_unused_model_is_not_the_video_model(tmp_path):
    # strategy kenburns + model kling generates ZERO kling clips; recording "kling"
    # anyway contaminated the model-vs-outcome analytics (SLO-211's Kling rule).
    d = _run(tmp_path, "kenburns:kling", "6 clips (0 AI via kling), est $0.0")
    out = telemetry.from_run(d)
    assert out["ai_scene_count"] == 0
    assert out["video_model"] == ""


def test_ai_count_comes_from_note_not_scenes(tmp_path):
    # free animators (drift/parallax/slice) are NOT AI generations: a script full of
    # them must not inflate ai_scene_count past what the clips stage actually billed.
    d = _run(tmp_path, "auto:ltx", "8 clips (3 AI via ltx), est $1.2")
    scenes = [Scene(id=i, start_s=(i - 1) * 6, end_s=i * 6, visual_prompt="x",
                    narration="n", animator=a)
              for i, a in enumerate(["parallax", "motion-driftright", "slice",
                                     "motion-driftleft", "static"], start=1)]
    paths.script_json(d).write_text(
        Script(topic="t", duration_s=30, scenes=scenes).model_dump_json())
    out = telemetry.from_run(d)
    assert out["ai_scene_count"] == 3          # from the note — the billed truth
    assert out["video_model"] == "ltx"
    assert out["kenburns_scene_count"] == 0


def test_cost_breakdown_populated_from_stages(tmp_path):
    d = _run(tmp_path, "auto:kling", "5 clips (2 AI via kling), est $0.7",
             extra_stages=[("visuals", "fal-nanobanana", 0.195),
                           ("audio", "fal-elevenlabs-sfx+fal-stable-audio", 0.2118)])
    out = telemetry.from_run(d)
    assert out["image_cost_usd"] == 0.195
    assert out["audio_cost_usd"] == 0.2118
    assert out["video_cost_usd"] == 0.0        # clips recorded $0 in this fixture
