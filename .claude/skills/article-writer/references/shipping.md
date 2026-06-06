# Shipping: dev.to + LinkedIn mechanics

Detailed reference for the **Ship it** step. dev.to is the canonical home (renders code,
tables, frontmatter); LinkedIn is a native teaser that funnels to it.

## dev.to

dev.to's editor is markdown-native. If you paste a whole file **including the `--- frontmatter ---`**,
it parses these keys:

```yaml
---
title: "Zero to Autopilot, Part N: …"
published: false        # false = draft; flip to true to go live
description: "one-line SEO/teaser sentence"
tags: ai, python, …     # MAX 4 tags, lowercase, no '#'
cover_image: <URL>      # MUST be an absolute URL
series: "Zero to Autopilot"   # auto-groups all parts on dev.to
canonical_url:          # set to the dev.to URL itself if cross-posting elsewhere
---
```

**The one gotcha: images.** Article markdown uses relative paths (`./images/x.png`). dev.to
can't see local files, so those break on paste. Fix it with the bundled tooling — don't upload
images by hand:

```bash
make devto      # → scripts/build_devto.sh
```

This (a) publishes every `articles/<slug>/images/` to the `gh-pages` site (additively — it
won't clobber the effects gallery) and (b) writes `articles/<slug>/devto.md`, a copy of
`article.md` with every `./images/` path (cover + inline) rewritten to its absolute
`https://dasein108.github.io/slope-studio/articles/<slug>/images/…` URL.

**Publish flow:** `make devto` → open `articles/<slug>/devto.md` → select-all → paste into
dev.to's markdown editor → set `published: true` → post. Frontmatter, cover, and images all
render in one paste.

After Part 1 went live at its real URL, wire that URL into later parts' `[Part 1](#)`
placeholders (sed with a non-`#` delimiter, e.g. `s@\[Part 1\](#)@[Part 1](<url>)@g`).

## LinkedIn

LinkedIn surfaces and their limits:
- **Feed post** — ~3,000 chars. ← the target. Renders no markdown.
- **Comment** — ~1,250 chars (this is where the links go).
- **Article** (long-form) — huge, but breaks code highlighting + tables and duplicates the
  dev.to canonical. **Don't re-paste the article here** — it makes the best material look worse.

### The play: a native humanized mini-story

Write a self-contained ~1,500–2,000 char **feed post** that delivers real value on its own
(2–3 concrete specifics) so nobody has to click to "get it" — LinkedIn rewards native value and
demotes posts whose body contains outbound links. Then put all links in the **first comment**.
Then the user pins the post to their profile's **Featured** section for permanence.

Rules:
- **Hook in the first ~210 chars** (everything before "…see more"). Lead with the most concrete
  shock (e.g. "$10.50 → 6¢, same pipeline").
- **Plain text.** No markdown — `**bold**`, `##`, `[text](url)` all show literally. Use line
  breaks and the occasional CAPS or emoji, sparingly.
- **Run the humanizing checklist** from SKILL.md hard — LinkedIn is where AI-slop tells are most
  obvious. Include one true, specific, slightly imperfect human beat.
- **4 hashtags max** at the end.
- **Links in the first comment, not the body.**

Save as `articles/<slug>/linkedin-post.md` with three blocks: RECOMMENDED body (the humanized
mini-story), a ≤352-char SHORT fallback (some surfaces/comment boxes cap at 352), and the
FIRST-COMMENT link block. Plus posting notes (attach one image — the strongest scroll-stopper
frame; best time = when the dev.to post is live so the comment link works; reuse the template
per part by swapping the hook + Part-N line + dev.to URL).

### First-comment link block (template)

```
📖 Part N: <dev.to URL>
🎬 The $10 video: https://www.youtube.com/shorts/gaR76MiAK0U
🐱 The 6¢ video: https://www.youtube.com/shorts/FWtEJjeK_vI
⭐ Code: https://github.com/dasein108/slope-studio
🎨 Effects gallery: https://dasein108.github.io/slope-studio/
```

### Example humanized opener (Part 1, for tone calibration)

> My first AI YouTube Short cost me $10.50. I didn't even notice until the fal.ai bill showed
> up and I went "oh no."
>
> My latest one cost 6 cents. Same pipeline.

Note the concrete moment, the flat short sentences, no em-dash pileup, no rhetorical setup.
