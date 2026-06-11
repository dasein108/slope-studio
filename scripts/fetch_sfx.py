"""Stage a free, reusable SFX library into assets/audio/sfx/ for the `local` sfx provider.

`assets/` is gitignored — this is fetch-on-demand, run once:
    python scripts/fetch_sfx.py

Two layers (both CC0 / no-attribution, monetization-safe):
  1. SYNTH STARTER (always, keyless) — a handful of generic cues synthesized in ffmpeg
     (whoosh / rumble / sparkle / impact / hum). Crude but immediately usable.
  2. FREESOUND CC0 (richer, needs FREESOUND_API_KEY) — real recordings (wind, fire, waves,
     crowd, sword, …) pulled CC0-only via the existing audio._freesound helper.

Files are named with multiple keywords so audio._local_pick matches a scene's `sfx` cue by
filename overlap (e.g. a cue "deep impact boom" → impact-boom-hit.mp3).
"""

from __future__ import annotations

from studio import ffmpeg, paths
from studio.config import env
from studio.providers import audio

# keyless synth starter: (filename stem with keywords, ffmpeg synth kind)
SYNTH = [
    ("wind-whoosh-swish", "whoosh"),
    ("low-rumble-tension-drone", "rumble"),
    ("high-sparkle-shimmer-chime", "sparkle"),
    ("impact-boom-hit-thump", "impact"),
    ("deep-cosmic-hum-space", "hum"),
]

# freesound CC0 (needs key): (query, filename stem with keywords)
FREESOUND = [
    ("wind howling ambience", "wind-ambience"),
    ("fire crackle campfire", "fire-crackle-flames"),
    ("rain storm ambience", "rain-storm"),
    ("ocean waves sea shore", "ocean-waves-sea"),
    ("crowd murmur tavern people", "crowd-murmur-people"),
    ("sword metal clash blade", "sword-clash-metal"),
    ("heartbeat pulse", "heartbeat-pulse"),
    ("distant bell toll church", "bell-toll-distant"),
    ("clock ticking", "clock-ticking"),
    ("birds forest ambience", "birds-forest-ambience"),
    ("thunder rumble storm", "thunder-rumble"),
    ("footsteps gravel walking", "footsteps-walking"),
]

CREDITS = """# assets/audio — sources & licensing

All audio here is **CC0 / public-domain or synthesized** (no attribution required, safe for
monetized video). Do not add CC-BY or CC-BY-NC files.

## sfx/
- `*-synth` style cues: generated locally by `ffmpeg.synth_sfx` (no license — fully synthetic).
- recorded cues: pulled from **Freesound, CC0 filter only** (`license:"Creative Commons 0"`)
  via `scripts/fetch_sfx.py` → `audio._freesound`. Each is CC0.

## music/
- `synth` provider: generated locally by `ffmpeg.synth_drone` (no license — fully synthetic).
- to add tracks: drop **CC0** loops here (Freesound CC0, OpenGameArt CC0). Pixabay audio is
  free-to-use but NOT CC0/redistributable — use it in a render, don't commit it as a pack.

Regenerate/refresh: `python scripts/fetch_sfx.py`
"""


def main() -> None:
    sfx = paths.audio_library_dir("sfx")
    sfx.mkdir(parents=True, exist_ok=True)
    paths.audio_library_dir("music").mkdir(parents=True, exist_ok=True)

    print(f"== synth starter → {sfx} ==")
    for stem, kind in SYNTH:
        dst = sfx / f"{stem}.mp3"
        try:
            ffmpeg.synth_sfx(dst, kind)
            print(f"  ✓ {stem}.mp3")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {stem}: {str(e)[:80]}")

    if env("FREESOUND_API_KEY"):
        print("== freesound CC0 (rich set) ==")
        for query, stem in FREESOUND:
            dst = sfx / f"{stem}.mp3"
            if dst.exists():
                print(f"  skip {stem} (exists)")
                continue
            try:
                note = audio._freesound(query, dst, want_music=False)
                print(f"  ✓ {stem}.mp3 — {note}")
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ {stem}: {str(e)[:80]}")
    else:
        print("== freesound skipped — no FREESOUND_API_KEY ==")
        print("   Free key (30s): https://freesound.org/apiv2/apply/ → add FREESOUND_API_KEY to .env → re-run.")
        print("   Or drop CC0 .mp3/.wav into the dir manually (Kenney CC0: https://kenney.nl/assets?q=audio).")

    (paths.audio_library_dir("sfx").parent / "CREDITS.md").write_text(CREDITS)
    n = len(list(sfx.glob("*.mp3")))
    print(f"done — {n} sfx in {sfx}; music beds are free via --music-provider synth")


if __name__ == "__main__":
    main()
