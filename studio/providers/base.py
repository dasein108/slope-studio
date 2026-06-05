"""Common result type for media-producing providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class GenResult:
    path: Path | None = None
    cost_usd: float = 0.0
    latency_s: float = 0.0
    provider: str = ""
    note: str = ""
