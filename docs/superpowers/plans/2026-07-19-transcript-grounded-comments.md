# Transcript-Grounded Comments — Implementation Plan

Extends the `studio/guerrilla/` subsystem built by
`docs/superpowers/plans/2026-07-18-guerrilla-marketing.md`. Same branch
(`feat/guerrilla-marketing`), same conventions, direct implementation rather than a new
spec cycle.

**Goal:** Ground every generated comment in what the video actually says, so it references a
real moment instead of paraphrasing the title.

## Why

An independent evaluation of a 10-comment batch found 1 of 10 postable. Root cause is
architectural, not prompt-level: `compose` only ever sees the video's title and description. It
has never seen the video. Three consecutive prompt rewrites each traded one verbal tic for
another ("If X, then Y?" → hedged-reviewer → "Why do we…?") because the model has nothing
concrete to react to.

Two concrete failures this causes:

- **Hallucination.** One comment asserted a Kaplan video discussed "Captain Richard de
  Crespigny's handling of Qantas Flight 32." Under a 520k-view video, attached to the
  operator's channel name, a fabricated claim is a permanent public liability.
- **A critic that cannot discriminate.** All 10 comments scored 4.6-4.8 and `rejected` was
  empty. With no ground truth the critic rewards fluency and question-endings — precisely the
  traits that form the bot fingerprint. It is selecting for detectability.

A transcript fixes both: the composer gets something specific to react to, and the critic gets
ground truth to verify against.

## Verified Feasibility

`youtube-transcript-api` fetched all three test videos with timestamps:

| video | segments | duration | words |
|---|---|---|---|
| Kaplan / theory of names | 696 | 24.8 min | 4,792 |
| Art of Thinking / shopping cart | 84 | 8.0 min | 1,413 |
| Eternalised / Steiner | 24 | 0.9 min | 139 |

The YouTube Data API's `captions.download` only works on videos the caller owns, so there is no
official route for third-party videos. The unofficial library is the only option.

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Timestamp citation | **Occasional** — only when the moment scores high on citability | Always-cite would become the fourth template. A weak citation is worse than none. |
| Long videos | **Chunk-and-rank** (~2-3× LLM calls) | Approved. Capping the transcript would miss the best moment, which is the whole point. |
| Delivery | **Direct implementation** on the existing branch | ~4 modules extending a reviewed subsystem, not a new product. |
| No transcript | **Skip the video** | Matches the existing skip-if-unclear rule. Shorts frequently lack transcripts. |

## Pipeline Change

```
discover → rank → transcript → highlight → compose → critic → rails → post
                  ^^^^^^^^^^^^^^^^^^^^^^                new
```

## Cost

A 25-minute video is ~6k tokens. Chunk-and-rank on a long video is ~3-4 LLM calls where there
was 1. At ~12 candidates/day this is still cents per day, but it is 5-10× current spend — so
the pre-LLM gates added in earlier fix waves (active window, daily cap, spacing short-circuit)
carry more weight now. Transcripts are cached in the database so a re-tick never refetches.

## Global Constraints

- Python >= 3.11. Ruff line-length 120. Lint via `uv run --with ruff ruff check <paths>`.
- `youtube-transcript-api` is a NEW dependency — add to a `guerrilla` optional extra in
  `pyproject.toml`, and import it lazily inside functions like every other optional dep in this
  codebase.
- Tests live in `tests/` as flat `test_guerrilla_<area>.py`. No test may hit the network, need
  an API key, or send Telegram.
- Every LLM-calling function keeps the established contract: injectable `complete` seam, entire
  body inside the `try`, failure returns an empty result rather than raising.
- Do not stage: `scripts/prune_channel.py`, `studio/marketing/ideate.py`,
  `studio/marketing/journal.py`, `uv.lock`, `scripts/shrink_final.sh`, `scripts/retitle_live.py`.

---

## Task 1 — `transcript.py`: fetch, normalize, cache

**Files:** create `studio/guerrilla/transcript.py`; modify `studio/guerrilla/db.py`
(add a `transcripts` table); modify `pyproject.toml`; test `tests/test_guerrilla_transcript.py`.

**Produces:**
- `Segment` (pydantic: `start: float`, `text: str`)
- `fetch(video_id, fetcher=None) -> list[Segment]` — `[]` on any failure, never raises
- `cached(conn, video_id, fetcher=None) -> list[Segment]` — DB-backed, fetches once
- `duration(segments) -> float`
- `stamp(seconds) -> str` — `M:SS`, or `H:MM:SS` past an hour
- `at(segments, seconds, window=15.0) -> str` — text near a timestamp, for verification
- `as_prompt(segments, start=0.0, end=None) -> str` — `[M:SS] text` lines for an LLM

Schema addition:
```sql
CREATE TABLE IF NOT EXISTS transcripts (
    video_id   TEXT PRIMARY KEY REFERENCES videos(video_id),
    fetched_at TEXT NOT NULL DEFAULT '',
    duration   REAL NOT NULL DEFAULT 0.0,
    segments   TEXT NOT NULL DEFAULT '[]'   -- JSON [[start, text], ...]
);
```

`fetcher` is the injection seam: production passes `None` and resolves the library lazily;
tests pass a stub returning canned segments. The library is an unofficial scraper — wrap it so
it is swappable, and treat every exception as "no transcript".

**Tests:** normalization from the library's shape; `[]` on fetcher exception; `cached` fetches
once then reads from the DB; `stamp` at 0s/63s/3723s; `at` returns nearby text; `as_prompt`
formats `[M:SS] text`.

## Task 2 — `highlight.py`: find the most comment-worthy moment

**Files:** create `studio/guerrilla/highlight.py`; test `tests/test_guerrilla_highlight.py`.

**Produces:**
- `Moment` (pydantic: `timestamp: float`, `quote: str`, `why: str`, `citability: float`)
- `CITE_THRESHOLD = 4.0`
- `best_moment(segments, title, provider="", complete=None) -> Moment | None`
- `should_cite(moment) -> bool` — `citability >= CITE_THRESHOLD`

Chunk-and-rank: split the transcript into ~4-minute chunks, ask the LLM for the single most
comment-worthy moment in each (returning timestamp, a short verbatim quote, why it is
interesting, and a `citability` score 0-5), then pick the highest-scoring across chunks. A
video under one chunk costs one call; a 25-minute video costs ~6.

`citability` is what makes timestamp citation occasional. Score it on whether the moment is
self-contained enough that a stranger scrolling comments would understand the reference without
watching — a surprising claim, a specific number, a name, a turn in the argument. Ambient
narration scores low. Only moments at or above the threshold get cited.

The returned `quote` must be verbatim from the transcript; the prompt must say so, and Task 4's
rail verifies it.

**Tests:** single-chunk video returns the stub's moment; multi-chunk picks the highest
citability; unparseable output and LLM exception both yield `None`; `should_cite` boundary at
exactly 4.0; empty transcript yields `None`.

## Task 3 — `compose` reacts to the moment

**Files:** modify `studio/guerrilla/compose.py`; test `tests/test_guerrilla_compose.py`.

`variants()` gains an optional `moment: Moment | None` and an optional `cite: bool`. When a
moment is present the prompt shows the quote, its timestamp and why it matters, and instructs
the model to react to THAT — disagree with it, extend it, or joke about it — not to summarize
the video. When `cite` is true the comment should reference the timestamp naturally (`"at
12:33"`); when false it must react to the moment's substance without citing a time.

Keep every existing hard rule, `STYLE_TAGS`, `MAX_LEN`, the `Variant` model, the JSON output
shape, and the anti-template instructions added in earlier commits. Backward compatible: with
`moment=None` the current title-and-summary behavior is unchanged, so existing tests pass.

**Tests:** moment text appears in the prompt; `cite=True` instructs citation and `cite=False`
forbids it; `moment=None` preserves current behavior; existing prompt-rule assertions still pass.

## Task 4 — `grounded` critic criterion + timestamp verification rail

**Files:** modify `studio/guerrilla/critic.py`, `studio/guerrilla/rails.py`;
tests `tests/test_guerrilla_critic.py`, `tests/test_guerrilla_rails.py`.

**Critic.** Add `grounded` to `CRITERIA` and to `DISQUALIFYING`. It scores whether every factual
claim the comment makes about the video is supported by the transcript excerpt supplied to the
judge. Fabricated specifics score 0 and the comment is skipped regardless of its mean — the same
treatment `no_self_promo` gets, for the same reason: it is not "below average", it is unpostable.

`judge()` and `ranked()`/`best()` gain an optional `transcript_excerpt: str = ""`. When empty,
`grounded` is scored neutrally so behavior is unchanged for callers that have no transcript, and
existing tests keep passing.

**Rail.** Add to `rails.py`, pure:
```python
def bad_timestamp(text: str, segments, tolerance: float = 30.0) -> str
```
Extract every `M:SS` / `H:MM:SS` from the comment. Return a reason string if any cited time
exceeds the video duration, or if no transcript segment within `tolerance` seconds plausibly
matches the comment's claim; `""` when clean. Wire into `post.post_comment` raising
`PostBlocked("bad_timestamp")`, and into `loop.tick`'s dry-run branch beside the existing
deny-list check. Fails closed: an unverifiable citation is rejected.

**Tests:** fabricated claim scores `grounded` 0 → skip despite a high mean; empty excerpt leaves
behavior unchanged; timestamp past duration rejected; timestamp matching a real segment accepted;
comment with no timestamp always clean.

## Task 5 — wire into the tick, then regenerate a batch

**Files:** modify `studio/guerrilla/loop.py`, `studio/guerrilla/topic.py`,
`studio/cli.py`; test `tests/test_guerrilla_loop.py`.

In `tick`, after the topic gate and before composing: fetch the cached transcript; if empty,
mark the video `skipped_transcript` and continue. Otherwise find the best moment, decide
`cite` from `should_cite`, and pass both the moment and a transcript excerpt through to
`compose` and `critic`.

`topic.classify` gains an optional transcript excerpt so subject classification uses real
content, which should reduce `skipped_topic` rejections.

Order matters for cost: the transcript fetch is free (network, cached), but `highlight` costs
LLM calls — so it must run AFTER every cheap gate has passed, never before.

Add `skipped_transcript` to the report's skip breakdown so the operator can see how many
candidates are lost to missing captions.

**Tests:** a candidate with no transcript is marked `skipped_transcript` and costs zero compose
calls; a candidate with one reaches `compose` carrying the moment; a low-citability moment
produces `cite=False`.

## Task 6 — regenerate and re-evaluate

Update the preview script to the new pipeline, generate a fresh batch of 10, and hand it to an
independent evaluator with no knowledge of this work — the same rubric used on the previous
batch (relevance, voice, provocation, click-motivation, bot-risk, batch-level tells, tag
honesty, critic correlation).

The bar: materially more than 1 of 10 postable, no fabricated claims, and no single shared
template across the batch. If the fingerprint problem survives transcript grounding, the
conclusion is that the approach is exhausted and the honest recommendation is manual curation.

## Out of Scope

- Translating non-English transcripts.
- Fetching transcripts for videos where captions are disabled — those are skipped.
- Replacing the unofficial library with an official route; none exists for third-party videos.
