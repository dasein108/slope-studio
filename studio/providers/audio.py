"""Sound-effect and background-music generation/sourcing.

Two media kinds, same GenResult contract as the other providers:

  generate_sfx   — short one-shot effects (sword clash, whoosh, breath, ambient)
  generate_music — a background-music bed for the whole run

COMMERCIAL-SAFE sources only (monetized YouTube/TikTok). See the deep-research
report in docs/ for licensing detail. Quick map:

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
                        Use Pixabay / YouTube Audio Library / Mixkit packs (free,
                        commercial-safe). (recommended free)
    silence             offline stub — silent track, $0.

Content-ID note: AI-generated and first-party-library audio carry LOWER false-claim
risk than RAW community SFX. NEVER pull CC-BY-NC from Freesound for monetized video.
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

# $0.20/gen is CONFIRMED on the stable-audio-25 audio-to-audio variant; the
# text-to-audio id + price should be re-checked at integration time.
FAL_MUSIC_MODEL = "fal-ai/stable-audio-25/text-to-audio"
FAL_MUSIC_COST = 0.20              # flat per generation (not per second)

FREESOUND_CC0 = 'license:"Creative Commons 0"'  # hard filter — no attribution, sellable


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
        cost, note = 0.0, _local_pick("sfx", prompt, dst, secs)
    elif provider == "silence":
        ffmpeg.silence(dst, secs)
        cost, note = 0.0, "silent stub"
    else:
        raise ValueError(f"unknown sfx provider {provider}")
    return GenResult(path=dst, cost_usd=cost, latency_s=round(time.time() - t0, 2),
                     provider=provider, note=note)


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
    elif provider == "silence":
        ffmpeg.silence(dst, seconds)
        cost, note = 0.0, "silent stub"
    else:
        raise ValueError(f"unknown music provider {provider}")
    return GenResult(path=dst, cost_usd=cost, latency_s=round(time.time() - t0, 2),
                     provider=provider, note=note)


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

    CC0 keeps us attribution-free and monetization-safe. CC-BY would also be legal
    with credit, but we hard-exclude anything non-CC0 here to stay zero-friction.
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
    best = max(files, key=lambda p: len(tokens & set(_tokens(p.stem))))
    shutil.copy(best, dst)
    return f"local:{kind} '{best.name}'"


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
