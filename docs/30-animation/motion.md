# Motion presets (`animator: "motion-*"` and `kenburns`)

Free pseudo-animation: move a static image. Implemented in `ffmpeg.motion`
(zoompan expressions), presets in `ffmpeg._MOTION`. No deps, $0.

## Presets

| `animator` | motion | use for |
|------------|--------|---------|
| `kenburns` (default) | slow centered zoom-in pan | safe default for any still |
| `motion-zoomin` | stronger push-in | "look closer", emphasis |
| `motion-zoomout` | pull-back reveal | establishing, "the bigger picture" |
| `motion-pulse` | gentle breathing scale | energy, beats, keep-alive |
| `motion-driftright` | pan left→right | forward progression, reading direction |
| `motion-driftleft` | pan right→left | rewind, "back to…" |
| `motion-driftup` | pan bottom→top | rising, growth, "up" |
| `motion-driftdown` | pan top→bottom | falling, descent, "down" |

## How it works

Each preset is a `(zoom, x, y)` zoompan expression triple; `{N}` = total frames.
The image is upscaled 2× for pan headroom, then zoompan renders `seconds × fps`
frames to a 1080×1920 clip. Clip length is later fit to the scene's narration
duration in `clips` (hold/trim).

## Choosing per scene

- Match the preset to the verb in the narration ("rises" → `driftup`, "zoom in" →
  `motion-zoomin`, "everything" → `motion-zoomout`).
- Alternate presets across scenes to avoid monotony.
- For text-free illustrations you can layer a headline too — see [`kinetic.md`](kinetic.md).

## Add a new preset

Add an entry to `ffmpeg._MOTION` with a zoompan `(z, x, y)` expression triple
(use `on` for frame index, `{N}` for total frames), then reference it as
`animator: "motion-<name>"`. No other changes needed.

## Example scene

```json
{"id": 4, "animator": "motion-driftright", "transition": "wipeleft",
 "on_screen_text": "STEP 3", "narration": "...", "visual_prompt": "..."}
```
