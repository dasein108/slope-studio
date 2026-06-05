"""Metadata stage — SEO-optimize title / description / tags for publishing.

An LLM pass over the script's topic + narration produces a hook title, a retention
description with a CTA, and YouTube tags. Falls back to deriving solid metadata from
the script deterministically when no LLM is available. Writes `06_final.json`, which
the publish stage consumes. See docs/40-publishing/youtube.md.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from studio import paths
from studio.models import Script
from studio.providers import llm
from studio.providers.base import GenResult

SYSTEM = """You are a YouTube Shorts growth expert. Output ONLY valid JSON. Write a
high-CTR title and SEO description for a vertical Short. Be punchy and curiosity-driven
without clickbait lies."""

USER_TMPL = """Topic: {topic}
Style/tone: {style}
Full narration:
{narration}

Return JSON exactly:
{{
  "title": "<=90 chars, a strong hook, may include 1 emoji, end with #Shorts>",
  "description": "2-4 sentences: hook + what they'll learn + a call to action (subscribe). Then a blank line and 3-6 hashtags.",
  "tags": ["10-15 lowercase keyword tags, no # symbol"]
}}"""


_STOP = {"that", "this", "with", "from", "your", "what", "when", "will", "they",
         "them", "into", "over", "than", "then", "have", "been", "more", "most"}


def _slugwords(text: str, n: int = 12) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    seen: list[str] = []
    for w in words:
        if w not in seen and w not in _STOP:
            seen.append(w)
        if len(seen) >= n:
            break
    return seen


def _fallback(script: Script) -> dict:
    """Deterministic metadata from the script (no LLM)."""
    title = script.title or script.topic
    if "#short" not in title.lower():
        title = f"{title} #Shorts"
    tags = [h.lstrip("#") for h in script.hashtags if h.strip("#")]
    tags += [w for w in _slugwords(script.topic) if w not in tags]
    desc = script.description or script.topic
    if script.hashtags and not any(h in desc for h in script.hashtags):
        desc = f"{desc}\n\n{' '.join(script.hashtags)}"
    return {"title": title[:100], "description": desc, "tags": tags[:15]}


def run(run_dir: Path, provider: str) -> GenResult:
    t0 = time.time()
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    meta = _fallback(script)
    note = "fallback (script-derived)"
    if provider and provider != "stub":
        try:
            narration = " ".join(s.narration for s in script.scenes if s.narration)
            raw = llm.complete(provider, SYSTEM, USER_TMPL.format(
                topic=script.topic, style=script.style, narration=narration[:4000]))
            data = json.loads(raw)
            meta = {
                "title": (data.get("title") or meta["title"])[:100],
                "description": data.get("description") or meta["description"],
                "tags": data.get("tags") or meta["tags"],
            }
            if "#short" not in meta["title"].lower():
                meta["title"] = f"{meta['title']} #Shorts"[:100]
            note = f"LLM ({provider})"
        except Exception as e:
            note = f"fallback (LLM failed: {str(e)[:60]})"
    meta["hashtags"] = script.hashtags
    paths.meta_json(run_dir).write_text(json.dumps(meta, indent=2))
    return GenResult(path=paths.meta_json(run_dir), latency_s=round(time.time() - t0, 2),
                     provider=provider, note=note)
