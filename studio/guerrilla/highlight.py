"""Pick the single most comment-worthy moment in a video transcript.

`compose` needs something concrete to react to, not a paraphrase of the
video's title. This module chunks a transcript into ~4-minute windows, asks
the LLM for the standout moment in each, and keeps the highest-scoring one
across the whole video. A video under one chunk costs a single LLM call; a
25-minute video costs roughly one call per ~4 minutes.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from studio.config import default_provider
from studio.guerrilla import transcript as tr

CHUNK_SECONDS = 240.0  # ~4 minutes
CITE_THRESHOLD = 4.0

SYSTEM = """You read an excerpt of a YouTube video's transcript and pick the SINGLE most
comment-worthy moment in it — the one a viewer would be most likely to react to.

CITABILITY (0.0-5.0). Score how self-contained the moment is: could a stranger scrolling the
comments understand the reference WITHOUT having watched the video? A surprising claim, a
specific number, a named person or work, or a sharp turn in the argument all score high (4-5).
Ambient narration, scene-setting, throat-clearing, or anything that only makes sense in the
flow of surrounding context scores low (0-2). This score is what decides whether a downstream
comment is allowed to cite the timestamp at all, so be honest and strict — most moments in most
videos are NOT citable on their own.

QUOTE. The `quote` field MUST be copied VERBATIM from the transcript excerpt below — the exact
words, not a paraphrase or a summary. A later verification step checks the quote against the
transcript, and a fabricated or reworded quote will be rejected outright. Keep it short (one
sentence or clause), not a whole paragraph.

TIMESTAMP. Use the `[M:SS]` or `[H:MM:SS]` value attached to the line the quote comes from,
converted to seconds as a plain number.

Output ONLY valid JSON:
{"timestamp": <seconds, a number>, "quote": "<verbatim text copied from the transcript>",
 "why": "<one sentence: why this moment is worth reacting to>", "citability": <0.0-5.0>}"""

USER_TMPL = """Video title: {title}

Transcript excerpt:
{excerpt}"""


class Moment(BaseModel):
    timestamp: float
    quote: str
    why: str
    citability: float


def _strip_fence(raw: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return m.group(1).strip() if m else raw.strip()


def _chunk_segments(segments: list[tr.Segment]) -> list[list[tr.Segment]]:
    """Group segments into contiguous ~`CHUNK_SECONDS`-wide windows by start
    time. Each chunk is guaranteed non-empty; there is no gap or overlap
    between chunks, so no segment is ever scored twice."""
    chunks: list[list[tr.Segment]] = []
    current: list[tr.Segment] = []
    chunk_start = 0.0
    for seg in segments:
        if current and seg.start - chunk_start >= CHUNK_SECONDS:
            chunks.append(current)
            current = []
        if not current:
            chunk_start = seg.start
        current.append(seg)
    if current:
        chunks.append(current)
    return chunks


def should_cite(moment: Moment) -> bool:
    return moment.citability >= CITE_THRESHOLD


def best_moment(segments: list[tr.Segment], title: str, provider: str = "",
                complete=None) -> Moment | None:
    """Chunk the transcript into ~4-minute windows, ask the LLM for the most
    comment-worthy moment in each, and return the highest-`citability` one
    across all chunks. Any failure — an empty transcript, unparseable JSON, a
    bad shape, an LLM exception — yields `None`, never raises."""
    try:
        if not segments:
            return None
        if complete is None:
            from studio.providers import llm
            complete = llm.complete
        provider = provider or default_provider("script")

        best: Moment | None = None
        for chunk in _chunk_segments(segments):
            excerpt = tr.as_prompt(chunk)
            raw = complete(provider, SYSTEM, USER_TMPL.format(title=title, excerpt=excerpt))
            data = json.loads(_strip_fence(raw))
            moment = Moment(
                timestamp=float(data["timestamp"]),
                quote=str(data["quote"]),
                why=str(data.get("why", "")),
                citability=float(data["citability"]),
            )
            if best is None or moment.citability > best.citability:
                best = moment
        return best
    except Exception:
        return None
