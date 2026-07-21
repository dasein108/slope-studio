"""Fetch, normalize, and cache YouTube video transcripts.

`youtube-transcript-api` scrapes YouTube's caption endpoints — it has no
official support contract, so it breaks in unpredictable ways: no captions on
the video, a network hiccup, a library-version shape change. Every failure
here collapses to "no transcript" instead of raising, so callers (highlight
selection, comment grounding) never need a try/except of their own.

This module is the foundation for grounding generated comments in what a
video actually says, rather than in the title/description alone.
"""

from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel

from studio.guerrilla import db


class Segment(BaseModel):
    start: float
    text: str


def _normalize(raw: list) -> list[Segment]:
    """Accept either the current library's snippet objects (`.start`/`.text`
    attributes) or the older dict shape (`"start"`/`"text"` keys)."""
    segments = []
    for item in raw:
        if isinstance(item, dict):
            segments.append(Segment(start=float(item["start"]), text=str(item["text"])))
        else:
            segments.append(Segment(start=float(item.start), text=str(item.text)))
    return segments


def _proxy_config():
    """Optional HTTP proxy for transcript fetching, or None for a direct connection.

    Some networks and datacenter IPs are rate-limited or blocked by YouTube for
    caption scraping, so a long-running loop may need to route through a proxy. Set
    TRANSCRIPT_PROXY_URL (e.g. http://user:pass@host:port) in .env to enable it;
    absent, we fetch directly (fine for one-off local use)."""
    from studio.config import env

    url = env("TRANSCRIPT_PROXY_URL")
    if not url:
        return None
    from youtube_transcript_api.proxies import GenericProxyConfig

    return GenericProxyConfig(http_url=url, https_url=url)


def _default_fetcher(video_id: str):
    from youtube_transcript_api import YouTubeTranscriptApi

    proxy = _proxy_config()
    api = YouTubeTranscriptApi(proxy_config=proxy) if proxy else YouTubeTranscriptApi()
    # A proxied endpoint may hand out an occasional rate-limited exit; a few retries
    # land a working one. Direct fetches don't benefit from retrying a blocked IP.
    attempts = 4 if proxy else 1
    last_err: Exception | None = None
    for _ in range(attempts):
        try:
            return _one_fetch(api, video_id)
        except Exception as e:  # noqa: BLE001 - retry any transient/proxy failure
            last_err = e
    raise last_err if last_err else RuntimeError("transcript fetch failed")


def _one_fetch(api, video_id: str):
    from youtube_transcript_api import YouTubeTranscriptApi

    if hasattr(api, "fetch"):
        return api.fetch(video_id)  # current versions: instance method
    return YouTubeTranscriptApi.get_transcript(video_id)  # older versions: classmethod


def fetch(video_id: str, fetcher=None) -> list[Segment]:
    """Fetch and normalize one video's transcript. Returns `[]` on ANY
    failure — no captions, network error, unexpected shape — never raises.

    `fetcher` is the injection seam: production resolves the real (lazily
    imported) library when left `None`; tests pass a stub `fetcher(video_id)
    -> list` so no test hits the network."""
    try:
        if fetcher is None:
            fetcher = _default_fetcher
        return _normalize(list(fetcher(video_id)))
    except Exception:
        return []


def cached(conn: sqlite3.Connection, video_id: str, fetcher=None) -> list[Segment]:
    """DB-backed transcript lookup. A present row — even one with empty
    `segments` — means "already fetched"; only an absent row triggers a
    fetch. Without that distinction a caption-less video would be refetched
    (and re-fail) on every tick."""
    row = conn.execute(
        "SELECT segments FROM transcripts WHERE video_id = ?", (video_id,)
    ).fetchone()
    if row is not None:
        return [Segment(start=start, text=text) for start, text in json.loads(row["segments"])]

    segments = fetch(video_id, fetcher=fetcher)
    conn.execute(
        """INSERT INTO transcripts (video_id, fetched_at, duration, segments)
           VALUES (?, ?, ?, ?)""",
        (
            video_id,
            db.now_iso(),
            duration(segments),
            json.dumps([[s.start, s.text] for s in segments]),
        ),
    )
    conn.commit()
    return segments


def duration(segments: list[Segment]) -> float:
    return segments[-1].start if segments else 0.0


def stamp(seconds: float) -> str:
    """`M:SS`, or `H:MM:SS` at or past one hour. 63 -> "1:03", 3723 -> "1:02:03"."""
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def at(segments: list[Segment], seconds: float, window: float = 15.0) -> str:
    """Concatenated text of segments within `window` seconds of `seconds`, so
    a claimed timestamp can be checked against what the video says there."""
    return " ".join(s.text for s in segments if abs(s.start - seconds) <= window)


def as_prompt(segments: list[Segment], start: float = 0.0, end: float | None = None) -> str:
    """One `[M:SS] text` line per segment starting at or after `start` and
    (if given) at or before `end`, for feeding an LLM a bounded window of the
    transcript."""
    lines = [
        f"[{stamp(s.start)}] {s.text}"
        for s in segments
        if s.start >= start and (end is None or s.start <= end)
    ]
    return "\n".join(lines)
