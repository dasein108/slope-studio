"""Canonical artifact paths within a run directory."""

from __future__ import annotations

from pathlib import Path

RUNS_ROOT = Path("runs")


def run_dir(run_id: str) -> Path:
    return RUNS_ROOT / run_id


def brand_dir(slug: str) -> Path:
    """Channel brand-kit assets (banner/profile/logo/brand.md) live here."""
    return RUNS_ROOT / "_brand" / slug


def script_json(d: Path) -> Path:
    return d / "01_script.json"


def critic_json(d: Path) -> Path:
    """Critic-gate verdict for the current scenario (stage 1.5)."""
    return d / "01_critic.json"


def visuals_dir(d: Path) -> Path:
    return d / "02_visuals"


def scene_image(d: Path, sid: int) -> Path:
    return visuals_dir(d) / f"scene_{sid:02d}.png"


def scene_image_bg(d: Path, sid: int) -> Path:
    """Separate background PLATE (subject removed) for true layered parallax — generated
    for parallax scenes on balanced+ tiers so fg/bg are genuinely different images."""
    return visuals_dir(d) / f"scene_{sid:02d}_bg.png"


def scene_image_fg(d: Path, sid: int) -> Path:
    """Separate FOREGROUND plate — the subject generated alone on a flat background and keyed
    to transparency (Route 1). A cleaner cutout than rembg-ing the busy main still; pairs with
    the bg plate for fully purpose-built layered parallax."""
    return visuals_dir(d) / f"scene_{sid:02d}_fg.png"


def clips_dir(d: Path) -> Path:
    return d / "03_clips"


def scene_clip(d: Path, sid: int) -> Path:
    return clips_dir(d) / f"scene_{sid:02d}.mp4"


def stitched(d: Path) -> Path:
    return d / "04_stitched.mp4"


def voice_dir(d: Path) -> Path:
    return d / "05_voice"


def scene_audio_dir(d: Path) -> Path:
    return voice_dir(d) / "scenes"


def scene_audio(d: Path, sid: int) -> Path:
    return scene_audio_dir(d) / f"scene_{sid:02d}.mp3"


def timing_json(d: Path) -> Path:
    """Per-scene clip durations derived from narration (drives clips + mux sync)."""
    return voice_dir(d) / "timing.json"


def narration_mp3(d: Path) -> Path:
    return voice_dir(d) / "narration.mp3"


def captions_srt(d: Path) -> Path:
    return voice_dir(d) / "captions.srt"


def final_with_audio(d: Path) -> Path:
    return voice_dir(d) / "final.mp4"


def master(d: Path) -> Path:
    return d / "06_final.mp4"


def meta_json(d: Path) -> Path:
    return d / "06_final.json"


def thumbnail(d: Path) -> Path:
    """YouTube preview/thumbnail (1280×720) — built by `studio thumbnail`, auto-set on upload."""
    return d / "06_thumb.png"


def publish_json(d: Path) -> Path:
    return d / "07_publish.json"


def stats_json(d: Path) -> Path:
    """Per-run YouTube stats snapshot (views/likes/comments/retention)."""
    return d / "08_stats.json"


def comments_json(d: Path) -> Path:
    """Per-run fetched comments (audience feedback)."""
    return d / "08_comments.json"


def sfx_dir(d: Path) -> Path:
    """Per-scene generated/sourced sound effects."""
    return d / "05b_sfx"


def sfx_placements_json(d: Path) -> Path:
    """[(path, global_start_s, gain_db)] the voice stage overlays onto narration."""
    return sfx_dir(d) / "placements.json"


def music_track(d: Path) -> Path:
    """The single background-music bed for the run."""
    return d / "05c_music.mp3"


# ---- local audio asset library (downloaded CC0 / licensed-safe packs) --------
# Drop license-safe files here, one tag-rich filename per asset, e.g.
# assets/audio/sfx/sword_clash_metal.mp3, assets/audio/music/calm_ambient_lofi.mp3.
# The `local` audio provider keyword-matches a clip's prompt against filenames.
AUDIO_LIBRARY_ROOT = Path("assets/audio")


def audio_library_dir(kind: str) -> Path:
    """kind = 'sfx' | 'music'."""
    return AUDIO_LIBRARY_ROOT / kind


# ---- mouth-sprite library for talking-head lip-sync (animator=talkinghead) --
# Drop a per-character sprite set here as transparent PNGs named by Rhubarb mouth
# shape: assets/mouths/<set>/{A,B,C,D,E,F,G,H,X}.png. Missing shapes are drawn by
# cardgen.mouth_sprite_image. See docs/30-animation/effects/talking-head.md.
MOUTH_LIBRARY_ROOT = Path("assets/mouths")


def mouth_library_dir(set_name: str = "default") -> Path:
    return MOUTH_LIBRARY_ROOT / (set_name or "default")


# ---- marketing-guru: cross-run, per-channel growth journal -----------------
def marketing_dir(channel: str = "") -> Path:
    """Namespace the viral-growth journal by channel (mirrors the OAuth token)."""
    return RUNS_ROOT / "_marketing" / (channel or "_default")


def journal_json(channel: str = "") -> Path:
    return marketing_dir(channel) / "journal.json"


def journal_md(channel: str = "") -> Path:
    return marketing_dir(channel) / "journal.md"


def marketing_report_md(channel: str = "") -> Path:
    return marketing_dir(channel) / "report.md"
