"""Image generation for the visuals stage."""

from __future__ import annotations

import math
import time
import urllib.parse
from pathlib import Path

import httpx

from studio import canvas
from studio.config import env
from studio.providers.base import GenResult

NANO_BANANA_COST = 0.039  # verified $/image (Gemini 2.5 Flash Image); best quality + char-ref
FLUX_SCHNELL_RATE = 0.003  # $/megapixel (fal-ai/flux/schnell), billed rounded up to nearest MP
# Request a portrait <=2MP so it bills as 2MP (not 3) → ~$0.006/img; normalize() upscales
# the still to the 1080x1920 canvas later. 1024x1792 = 1.84MP, 9:~15.75 (near 9:16).
_FLUX_W, _FLUX_H = 1024, 1792


def _mp_cost(w: int, h: int, rate: float) -> float:
    return round(math.ceil(w * h / 1_000_000) * rate, 4)


def generate(provider: str, prompt: str, dst: Path, refs: list[Path] | None = None,
             aspect: str = "9:16", w: int = 0, h: int = 0,
             headline: str = "", index: int = 0) -> GenResult:
    # stub/card draw at native canvas size; fal/pollinations request by `aspect`.
    w, h = w or canvas.W, h or canvas.H
    t0 = time.time()
    if provider == "card":
        from studio.providers import cardgen
        cardgen.render(headline or prompt, dst, index=index, w=w, h=h)
        cost = 0.0
    elif provider == "stub":
        from studio import ffmpeg
        colors = ["teal", "darkslateblue", "maroon", "darkgreen", "indigo", "sienna"]
        ffmpeg.placeholder_image(dst, prompt, colors[abs(hash(prompt)) % len(colors)], w, h)
        cost = 0.0
    elif provider == "pollinations":
        _pollinations(prompt, dst, w, h)
        cost = 0.0
    elif provider == "fal-nanobanana":
        _fal_nanobanana(prompt, dst, refs, aspect)
        cost = NANO_BANANA_COST
    elif provider == "fal-flux-schnell":
        # cheap, fast, good — for backgrounds/overlays (no character-ref consistency).
        _fal_flux_schnell(prompt, dst)
        cost = _mp_cost(_FLUX_W, _FLUX_H, FLUX_SCHNELL_RATE)
    else:
        raise ValueError(f"unknown image provider {provider}")
    return GenResult(path=dst, cost_usd=cost, latency_s=round(time.time() - t0, 2),
                     provider=provider)


def _pollinations(prompt: str, dst: Path, w: int, h: int) -> None:
    enc = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{enc}?width={w}&height={h}&nologo=true"
    r = httpx.get(url, timeout=httpx.Timeout(180.0), follow_redirects=True)
    r.raise_for_status()
    dst.write_bytes(r.content)


def _fal_nanobanana(prompt: str, dst: Path, refs: list[Path] | None,
                    aspect: str = "9:16") -> None:
    import fal_client  # optional dep

    if not env("FAL_KEY"):
        raise RuntimeError("missing FAL_KEY")
    # request vertical so the source isn't letterboxed into the 9:16 clip.
    args: dict = {"prompt": prompt, "num_images": 1, "aspect_ratio": aspect}
    if refs:
        # upload references for character consistency
        args["image_urls"] = [fal_client.upload_file(str(p)) for p in refs]
        model = "fal-ai/nano-banana/edit"
    else:
        model = "fal-ai/nano-banana"
    result = fal_client.run(model, arguments=args)
    img_url = result["images"][0]["url"]
    data = httpx.get(img_url, timeout=httpx.Timeout(180.0)).content
    dst.write_bytes(data)


def _fal_flux_schnell(prompt: str, dst: Path) -> None:
    import fal_client  # optional dep

    if not env("FAL_KEY"):
        raise RuntimeError("missing FAL_KEY")
    result = fal_client.run("fal-ai/flux/schnell", arguments={
        "prompt": prompt,
        "image_size": {"width": _FLUX_W, "height": _FLUX_H},
        "num_images": 1,
        "num_inference_steps": 4,  # schnell is a 1-4 step model
    })
    img_url = result["images"][0]["url"]
    dst.write_bytes(httpx.get(img_url, timeout=httpx.Timeout(180.0)).content)
