"""Semantic voice + tone -> concrete TTS settings, per provider.

Author picks a semantic voice (man|woman|cartoon|narrator) and a tone
(neutral|serious|mystical|friendly|sad|excited) in the scenario; this maps them to
real settings. edge approximates tone with rate/pitch; openai-tts uses real
instruction-based tone. See docs/30-animation/voices.md.
"""

from __future__ import annotations

# --- edge-tts concrete voices (free MS Edge) ---
EDGE_VOICES = {
    "woman": "en-US-AriaNeural",
    "man": "en-US-GuyNeural",
    "narrator": "en-GB-RyanNeural",
    "cartoon": "en-US-AnaNeural",   # child voice; pitched up below for a cartoon feel
}
# edge tone -> (rate, pitch). rate like "+0%", pitch like "+0Hz".
EDGE_TONES = {
    "neutral":  ("+0%", "+0Hz"),
    "serious":  ("-8%", "-3Hz"),
    "mystical": ("-14%", "-4Hz"),
    "friendly": ("+6%", "+8Hz"),
    "sad":      ("-16%", "-6Hz"),
    "excited":  ("+14%", "+12Hz"),
    "poetic":   ("-18%", "-3Hz"),   # slow + breathy approximation (edge can't place accents)
}

# --- OpenAI gpt-4o-mini-tts ---
OPENAI_VOICES = {
    "woman": "nova",
    "man": "onyx",
    "narrator": "onyx",
    "cartoon": "fable",
}
OPENAI_TONES = {
    "neutral":  "Speak in a clear, neutral narrator voice.",
    "serious":  "Speak in a serious, measured, authoritative tone.",
    "mystical": "Speak slowly in a mystical, hushed, almost whispering tone full of wonder.",
    "friendly": "Speak in a warm, friendly, upbeat and conversational tone.",
    "sad":      "Speak in a soft, slow, melancholic tone.",
    "excited":  "Speak in an energetic, excited, fast-paced tone.",
    "poetic":   (
        "Read this as poetry, aloud to one person. Slow, deliberate, unhurried. "
        "Pause fully at every line break and on every '…' or '—'; let each image land "
        "before the next. Stress the key noun or verb in each line and lift the final "
        "word of a line slightly. Warm, intimate, hushed. Never rush; let silence do work."
    ),
}


def resolve(provider: str, voice_name: str, tone: str) -> dict:
    """Return concrete TTS settings for a provider.

    edge   -> {"voice", "rate", "pitch"}
    openai -> {"voice", "instructions"}
    """
    v = (voice_name or "woman").lower()
    t = (tone or "neutral").lower()
    if provider == "edge":
        voice = EDGE_VOICES.get(v, EDGE_VOICES["woman"])
        rate, pitch = EDGE_TONES.get(t, EDGE_TONES["neutral"])
        if v == "cartoon":  # push the child voice higher for a cartoon feel
            pitch = "+18Hz"
        return {"voice": voice, "rate": rate, "pitch": pitch}
    if provider == "openai-tts":
        return {"voice": OPENAI_VOICES.get(v, OPENAI_VOICES["woman"]),
                "instructions": OPENAI_TONES.get(t, OPENAI_TONES["neutral"])}
    # unknown provider: best-effort edge mapping
    return {"voice": EDGE_VOICES.get(v, EDGE_VOICES["woman"]), "rate": "+0%", "pitch": "+0Hz"}
