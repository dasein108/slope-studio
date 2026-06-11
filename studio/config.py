"""Environment + provider-default resolution.

Default rule: use the best provider whose key is present, else fall back to the
free path. Any stage can be overridden with --provider on the CLI.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def env(key: str) -> str | None:
    val = os.environ.get(key)
    return val.strip() if val and val.strip() else None


@lru_cache
def have() -> dict[str, bool]:
    return {
        "fal": bool(env("FAL_KEY")),
        "openrouter": bool(env("OPENROUTER_API_KEY")),
        "groq": bool(env("GROQ_API_KEY")),
        "openai": bool(env("OPENAI_API_KEY")),
        "gemini": bool(env("GEMINI_API_KEY")),
        "ollama": bool(env("OLLAMA_HOST")),
        "freesound": bool(env("FREESOUND_API_KEY")),
    }


def default_provider(stage: str) -> str:
    """Pick a sensible default provider for a stage given available keys."""
    h = have()
    if stage == "script":
        if h["openai"]:
            return "openai"
        if h["gemini"]:
            return "gemini"
        if h["groq"]:
            return "groq"
        if h["openrouter"]:
            return "openrouter"
        if h["ollama"]:
            return "ollama"
        return "stub"  # deterministic offline split, lets the pipeline run keyless
    if stage == "visuals":
        if h["fal"]:
            return "fal-nanobanana"  # Nano Banana via fal — quality + character-ref
        return "card"  # offline typographic cards (Pillow); pollinations paywalls anon
    if stage == "visuals_cheap":
        if h["fal"]:
            return "fal-flux-schnell"  # ~$0.006/img, 4x cheaper — backgrounds/overlays
        return "card"
    if stage == "clips":
        if h["fal"]:
            return "fal-i2v"
        return "kenburns"  # free ffmpeg pan/zoom, no AI video
    if stage == "voice":
        return "openai-tts" if h["openai"] else "edge"
    if stage == "sfx":
        if h["fal"]:
            return "fal-elevenlabs-sfx"
        if h["freesound"]:
            return "freesound"  # CC0/public-domain, no attribution/community-license risk
        return "local"  # open local packs; falls back to silence if empty
    if stage == "music":
        if h["fal"]:
            return "fal-stable-audio"
        if h["freesound"]:
            return "freesound"  # CC0/public-domain, no attribution/community-license risk
        return "local"  # open local packs; silence if empty
    if stage == "publish":
        return "youtube"
    raise ValueError(f"unknown stage {stage}")
