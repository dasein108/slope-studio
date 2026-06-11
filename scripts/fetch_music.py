"""Fetch reusable music/soundscape beds into assets/audio/music/.

Fetches only Freesound CC0/public-domain previews for zero-friction video use:

    .venv/bin/python scripts/fetch_music.py --query "tanpura drone"

The script downloads Freesound preview MP3s, not original files, so OAuth is not needed.
It uses FREESOUND_API_KEY from .env.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import httpx

from studio import paths
from studio.config import env

API = "https://freesound.org/apiv2"
CC0 = "http://creativecommons.org/publicdomain/zero/1.0/"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:80] or "freesound-music"


def _get(path: str, params: dict[str, str | int]) -> dict:
    key = env("FREESOUND_API_KEY")
    if not key:
        raise SystemExit("missing FREESOUND_API_KEY in .env")
    r = httpx.get(
        f"{API}{path}",
        params={**params, "token": key},
        timeout=httpx.Timeout(45.0),
    )
    r.raise_for_status()
    return r.json()


def _download(url: str, dst: Path) -> None:
    with httpx.stream("GET", url, timeout=httpx.Timeout(60.0), follow_redirects=True) as r:
        r.raise_for_status()
        with dst.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)


def _fetch_sound(sound: dict) -> Path:
    license_url = sound.get("license", "")
    if license_url != CC0:
        raise SystemExit(f"refusing non-CC0/public-domain sound #{sound.get('id')} ({license_url})")
    # Prefer lq previews for reusable beds: smaller, reliable to fetch, and still fine under narration.
    preview = sound.get("previews", {}).get("preview-lq-mp3") or sound.get("previews", {}).get("preview-hq-mp3")
    if not preview:
        raise SystemExit(f"sound #{sound.get('id')} has no mp3 preview")
    music = paths.audio_library_dir("music")
    music.mkdir(parents=True, exist_ok=True)
    filename = f"freesound-{sound['id']}-{_slug(sound.get('name', 'music'))}.mp3"
    dst = music / filename
    if not dst.exists():
        _download(preview, dst)
    return dst


def fetch_by_id(sound_id: int) -> Path:
    sound = _get(
        f"/sounds/{sound_id}/",
        {"fields": "id,name,username,license,url,duration,previews,tags"},
    )
    return _fetch_sound(sound)


def fetch_by_query(query: str, duration_min: float, duration_max: float) -> Path:
    license_filter = 'license:"Creative Commons 0"'
    data = _get(
        "/search/text/",
        {
            "query": query,
            "filter": f"{license_filter} duration:[{duration_min:g} TO {duration_max:g}]",
            "sort": "score",
            "fields": "id,name,username,license,url,duration,previews,tags",
            "page_size": 1,
        },
    )
    hits = data.get("results", [])
    if not hits:
        raise SystemExit(f"no Freesound match for query: {query!r}")
    return _fetch_sound(hits[0])


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch Freesound music beds into assets/audio/music/")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--sound-id", type=int, help="Freesound sound id, e.g. 155500")
    src.add_argument("--query", help="Freesound search query")
    ap.add_argument("--duration-min", type=float, default=20.0)
    ap.add_argument("--duration-max", type=float, default=300.0)
    args = ap.parse_args()

    if args.sound_id:
        dst = fetch_by_id(args.sound_id)
    else:
        dst = fetch_by_query(args.query, args.duration_min, args.duration_max)
    print(f"saved {dst}")


if __name__ == "__main__":
    main()
