---
name: youtube-branding
description: Create a complete YouTube channel brand kit — banner, profile picture, transparent video logo/watermark, plus channel keywords and description — from a channel name + slogan + niche. Use when the user wants to brand or rebrand a YouTube (or other) channel: design/generate a banner, avatar, logo, watermark, or write channel keywords/description. A marketing-guru lego-block; drives the `studio brand` CLI (real images via Nano Banana).
---

# youtube-branding

The **channel-identity** lego-block of the marketing-guru family. Before you ideate
and deploy videos (`marketing-ideate` → `marketing-deploy`), a channel needs a face:
this skill turns a **name + slogan + niche** into a full, upload-ready brand kit.

| Asset | Size | YouTube use |
|-------|------|-------------|
| `banner.png` | 2560×1440 | Channel banner (art + exact wordmark in the safe area) |
| `profile.png` | 1024×1024 | Channel profile picture / avatar |
| `logo.png` | 1024² transparent | Branding master (transparent PNG) |
| `logo_512.png` | 512² transparent | **Watermark to overlay ON videos** |
| `brand.md` | — | Channel keywords + description (copy-paste) |

Where it sits in the growth loop (see `marketing-guru`):
```
   [ youtube-branding ]  →  IDEATE → BACKLOG → DEPLOY → MEASURE → LEARN
      (channel setup,         (what to make & how it does, per channel)
       once / on rebrand)
```

## How it works — division of labour

The mechanical pipeline lives in the `studio` package (`studio/marketing/brand.py`)
and is driven by the **`studio brand <spec.json>`** CLI command. It:
- requests the art **text-free** from Nano Banana, then **Pillow-overlays the wordmark**
  in YouTube's safe area (never trust the image model to spell),
- cuts the logo to transparency with **rembg**, and cover-crops to upload sizes.

**You (the agent)** author the *brand identity* — palette, emblem concept, banner scene
— into a brand-spec JSON. That creative judgement is the whole job; the CLI is just I/O.

## Workflow

### 0. Setup (once)
```bash
cd /Users/dasein/dev/slope-studio
source .venv/bin/activate 2>/dev/null || { uv venv && source .venv/bin/activate && uv pip install -e ".[fal]"; }
grep -q FAL_KEY .env && echo "FAL_KEY ok" || echo "MISSING FAL_KEY — set it in .env (needed for real art)"
```

### 1. Gather inputs
You need: **channel name**, **slogan**, and the **niche/aesthetic**. If the aesthetic is
unstated, infer one from the niche (don't over-ask) — pick a palette + a single
repeatable **motif/emblem** that ties avatar↔logo.

### 2. Author a brand-spec JSON
Copy [`example-spec.json`](example-spec.json) and rewrite every field. Rules that make
the output good:
- **`style`** is appended to all three prompts and **MUST end with** `no text, no letters, no words` — the wordmark is added later by Pillow, so the art must be clean.
- **`logo_prompt`** → a flat, simple, *iconic* emblem on a **plain solid background**
  (rembg cuts that background out). Keep it legible at watermark size — few elements.
- **`profile_prompt`** → the **same motif**, centered, filling the square, readable when tiny.
- **`banner_prompt`** → wide 16:9 cinematic art with **empty negative space across the
  centre** (push detail to the left/right edges) so the wordmark has room.
- **`palette`** → `primary` (deep bg), `accent` (title glow + rule), `highlight`
  (slogan), `text` (title fill), each `[r,g,b]`.
- **`name`** / **`slogan`** are the exact wordmark text; **`keywords`** / **`description`**
  are the channel copy. **`slug`** is the output folder under `runs/_brand/`.

### 3. (optional, free) Dry-run the wiring
```bash
# validates the spec + full Pillow/rembg pipeline with offline placeholder art, $0.
# ⚠ writes to runs/_brand/<slug>/ and OVERWRITES — set a THROWAWAY "slug" for the test.
studio brand myspec.json --provider stub
```

### 4. Generate the real kit (~$0.12)
```bash
studio brand myspec.json
```
Three Nano Banana stills @ $0.039 = **~$0.117**. Output lands in `runs/_brand/<slug>/`.

### 5. Eyeball every asset and iterate
**Always** view `banner.png`, `profile.png`, `logo.png` — verify:
- banner wordmark is centered, legible, not colliding with busy art;
- logo cut is clean (no halo) and transparent (`logo.png` corner alpha = 0);
- the motif is the **same** emblem on logo and profile.

Re-roll a weak asset by tweaking its prompt in the spec and re-running (a full run
re-rolls all three stills; accept the small re-spend, or dry-run with `stub` first).

### 6. Deliver
Report the asset paths, the keywords, and the description, and where each goes on
YouTube (banner / picture / Settings→Basic info). Offer the **video watermark** overlay:
```bash
# overlay logo_512.png bottom-right at ~10% width on a finished video
ffmpeg -i in.mp4 -i runs/_brand/<slug>/logo_512.png -filter_complex \
  "[1]scale=iw*0.10:-1[wm];[0][wm]overlay=W-w-40:H-h-40" -c:a copy out.mp4
```

## Notes & gotchas
- **Never bake channel text into the AI image** — image models misspell. `name`/`slogan`
  are always Pillow-overlaid; that's why `style` must forbid text.
- **Custom banner/profile** upload anytime; a custom **video thumbnail** (different thing,
  see film-maker `studio thumbnail`) needs a *verified* YouTube channel.
- Logo background removal is **rembg** (already a dep) — it cuts a clear foreground subject
  from a plain background, so author `logo_prompt` with a clean subject on a flat bg.
- Fonts auto-pick the boldest macOS face (Avenir Next Condensed / Futura / Helvetica),
  with graceful fallback.
- This makes **static brand art**, not video. Produce videos with `film-maker`; decide
  what to post and run the loop with `marketing-guru`.
