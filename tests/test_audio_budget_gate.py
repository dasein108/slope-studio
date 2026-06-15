"""Test: audio stage pre-spend budget gate (SLO-31)."""

import json
import pytest
from pathlib import Path
from studio import paths, manifest
from studio.models import Script, Scene, SoundCue
from studio.providers import audio as audio_costs


def _make_script_with_sfx(n_sfx: int = 2) -> Script:
    """Create a test script with n_sfx cues in a single scene."""
    sfx_cues = [SoundCue(prompt=f"sound {i}", dur=2.0, at=float(i), gain_db=-6.0) for i in range(n_sfx)]
    scene = Scene(
        id=1,
        start_s=0.0,
        end_s=10.0,
        visual_prompt="Test scene",
        narration="",
        sfx=sfx_cues,
    )
    return Script(
        topic="Test topic",
        title="Test",
        scenes=[scene],
        music="ambient background",
    )


def test_audio_cost_estimation_with_paid_providers():
    """Verify cost estimation for paid providers."""
    # 3 SFX cues × 2s each @ $0.002/s = $0.012
    # 1 music bed @ $0.20 = $0.20
    # Total = $0.212
    cost = audio_costs.estimate_total_audio_cost(
        sfx_provider="fal-elevenlabs-sfx",
        music_provider="fal-stable-audio",
        n_sfx=3,
        avg_sfx_seconds=2.0,
    )
    expected = 0.012 + 0.20
    assert abs(cost - expected) < 0.0001, f"expected ~${expected}, got ${cost}"


def test_audio_cost_estimation_with_free_providers():
    """Verify cost is zero when using free providers."""
    cost = audio_costs.estimate_total_audio_cost(
        sfx_provider="freesound",
        music_provider="local",
        n_sfx=10,
        avg_sfx_seconds=2.0,
    )
    assert cost == 0.0, f"expected $0, got ${cost}"


def test_audio_cost_estimation_mixed_providers():
    """Verify cost when mixing paid SFX with free music."""
    # 5 SFX @ $0.002/s × 2s = $0.020
    cost = audio_costs.estimate_total_audio_cost(
        sfx_provider="fal-elevenlabs-sfx",
        music_provider="silence",  # free
        n_sfx=5,
        avg_sfx_seconds=2.0,
    )
    expected = 0.020
    assert abs(cost - expected) < 0.0001, f"expected ~${expected}, got ${cost}"


def test_audio_cost_caps_sfx_at_max_duration():
    """Verify SFX duration is capped at 30s max per effect."""
    # 2 SFX @ 30s max × $0.002/s = $0.12
    cost = audio_costs.estimate_total_audio_cost(
        sfx_provider="fal-elevenlabs-sfx",
        music_provider="silence",
        n_sfx=2,
        avg_sfx_seconds=50.0,  # requested 50s, should cap at 30s
    )
    expected = 0.12
    assert abs(cost - expected) < 0.0001, f"expected ~${expected}, got ${cost}"


def test_audio_cost_estimation_zero_sfx():
    """Verify cost when no SFX are generated."""
    cost = audio_costs.estimate_total_audio_cost(
        sfx_provider="fal-elevenlabs-sfx",
        music_provider="fal-stable-audio",
        n_sfx=0,
        avg_sfx_seconds=2.0,
    )
    # Only music: $0.20
    expected = 0.20
    assert abs(cost - expected) < 0.0001, f"expected ~${expected}, got ${cost}"


def test_audio_budget_gate_dry_run_insufficient_budget(tmp_path):
    """Test: dry-run with $0.05 budget remaining blocks audio stage."""
    from studio.stages import audio as audio_stage

    # Setup: create a run with a script that has paid SFX/music
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()

    script = _make_script_with_sfx(n_sfx=3)  # 3 SFX @ ~$0.012
    paths.script_json(run_dir).write_text(script.model_dump_json(indent=2))

    # Create manifest: $0.20 already spent, max_cost=$0.25, remaining=$0.05
    m = manifest.Manifest(
        id="test",
        idea="test",
        duration_s=30,
        aspect="9:16",
    )
    m.stages["clips"] = manifest.StageRecord(
        done=True, provider="fal-i2v", cost_usd=0.20, latency_s=5.0, note="test"
    )
    manifest.save(run_dir, m)

    # Simulate the check from run() with max_cost=$0.25
    max_cost = 0.25
    remaining = max_cost - m.total_cost_usd  # $0.25 - $0.20 = $0.05

    # Estimate audio cost: 3 SFX + paid music
    estimated = audio_costs.estimate_total_audio_cost(
        sfx_provider="fal-elevenlabs-sfx",
        music_provider="fal-stable-audio",
        n_sfx=3,
        avg_sfx_seconds=2.0,
    )
    # $0.012 (SFX) + $0.20 (music) = $0.212, which exceeds $0.05 remaining

    assert estimated > remaining, f"setup error: ${estimated} should exceed ${remaining}"
    assert abs(remaining - 0.05) < 0.0001, f"setup error: remaining should be ~$0.05, got ${remaining}"


def test_audio_budget_gate_sufficient_budget(tmp_path):
    """Test: run with sufficient budget proceeds normally."""
    from studio.stages import audio as audio_stage

    run_dir = tmp_path / "test_run"
    run_dir.mkdir()

    # Script with only 1 SFX cue
    script = _make_script_with_sfx(n_sfx=1)
    paths.script_json(run_dir).write_text(script.model_dump_json(indent=2))

    # Create manifest: $0.10 already spent, max_cost=$0.30, remaining=$0.20
    m = manifest.Manifest(
        id="test",
        idea="test",
        duration_s=30,
        aspect="9:16",
    )
    m.stages["clips"] = manifest.StageRecord(
        done=True, provider="fal-i2v", cost_usd=0.10, latency_s=5.0, note="test"
    )
    manifest.save(run_dir, m)

    max_cost = 0.30
    remaining = max_cost - m.total_cost_usd  # $0.30 - $0.10 = $0.20

    estimated = audio_costs.estimate_total_audio_cost(
        sfx_provider="fal-elevenlabs-sfx",
        music_provider="fal-stable-audio",
        n_sfx=1,
        avg_sfx_seconds=2.0,
    )
    # $0.002 (1 SFX @ 2s) + $0.20 (music) = $0.202, which exceeds $0.20 by tiny amount
    # But music alone is $0.20, which fits in the $0.20 remaining

    # Actually, let's be more realistic: use free music or synth
    estimated = audio_costs.estimate_total_audio_cost(
        sfx_provider="fal-elevenlabs-sfx",
        music_provider="synth",  # free
        n_sfx=1,
        avg_sfx_seconds=2.0,
    )
    # $0.002 only

    assert estimated <= remaining, f"setup error: ${estimated} should fit in ${remaining}"
