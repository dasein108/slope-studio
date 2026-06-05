# Captions (optional, compact, never clipped)

**Captions are OFF by default.** YouTube (and TikTok) auto-generate captions from the
audio, so most videos don't need burned-in text — and a burned wall of text covers the
visuals. Turn them on only when you want them baked into the pixels (e.g. silent
autoplay feeds): `studio voice <id> --captions burn` or `studio run … --captions burn`.

The `narrate` stage always writes an aligned `captions.srt` regardless — so you can
upload that sidecar to YouTube even when not burning.

## When burned: how it stays on-frame

Burned captions are overlaid as **Pillow-rendered PNG strips** (this machine's ffmpeg
lacks `drawtext`/`subtitles`). Cues come from edge-tts at **sentence** granularity
(`SubMaker`), so a single cue can be a whole sentence (100–150+ chars).

- `cardgen.caption_strip(text, dst)` renders a transparent PNG that is **guaranteed to
  fit a compact lower-third band**:
  1. **Fill-width wrap** — chars-per-line is derived from the font's measured average
     glyph width, so each line fills the usable width → the **fewest possible lines** →
     shortest block (a 152-char cue becomes ~5 lines, not 7).
  2. **Height budget + hard cap** — the font shrinks (56→22px) until the block fits
     **~22% of canvas height**, and the PNG height is then **hard-capped** at that
     budget. It can never be taller than the band.
- `ffmpeg.burn_subs(video, srt, dst)` overlays each strip at `H-h-margin` where
  `margin ≈ 11.5% of H` (clears the TikTok/Shorts action bar). Tight-fit strip +
  bottom margin ⇒ the whole caption is always inside the safe area, **top and bottom**.

## Why this exists (fixed bugs)

1. Long sentence cues used to render at near-full font (64px) across 7 lines, covering
   ~29% of the frame and reading as clipped in cropped player viewports. Fill-width
   wrap + 22% budget + hard height cap fix it.
2. Captions used to be **on by default** and burned into every video. Now off by
   default — opt in per render.

## Authoring tips

- Default: leave captions off; let YouTube auto-caption. Upload `captions.srt` if you
  want accurate sidecar subs.
- Burn (`--captions burn`) for feeds where audio is muted by default and you want text
  baked in. Keep narration sentences punchy (≤ ~16 words) so cues stay 2–3 lines.
- Tune `max_h` (default `0.22*H`) in `cardgen.caption_strip` and the `~0.115*H` margin
  in `ffmpeg.burn_subs` if a platform's safe-area differs.
- `studio voice <id> --captions burn|off` (default **off**). Any value other than
  `burn` skips burning.
