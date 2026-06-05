# Captions (burned, never clipped)

Captions are burned in by overlaying **Pillow-rendered PNG strips** (this machine's
ffmpeg lacks `drawtext`/`subtitles`). Cues come from edge-tts at **sentence**
granularity (`SubMaker`), so a single cue can be a whole sentence.

## The components

- `cardgen.caption_strip(text, dst)` — renders a **tight-fit** transparent PNG: it
  wraps the text and shrinks the font on **both width AND height** (64→30px) until
  the whole block fits, then sizes the canvas to exactly the text + padding. So the
  PNG is never taller than its content.
- `ffmpeg.burn_subs(video, srt, dst)` — overlays each strip at `H-h-220`: lower
  third, **clear of the TikTok/Shorts action bar** (~bottom 200px). Because the
  strip is tight-fit, the full block is always on-frame.

## Why this exists (fixed bug)

Long sentence cues used to overflow a fixed-height strip and get clipped off the
bottom of the frame. The tight-fit strip + height-aware shrink + raised overlay
margin guarantee the whole caption is visible in the safe area.

## Authoring tips

- Keep narration sentences punchy (≤ ~16 words). 2–3 caption lines look best;
  4-line cues fit but sit low.
- Tune `max_h` (default 560) in `cardgen.caption_strip` and the `H-h-220` margin in
  `ffmpeg.burn_subs` if a platform's safe-area differs.
- `studio voice <id> --captions burn|soft|none` selects burn-in / sidecar / off.
