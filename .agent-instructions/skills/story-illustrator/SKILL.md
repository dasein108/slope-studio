---
name: story-illustrator
description: >
  Operator playbook for long-form story/audiobook illustration videos with
  CONSISTENT recurring characters. Use when the user wants to illustrate an
  existing story or audiobook text as a video, build/rebuild a character card
  from a reference-image folder (characters/<name>/), or debug character look
  drift between generated scenes.
---

# story-illustrator — long videos from prose, with characters that keep their face

Turns finished prose (a story, an audiobook chapter) into a long illustrated video.
Characters are *learned once* from a folder of reference images and stay visually
consistent across every scene — including multi-character scenes.

## Mental model

Two artifacts do all the anti-drift work; protect them:

1. **The character card** (`characters/<name>/card.json`) — a LOCKED identity
   descriptor + 1 canonical anchor image. The descriptor is injected verbatim into
   every scene prompt at render time (the storyboard LLM never sees it, so it can't
   paraphrase it). The SAME anchor image is sent to the image model for every scene.
2. **The storyboard script** (`01_script.json`) — scenes carry `characters: [...]`
   tags; `visual_prompt` holds ONLY action + setting, never a character's look.

Generation = Nano Banana edit mode (multi-image reference) for character scenes,
cheap model (flux-schnell/pollinations) for scenery beats — roughly halves cost.
A vision drift-gate compares each rendered character scene against the card and
regenerates once with concrete corrections.

## Workflow

### 1. Prepare characters (once per character)

Put 2–8 clear reference images in `characters/<name>/` (face visible, single
subject). Then:

```bash
studio characters-build gurdjieff                      # card + best-ref anchor
studio characters-build gurdjieff --portrait --style "painterly 1900s oil"
```

`--portrait` renders ONE neutral master portrait (from the best reference, in the
video's art style) and makes it the sole anchor — strongest consistency; use it
whenever the character recurs across videos. Rebuild the card if the folder changes.
Check the printed descriptor: fix wrong facts by editing `card.json` directly
(it's yours to curate — the build is a starting point).

### 1b. Characters WITHOUT reference images (text-derived cards)

A story usually has characters nobody has photos of (the abbot, the sister, the
stranger). Their look must still be decided ONCE and reused — otherwise the image
model re-imagines them every scene and they drift. Two ways to lock them:

- **Automatic:** `studio storyboard --discover` (the default) lists the story's
  recurring characters, and for any without a card analyzes the WHOLE story text,
  extracts every physical characteristic the prose states, invents concrete
  era-consistent specifics where the text is silent (committed, never "average"),
  and writes a text-derived `card.json` (no images, descriptor-only).
- **Manual:** `studio characters-extract "the abbot" stories/ch1.txt` — same
  analysis for one named character; then curate the descriptor by hand.

Text-derived cards flow through the same machinery: the locked descriptor is
injected verbatim into every scene ("draw from this description IDENTICALLY"),
character scenes stay on the reference-capable model, and the drift gate verifies
frames against the descriptor. Image-backed and text-derived characters mix freely
in one scene. If a text character later gets real photos: drop them in the folder
and `characters-build` — the image card replaces the text card.

### 2. Storyboard the prose

```bash
studio storyboard story.txt --duration 1800 --aspect 16:9 \
    --style "painterly, muted, 1900s" --characters-root characters/
```

~18s per beat (1800s → ~100 beats). Discovery runs first (see 1b): unknown
recurring characters get text-derived cards before segmentation, so every tagged
character has a locked identity before the first frame renders. Inspect
`01_script.json`: are the right character names tagged on the right scenes?
Aliases live on the card — add story spellings ("G.", "Georgi Ivanovich") to
`card.json` `aliases` and re-run if beats were missed. Also skim the generated
text-derived descriptors under `characters/*/card.json` — edit any wrong invention
NOW, before rendering (changing a look after frames exist is the drift you're
trying to avoid).

### 3. Render

```bash
studio visuals <run_id> --characters-root characters/          # drift gate ON
studio narrate <run_id> && studio clips <run_id> --strategy kenburns
studio stitch <run_id> && studio audio <run_id> && studio voice <run_id> && studio save <run_id>
```

Character scenes bill Nano Banana ($0.039 + occasional $0.039 retry); scenery
beats use the cheap provider. 30-min video ≈ $2–4 in images. Motion comes free
from the animator library (kenburns/parallax/drift); long-form pacing tricks
(silent interludes, reused stills) apply as in the film-maker skill.

### 4. Verify consistency by eye

Spot-check 5–6 character frames across the video (`02_visuals/scene_*.png`),
early/middle/late. If a face drifted despite the gate:
- rebuild the card with `--portrait` (single-anchor beats multi-ref folders);
- tighten the descriptor (name the 2–3 non-negotiable features first);
- confirm the same `--style` string was used everywhere (style drift reads as
  character drift).

## Publishing a whole BOOK, chapter by chapter

```bash
pdftotext -enc UTF-8 book.pdf stories/<book>/book.txt      # if source is a PDF
studio book-split stories/<book>/book.txt                   # → ch01..chNN.txt + index.json
# build the recurring cast ONCE (shared by every chapter — that's the whole point):
studio characters-extract gurdjieff stories/<book>/ch01.txt --age-shift -15
# per chapter, in order:
studio storyboard stories/<book>/ch05.txt --duration 600
studio visuals <run_id> --characters-root characters/
studio narrate <run_id> && studio clips <run_id> --strategy kenburns && studio stitch <run_id>
studio audio <run_id> --sfx-provider freesound --music-provider synth   # sounds: see below
studio voice <run_id> && studio save <run_id>
```

- `book-split` cleans PDF page furniture first (running heads/footers, standalone
  page numbers, form feeds, decorative separators, hyphenated line breaks — narration
  must never read a page number aloud; `--no-clean` to skip) and ignores
  table-of-contents lines automatically (`--pattern` for unusual headings). Non-Latin books work end-to-end: narration stays in the source language
  (prompted), descriptors stay English (image models read English best), and card
  `aliases` carry the source-language spellings so tagging works.
- The cast cards are built once and REUSED for all chapters — never rebuild between
  chapters of the same book (that would be self-inflicted drift). Curate the cards
  after chapter 1 renders, then freeze them.
- `--age-shift -15` on either card builder depicts a character N years younger/older
  than the sources show, stated explicitly in the locked descriptor.

## Character age = STORY-TIME age (and it moves)

A character's depicted age is their age **at the point in the story being
illustrated** — never their age in famous later-life photographs, and never a
guess frozen for the whole book:

1. **Anchor the base**: descriptor states the age at the book's opening, and the
   card `note` records the base year (e.g. "37 at book start, 1915").
2. **Track narrative time**: when the text says years passed ("десять лет спустя",
   a dated chapter, a war ends), age every affected card by that much — edit the
   age words in the descriptors BEFORE rendering those chapters, and note the
   chapter range the edit applies to.
3. **Mind obstacles the text imposes** (illness, prison, hard travel age a face;
   the descriptor may say so when the story does).
4. **CLARIFY FIRST when unclear.** If the story's date, a character's age, or a
   time jump cannot be established from the text or the operator's brief — ASK
   the operator BEFORE starting visuals. Age is the one thing you cannot cheaply
   remake later (it invalidates every character frame). This is the explicit
   exception to "don't ask, run".

## Defaults — don't ask, run

When the operator gives no preference, use these and proceed (mention them in the
report, don't question first):

| Missing info | Default |
|---|---|
| style | leave `--style` empty → era-appropriate painterly, decided by the storyboard LLM from the text |
| aspect / duration | 16:9, 600s per chapter |
| character look (non-age) | whatever the story + card builder derive |
| character AGE | **not defaultable — see the story-time age section; ask if unclear** |
| voice | `narrator`, tone `neutral`, story's own language |
| sounds | the sparse policy below |

## Sounds — sparse, cheap, quiet (policy)

The storyboard prompt already enforces this shape; keep it when editing scripts:

- **Sparse:** at most 1 beat in 5 carries an sfx cue, and only where the text names a
  real sound (train, rain, bell, door). Purely visual beats get nothing.
- **Quiet:** cues at `gain_db: -14` (well under narration); the voice stage ducks the
  bed further. Never add music per-scene — one `Script.music` mood for the whole
  video or none.
- **Cheap:** `studio audio <run> --sfx-provider freesound --music-provider synth`
  (both $0). The default audio providers silently bill (~$0.20/video) — only use
  fal SFX/stable-audio when the operator asks for premium sound.

## Gotchas (earned on the first real book)

- **Re-narrating invalidates every existing clip.** Clips are cut to the narration
  timing; if you re-run narrate (different provider/voice), you MUST `studio clips
  <run> --force` afterwards — otherwise old-timing and new-timing clips mix and the
  master desyncs mid-video. Clips are free; always rebuild.
- **edge-tts throttles bursts** — the provider retries 3× with backoff now, but if a
  whole-book batch still trips it, space chapters out.
- **Big chapters are chunked automatically** (~24k chars per LLM call) — one giant
  call times out AND tags characters poorly. Don't raise CHUNK_CHARS.
- **Non-English narration**: pass `--voice-name ru-narrator` (voices.py maps
  language-prefixed names); plain `narrator` falls back to an English voice.
- **Overlay text is banned; diegetic text is welcome.** The image model sometimes
  renders the prompt as a garbled overlay caption — story-mode visuals append a
  no-OVERLAY instruction automatically (captions/subtitles/floating labels banned;
  text on objects IN the scene — newspaper headlines, signs, chalkboards, book
  spines — is absolutely fine, as is deliberate lettering when the style calls for
  it, e.g. comics). Do NOT proactively scan every frame: the operator points at an
  offending slide. Remake procedure: delete that `02_visuals/scene_NN.png` + its
  `03_clips/scene_NN.mp4`, re-run `studio visuals` + `clips` (both resume-only,
  regenerating just the missing pieces), then stitch/voice/save.
  Tip when a batch DOES need review: a PIL contact sheet (6-col grid of 480px
  thumbs) shows a whole chapter in 2 images.

## Rules

- Never let a scene's `visual_prompt` describe a known character's face/hair/
  clothes — identity comes from the card only. Fix the storyboard, not the image.
- Multi-character scenes: max 3 tagged characters (model reference limit); pick
  the 3 who matter for the action.
- `--no-verify-chars` only for cheap drafts; the gate is the drift insurance.
- Keyless/dev: every step runs with `--provider stub` (placeholder images,
  substring character tagging) — wiring can be tested for $0.
