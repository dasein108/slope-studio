"""Decide what a video is actually about, and how sure we are.

The operator's hard rule: if the subject is not clearly understandable from the
title and description, skip the video. A confidently wrong comment is worse than
no comment — it reads as a bot, which is exactly the signal to avoid.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from studio.config import default_provider

CONFIDENCE_THRESHOLD = 0.7
DESC_LIMIT = 1200

SYSTEM = """You classify YouTube videos by subject so a commenter can decide whether they
understand the video well enough to say something relevant.

Judge ONLY from the title and description given. Do not speculate about content you cannot
see. If the title is generic ("vlog #47", "Episode 12", "my thoughts"), if the description is
empty or purely promotional, or if you cannot name a specific subject, report LOW confidence.
Being unsure is a correct and useful answer.

Output ONLY valid JSON:
{"topic": "<a short noun phrase naming the subject>",
 "confidence": <0.0-1.0, how sure you are what this video is about>,
 "summary": "<one sentence a reader of the video would agree with>"}"""

# Used only when a transcript excerpt is available (see `classify()`) — mirrors the
# SYSTEM/SYSTEM_GROUNDED split in `critic.py`. The base SYSTEM's "Judge ONLY from the title and
# description" instruction would be actively wrong once real transcript content is on hand, so
# this variant tells the model to prefer the excerpt when it and the title/description disagree.
SYSTEM_WITH_EXCERPT = """You classify YouTube videos by subject so a commenter can decide whether they
understand the video well enough to say something relevant.

Judge from the title, description, AND the transcript excerpt given below — the excerpt is real
spoken content from the video, so prefer it over the title/description whenever they seem to
point at different subjects. If the title is generic ("vlog #47", "Episode 12", "my thoughts"),
the description is empty or purely promotional, and the excerpt still doesn't make the subject
clear, report LOW confidence. Being unsure is a correct and useful answer.

Output ONLY valid JSON:
{"topic": "<a short noun phrase naming the subject>",
 "confidence": <0.0-1.0, how sure you are what this video is about>,
 "summary": "<one sentence a reader of the video would agree with>"}"""

USER_TMPL = """Title: {title}

Description:
{description}"""

USER_TMPL_EXCERPT = """Title: {title}

Description:
{description}

Transcript excerpt:
{transcript_excerpt}"""


class Topic(BaseModel):
    topic: str = ""
    confidence: float = 0.0
    summary: str = ""


def _strip_fence(raw: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return m.group(1).strip() if m else raw.strip()


def classify(title: str, description: str, provider: str = "", complete=None,
            transcript_excerpt: str = "") -> Topic:
    """Classify one video. Any failure yields confidence 0.0 — never raises.

    `transcript_excerpt` is optional real transcript content for the video. When empty — every
    caller before this one, and any caller today with no cached transcript — behavior is
    byte-for-byte identical to before this parameter existed: the original SYSTEM/USER_TMPL pair
    is used. Only when a non-empty excerpt is supplied does the prompt switch to
    SYSTEM_WITH_EXCERPT/USER_TMPL_EXCERPT, which tells the model to ground subject detection in
    what the video actually says rather than the title/description alone.
    """
    try:
        if complete is None:
            from studio.providers import llm
            complete = llm.complete
        provider = provider or default_provider("script")
        if transcript_excerpt:
            system = SYSTEM_WITH_EXCERPT
            user = USER_TMPL_EXCERPT.format(title=title, description=(description or "")[:DESC_LIMIT],
                                            transcript_excerpt=transcript_excerpt)
        else:
            system = SYSTEM
            user = USER_TMPL.format(title=title, description=(description or "")[:DESC_LIMIT])
        raw = complete(provider, system, user)
        return Topic(**json.loads(_strip_fence(raw)))
    except Exception:
        return Topic()


def is_clear(t: Topic) -> bool:
    return bool(t.topic) and t.confidence >= CONFIDENCE_THRESHOLD
