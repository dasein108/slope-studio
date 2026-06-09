"""Local video generation via a running ComfyUI server (Apple Silicon / MPS).

Free, offline i2v for DRAFT/PREVIEW clips. Slow (minutes per few seconds) — not a
fal replacement for production. Backed by API-format workflow templates in
`workflows/*.json` that this module patches per scene (image, prompt, length, dims).

Model filenames are NOT hardcoded: they're auto-filled from the live `/object_info`
enums by matching `MODEL_FILL` patterns, so the templates survive whatever exact
bf16 safetensors you downloaded. Use bf16 (not fp8 — fp8 is broken on Metal).

Run directly to smoke-test a single clip:
    python -m studio.providers.comfy_local some_still.png "a slow cinematic push-in" \\
        --model wan-local --seconds 2 --out /tmp/clip.mp4
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import httpx

COMFY_URL = "http://127.0.0.1:8188"
_WF_DIR = Path(__file__).parent / "workflows"

# model spec per --video-model name → template + fps + frame grid (length must be n*mult+1)
# wan-local defaults to the GGUF Q4 graph — small weights + tiled VAE decode so it fits
# 32 GB without swap-hanging the Mac. wan-local-fp16 is the heavier bf16 path (~22 GB).
LOCAL_MODELS = {
    "wan-local":      {"wf": "wan5b_gguf.json", "fps": 24, "frame_mult": 4},
    "wan-local-fp16": {"wf": "wan5b.json", "fps": 24, "frame_mult": 4},
    "ltx-local":      {"wf": "ltx2b.json", "fps": 25, "frame_mult": 8},
}

# how to auto-fill each loader's model-file field from /object_info enums.
# {class_type: (input_field, [substring patterns, first match wins])}
MODEL_FILL = {
    "UNETLoader":             ("unet_name", ["wan"]),
    "UnetLoaderGGUF":         ("unet_name", ["wan"]),
    "CheckpointLoaderSimple": ("ckpt_name", ["ltx", "ltxv"]),
    "VAELoader":              ("vae_name", ["wan", "ltx", "ltxv"]),
    "CLIPLoader":             ("clip_name", ["umt5", "t5xxl", "t5"]),
    "CLIPLoaderGGUF":         ("clip_name", ["umt5", "t5xxl", "t5"]),
}

_CAP_SECONDS = 2.0  # local is slow — generate only this much motion; hold last frame for the rest
                    # (≈45 frames @24fps: the steady sweet spot; more frames → MPS memory thrash)


def _client() -> httpx.Client:
    return httpx.Client(base_url=COMFY_URL, timeout=httpx.Timeout(30.0))


def server_up() -> bool:
    try:
        with _client() as c:
            return c.get("/system_stats").status_code == 200
    except httpx.HTTPError:
        return False


def snap_frames(seconds: float, fps: int, mult: int) -> int:
    """Map seconds → a valid frame count on the model's temporal grid (n*mult + 1)."""
    target = int(min(seconds, _CAP_SECONDS) * fps)
    n = max(1, (target - 1) // mult)
    return n * mult + 1


def _node_id(wf: dict, class_type: str, nth: int = 0) -> str | None:
    hits = [k for k, v in wf.items() if v.get("class_type") == class_type]
    return hits[nth] if len(hits) > nth else None


def _enum_options(c: httpx.Client, class_type: str, field: str) -> list[str]:
    info = c.get(f"/object_info/{class_type}").json()[class_type]
    spec = info["input"]["required"].get(field) or info["input"].get("optional", {}).get(field)
    opts = spec[0]
    if isinstance(opts, list) and opts and isinstance(opts[0], str):
        return opts  # legacy enum: [choices...]
    if isinstance(opts, list) and len(opts) > 1 and isinstance(opts[1], dict):
        return opts[1].get("options", [])  # v3 COMBO: ["COMBO", {options:[...]}]
    return []


def _autofill_models(c: httpx.Client, wf: dict) -> None:
    """Fill every loader's model-file field from the live server's available files."""
    for node in wf.values():
        ct = node.get("class_type")
        fill = MODEL_FILL.get(ct)
        if not fill:
            continue
        field, patterns = fill
        if not str(node["inputs"].get(field, "")).startswith("__"):
            continue  # already concrete
        # CLIP loaders serve both models — pick the encoder the `type` actually needs.
        if ct in ("CLIPLoader", "CLIPLoaderGGUF"):
            patterns = ["umt5", "t5"] if node["inputs"].get("type") == "wan" else ["t5xxl", "t5"]
        files = _enum_options(c, ct, field)
        pick = next((f for p in patterns for f in files if p.lower() in f.lower()), None)
        if pick is None:
            raise RuntimeError(
                f"no model file for {ct}.{field} matching {patterns}; "
                f"available={files or '[]'} — download the model into ComfyUI/models/"
            )
        node["inputs"][field] = pick


def _upload_image(c: httpx.Client, image: Path) -> str:
    with open(image, "rb") as f:
        r = c.post("/upload/image", files={"image": (image.name, f, "image/png")},
                   data={"overwrite": "true"})
    r.raise_for_status()
    return r.json()["name"]


def _find_output_video(c: httpx.Client, outputs: dict) -> bytes:
    """Pull the saved mp4 from a /history outputs blob, tolerant of node-shape differences."""
    for node_out in outputs.values():
        for key in ("images", "gifs", "videos", "video"):
            items = node_out.get(key)
            if not items:
                continue
            items = items if isinstance(items, list) else [items]
            for it in items:
                fn = it.get("filename", "")
                if fn.endswith((".mp4", ".webm", ".mov")):
                    r = c.get("/view", params={"filename": fn, "subfolder": it.get("subfolder", ""),
                                               "type": it.get("type", "output")},
                              timeout=httpx.Timeout(120.0))
                    r.raise_for_status()
                    return r.content
    raise RuntimeError(f"no video in ComfyUI outputs: {json.dumps(outputs)[:400]}")


def generate(image: Path, prompt: str, seconds: float, dst: Path, model: str = "wan-local",
             width: int = 480, height: int = 832, poll_s: float = 3.0,
             timeout_s: float = 2700.0) -> Path:
    """Render one clip on the local ComfyUI server. Returns dst. Raises on failure."""
    spec = LOCAL_MODELS.get(model)
    if spec is None:
        raise ValueError(f"unknown local model {model}; choose {list(LOCAL_MODELS)}")
    wf = json.loads((_WF_DIR / spec["wf"]).read_text())
    frames = snap_frames(seconds, spec["fps"], spec["frame_mult"])

    with _client() as c:
        if not server_up():
            raise RuntimeError(f"ComfyUI not reachable at {COMFY_URL} — start it first")
        _autofill_models(c, wf)
        img_name = _upload_image(c, image)

        # patch the per-scene inputs by node class_type (robust to id changes)
        wf[_node_id(wf, "LoadImage")]["inputs"]["image"] = img_name
        wf[_node_id(wf, "CLIPTextEncode", 0)]["inputs"]["text"] = prompt or "subtle cinematic motion"
        for ct in ("Wan22ImageToVideoLatent", "LTXVImgToVideo"):
            nid = _node_id(wf, ct)
            if nid:
                wf[nid]["inputs"].update(length=frames, width=width, height=height)
        wf[_node_id(wf, "KSampler")]["inputs"]["seed"] = uuid.uuid4().int & 0xFFFFFFFF

        cid = uuid.uuid4().hex
        pid = c.post("/prompt", json={"prompt": wf, "client_id": cid}).json()
        if "error" in pid:
            raise RuntimeError(f"ComfyUI rejected workflow: {json.dumps(pid)[:600]}")
        pid = pid["prompt_id"]

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            hist = c.get(f"/history/{pid}", timeout=httpx.Timeout(30.0)).json()
            if pid in hist:
                status = hist[pid].get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI run failed: {json.dumps(status)[:600]}")
                data = _find_output_video(c, hist[pid]["outputs"])
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
                return dst
            time.sleep(poll_s)
    raise TimeoutError(f"ComfyUI clip exceeded {timeout_s}s")


def _main() -> None:
    ap = argparse.ArgumentParser(description="Smoke-test a local ComfyUI i2v clip.")
    ap.add_argument("image", type=Path)
    ap.add_argument("prompt")
    ap.add_argument("--model", default="wan-local", choices=list(LOCAL_MODELS))
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--height", type=int, default=832)
    ap.add_argument("--out", type=Path, default=Path("/tmp/local_clip.mp4"))
    a = ap.parse_args()
    t0 = time.time()
    out = generate(a.image, a.prompt, a.seconds, a.out, a.model, a.width, a.height)
    print(f"OK {out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    _main()
