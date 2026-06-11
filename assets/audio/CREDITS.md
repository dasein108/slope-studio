# assets/audio — sources & licensing

Audio here must be **synthetic, CC0/public-domain, or otherwise explicitly reusable for this
channel**. Do not add copyrighted files, CC-BY/attribution-required files, CC-BY-NC/non-commercial
files, platform-restricted files, or unclear-license community files.

## sfx/
- `*-synth` style cues: generated locally by `ffmpeg.synth_sfx` (no license — fully synthetic).
- recorded cues: pulled from **Freesound, CC0 filter only** (`license:"Creative Commons 0"`)
  via `scripts/fetch_sfx.py` → `audio._freesound`. Each is CC0.

## music/
- `synth` provider: generated locally by ffmpeg synth helpers (no license — fully synthetic).
- CC0/public-domain loops can be added freely.
- Freesound music fetched by `scripts/fetch_music.py` is CC0/public-domain only.
- Paid/generated provider output from fal is allowed in renders through the provider pipeline.
- Do not stage CC-BY tracks here; the project does not maintain an attribution workflow.

Regenerate/refresh: `python scripts/fetch_sfx.py`
