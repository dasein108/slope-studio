"""Stage 7 — optional publish to YouTube (TikTok stub: audit-gated)."""

from __future__ import annotations

import json
from pathlib import Path

from studio import paths
from studio.providers import publish as pub
from studio.providers.base import GenResult


def run(run_dir: Path, provider: str, privacy: str = "public",
        channel: str = "") -> GenResult:
    master = paths.master(run_dir)
    if not master.exists():
        raise FileNotFoundError("no master; run save first")
    meta = json.loads(paths.meta_json(run_dir).read_text())
    tags = meta.get("tags") or [h.lstrip("#") for h in meta.get("hashtags", [])]
    thumb = paths.thumbnail(run_dir)
    res = pub.publish(provider, master, meta.get("title", ""),
                      meta.get("description", ""), tags, privacy=privacy, channel=channel,
                      thumbnail=thumb if thumb.exists() else None)
    paths.publish_json(run_dir).write_text(json.dumps({
        "provider": provider, "privacy": privacy, "channel": channel, "result": res.note,
    }, indent=2))
    return res
