---
name: article-writer
description: >
  Plan, write, critically review, and ship a technical build-log article series
  (the "Zero to Autopilot" series about this repo) to dev.to and LinkedIn. Use
  whenever the user wants to plan an article series, draft or write an article or
  "Part N", review/revise drafts for quality and de-duplication, pick/prepare
  images, generate dev.to-ready copy-paste markdown, or craft a LinkedIn feed
  post + follow-up comment. Trigger on phrases like "write part N", "draft the
  article", "plan the series", "review the articles", "prepare for dev.to",
  "make the linkedin post" — even if they don't say the word "skill" or "article".
---

# Article Writer — engineering build-log series for dev.to + LinkedIn

This skill captures the proven workflow for the **Zero to Autopilot** series:
a developer-audience build log of the Slope Studio repo, published on dev.to (canonical)
and teased on LinkedIn. The goal is **professional-grade, genuinely human** writing that
shows real engineering skill — grounded in this repo's actual code and measured numbers,
never invented.

Work lives in `articles/` (gitignored). The series plan is `articles/PLAN.md`. Each part
is `articles/<NN-slug>/article.md` with images in `articles/<NN-slug>/images/`.

## When to do what

| User says… | Do this section |
|---|---|
| "plan the series" / "offer names" | **Plan the series** |
| "write Part N" / "draft the article" | **Write an article** |
| "review / revise / critic the articles" | **Review & revise** |
| "ship Part N" / "prepare for dev.to" / "linkedin post" | **Ship it** (+ `references/shipping.md`) |

Always read `articles/PLAN.md` first — it holds the agreed audience, voice, data policy,
per-article outline, and conventions. Keep it in sync when scope changes.

## Core principles (these are the whole point)

1. **Ground every claim in the repo.** Numbers come from real manifests (`runs/<id>/project.json`),
   real code (`studio/…`), and real prices (`studio/providers/video.py` `FAL_MODELS`,
   `image.py`). Read the file before quoting a number. Never invent a cost, a metric, or an
   API detail — fabricated specifics are the fastest way to lose an engineer's trust.
2. **Show real code, lightly trimmed.** Paste actual functions/snippets (elided with `# ...`),
   not pseudocode. The credibility is in "this is the real thing."
3. **Be honest, including failures.** The flops (the cat-series cannibalization, fal moderation
   blocks, the unsolved LLM→manim problem) are *content*, not embarrassments. Candor reads as
   competence.
4. **Human voice, not LinkedIn-AI-slop.** See the anti-tell checklist below. This is non-negotiable —
   the whole series argues against slop, so the writing can't read like it.
5. **Respect the data policy.** Quantitative audience metrics (views/retention/CTR) are held
   until they've matured (≥1 week) and live in the final part. Earlier parts use code, cost,
   and *qualitative* outcomes only. Mark each article's header with **Data status: real-now**
   or **await-Nwk**.

## Plan the series

Produce/maintain `articles/PLAN.md` with: audience + publish target; series name; the
narrative spine; the per-article skeleton; a **data policy** (what's real-now vs awaited);
cross-cutting conventions; and a numbered per-article outline (thesis · content · skill shown ·
ends-on hook). When offering series names, give 2–3 distinct angles with a recommendation and
reasoning. Decompose if it's really several series.

## Write an article

Each `article.md` follows this skeleton (scale sections to their weight):

```
frontmatter (see references/shipping.md for the exact dev.to keys)
> Series banner: which part, one-line recap of prior parts (link Part 1's real URL), the
>   Data status line, and the gallery/repo links.
![cover](./images/cover.png)
## Hook section — a concrete, surprising opener (a number, a failure, a claim)
## The problem — what hurt, made real
## What I built — the design, with REAL code snippets
## Receipts — real numbers / a manifest log / a results table
## What I'd tell another AI engineer  (a > blockquote "Takeaway")
---
**Next — Part N+1: …** one-paragraph tease
▶ gallery · ⭐ repo · 🔔 subscribe   (the standard footer)
```

Conventions, every article:
- **One idea per article.** It owns its subsystem; it *references* (links) prior parts rather
  than re-explaining them. Re-teaching content already covered is the #1 redundancy smell.
- **Recaps are one sentence + a link**, never a re-derivation.
- **Standard footer**: `▶ Live effects gallery` · `⭐ Star the repo` · `🔔 Subscribe`.
- **Images**: pull from real `runs/<id>/02_visuals/*.png` (skip ~10 KB stubs). **View each
  candidate with Read before choosing** — caption it for what it actually shows. Don't reuse
  the same source frame across two articles. Static frames can't show motion/atmosphere — for
  those, link the live gallery instead of a dead still.
- **Repo/links**: repo `github.com/dasein108/slope-studio`, gallery
  `dasein108.github.io/slope-studio`, channel + the two reference Shorts (the $10 one
  `gaR76MiAK0U`, the 6¢ one `FWtEJjeK_vI`).

### The humanizing checklist (read drafts against this)

LinkedIn/AI-tell smells to hunt down and cut:
- Rhetorical scaffolding: "Here's the thing—", "Why does that matter? Because…", "The first
  lesson was brutal." → just say the thing.
- Em-dash overload (—). Vary punctuation; some sentences should be short and flat.
- Too-perfect parallelism / slogan lines ("cheap enough to X, smart enough to Y"). One is fine;
  three is a tell.
- Hashtag/emoji stuffing.
- No texture. Real writing has a concrete moment, mild self-deprecation, an aside ("I checked
  the bill and went 'oh no'"). Add one true, specific human beat per piece.
Aim for: a competent engineer telling a sharp story to a peer — not a thought-leader performing.

## Review & revise (critic pass)

When asked to review, act as a critic and **make the edits**, don't just list them. Check:
1. **Cross-article redundancy** — the same story/section told in full twice (e.g. the audio
   layer, the indie-dev origin, the per-second cost story). Pick ONE home; everywhere else
   references it. This is the dominant defect in a series binge-read.
2. **Structure** — consistent skeleton, logical section separation, no sprawl, no stacked
   duplicate CTA blocks. Each article standalone yet not repetitive for series readers.
3. **Unfulfilled promises** — "gets its own treatment later" with no such part. Remove or fulfill.
4. **Image dup** — same source frame in two parts; swap one.
5. **Voice** — run the humanizing checklist.
6. **Accuracy** — spot-check that quoted numbers/code still match the repo.
Lead the user with a short critic verdict (what's strong, what's the main flaw), then apply fixes.

## Ship it

Shipping has two surfaces — see **`references/shipping.md`** for the exact mechanics
(dev.to frontmatter rules, `make devto` image hosting, the LinkedIn humanized mini-story +
first-comment template + the ≤352 fallback + Featured pin). The short version:

- **dev.to** = canonical. Run `make devto`, then paste `articles/<slug>/devto.md` (it has
  absolute image URLs so it's a single copy-paste). Flip `published: true`.
- **LinkedIn** = a native humanized **feed post** (not a re-paste of the article — that renders
  badly and duplicates the canonical), with the links in the **first comment**, pinned to
  Featured. Save it as `articles/<slug>/linkedin-post.md`.
- After Part 1 is live, wire its real dev.to URL into later parts' `[Part 1](#)` placeholders.
