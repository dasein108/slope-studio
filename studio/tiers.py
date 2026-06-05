"""Tier presets — one knob to set providers across all stages.

A tier maps each stage to a provider. `studio run --tier X` applies these unless a
specific --*-provider flag overrides. The video 'strategy' decides per-scene AI vs
free Ken Burns (see studio/stages/clips.py).

Tiers (cheapest → best):
  free      everything offline/free. No spend, no AI video, no quality images.
  cheap     real Nano Banana stills + free Ken Burns motion. ~$0.04/scene (images only).
  balanced  Nano Banana stills + SMART AI video within --max-cost (auto hero scenes).
  premium   Nano Banana stills + AI video on EVERY scene + best voice. Cost scales per second.
"""

from __future__ import annotations

# NOTE: `script` is omitted on paid tiers ON PURPOSE — it falls through to
# config.default_provider("script") (a real LLM when a key is present, else stub).
# Only `free` pins "stub" so it stays fully offline. The per-scene AI-vs-Ken-Burns
# decision lives in `strategy` (+ clips.plan), not a provider key.
TIER_PRESETS: dict[str, dict[str, str]] = {
    "free": {
        "script": "stub",  # offline tier: never call an LLM even if a key exists
        "image": "card", "image_cheap": "card",
        "voice": "edge", "strategy": "kenburns",
        "sfx": "silence", "music": "silence",  # offline, $0
    },
    "cheap": {
        # everything on the cheap image model (~$0.006/img); no char-ref consistency.
        "image": "fal-flux-schnell", "image_cheap": "fal-flux-schnell",
        "voice": "edge", "strategy": "kenburns",
        "sfx": "local", "music": "local",  # free downloaded packs; silence if empty
    },
    "balanced": {
        # hero/character scenes → Nano Banana; backgrounds/overlays → FLUX schnell.
        "image": "fal-nanobanana", "image_cheap": "fal-flux-schnell",
        "voice": "edge", "strategy": "auto",  # fill AI within --max-cost
        "sfx": "fal-elevenlabs-sfx", "music": "fal-stable-audio",
    },
    "premium": {
        "image": "fal-nanobanana", "image_cheap": "fal-flux-schnell",
        "voice": "openai-tts", "strategy": "all",  # AI every scene
        "sfx": "fal-elevenlabs-sfx", "music": "fal-stable-audio",
    },
}

DEFAULT_MODEL_BY_TIER = {
    "free": "kling", "cheap": "kling", "balanced": "ltx", "premium": "kling",
}


def preset(tier: str) -> dict[str, str]:
    if tier not in TIER_PRESETS:
        raise ValueError(f"unknown tier {tier}; choose from {list(TIER_PRESETS)}")
    return TIER_PRESETS[tier]
