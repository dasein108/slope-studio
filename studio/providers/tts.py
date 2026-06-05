"""Text-to-speech for the voiceover stage. Produces mp3 (+ srt when possible).

Voice + tone are semantic (man|woman|cartoon|narrator × neutral|serious|mystical|
friendly|sad|excited), resolved to concrete provider settings in studio/voices.py.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx

from studio import voices
from studio.config import env
from studio.providers.base import GenResult

OPENAI_TTS_COST_PER_1K = 0.015  # estimate for tts-1; refine per model


def synth(provider: str, text: str, mp3: Path, srt: Path | None = None,
          voice_name: str = "woman", tone: str = "neutral") -> GenResult:
    t0 = time.time()
    cfg = voices.resolve(provider, voice_name, tone)
    if provider == "edge":
        asyncio.run(_edge(text, mp3, srt, cfg))
        cost = 0.0
    elif provider == "openai-tts":
        _openai(text, mp3, cfg)
        cost = round(len(text) / 1000 * OPENAI_TTS_COST_PER_1K, 4)
    else:
        raise ValueError(f"unknown tts provider {provider}")
    return GenResult(path=mp3, cost_usd=cost, latency_s=round(time.time() - t0, 2),
                     provider=provider)


def synth_scene(provider: str, text: str, mp3: Path, voice_name: str = "woman",
                tone: str = "neutral") -> list[tuple[float, float, str]]:
    """Synthesize one scene's narration. Return caption cues (start,end,text) relative
    to the clip start (empty if the provider yields no timing)."""
    cfg = voices.resolve(provider, voice_name, tone)
    if provider == "edge":
        return asyncio.run(_edge_scene(text, mp3, cfg))
    if provider == "openai-tts":
        _openai(text, mp3, cfg)
        return []
    raise ValueError(f"unknown tts provider {provider}")


async def _edge_scene(text: str, mp3: Path, cfg: dict) -> list[tuple[float, float, str]]:
    import edge_tts

    communicate = edge_tts.Communicate(text, cfg["voice"], rate=cfg["rate"], pitch=cfg["pitch"])
    sm = edge_tts.SubMaker()
    got = False
    with mp3.open("wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"].endswith("Boundary"):
                sm.feed(chunk)
                got = True
    if not got:
        return []
    tmp = mp3.with_suffix(".scene.srt")
    tmp.write_text(sm.get_srt())
    from studio.ffmpeg import _parse_srt
    cues = _parse_srt(tmp)
    tmp.unlink(missing_ok=True)
    return cues


async def _edge(text: str, mp3: Path, srt: Path | None, cfg: dict) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, cfg["voice"], rate=cfg["rate"], pitch=cfg["pitch"])
    submaker = edge_tts.SubMaker()
    got_boundary = False
    with mp3.open("wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"].endswith("Boundary"):  # Word- or SentenceBoundary
                submaker.feed(chunk)
                got_boundary = True
    if srt is not None and got_boundary:
        srt.write_text(submaker.get_srt())


def _openai(text: str, mp3: Path, cfg: dict) -> None:
    key = env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("missing OPENAI_API_KEY")
    r = httpx.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gpt-4o-mini-tts", "voice": cfg["voice"],
              "input": text, "instructions": cfg.get("instructions", "")},
        timeout=httpx.Timeout(180.0),
    )
    r.raise_for_status()
    mp3.write_bytes(r.content)
