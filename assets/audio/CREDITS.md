# assets/audio — sources & licensing

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
