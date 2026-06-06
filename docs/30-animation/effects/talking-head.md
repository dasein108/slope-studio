# Talking head — 2D lip-sync on a static face

Cheap anime/VTuber-style narration: the **face stays static, the mouth moves** in sync
with the voiceover. Free, headless, deterministic, commercial-clean. **Tier 2 is wired**
as `animator:"talkinghead"`.

## The three tiers (and why we shipped Tier 2)

| tier | technique | cost / deps | quality | commercial |
|------|-----------|-------------|---------|-----------|
| 1 amplitude flap | RMS envelope → open/mid/closed mouth | $0, no deps | rough flap | ✅ clean — *backlog* |
| **2 Rhubarb visemes** ✅ | phoneme→mouth-shape timeline → sprite swap | $0, **Rhubarb binary** (MIT) | good 2D lip-sync | ✅ clean |
| 3 AI talking-head | Wav2Lip / SadTalker / LatentSync | GPU + model | photoreal | ⚠️ **Wav2Lip = non-commercial** (LRS2); verify each |

**Tier 2 (Rhubarb)** is the sweet spot for this pipeline: free, runs headless next to the
per-scene narration we already synth, deterministic, and its stylized look matches the
anime/ukiyo-e direction. AI talking-heads (Tier 3) need a GPU and carry licensing
landmines (Wav2Lip's code was relicensed to **non-commercial/research only**) — avoid for a
monetized channel unless you confirm a clean license.

Sources: [Rhubarb Lip Sync (MIT)](https://github.com/DanielSWolf/rhubarb-lip-sync) ·
[Wav2Lip non-commercial](https://github.com/Rudrabha/Wav2Lip/issues/623). See
[`sources.md`](sources.md).

## How the wired `talkinghead` animator works

Code: `animate._talkinghead` (+ `ffmpeg.to_wav` / `ffmpeg.frames_to_video`,
`cardgen.mouth_sprite_image`). Per scene:

1. The scene's narration mp3 (`05_voice/scenes/scene_NN.mp3`, produced by **narrate**,
   which runs before clips) → mono WAV.
2. **Rhubarb** analyzes the WAV (+ the scene `narration` text as a dialog hint for
   accuracy) → a timeline of mouth **shapes** (`A`–`H`, `X`; the Preston-Blair /
   Hanna-Barbera standard) as JSON `{"mouthCues":[{"start","end","value"}]}`.
3. The scene still is the **static face**; for each video frame we composite the active
   shape's **mouth sprite** at the mouth anchor.
4. Frames → silent mp4. The voice stage later muxes the SAME narration over the video, so
   the lips line up.

Determinism: same audio + same sprites → same frames (no RNG). If `rhubarb` or the audio is
missing, the scene **falls back to kenburns** (recorded in the manifest note) — never breaks.

## Install Rhubarb (one-time)

It's a prebuilt binary on GitHub Releases (**not** in Homebrew — there is no
`rhubarb-lip-sync` formula), MIT-licensed, commercial-OK. It ships **with a `res/`
folder it needs alongside the executable**, so don't copy the bare binary — keep the
folder and put a symlink (or the folder) on PATH.

```bash
# macOS (latest = v1.14.0). The mac build is x86_64 → Apple Silicon runs it via Rosetta.
mkdir -p ~/tools && cd ~/tools
curl -fL -o rhubarb.zip https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-macOS.zip
unzip -oq rhubarb.zip && rm rhubarb.zip
DIR="$HOME/tools/Rhubarb-Lip-Sync-1.14.0-macOS"
xattr -dr com.apple.quarantine "$DIR"          # clear Gatekeeper quarantine
ln -sf "$DIR/rhubarb" /opt/homebrew/bin/rhubarb # or any dir on PATH (~/.local/bin)
command -v rhubarb && rhubarb --version
# Apple Silicon: if you see "bad CPU type", install Rosetta:
#   softwareupdate --install-rosetta --agree-to-license
```
Other OSes: grab `…-Linux.zip` / `…-Windows.zip` from
<https://github.com/DanielSWolf/rhubarb-lip-sync/releases>. A bare-binary symlink works
because Rhubarb resolves the symlink to find its `res/` folder (verified).

## Authoring a talking-head scene

```jsonc
{
  "id": 3, "start_s": 8, "end_s": 13,
  "visual_prompt": "<character>, head-and-shoulders portrait, mouth closed, facing camera",
  "narration": "And that is why the cat always lands on its feet.",
  "animator": "talkinghead",
  "mouth_xy": [0.5, 0.62, 0.18],    // mouth anchor (x, y) + optional width, all fractions
  "mouth_set": "pols-narrator"      // optional: assets/mouths/pols-narrator/{A..X}.png
}
```

- **`mouth_xy`** — where the mouth sits on YOUR face still, as fractions 0–1: `[x, y]` or
  `[x, y, width]`. The optional **3rd value scales the mouth sprite** to that fraction of the
  frame width, so the mouth matches the face's size (default width `0.18`).
- **Auto-detection (LLM):** any of `x` / `y` / `width` you leave out is filled in by a
  vision LLM that locates the mouth on the actual rendered face (`animate._detect_mouth` →
  `llm.vision_json`, Gemini by default). So you can omit `mouth_xy` entirely and it'll try to
  place + size the mouth for you. It's best-effort — on clear human/portrait faces it's
  usually good; on small or stylized cartoon/animal faces it can land off, so **pin
  `mouth_xy` explicitly when you need precision** (the manifest note shows `+llm-mouth` when
  detection ran). Detection failures (no key, bad output) fall back to your anchor or the
  `[0.5, 0.6, 0.18]` default — lip-sync never breaks.
- **`mouth_set`** — name of a sprite set under `assets/mouths/<set>/`. Omit for the drawn
  cartoon default.
- Generate the face with a **closed mouth** ("mouth closed" in the prompt) so the open
  sprites read as the mouth opening.

## Mouth sprites — drawn default vs. your own (recommended for quality)

The drawn default (`cardgen.mouth_sprite_image`) is a legible cartoon mouth per shape —
fine for stylized/faceless, but it won't match an arbitrary AI face's art style. For a
polished look, **drop a matching sprite set** (one transparent PNG per Rhubarb shape) into
`assets/mouths/<set>/`:

```
assets/mouths/pols-narrator/
  A.png  B.png  C.png  D.png  E.png  F.png  G.png  H.png  X.png
```
A/X = closed (rest), D = wide open, F = puckered (see the shape guide in the
[Rhubarb README](https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes)). Size each
PNG to the mouth region; it's centered on `mouth_xy`. Missing shapes fall back to drawn.
(`assets/` mirrors the `assets/audio/` library convention.)

## Limitations & roadmap

- **Anchor is manual** (no landmark detection). A mediapipe/face-mesh auto-anchor is a
  backlog enhancement.
- **Static head only** — no head bob/blink. Could add a subtle idle motion later.
- **Tier 1 amplitude fallback** (no Rhubarb, drives the mouth off loudness) is documented
  backlog — today, no Rhubarb → kenburns.
- Belongs to the **"Avatar narrator format"** roadmap item (`docs/20-research/open-questions.md`).

## Status

✅ **Live** — `animator:"talkinghead"`. Promote-an-effect mechanics:
[README → adding an effect](README.md#adding-an-effect).
