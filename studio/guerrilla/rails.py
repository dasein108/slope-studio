"""Rate discipline and content rails — the ban defense.

Pure predicates, so every rule is exhaustively testable without a network client.
`post.py` is the only caller; nothing reaches YouTube without passing through here.

The deny-list exists because prompts are advisory and code is not. An LLM that
ignores "never self-promote" once per thousand comments still eventually posts
the comment that gets the channel flagged.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone

from studio.guerrilla import transcript

# TLDs the link rule watches for, both as literal dots ("bit.ly") and spelled
# out ("example dot com") — kept as one group so both alternatives stay in sync.
_LINK_TLDS = r"com|net|org|io|be|tv|me|ly|gg|co|link|app"

# One emoji character, in whatever form it takes.
_EMOJI_CHAR = r"[\U0001F300-\U0001FAFF☀-➿]"

# Rules are ordered: the first match names the violation.
DENY_RULES: list[tuple[str, re.Pattern]] = [
    ("link", re.compile(
        rf"https?://|www\.|\b[\w-]+\.(?:{_LINK_TLDS})\b|"
        rf"\b[\w-]+\s+dot\s+(?:{_LINK_TLDS})\b", re.I)),
    ("channel_name", re.compile(
        # Tolerant of leetspeak/spacing: "p4rad0x n01r", "parad0x  noir".
        # Word-boundary anchored so the short aliases ("P.O.L.S.") only match
        # as a standalone token — otherwise "p.o.l.s." matches inside
        # ordinary words like "Polska" or "polls".
        r"\bp[a4]r[a4]d[o0]x\s*n[o0][i1]r\b|\bslope\s*studio\b|"
        r"\bstarship\s*pilot\b|\bp\.?o\.?l\.?s\.?\b", re.I)),
    ("self_promo", re.compile(
        r"\b(check\s+(?:it\s+)?out|subscribe|my\s+channel|my\s+video|watch\s+my|"
        r"link\s+in\s+bio|i\s+made\s+a\s+video|on\s+my\s+page|follow\s+for\s+more|"
        r"smash\s+(?:that\s+)?like(?:\s+button)?|drop\s+a\s+like|"
        r"new\s+video\s+every\s+week|dm\s+me|comment\s+below)\b", re.I)),
    ("hashtag", re.compile(r"#\w+")),
    ("emoji_spam", re.compile(
        # 3+ consecutive, or 4+ anywhere in the text.
        rf"{_EMOJI_CHAR}{{3,}}|(?:.*?{_EMOJI_CHAR}){{4}}")),
]

# Standalone tokens and prefixes that flip a phrase's meaning without
# changing its character-gram footprint much: "makes sense" / "makes no
# sense" and "agree" / "disagree" only differ by one of these, but they are
# not near-duplicates — they're opposites. See `_negates`.
_NEGATION_WORDS = {"no", "not", "never", "non", "without"}
_NEGATION_PREFIXES = ("dis", "un", "non")

# Two separate thresholds because the two `shingles()` paths behave
# differently at the same cutoff. Measured against real comment pairs, the
# word-shingle path (comments with more than `k` words) sits at 0.429-0.636
# jaccard for one-word edits of the same comment — the exact near-duplicate
# pattern this rail exists to catch — while genuinely unrelated long
# comments sit at 0.0. A single 0.5 threshold let those one-word edits
# through; 0.3 catches them with a wide safety margin above the unrelated
# baseline. The character-gram fallback (comments with at most `k` words)
# can't drop to 0.3 too: it already over-blocks at 0.5 on short antonym
# pairs ("this aged well" / "this aged badly"), so it keeps the higher bar.
SIMILARITY_THRESHOLD = 0.3
SHORT_TEXT_THRESHOLD = 0.5
ACTIVE_START_HOUR = 9
ACTIVE_END_HOUR = 23
BLACKOUT_HOURS = 6
BASE_INTERVAL_MIN = 12
JITTER = 0.4


def violates_denylist(text: str) -> str:
    """Name of the first rule the text breaks, or '' if clean."""
    for name, pattern in DENY_RULES:
        if pattern.search(text):
            return name
    return ""


# `M:SS` or `H:MM:SS`. The optional third group distinguishes the two shapes:
# present, group 1 is hours; absent, group 1 is minutes. Both the minute/second
# and second/second groups require exactly two digits with a `0-5` leading
# digit, which is what keeps this from firing on unrelated `N:N` text like a
# `16:9` aspect ratio or a `2:1` ratio — those never have a valid MM/SS shape.
# The trailing negative lookahead excludes time-of-day: "12:30 pm" (or
# "12:30pm", "12:30 p.m.") has the same M:SS shape as a video timestamp but
# means something else entirely, and without this a comment that mentions a
# clock time would be checked against the transcript and rejected as an
# unverifiable citation. The optional third (seconds) group is POSSESSIVE
# (`?+`, not `?`) rather than the usual greedy-with-backtracking `?`: without
# that, "1:02:03 a.m." would fail the lookahead with all three groups taken,
# backtrack to dropping the seconds group, and then match "1:02" instead —
# what comes after "1:02" is ":03 a.m.", which does NOT start with am/pm, so
# the lookahead would wrongly pass and "1:02" would slip through as a bogus
# video-timestamp citation. Possessive means once the optional group matches,
# it is never given back to satisfy the rest of the pattern.
_TIMESTAMP_RE = re.compile(r"\b(\d{1,2}):([0-5]\d)(?::([0-5]\d))?+\b(?!\s*[ap]\.?m\.?\b)", re.I)


def _extract_timestamps(text: str) -> list[float]:
    """Every cited `M:SS`/`H:MM:SS` in `text`, converted to seconds."""
    times = []
    for m in _TIMESTAMP_RE.finditer(text):
        first, second, third = m.group(1), m.group(2), m.group(3)
        if third is not None:
            times.append(int(first) * 3600 + int(second) * 60 + int(third))
        else:
            times.append(int(first) * 60 + int(second))
    return times


def bad_timestamp(text: str, segments, tolerance: float = 30.0) -> str:
    """Reason string if any timestamp `text` cites doesn't check out against the
    video's actual transcript, else "".

    A cited time is rejected if it falls beyond the video's own duration, or if
    no transcript segment within `tolerance` seconds plausibly matches it —
    `transcript.at` returning nothing near a claimed moment means there is
    nothing there for the comment to be referencing. A comment that cites no
    timestamp at all is always clean; this rail only ever engages once a
    comment stakes a specific, checkable claim.

    Fails closed by construction: a video with no cached transcript has
    `segments == []`, so `transcript.duration` is `0.0` and any cited time
    beyond it is rejected the same way a genuinely out-of-range one would be —
    an unverifiable citation is treated as an unsafe one, never a free pass.
    """
    times = _extract_timestamps(text)
    if not times:
        return ""
    video_duration = transcript.duration(segments)
    for seconds in times:
        if seconds > video_duration:
            return f"timestamp {transcript.stamp(seconds)} exceeds video duration"
        if not transcript.at(segments, seconds, window=tolerance):
            return f"timestamp {transcript.stamp(seconds)} has no matching transcript segment"
    return ""


def shingles(text: str, k: int = 4) -> set[str]:
    """Word k-grams — what near-duplicate detection compares.

    Text with at most k words can only ever produce a single word shingle,
    which collapses similarity to exact string match — a one-word edit
    ("mind blown genuinely" -> "mind blown honestly") would then defeat
    duplicate detection outright. Below that length, fall back to character
    2-grams over the normalized text so similarity degrades smoothly instead
    of cliffing to zero. Longer text keeps the word-shingle behavior as-is.
    """
    words = re.findall(r"\w+", text.lower())
    if not words:
        return set()
    if len(words) <= k:
        normalized = " ".join(words)
        char_n = 2
        if len(normalized) < char_n:
            return {normalized}
        return {normalized[i:i + char_n] for i in range(len(normalized) - char_n + 1)}
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _negates(text_a: str, text_b: str) -> bool:
    """True if the two texts differ by a negation marker.

    Character-gram similarity can't tell "makes sense" from "makes no
    sense" apart — one word added, footprint barely moves — but they mean
    the opposite thing. Whenever the only words that differ between two
    texts are a bare negator ("no", "not", "never"...) or a negated/base
    pair ("disagree"/"agree", "unhelpful"/"helpful"), treat that as a
    deliberate meaning flip rather than a near-duplicate, regardless of how
    high the shingle jaccard reads.
    """
    words_a = set(re.findall(r"\w+", text_a.lower()))
    words_b = set(re.findall(r"\w+", text_b.lower()))
    for word in words_a ^ words_b:
        if word in _NEGATION_WORDS:
            return True
        for prefix in _NEGATION_PREFIXES:
            stem = word.removeprefix(prefix)
            if stem != word and (stem in words_a or stem in words_b):
                return True
    return False


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text.lower()))


def too_similar(text: str, recent: list[str], k: int = 4,
                 threshold: float = SIMILARITY_THRESHOLD,
                 short_threshold: float = SHORT_TEXT_THRESHOLD) -> bool:
    """True if the text closely repeats something recently posted.

    Near-duplicate text across many videos is what YouTube's spam filter
    actually matches on — more so than volume.

    `shingles()` silently switches representation at `k` words: word-grams
    above it, character-grams at or below it. A jaccard score only means
    the same thing as another score if both were computed on the same
    representation, so the threshold has to follow the path each
    comparison actually took, not a global cutoff. If either side of a
    given pair drops to the character-gram fallback, that comparison uses
    `short_threshold` — never `threshold`, which is calibrated for
    word-shingle scores and would over-trigger on character-gram ones.
    """
    s = shingles(text, k)
    text_is_short = _word_count(text) <= k
    for prev in recent:
        prev_is_short = _word_count(prev) <= k
        active_threshold = short_threshold if (text_is_short or prev_is_short) else threshold
        if jaccard(s, shingles(prev, k)) >= active_threshold and not _negates(text, prev):
            return True
    return False


def _to_utc(dt: datetime) -> datetime:
    """Normalize to UTC: naive is treated as already UTC, aware is converted.

    Matches how `watchlist.on_cooldown` and `discover.age_minutes` handle
    parsed timestamps. Without this, the same real instant can evaluate as
    blocked or allowed depending on which tzinfo the caller happened to
    attach to `now` (e.g. `datetime.now().astimezone()` vs UTC).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def in_active_window(now: datetime, start_hour: int = ACTIVE_START_HOUR,
                      end_hour: int = ACTIVE_END_HOUR) -> bool:
    """Comments only during plausible waking hours. 04:00 posting reads as a bot."""
    now = _to_utc(now)
    return start_hour <= now.hour < end_hour


def in_blackout(now: datetime, publish_times: list[str],
                 hours: int = BLACKOUT_HOURS) -> bool:
    """True near one of our own publishes.

    Keeps comment-driven visitors separable from upload-driven ones, which is
    what makes the switchback readout interpretable.
    """
    now = _to_utc(now)
    window = timedelta(hours=hours)
    for ts in publish_times:
        if not ts:
            continue
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if abs(now - dt) <= window:
            return True
    return False


def next_delay_seconds(rng, base_minutes: float = BASE_INTERVAL_MIN,
                        jitter: float = JITTER) -> float:
    """Seconds to wait before the next comment. Never a fixed cadence."""
    factor = 1.0 + rng.uniform(-jitter, jitter)
    return base_minutes * 60.0 * factor


def recent_texts(conn: sqlite3.Connection, limit: int = 200) -> list[str]:
    return [r["text"] for r in conn.execute(
        "SELECT text FROM comments ORDER BY posted_at DESC LIMIT ?", (limit,))]


def recent_styles(conn: sqlite3.Connection, limit: int = 5) -> list[str]:
    """Style tags of our `limit` most recent posts, newest first."""
    return [r["style_tag"] for r in conn.execute(
        "SELECT style_tag FROM comments ORDER BY posted_at DESC LIMIT ?", (limit,))]


def repeats_opening(text: str, recent: list[str], words: int = 4) -> bool:
    """True if `text`'s first `words` words match the opening of any comment
    in `recent`, once both sides are lowercased and stripped of punctuation.

    `too_similar` compares whole-text shingle overlap, so it only fires when
    two comments share substantial CONTENT. A template-driven bot instead
    reuses the same sentence-opening scaffold ("If X, ...") across comments
    that are otherwise about unrelated videos — low content overlap, but the
    exact same first few words every time. That is the actual pattern
    spam filters and human reviewers key on, so it needs its own check.
    """
    text_opening = _normalized_opening(text, words)
    if not text_opening:
        return False
    return any(text_opening == _normalized_opening(prev, words) for prev in recent)


def _normalized_opening(text: str, words: int) -> str:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return " ".join(tokens[:words])


def style_overused(style_tag: str, recent_styles: list[str], limit: int = 2,
                    window: int = 5) -> bool:
    """True if `style_tag` already appears at least `limit` times in the
    last `window` entries of `recent_styles`.

    Forces rotation across the four style tags rather than letting one
    (e.g. `provocative_question`) dominate a batch — the other half of the
    template-monoculture defect that `repeats_opening` alone can't catch:
    a bot can vary its wording enough to dodge that check while still
    leaning on the same rhetorical register every time.
    """
    return recent_styles[:window].count(style_tag) >= limit
