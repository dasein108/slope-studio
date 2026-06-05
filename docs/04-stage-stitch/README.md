# Stage 4 — Stitch (Glue Clips + Transitions)

Pure **ffmpeg**. Free, deterministic, scriptable. ✅ ffmpeg is the verified standard for CLI video assembly. No AI needed.

## Job
Take `03_clips/*.mp4`, normalize them (same resolution/fps/pixel format/aspect), and concatenate with transitions into `04_stitched.mp4` (video only — audio comes in stage 5). Also: pad/crop to 9:16, add B-roll/overlays, on-screen text.

## Normalize first (clips from different models differ)
```bash
# scale+pad every clip to 1080x1920, 30fps, yuv420p
ffmpeg -i scene_01.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,\
pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30" -pix_fmt yuv420p -an norm_01.mp4
```

## Transitions — `xfade`
ffmpeg's `xfade` filter does crossfades/wipes/slides between two streams. Offset = (clip1 duration − transition duration).
```bash
ffmpeg -i norm_01.mp4 -i norm_02.mp4 -filter_complex \
"[0][1]xfade=transition=fade:duration=0.5:offset=5.5" out.mp4
```
Useful `transition=` values: `fade`, `fadeblack`, `wipeleft/right/up/down`, `slideleft`, `circleopen`, `dissolve`, `smoothleft`, `pixelize`, `radial`. For N clips, chain `xfade` filters or build the filtergraph programmatically.

- **Hard cuts** (fastest, best for fast-paced shorts): just `concat`. Faster + often higher retention than fancy transitions.
- **Concat demuxer** (no re-encode, same codec params) is fastest:
```bash
printf "file 'norm_01.mp4'\nfile 'norm_02.mp4'\n" > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c copy 04_stitched.mp4
```

## Extras done here
- **Ken Burns** (budget no-video path): pan/zoom a still → motion clip via `zoompan`.
- **On-screen text** from `01_script.json` `on_screen_text`: `drawtext` or burn an ASS subtitle. (Or defer captions to stage 5.)
- **B-roll / overlay** (logo, progress bar): `overlay` filter.
- **Background music bed:** mix here or in stage 5.

## Helper libraries (optional, over raw ffmpeg)
🔶 `ffmpeg-python` (filtergraph in Python), `moviepy` (higher-level, slower, easy transitions/text), `auto-editor` (silence trimming). MoviePy is convenient for text/transitions but slower than hand-written ffmpeg; for a pipeline, generate ffmpeg commands programmatically.

## Recommendation
- Fast-paced shorts: **hard cuts + concat demuxer** (fastest, retention-friendly), occasional `xfade` for chapter breaks.
- Build the filtergraph in Python from the scene manifest (durations known) so transitions are data-driven.

## CLI
```
studio stitch --clips runs/<id>/03_clips/ --transition fade --transition-s 0.4 \
  --aspect 9:16 --fps 30 --out runs/<id>/04_stitched.mp4
```
