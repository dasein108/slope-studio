"""Sound-effect and background-music generation/sourcing.

Two media kinds, same GenResult contract as the other providers:

  generate_sfx   — short one-shot effects (sword clash, whoosh, breath, ambient)
  generate_music — a background-music bed for the whole run

License-safe sources only (monetized YouTube/TikTok). Paid/generated providers are
allowed when their terms cover our use; community/library audio is filtered to avoid
copyrighted, attribution-required, non-commercial, or platform-restricted material.

  SFX providers
    fal-elevenlabs-sfx  ElevenLabs Sound Effects V2 on fal — $0.002/s, "Commercial
                        use" badge. Reuses FAL_KEY. ≤30s/effect. (recommended paid)
    freesound           Freesound API, filtered to CC0 — free, no attribution.
                        Needs FREESOUND_API_KEY. (recommended free programmatic)
    local               pick a downloaded clip from assets/audio/sfx/ by keyword.
    silence             offline stub — a silent clip, $0, for wiring/draft.

  Music providers
    fal-stable-audio    Stable Audio 2.5 on fal — flat $0.20/generation (instrumental,
                        ≤~3min). Cheapest for a full-length bed. (recommended paid)
    local               pick a downloaded track from assets/audio/music/ by keyword.
                        Only add files with license-safe reuse for this channel.
    silence             offline stub — silent track, $0.

Content-ID note: AI-generated and first-party-library audio carry LOWER false-claim
risk than raw community SFX. NEVER pull copyrighted, CC-BY/attribution-required,
CC-BY-NC/non-commercial, or platform-restricted Freesound/community audio.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import httpx

from studio import ffmpeg, paths
from studio.config import env
from studio.providers.base import GenResult

# --- verified pricing / model ids (deep-research, mid-2026 — re-confirm at integ) ---
FAL_SFX_MODEL = "fal-ai/elevenlabs/sound-effects/v2"
FAL_SFX_COST_PER_S = 0.002          # confirmed on the fal model page
SFX_MAX_S = 30.0                    # ElevenLabs Sound Effects hard cap
LOCAL_SFX_MAX_S = 5.0               # accents only; ambience/music belong elsewhere

# $0.20/gen is CONFIRMED on the stable-audio-25 audio-to-audio variant; the
# text-to-audio id + price should be re-checked at integration time.
FAL_MUSIC_MODEL = "fal-ai/stable-audio-25/text-to-audio"
FAL_MUSIC_COST = 0.20              # flat per generation (not per second)

FREESOUND_CC0 = 'license:"Creative Commons 0"'  # hard filter — no attribution, sellable

_SFX_FAMILY_KEYWORDS = {
    "impact": ("impact", "hit", "boom", "crash", "shock", "drop", "thump"),
    "whoosh": ("whoosh", "swish", "rush", "fast", "vanish"),
    "sparkle": ("glitch", "spark", "shimmer", "chime", "digital", "ticker", "alarm"),
    "rumble": ("rumble", "swell", "tension", "tense", "mechanical", "low", "drone"),
    "hum": ("hum", "cosmic"),
    "bell": ("bell", "toll"),
    "wind": ("wind", "gust"),
}


def expected_music_cost(provider: str) -> float:
    """Predicted music-bed cost, for whole-video budgeting. Only `fal-stable-audio`
    costs money ($0.20 flat); `local`/`freesound`/`silence` are free. SFX is per-second
    and negligible (~$0.002/s), so it's not reserved against the budget."""
    return FAL_MUSIC_COST if provider == "fal-stable-audio" else 0.0


# --------------------------------------------------------------------------- SFX
def generate_sfx(provider: str, prompt: str, seconds: float, dst: Path) -> GenResult:
    """Produce one sound effect for `prompt` (~`seconds` long) at `dst` (mp3)."""
    t0 = time.time()
    secs = min(max(0.5, seconds), SFX_MAX_S)
    note = ""
    if provider == "fal-elevenlabs-sfx":
        _fal_sfx(prompt, secs, dst)
        cost = round(secs * FAL_SFX_COST_PER_S, 4)
        note = f"fal:elevenlabs-sfx ${cost}"
    elif provider == "freesound":
        cost, note = 0.0, _freesound(prompt, dst, want_music=False)
    elif provider == "local":
        cost, note = 0.0, _local_pick("sfx", prompt, dst, min(secs, LOCAL_SFX_MAX_S))
    elif provider == "silence":
        ffmpeg.silence(dst, secs)
        cost, note = 0.0, "silent stub"
    else:
        raise ValueError(f"unknown sfx provider {provider}")
    return GenResult(path=dst, cost_usd=cost, latency_s=round(time.time() - t0, 2),
                     provider=provider, note=note)


def sfx_family(prompt: str) -> str:
    """Return a stable family name used to prevent repetitive accent patterns."""
    p = (prompt or "").lower()
    for family, keywords in _SFX_FAMILY_KEYWORDS.items():
        if any(word in p for word in keywords):
            return family
    return " ".join(sorted({t for t in _tokens(prompt) if len(t) > 2}))


def _fal_sfx(prompt: str, seconds: float, dst: Path) -> None:
    import fal_client

    if not env("FAL_KEY"):
        raise RuntimeError("missing FAL_KEY")
    result = fal_client.run(FAL_SFX_MODEL, arguments={
        "text": prompt,
        "duration_seconds": round(seconds, 1),
    })
    _download_audio(result, dst)


# ------------------------------------------------------------------------- MUSIC
def generate_music(provider: str, prompt: str, seconds: float, dst: Path) -> GenResult:
    """Produce a background-music bed for `prompt` (~`seconds` long) at `dst` (mp3).

    Beds are looped to length at mix time (ffmpeg.duck_music), so a short generation
    is fine — `seconds` is a hint, not a hard requirement.
    """
    t0 = time.time()
    note = ""
    if provider == "fal-stable-audio":
        _fal_music(prompt, seconds, dst)
        cost, note = FAL_MUSIC_COST, f"fal:stable-audio ${FAL_MUSIC_COST}"
    elif provider == "freesound":
        cost, note = 0.0, _freesound(prompt, dst, want_music=True)
    elif provider == "local":
        cost, note = 0.0, _local_pick("music", prompt, dst, seconds)
    elif provider == "synth":
        _synth_music(prompt, seconds, dst)
        cost, note = 0.0, "synth:music bed (free)"
    elif provider == "silence":
        ffmpeg.silence(dst, seconds)
        cost, note = 0.0, "silent stub"
    else:
        raise ValueError(f"unknown music provider {provider}")
    return GenResult(path=dst, cost_usd=cost, latency_s=round(time.time() - t0, 2),
                     provider=provider, note=note)


def _synth_music(prompt: str, seconds: float, dst: Path) -> None:
    """Map a mood prompt to a free ffmpeg music bed.

    The recipes are intentionally distinct: ancient/folk gets a pulsed plucked texture,
    bright/hopeful gets a major pad, neutral/calm stays an understated drone.
    """
    p = (prompt or "").lower()
    major = any(w in p for w in ("major", "bright", "happy", "playful", "wry", "hopeful", "warm"))
    # roots stay OUT of the sub-bass (>= the synth_drone ~87 Hz floor) so the bed is felt as
    # tone, not pressure. Deep moods sit low-but-audible (G2/A2), not as a 49 Hz rumble.
    if any(w in p for w in ("cosmic", "space", "void", "dread", "dark", "black hole", "horror", "ominous")):
        root, bright = 98.0, 0.3
        ffmpeg.synth_drone(dst, seconds, root_hz=root, brightness=bright, minor=True)
    elif any(w in p for w in ("mournful", "sad", "melancholy", "tragic", "elegiac", "lament", "grief")):
        root, bright = 110.0, 0.4
        ffmpeg.synth_drone(dst, seconds, root_hz=root, brightness=bright, minor=True)
    elif any(w in p for w in ("tense", "suspense", "mystery", "eerie", "unease")):
        root, bright = 98.0, 0.35
        ffmpeg.synth_drone(dst, seconds, root_hz=root, brightness=bright, minor=True)
    elif any(w in p for w in ("lyre", "ancient", "folk", "pastoral", "tanpura")):
        ffmpeg.synth_plucked_bed(dst, seconds, root_hz=220.0)
    elif any(w in p for w in ("major", "bright", "happy", "playful", "hopeful")):
        ffmpeg.synth_major_pad(dst, seconds, root_hz=196.0)
    else:
        root, bright = 131.0, 0.45
        ffmpeg.synth_drone(dst, seconds, root_hz=root, brightness=bright, minor=not major)


def _fal_music(prompt: str, seconds: float, dst: Path) -> None:
    import fal_client

    if not env("FAL_KEY"):
        raise RuntimeError("missing FAL_KEY")
    result = fal_client.run(FAL_MUSIC_MODEL, arguments={
        "prompt": prompt or "calm cinematic ambient background, instrumental",
        "seconds_total": int(min(max(10.0, seconds), 180.0)),  # model caps ~3min; must be int
    })
    _download_audio(result, dst)


# ----------------------------------------------------------------- free sources
def _freesound(query: str, dst: Path, want_music: bool) -> str:
    """Search Freesound, CC0-only, download the HQ preview (token-only, no OAuth).

    CC0 keeps Freesound/community imports attribution-free and monetization-safe.
    Hard-exclude anything non-CC0 to avoid CC-BY attribution workflow, CC-BY-NC,
    copyright, and platform/license ambiguity.
    """
    key = env("FREESOUND_API_KEY")
    if not key:
        raise RuntimeError("missing FREESOUND_API_KEY")
    filt = FREESOUND_CC0 + (" duration:[20 TO 200]" if want_music else " duration:[0.1 TO 30]")
    r = httpx.get("https://freesound.org/apiv2/search/text/", params={
        "query": query, "filter": filt, "sort": "score",
        "fields": "id,name,license,previews", "page_size": 5,
        "token": key,
    }, timeout=httpx.Timeout(60.0))
    r.raise_for_status()
    hits = r.json().get("results", [])
    if not hits:
        ffmpeg.silence(dst, 3.0)
        return "freesound: no CC0 match -> silence"
    top = hits[0]
    url = top["previews"]["preview-hq-mp3"]
    dst.write_bytes(httpx.get(url, timeout=httpx.Timeout(180.0)).content)
    return f"freesound CC0 #{top['id']} '{top['name']}'"


def _local_pick(kind: str, prompt: str, dst: Path, seconds: float) -> str:
    """Copy the best keyword match from assets/audio/<kind>/ to `dst`.

    Scores files by how many prompt tokens appear in the filename stem. Falls back
    to the first file, or to silence if the library is empty/missing.
    """
    lib = paths.audio_library_dir(kind)
    files = sorted(p for p in lib.glob("*") if p.suffix.lower() in {".mp3", ".wav", ".ogg", ".m4a"}) \
        if lib.exists() else []
    if not files:
        ffmpeg.silence(dst, seconds)
        return f"local:{kind} empty ({lib}) -> silence"
    tokens = {t for t in _tokens(prompt) if len(t) > 2}
    scored = [(len(tokens & set(_tokens(p.stem))), p) for p in files]
    score, best = max(scored, key=lambda item: item[0])
    if score == 0 and kind == "sfx":
        synth = _synth_sfx_for_prompt(prompt)
        if synth:
            ffmpeg.synth_sfx(dst, synth)
            ffmpeg.trim_audio(dst, dst.with_suffix(".trim.mp3"), min(seconds, LOCAL_SFX_MAX_S))
            dst.with_suffix(".trim.mp3").replace(dst)
            return f"synth-sfx:{synth} (no local keyword match)"
        ffmpeg.silence(dst, min(seconds, LOCAL_SFX_MAX_S))
        return "local:sfx no keyword match -> silence"
    if kind == "sfx":
        ffmpeg.trim_audio(best, dst, min(seconds, LOCAL_SFX_MAX_S))
        return f"local:sfx '{best.name}' trimmed {min(seconds, LOCAL_SFX_MAX_S):.1f}s"
    shutil.copy(best, dst)
    return f"local:{kind} '{best.name}'"


def _synth_sfx_for_prompt(prompt: str) -> str | None:
    family = sfx_family(prompt)
    if family == "impact":
        return "impact"
    if family == "whoosh":
        return "whoosh"
    if family == "sparkle":
        return "sparkle"
    if family == "rumble":
        return "rumble"
    if family == "hum":
        return "hum"
    return None


def _tokens(s: str) -> list[str]:
    return [t for t in "".join(c if c.isalnum() else " " for c in s.lower()).split() if t]


def _download_audio(result: dict, dst: Path) -> None:
    """Pull the audio URL out of a fal result (handles the common shapes)."""
    if "audio" in result:
        url = result["audio"]["url"] if isinstance(result["audio"], dict) else result["audio"]
    elif "audio_file" in result:
        url = result["audio_file"]["url"]
    else:
        url = result["url"]
    dst.write_bytes(httpx.get(url, timeout=httpx.Timeout(600.0)).content)
