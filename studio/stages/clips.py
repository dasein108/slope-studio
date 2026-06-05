"""Stage 3 — one short clip per scene. Strategy decides AI i2v vs free Ken Burns.

Strategies:
  kenburns  every scene = free pan/zoom on the still ($0).
  all       every scene = AI i2v (cost scales per second — can be expensive).
  hybrid    only scenes in ai_scene_ids get AI; the rest Ken Burns.
  auto      SMART: spend the AI budget on the highest-priority scenes that fit
            `max_cost`, Ken-Burns the rest. Priority = scene.priority, else a
            hero heuristic (hook + outro + evenly-spread beats).

Budget safety: cost is estimated BEFORE generation; the stage aborts (kenburns/all/
hybrid) or trims (auto) so spend never exceeds max_cost. A running guard backstops.
"""

from __future__ import annotations

import json
from pathlib import Path

from studio import animate, canvas, ffmpeg, paths
from studio.models import Scene, Script
from studio.providers import video
from studio.providers.base import GenResult


class BudgetError(RuntimeError):
    pass


def _effective_priority(scene: Scene, index: int, total: int) -> float:
    """Higher = animate first. Honors explicit priority, else a hero heuristic."""
    if scene.priority:
        return float(scene.priority)
    if index == 0:
        return 3.0           # hook
    if index == total - 1:
        return 2.5           # outro / CTA
    if index % 3 == 0:
        return 1.0           # spread some motion through the middle
    return 0.0


def plan(script: Script, strategy: str, model: str,
         ai_scene_ids: set[int] | None, max_cost: float | None) -> tuple[dict[int, str], float]:
    """Return {scene_id: provider} and the total pre-flight AI cost estimate."""
    scenes = script.scenes
    n = len(scenes)
    chosen_ai: set[int] = set()

    if strategy == "kenburns":
        pass
    elif strategy == "all":
        chosen_ai = {s.id for s in scenes}
    elif strategy == "hybrid":
        chosen_ai = set(ai_scene_ids or set())
    elif strategy == "auto":
        # greedily animate by priority while the running AI cost fits the budget.
        budget = max_cost if max_cost is not None else float("inf")
        ranked = sorted(
            range(n),
            key=lambda i: (_effective_priority(scenes[i], i, n), -i),
            reverse=True,
        )
        spent = 0.0
        # highest-priority scenes first; keep filling any scene whose clip still fits.
        for i in ranked:
            c = video.estimate_cost("fal-i2v", model, scenes[i].duration_s)
            if spent + c <= budget:
                chosen_ai.add(scenes[i].id)
                spent += c
    else:
        raise ValueError(f"unknown strategy {strategy}")

    per_scene = {s.id: ("fal-i2v" if s.id in chosen_ai else "kenburns") for s in scenes}
    est = round(sum(video.estimate_cost(per_scene[s.id], model, s.duration_s) for s in scenes), 4)
    return per_scene, est


def run(run_dir: Path, strategy: str = "kenburns", model: str = "kling",
        ai_scene_ids: set[int] | None = None, max_cost: float | None = None,
        force: bool = False) -> GenResult:
    script = Script.model_validate_json(paths.script_json(run_dir).read_text())
    canvas.set_from_aspect(script.aspect)
    paths.clips_dir(run_dir).mkdir(parents=True, exist_ok=True)

    # per-scene clip durations from narration (if the narrate stage ran), else the
    # script's planned timings. This is what keeps clips synced to the voiceover.
    timing: dict[str, float] = {}
    if paths.timing_json(run_dir).exists():
        timing = json.loads(paths.timing_json(run_dir).read_text())

    def clip_seconds(s: Scene) -> float:
        return float(timing.get(str(s.id), s.duration_s))

    per_scene, estimate = plan(script, strategy, model, ai_scene_ids, max_cost)
    ai_n = sum(1 for p in per_scene.values() if p == "fal-i2v")

    # PRE-FLIGHT: auto already trims to fit; all/hybrid must refuse if over budget.
    if max_cost is not None and estimate > max_cost + 1e-6:
        raise BudgetError(
            f"clips estimate ${estimate} ({ai_n} AI scenes, {strategy}/{model}) exceeds "
            f"--max-cost ${max_cost}. Use --video-strategy auto, fewer --ai-scenes, a "
            f"cheaper --video-model (ltx/wan), --tier cheap, or lower --duration."
        )

    total_cost, total_latency, n = 0.0, 0.0, 0
    for scene in script.scenes:
        dst = paths.scene_clip(run_dir, scene.id)
        if dst.exists() and not force:
            continue
        img = paths.scene_image(run_dir, scene.id)
        if not img.exists():
            raise FileNotFoundError(f"missing image for scene {scene.id}; run visuals first")
        prov = per_scene[scene.id]
        secs = clip_seconds(scene)
        next_cost = video.estimate_cost(prov, model, secs)
        if max_cost is not None and total_cost + next_cost > max_cost + 1e-6:
            raise BudgetError(
                f"stopping at scene {scene.id}: spent ${round(total_cost, 4)}, next clip "
                f"${next_cost} would exceed --max-cost ${max_cost}."
            )
        raw = dst.with_name(dst.stem + "_raw.mp4")
        if prov == "fal-i2v":
            res = video.generate(prov, img, scene.motion_hint or scene.visual_prompt,
                                 secs, raw, model=model)
        else:
            # free scene: use the scene's chosen animator (default kenburns).
            # hand it the scene's narration audio (if narrate ran) for talkinghead lip-sync.
            sa = paths.scene_audio(run_dir, scene.id)
            note = animate.render(scene.animator or "kenburns", scene, img, raw, secs,
                                  audio=sa if sa.exists() else None)
            res = GenResult(path=raw, cost_usd=0.0, provider=scene.animator or "kenburns",
                            note=note)
        # fit each clip to its exact narration-driven length (hold/trim last frame).
        ffmpeg.normalize(raw, dst, target_dur=secs)
        raw.unlink(missing_ok=True)
        total_cost += res.cost_usd
        total_latency += res.latency_s
        n += 1
    return GenResult(path=paths.clips_dir(run_dir), cost_usd=round(total_cost, 4),
                     latency_s=round(total_latency, 2), provider=f"{strategy}:{model}",
                     note=f"{n} clips ({ai_n} AI via {model}), est ${estimate}")
