"""Clip generation for the video stage.

PRICING IS PER SECOND for most hosted i2v models — a 150s video of kling costs
~$10.50 no matter how it's sliced. Use `estimate_cost` for a pre-flight check and
prefer `kenburns` (free) or a hybrid for tight budgets. See docs/10-architecture/cost-model.md.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from studio import ffmpeg
from studio.config import env
from studio.providers.base import GenResult

# fal i2v models with REAL pricing. `per_s` = USD per second of output; `per_video` = flat
# per clip. Verified against fal.ai model pages on 2026-06-04 (prices churn — re-check
# before a big run):
#   kling v2.5 turbo pro  $0.07/s  CONFIRMED from this account's billing ($0.70 / 10s clip)
#   ltx-2 fast            $0.04/s @1080p ($0.08 @1440p, $0.16 @2160p)
#   seedance v1 pro       $0.30/s
#   hailuo-02 standard    ~$0.045/s @768p (~$0.27 / 6s)  — was wrongly modeled as flat $0.49
#   wan-pro               $0.16/s  (~$0.80 / 6s clip)     — was wrongly modeled as flat $0.16
# CHEAPEST short naive-motion clip: ltx ($0.04/s → 5s ≈ $0.20) or hailuo (~$0.22 / 5s).
FAL_MODELS = {
    "kling":    {"id": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video", "per_s": 0.07},
    "ltx":      {"id": "fal-ai/ltx-2/image-to-video/fast",                 "per_s": 0.04},
    "seedance": {"id": "fal-ai/bytedance/seedance/v1/pro/image-to-video",  "per_s": 0.30},
    "hailuo":   {"id": "fal-ai/minimax/hailuo-02/standard/image-to-video", "per_s": 0.045},
    "wan":      {"id": "fal-ai/wan-pro/image-to-video",                    "per_s": 0.16},
}


# Accepted clip-duration grids (seconds) for models that DON'T take the common 5/10.
# ltx-2 accepts even durations 6..20, but we cap at 10s (like the other i2v models) for
# cost control — longer scenes hold the last frame via normalize() rather than pay more.
_DUR_GRID = {
    "ltx": [6, 8, 10],
}


def _clip_dur(model: str, seconds: float) -> int:
    """Snap a desired clip length to the model's accepted duration grid (capped per model)."""
    grid = _DUR_GRID.get(model)
    if grid:
        return next((g for g in grid if g >= seconds), grid[-1])
    return 10 if seconds > 6 else 5  # default grid: kling, wan, hailuo, seedance


def estimate_cost(provider: str, model: str, seconds: float) -> float:
    """Predicted cost for ONE clip of `seconds`. kenburns is free."""
    if provider == "kenburns":
        return 0.0
    spec = FAL_MODELS.get(model, FAL_MODELS["kling"])
    if "per_video" in spec:
        return round(spec["per_video"], 4)
    # i2v models bill per second, clamped to the model's accepted duration grid.
    return round(_clip_dur(model, seconds) * spec["per_s"], 4)


def generate(provider: str, image: Path, prompt: str, seconds: float, dst: Path,
             model: str = "kling") -> GenResult:
    t0 = time.time()
    if provider == "kenburns":
        ffmpeg.ken_burns(image, dst, seconds)
        cost, note = 0.0, "ken-burns (free)"
    elif provider == "fal-i2v":
        _fal_i2v(image, prompt, seconds, dst, model)
        cost = estimate_cost(provider, model, seconds)
        note = f"fal:{model} ${cost}"
    else:
        raise ValueError(f"unknown video provider {provider}")
    return GenResult(path=dst, cost_usd=cost, latency_s=round(time.time() - t0, 2),
                     provider=provider, note=note)


def _fal_i2v(image: Path, prompt: str, seconds: float, dst: Path, model: str) -> None:
    import fal_client

    if not env("FAL_KEY"):
        raise RuntimeError("missing FAL_KEY")
    model_id = FAL_MODELS.get(model, FAL_MODELS["kling"])["id"]
    img_url = fal_client.upload_file(str(image))
    dval = _clip_dur(model, seconds)  # snap to the model's accepted duration grid
    # grid models (ltx) validate against integer literals; others expect the legacy "5"/"10" strings.
    dur = dval if model in _DUR_GRID else str(dval)
    result = fal_client.run(model_id, arguments={
        "prompt": prompt or "subtle natural motion, cinematic",
        "image_url": img_url,
        "duration": dur,
    })
    video_url = result["video"]["url"] if "video" in result else result["url"]
    data = httpx.get(video_url, timeout=httpx.Timeout(600.0)).content
    dst.write_bytes(data)
