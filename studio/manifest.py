"""project.json — the run manifest. Tracks config, per-stage results, cost."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class StageRecord(BaseModel):
    done: bool = False
    provider: str = ""
    cost_usd: float = 0.0
    latency_s: float = 0.0
    n: int = 0
    note: str = ""


class Manifest(BaseModel):
    id: str
    idea: str
    duration_s: int = 150
    aspect: str = "9:16"
    voice: bool = True
    style: str = ""
    tier: str = "balanced"
    stages: dict[str, StageRecord] = Field(default_factory=dict)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(s.cost_usd for s in self.stages.values()), 4)

    def record(self, stage: str, **kw) -> None:
        self.stages[stage] = StageRecord(**kw)

    def is_done(self, stage: str) -> bool:
        return stage in self.stages and self.stages[stage].done


def manifest_path(run_dir: Path) -> Path:
    return run_dir / "project.json"


def load(run_dir: Path) -> Manifest:
    p = manifest_path(run_dir)
    if not p.exists():
        raise FileNotFoundError(f"no manifest at {p} — run `studio init` first")
    return Manifest.model_validate_json(p.read_text())


def save(run_dir: Path, m: Manifest) -> None:
    manifest_path(run_dir).write_text(m.model_dump_json(indent=2))
