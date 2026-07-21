"""Score candidate comments before anything reaches YouTube.

Deliberately NOT the `studio/stages/critic.py` content critic — that one is
calibrated to decline nearly everything, which is fine for a $2 video render and
fatal for a gate that must pass ~12 comments a day.

Three criteria are disqualifying rather than averageable: a comment that promotes
us, insults someone, or fabricates a specific about the video is not "below
average", it is unpostable. `grounded` — whether every factual claim the comment
makes about the video is supported by a transcript excerpt — only has ground
truth to check against when a caller supplies one; see `judge()` for how an
absent excerpt keeps `grounded` from ever disqualifying.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from studio.config import default_provider
from studio.guerrilla.compose import Variant

CRITERIA = ("on_topic", "provocative_or_funny", "not_generic", "no_self_promo", "not_offensive",
            "grounded")
# Criteria not requested from the model when there is no transcript excerpt to judge them
# against — see `judge()`. Kept in sync with CRITERIA minus "grounded" by construction rather
# than hand-maintained, so a future criterion added to CRITERIA doesn't silently need this too.
UNGROUNDED_CRITERIA = tuple(c for c in CRITERIA if c != "grounded")
DISQUALIFYING = ("no_self_promo", "not_offensive", "grounded")
DISQUALIFY_BELOW = 3.0
AUTO_POST = 4.0
QUEUE = 3.0

SYSTEM = """You judge whether a YouTube comment is worth posting under a specific video, from
an account whose only goal is that readers find the comment interesting enough to click the
commenter's name.

Score each criterion 0-5:
- on_topic: does it engage THIS video's actual subject? A comment that would fit under any
  video scores 0-1.
- provocative_or_funny: would a reader want to reply, argue, or laugh? Bland scores low.
- not_generic: is it specific and particular? "Great video", "so underrated", "first" score 0.
- no_self_promo: 5 if it never references the commenter's own channel/videos and contains no
  link or handle. 0 if it does ANY of that.
- not_offensive: 5 if nobody could reasonably take offense. 0 for insults, slurs, or attacks on
  the creator, the audience, or any group.

Output ONLY valid JSON:
{"scores": {"on_topic": 0.0, "provocative_or_funny": 0.0, "not_generic": 0.0,
            "no_self_promo": 0.0, "not_offensive": 0.0}}"""

# Used only when a transcript excerpt is available (see `judge()`). Asks for one additional
# criterion, "grounded", scored against real ground truth instead of the model's own guess about
# what the video probably says.
SYSTEM_GROUNDED = """You judge whether a YouTube comment is worth posting under a specific video, from
an account whose only goal is that readers find the comment interesting enough to click the
commenter's name. You are given an excerpt of the video's actual transcript as ground truth.

Score each criterion 0-5:
- on_topic: does it engage THIS video's actual subject? A comment that would fit under any
  video scores 0-1.
- provocative_or_funny: would a reader want to reply, argue, or laugh? Bland scores low.
- not_generic: is it specific and particular? "Great video", "so underrated", "first" score 0.
- no_self_promo: 5 if it never references the commenter's own channel/videos and contains no
  link or handle. 0 if it does ANY of that.
- not_offensive: 5 if nobody could reasonably take offense. 0 for insults, slurs, or attacks on
  the creator, the audience, or any group.
- grounded: does EVERY factual claim the comment makes about the video hold up against the
  transcript excerpt below? A comment that asserts a specific claim, number, name, quote, or
  moment the excerpt does not support is fabricating — score it 0, no partial credit for the
  rest reading well. A comment that reacts to the video in general terms without asserting
  anything the excerpt would need to back up scores 5.

Output ONLY valid JSON:
{"scores": {"on_topic": 0.0, "provocative_or_funny": 0.0, "not_generic": 0.0,
            "no_self_promo": 0.0, "not_offensive": 0.0, "grounded": 0.0}}"""

USER_TMPL = """Video title: {title}
What the video is about: {summary}

The proposed comment:
{text}"""

USER_TMPL_GROUNDED = """Video title: {title}
What the video is about: {summary}

Transcript excerpt (ground truth for the "grounded" criterion):
{transcript_excerpt}

The proposed comment:
{text}"""


class Verdict(BaseModel):
    score: float = 0.0
    breakdown: dict[str, float] = {}
    decision: str = "skip"   # auto | queue | skip


def _strip_fence(raw: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return m.group(1).strip() if m else raw.strip()


def _decide(breakdown: dict[str, float]) -> tuple[float, str]:
    # `.get(k, DISQUALIFY_BELOW)` rather than `.get(k, 0.0)`: a key genuinely
    # absent from `breakdown` (only ever "grounded", when `judge()` had no
    # transcript excerpt to score it against) must never disqualify — the
    # default has to sit AT the threshold, not below it, so the "not < below"
    # comparison reads as "no evidence of a problem" rather than "worst
    # possible score". Keys that ARE present keep disqualifying exactly as
    # before; this only changes what happens when a criterion never ran.
    mean = sum(breakdown.values()) / len(breakdown)
    if any(breakdown.get(k, DISQUALIFY_BELOW) < DISQUALIFY_BELOW for k in DISQUALIFYING):
        return mean, "skip"
    if mean >= AUTO_POST:
        return mean, "auto"
    if mean >= QUEUE:
        return mean, "queue"
    return mean, "skip"


def judge(variant: Variant, title: str, summary: str, provider: str = "",
          complete=None, transcript_excerpt: str = "") -> Verdict:
    """Score one variant. Any failure yields a skip verdict — never raises.

    `transcript_excerpt` is the ground truth for the `grounded` criterion. When
    it's empty — every caller before this one, and any caller today that has no
    transcript for the video — `grounded` is not asked about at all: the model
    only sees the original 5-criterion prompt, and `breakdown` never gets a
    `grounded` key. `_decide` then treats that absence as non-disqualifying, so
    behavior (score, decision) is byte-for-byte identical to before this
    criterion existed. Only when a real excerpt is supplied does `grounded`
    enter the prompt, the parsed breakdown, and therefore the mean and the
    disqualify check.
    """
    try:
        if complete is None:
            from studio.providers import llm
            complete = llm.complete
        provider = provider or default_provider("script")
        if transcript_excerpt:
            system, criteria = SYSTEM_GROUNDED, CRITERIA
            user = USER_TMPL_GROUNDED.format(title=title, summary=summary,
                                             transcript_excerpt=transcript_excerpt,
                                             text=variant.text)
        else:
            system, criteria = SYSTEM, UNGROUNDED_CRITERIA
            user = USER_TMPL.format(title=title, summary=summary, text=variant.text)
        raw = complete(provider, system, user)
        scores = json.loads(_strip_fence(raw))["scores"]
        breakdown = {k: float(scores[k]) for k in criteria}
        mean, decision = _decide(breakdown)
        return Verdict(score=round(mean, 2), breakdown=breakdown, decision=decision)
    except Exception:
        return Verdict()


def ranked(variants: list[Variant], title: str, summary: str, provider: str = "",
          complete=None, transcript_excerpt: str = "") -> list[tuple[Variant, Verdict]]:
    """Judge every variant and return (variant, verdict) pairs, best score first."""
    judged = [(v, judge(v, title, summary, provider, complete, transcript_excerpt))
              for v in variants]
    judged.sort(key=lambda t: t[1].score, reverse=True)
    return judged


def best(variants: list[Variant], title: str, summary: str, provider: str = "",
         complete=None, transcript_excerpt: str = "") -> tuple[Variant | None, Verdict | None, int]:
    """Judge every variant and return the highest scorer with its original index."""
    if not variants:
        return None, None, -1
    winner, verdict = ranked(variants, title, summary, provider, complete, transcript_excerpt)[0]
    idx = next(i for i, v in enumerate(variants) if v is winner)
    return winner, verdict, idx
