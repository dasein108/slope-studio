# Stage 2 — Visuals (Scene Images + Consistent Character/Avatar)

Generate one keyframe per scene, and (optionally) a reusable character with multiple poses/views. Two sub-modes:

- **A. Scene illustration** — independent image per scene from `visual_prompt`. Simplest.
- **B. Consistent character** — same character across all scenes (and a pose/view sheet for avatar work in stage 3). Solved by reference images or a trained LoRA.

## Why this stage matters
Stage 3 video quality is capped by stage 2 image quality (most clips are image-to-video). Cheap, consistent, high-res keyframes here = cheaper, better video downstream. Iterating images costs cents; iterating video costs dollars.

## Image model options (price / features / speed / quality)

> ✅ = verified by research. 🔶 = approximate domain knowledge, re-check.

| Model | Price 🔶 (✅ where noted) | Character consistency | Ref images | Quality | Notes |
|-------|------|----------------------|-----------|---------|-------|
| **Gemini 2.5 Flash Image (Nano Banana)** | **$0.039/img** ✅ | native, strong ✅ | yes | high | **best value pick.** "same character in different environments / multi-angle / consistent brand assets" ✅ |
| **Nano Banana 2** | 🔶 ~$0.06–0.13/img (higher-res tiers) | strongest; up to **5 characters** | **up to 14** ✅ | very high | exceptional text rendering ✅, multi-image compositing ✅ |
| **Seedream 4 / 4.5 / 5** (ByteDance) | 🔶 ~$0.03/img | strong | **10 ref** ✅ | high | strong NB competitor; good consistency ✅ |
| **FLUX.1 [dev]** (open) | self-host (RunPod) or ~$0.003–0.03 via fal/Replicate 🔶 | via LoRA/IP-Adapter | with adapters | high | best open base; LoRA-trainable for fixed char |
| **FLUX.1 Pro / Ultra** | 🔶 ~$0.04–0.06/img | 1 ref | very high | photoreal; API only |
| **SDXL** (open) | self-host cheap 🔶 | LoRA/IP-Adapter | with adapters | good | mature ecosystem (ControlNet, IP-Adapter), cheapest self-host |
| **Midjourney v6/v7** | ~$10–30/mo sub 🔶 | `--cref` char ref | yes | best aesthetics | no official API (ToS risk for automation) |
| **Ideogram V3** | 🔶 ~$0.04–0.08/img | 1 ref ✅ | limited | high; best-in-class text | great for on-screen text/logos |
| **GPT Image (gpt-image-1)** | 🔶 ~$0.01–0.17/img by size | 1 ref ✅ | limited | high | good instruction-following |
| **Pollinations.ai** | **free** ✅ | none | no | medium | no signup ✅; throttles ~1/15s + may watermark since Mar 2025 ✅ |

## Character consistency — the core problem

Ranked by effort:
1. **Reuse the character text string** in every prompt (free, ~60% consistent). Always do this.
2. **Reference images** — Nano Banana (up to 14 ✅), Seedream (10 ✅), Midjourney `--cref`, IP-Adapter on SDXL/FLUX. Good for "same person, new scene." Best effort/quality ratio today.
3. **Trained LoRA** — when you need a *fixed* recurring character/mascot across many videos, or a specific art style. See below.

> ⚠️ Even Nano Banana hedges: Google itself says consistency "may not always get it right" ✅. Build a cheap re-roll loop (generate 2-4 candidates, pick best — optionally with a vision-LLM scorer).

### Avatar / pose sheet (for stage 3 talking-avatar or animation)
Generate the character in a neutral front view + side + 3/4 + key expressions/poses. Nano Banana ("single product from multiple angles" ✅) or a LoRA does this well. This sheet feeds: (a) talking-avatar tools that need a clean face image, (b) i2v that needs the character in scene-specific poses.

## LoRA training on RunPod (optional, for fixed character)
- **When:** recurring mascot/host across many videos, or a brand art style reference images can't hold.
- **Data:** 10-30 images of the subject (can be NB-generated from a few references → bootstrap).
- **How:** FluxGym / kohya_ss / ai-toolkit on a RunPod pod. ✅ RunPod billing is per-second; RTX 4090 **$0.69/hr** ✅, A6000 **$0.49/hr** ✅, A100 80GB **$1.39–1.49/hr** ✅, H100 **$2.89–3.29/hr** ✅. FLUX LoRA trains in ~20-60 min on a 4090/A100.
- **Cost:** 🔶 ~$1-5 of GPU time per LoRA (one-time). A widely-cited community guide reports training a FLUX LoRA "for $1" (blog source, treat as ballpark 🔶).
- **Output:** small `.safetensors` applied at inference on FLUX/SDXL.
- **VRAM:** 🔶 FLUX LoRA training ≈ 24GB (4090) workable with optimizations; 48GB (A6000) comfortable. SDXL LoRA fits 16-24GB.

## Recommendation
- **Default:** Nano Banana (Gemini 2.5 Flash Image) — cheapest path to consistent scenes. Pass character reference image(s) per scene.
- **Fixed mascot at volume:** train one FLUX LoRA on RunPod (~$1-5 once), generate scenes locally/serverless thereafter.
- **Free draft:** Pollinations (accept watermark/throttle) or self-host SDXL on a RunPod pod.
- **On-screen text / logos:** Ideogram V3 for text-heavy frames.

## CLI
```
# per-scene images, consistent character via reference
studio visuals --script runs/<id>/01_script.json --provider nano-banana \
  --char-ref runs/<id>/02_visuals/character/ref_front.png \
  --out runs/<id>/02_visuals/

# build character pose/view sheet first
studio character --desc "curious marine biologist, red beanie..." \
  --views front,side,3q --expressions neutral,excited,thinking \
  --provider nano-banana --out runs/<id>/02_visuals/character/

# optional: train a LoRA on RunPod
studio lora-train --images ./char_dataset/ --base flux-dev \
  --runpod-gpu rtx4090 --out runs/<id>/02_visuals/character/lora/
```
