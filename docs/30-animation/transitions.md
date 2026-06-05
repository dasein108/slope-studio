# Transitions

Per-scene transitions, chosen by narrative context. Set `transition` (and optional
`transition_dur`) on the scene the transition leads *into*. Implemented in
`ffmpeg.concat_xfade_seq`; allowlist in `ffmpeg.TRANSITIONS`.

## Vocabulary & when to use

| `transition` | feel | use when the narration… |
|--------------|------|--------------------------|
| `cut` (default) | instant | is fast/punchy; list items; energetic montage |
| `fade` | soft crossfade | continues the same thought gently |
| `fadeblack` / `fadewhite` | hard reset | starts a NEW chapter/topic |
| `dissolve` | dreamy blend | memory, abstraction, "imagine…" |
| `wipeleft` / `wiperight` | directional push | "next…", sequence, timeline, cause→effect |
| `wipeup` / `wipedown` | vertical push | reveal above/below, stacking |
| `slideleft/right/up/down` | panel slide | enumerated points, comparisons |
| `smoothleft/right/up/down` | eased slide | smoother version of slide |
| `circleopen` | iris reveal | "the answer is…", a reveal, zoom-to-detail |
| `circleclose` | iris collapse | conclusion, focusing down |
| `radial` / `pixelize` | stylized | tech/data/digital topics |
| `zoomin` | push-through | dramatic emphasis, "look closer" |

Full set is in `ffmpeg.TRANSITIONS`; unknown names fall back to `fade`.

## Defaults & duration

- Global default transition for a run: `--transition` (default **`cut`**), `--transition-s` (default 0.4).
- A scene's `transition`/`transition_dur` override the global for that boundary.
- `cut` is rendered as a 1-frame crossfade (imperceptible) so it composes uniformly
  with the compensated stitch. Durations are clamped to fit the neighboring clips.

## Sync {#sync}

`xfade` overlaps shorten the timeline (each transition removes `dur` seconds). Left
uncompensated this drifts the video behind the audio (~5.5s over a 200s video).
`concat_xfade_seq` **pre-extends each non-last clip by its outgoing transition
duration** (holds the last frame), so:

```
output_length == Σ clip_durations == narration_length     # no drift, no truncation
```

xfade `offset` for scene *i* is simply `Σ_{k<i} duration_k`. Verified: stitched
within ~0.02s of narration on a 200s video.

## Authoring tips

- Default most boundaries to `cut` (retention-friendly for Shorts); reserve fancy
  transitions for genuine topic shifts or reveals.
- Match direction to motion: a `motion-driftright` scene reads well entered with `wipeleft`.
- Keep `transition_dur` ≤ ~0.6s for Shorts pacing.

## CLI

```bash
studio stitch <id> --transition cut          # global default; per-scene fields override
```
Per-scene control lives entirely in `01_script.json` (`transition`, `transition_dur`).
