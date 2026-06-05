# Kinetic typography (`animator: "kinetic"`)

Motion-graphics look: an animated background still + a big headline that **slides up
and fades in**. Free (Pillow + ffmpeg), $0. Implemented in `ffmpeg.kinetic` +
`cardgen.headline_png`; orchestrated in `animate._kinetic`.

## What it produces

- Background: the scene image with a `pulse` motion preset.
- Foreground: `on_screen_text` rendered as a bold white/stroked headline PNG, overlaid
  at ~18% height, fading in over 0.6s while sliding up 50px.

## Pairing rule (important)

Use kinetic with a **text-free background** — i.e. `fal-nanobanana` illustrations.
The free `card` image provider already bakes `on_screen_text` into the image, so
kinetic over a card renders the headline **twice**. Options:
- Pair kinetic with `--image-provider fal-nanobanana` (illustrations have no baked text), or
- Use a plain (textless) background for kinetic scenes.

## Choosing per scene

- Great for hook scenes, statements, and "quote" style beats.
- Combine with `transition: "fade"` or `slideup` for a smooth motion-graphics feel.
- The narration still plays + sentence captions still burn at the bottom; the kinetic
  headline sits separately near the top, so they don't collide.

## Tuning

Edit `ffmpeg.kinetic` (fade duration, slide distance, y position, base preset) and
`cardgen.headline_png` (font size, stroke, wrap width). Keep ALL ffmpeg in
`studio/ffmpeg.py`.

## Example scene

```json
{"id": 1, "animator": "kinetic", "transition": "cut",
 "on_screen_text": "YOU'RE BEING LIED TO",
 "narration": "Everything you learned about this is about to change.",
 "visual_prompt": "<character/style>, dramatic abstract background, 9:16"}
```
(Author this scene's image via fal-nanobanana so the headline isn't doubled.)
