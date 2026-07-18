# Changelog

All notable changes to Slope Studio are recorded here. Versions follow
[semantic versioning](https://semver.org/).

## [0.2.0] — 2026-07-18

### Added

- **Story-illustrator mode.** Turn existing prose — a story, an audiobook
  chapter, a whole book — into video, with recurring characters that keep one
  constant look across every scene and every video.
  - `studio characters-build <name>` learns a character from a folder of
    reference images and writes `characters/<name>/card.json`: a locked identity
    descriptor plus 1–2 canonical anchor images. The *same* anchor goes to the
    image model for every scene, which is the main anti-drift mechanism.
    `--portrait` renders a neutral master portrait and makes it the sole anchor.
  - `studio characters-extract <name> <story>` builds a card for a character
    with no pictures at all, from a whole-story text analysis.
  - `studio storyboard <story>` segments finished prose into timed illustratable
    beats, tagging each with the characters that appear in it. Unknown recurring
    characters get a text-derived card automatically (`--discover`, on by
    default).
  - `studio book-split <book.txt>` chunks a book into per-chapter files,
    stripping PDF page furniture first so narration never reads a page number
    aloud.
  - `studio visuals --characters-root characters/` injects each scene's card
    anchors and descriptor, forces character scenes onto the quality model, and
    runs a vision drift check with at most one corrected regeneration
    (`--no-verify-chars` to skip).
- **`studio narrate --continuous`** — one fluent TTS pass over the whole
  narration, with scene timings derived from the resulting speech instead of
  imposed on it. Removes the per-scene micro-pauses that make long-form
  narration sound torn.
- Russian edge voices, so non-English books narrate in their source language.
- Per-stage cost breakdown (image / video / audio) in run telemetry.
- Age-bucketed metric snapshots (1d/3d/7d/14d/30d) on `marketing measure`, so
  video metrics form a time series rather than one overwritten number.
- Operator scripts: `prune_low_views.py` and `prune_channel.py` (unlist stale
  low-view uploads, the latter against channel truth rather than the journal),
  and `paperclip_lock_janitor.py` (recover Paperclip tasks stranded by a run
  that died holding a lock).

### Fixed

- **Stage re-runs no longer erase money already spent.** `Manifest.record()`
  replaced the whole record, so a resumed stage that skipped its existing
  artifacts wrote `cost_usd=0` over real spend — under-reporting the run total
  and letting the budget guard re-allow budget that was already gone. Costs now
  accumulate across invocations.
- **Telemetry no longer reports AI video on zero-spend runs.** `video_model` was
  taken from the clips provider string even when that model generated nothing,
  and `ai_scene_count` was re-derived from the script in a way that counted every
  free animator (drift, parallax, slice, …) as an AI generation. Both now come
  only from the clips stage's record of real generations.
- **Art-direction rails are enforced at the render boundary.** Agent- and
  hand-authored scripts are written straight to `01_script.json` and never pass
  through the script stage, so they bypassed the zoom ban, the
  parallax-on-subject guard, atmosphere justification, and the taste caps.
- edge TTS now retries with backoff. It throttles bursts and intermittently
  returns `NoAudioReceived` when a long run synthesizes dozens of scenes back to
  back, which used to fail the whole narrate stage.
- Scene fields accept a single object where a one-item list is expected — some
  LLMs emit that shape.

### Changed

- Org agent playbooks: a hard three-video daily target (2 exploit + 1 explore)
  topped up within a single heartbeat; a mandatory full-journal duplicate check
  by subject across all statuses; check the channel before retrying a failed
  upload (an SSL error on the final chunk usually means it landed); and never
  cancel a ticket being handed back, which would wake its assignee to nothing.
- The Hermes + ACP orchestrator plan is marked superseded — it was a proposal,
  was never implemented, and Paperclip filled the role. Kept for its design
  rationale.
- `stories/` and `characters/` are gitignored. Source prose and reference photos
  are raw material, not code; the READMEs document the expected layout.

## [0.1.0]

Initial release: idea → published Short.
