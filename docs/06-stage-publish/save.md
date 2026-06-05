# Stage 6 — Save (Platform-Correct Master)

Trivial ffmpeg encode pass producing the final master from `05_voice/final.mp4`.

## Platform encode targets (2026)
- **Container/codec:** MP4, H.264 (High profile) video + AAC audio. H.265 ok but H.264 is safest for ingestion.
- **Resolution:** 1080x1920 (9:16). Up to 4K vertical accepted but 1080p is the sweet spot.
- **Frame rate:** 30fps (or match source; 24/30/60 all fine).
- **Bitrate:** ~8-12 Mbps video for 1080p vertical; CRF 18-23 with `-preset slow` is simpler.
- **Audio:** AAC 128-192kbps, 48kHz, loudness ~-14 LUFS (done in stage 5).
- **Duration:** ≤180s for YouTube **Shorts** eligibility (now 3 min ✅); TikTok up to 10 min. 150s default fits both.
- **Pixel format:** `yuv420p` (compatibility).

```bash
ffmpeg -i 05_voice/final.mp4 \
  -c:v libx264 -profile:v high -preset slow -crf 20 -pix_fmt yuv420p \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1" \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart \
  06_final.mp4
```
`-movflags +faststart` puts the moov atom first → faster upload processing.

## Metadata sidecar
Write `06_final.json` with `title`, `description`, `hashtags` (from stage 1) so stage 7 publish needs no recomputation.

## CLI
```
studio save --in runs/<id>/05_voice/final.mp4 --aspect 9:16 --fps 30 \
  --out runs/<id>/06_final.mp4
```
