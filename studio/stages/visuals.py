"""Stage 2 — one keyframe image per scene (consistent character via prompt/refs)."""

from __future__ import annotations

from pathlib import Path

from studio import canvas, paths
from studio.models import Script
from studio.providers import image
from studio.providers.base import GenResult


PLATE_SUFFIX = (
    ". BACKGROUND PLATE — render the EXACT same scene, setting, composition and lighting "
    "but with every person, figure, character and main foreground subject COMPLETELY "
    "REMOVED: empty architecture and scenery only, no people anywhere, a clean uninhabited "
    "background"
)


def run(run_dir: Path, provider: str, char_ref: Path | None = None,
        force: bool = False, cheap_provider: str = "", parallax_plates: bool = False) -> GenResult:
    """Generate one keyframe per scene. With `cheap_provider`, scenes flagged
    `image_role="bg"` (backgrounds/overlays) use the cheaper model, while
    `hero`/default scenes (character/main person) use the quality `provider` — and
    only those get the character reference (cheap models ignore it anyway).

    `parallax_plates` (balanced+ tiers): for every `animator:"parallax"` scene also
    generate a SEPARATE background plate (subject removed) → true layered parallax with
    genuinely different fg/bg images (no torn frame, no inpaint hole). +1 image/scene."""
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    canvas.set_from_aspect(script.aspect)
    paths.visuals_dir(run_dir).mkdir(parents=True, exist_ok=True)
    refs = [char_ref] if char_ref else None

    total_cost, total_latency = 0.0, 0.0
    counts: dict[str, int] = {}
    for idx, scene in enumerate(script.scenes):
        dst = paths.scene_image(run_dir, scene.id)
        # backgrounds/overlays → cheap model (no char ref); else quality + ref.
        if scene.image_role == "bg" and cheap_provider:
            prov, use_refs = cheap_provider, None
        else:
            prov, use_refs = provider, refs
        # reinforce consistency: prepend the reusable character string.
        prompt = scene.visual_prompt
        if script.character and script.character not in prompt:
            prompt = f"{script.character}. {prompt}"
        if not (dst.exists() and not force):
            res = image.generate(prov, prompt, dst, refs=use_refs, aspect=script.aspect,
                                 headline=scene.on_screen_text, index=idx)
            total_cost += res.cost_usd
            total_latency += res.latency_s
            counts[prov] = counts.get(prov, 0) + 1
        # layered-parallax background plate (subject removed) — balanced+ only.
        if parallax_plates and (scene.animator or "").strip() == "parallax":
            bgdst = paths.scene_image_bg(run_dir, scene.id)
            if not (bgdst.exists() and not force):
                res2 = image.generate(prov, prompt + PLATE_SUFFIX, bgdst, refs=None,
                                      aspect=script.aspect, index=idx)
                total_cost += res2.cost_usd
                total_latency += res2.latency_s
                counts[f"{prov}+plate"] = counts.get(f"{prov}+plate", 0) + 1
    n = sum(counts.values())
    mix = ", ".join(f"{v}×{k}" for k, v in counts.items()) or "0"
    return GenResult(path=paths.visuals_dir(run_dir), cost_usd=round(total_cost, 4),
                     latency_s=round(total_latency, 2),
                     provider="+".join(counts) or provider, note=f"{n} images ({mix})")
