"""Marketing analytics helpers for age-bucket snapshots and feature slicing."""

from __future__ import annotations

import csv
import io
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from studio.marketing import journal as mj
from studio.marketing import score

DEFAULT_BUCKETS = (1, 3, 7, 14, 30)


def bucket_name(days: int) -> str:
    return f"{days}d"


def parse_buckets(spec: str = "") -> list[int]:
    if not spec:
        return list(DEFAULT_BUCKETS)
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip().lower().removesuffix("d")
        if part:
            out.append(int(part))
    return sorted(set(out))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def age_days(e: mj.Entry) -> float:
    if e.metrics and e.metrics.age_days:
        return e.metrics.age_days
    if not e.published_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(e.published_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - dt).total_seconds() / 86400.0, 2)
    except ValueError:
        return 0.0


def cost_per_view(e: mj.Entry, m: mj.Metrics | None) -> float:
    if not m or m.views <= 0:
        return 0.0
    return round(e.cost_usd / m.views, 6)


def virality_per_dollar(e: mj.Entry, m: mj.Metrics | None, virality: float | None = None) -> float:
    if not e.cost_usd:
        return 0.0
    v = virality if virality is not None else (score.virality(m) if m else e.virality)
    return round((v or 0.0) / e.cost_usd, 4)


def snapshot_for_bucket(e: mj.Entry, bucket: str) -> mj.MetricSnapshot | None:
    return next((s for s in e.snapshots if s.bucket == bucket), None)


def metric_at(e: mj.Entry, bucket: str = "latest") -> tuple[mj.Metrics | None, float | None]:
    if bucket and bucket != "latest":
        s = snapshot_for_bucket(e, bucket)
        return s, score.virality(s) if s else None
    return e.metrics, e.virality


def due_entries(j: mj.Journal, buckets: Iterable[int] = DEFAULT_BUCKETS) -> list[dict]:
    due: list[dict] = []
    for e in j.entries:
        if not e.video_id or e.status not in ("deployed", "measured"):
            continue
        age = age_days(e)
        missing = [
            bucket_name(b) for b in buckets
            if age >= b and snapshot_for_bucket(e, bucket_name(b)) is None
        ]
        if missing:
            due.append({"id": e.id, "video_id": e.video_id, "age_days": age, "due": missing})
    return due


def buckets_to_write(e: mj.Entry, age_days: float, buckets: Iterable[int]) -> list[str]:
    return [
        bucket_name(b) for b in buckets
        if age_days >= b and snapshot_for_bucket(e, bucket_name(b)) is None
    ]


def upsert_snapshot(e: mj.Entry, bucket: str, m: mj.MetricSnapshot) -> None:
    e.snapshots = [s for s in e.snapshots if s.bucket != bucket]
    e.snapshots.append(m)
    e.snapshots.sort(key=lambda s: parse_buckets(s.bucket)[0] if s.bucket else 0)


def entry_features(e: mj.Entry, key: str) -> list[str]:
    if key == "theme":
        return [e.theme or "(none)"]
    if key == "tags":
        return e.tags or ["(none)"]
    if key == "effects":
        return e.effects or ["(none)"]
    if key == "animators":
        return e.animators or ["(none)"]
    if key == "music_provider":
        return [e.music_provider or e.providers.get("audio", "").split("+")[-1] or "(none)"]
    if key == "sfx_provider":
        return [e.sfx_provider or e.providers.get("audio", "").split("+")[0] or "(none)"]
    if key == "video_model":
        return [e.video_model or "(none)"]
    if key == "tier":
        return [e.tier or "(none)"]
    if key == "voice_provider":
        return [e.voice_provider or e.providers.get("voice", "") or "(none)"]
    if key == "tone":
        return [e.tone or "(none)"]
    if key == "transitions":
        return e.transitions or ["(none)"]
    if key.startswith("provider."):
        return [e.providers.get(key.split(".", 1)[1], "(none)") or "(none)"]
    val = getattr(e, key, "")
    if isinstance(val, list):
        return [str(v) for v in val] or ["(none)"]
    return [str(val or "(none)")]


def metric_value(e: mj.Entry, metric: str, bucket: str = "latest") -> float | None:
    m, virality = metric_at(e, bucket)
    if metric == "cost_usd":
        return e.cost_usd or None
    if metric == "cost_per_minute":
        return e.cost_per_minute or None
    if metric == "cost_per_view":
        return cost_per_view(e, m) or None
    if metric == "virality_per_dollar":
        return virality_per_dollar(e, m, virality) or None
    if metric == "virality":
        return virality
    if not m:
        return None
    val = getattr(m, metric, None)
    return float(val) if val is not None else None


@dataclass
class SliceRow:
    group: str
    n: int
    mean: float
    median: float
    win_rate: float
    cost_per_view: float
    virality_per_dollar: float
    best: list[str]
    worst: list[str]


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 4) if values else 0.0


def _median(values: list[float]) -> float:
    return round(statistics.median(values), 4) if values else 0.0


def slice_entries(
    entries: list[mj.Entry],
    group_by: list[str],
    metric: str = "virality",
    bucket: str = "latest",
) -> list[SliceRow]:
    groups: dict[str, list[tuple[mj.Entry, float]]] = {}
    for e in entries:
        value = metric_value(e, metric, bucket)
        if value is None:
            continue
        keys = [";".join(entry_features(e, g)) for g in group_by]
        group = " | ".join(f"{g}={v}" for g, v in zip(group_by, keys))
        groups.setdefault(group, []).append((e, value))

    rows: list[SliceRow] = []
    for group, pairs in groups.items():
        values = [v for _, v in pairs]
        ranked = sorted(pairs, key=lambda p: p[1], reverse=True)
        wins = sum(1 for e, _ in pairs if e.outcome == "win")
        cpv = [cost_per_view(e, metric_at(e, bucket)[0]) for e, _ in pairs]
        vpd = [virality_per_dollar(e, metric_at(e, bucket)[0], metric_at(e, bucket)[1]) for e, _ in pairs]
        rows.append(SliceRow(
            group=group,
            n=len(pairs),
            mean=_mean(values),
            median=_median(values),
            win_rate=round(wins / len(pairs), 3) if pairs else 0.0,
            cost_per_view=_median([v for v in cpv if v]),
            virality_per_dollar=_median([v for v in vpd if v]),
            best=[e.id for e, _ in ranked[:3]],
            worst=[e.id for e, _ in ranked[-3:]],
        ))
    return sorted(rows, key=lambda r: (r.median, r.mean, r.n), reverse=True)


def _matches(e: mj.Entry, spec: str) -> bool:
    op = "!=" if "!=" in spec else "="
    key, value = [p.strip() for p in spec.split(op, 1)]
    values = entry_features(e, key)
    matched = value in values
    return not matched if op == "!=" else matched


def compare_entries(entries: list[mj.Entry], feature: str, bucket: str, metric: str) -> dict:
    yes = [e for e in entries if _matches(e, feature)]
    no = [e for e in entries if not _matches(e, feature)]
    yes_vals = [v for e in yes if (v := metric_value(e, metric, bucket)) is not None]
    no_vals = [v for e in no if (v := metric_value(e, metric, bucket)) is not None]
    yes_med = _median(yes_vals)
    no_med = _median(no_vals)
    lift = round((yes_med - no_med) / no_med, 4) if no_med else 0.0
    return {
        "feature": feature,
        "bucket": bucket,
        "metric": metric,
        "with": {"n": len(yes_vals), "median": yes_med, "mean": _mean(yes_vals), "examples": [e.id for e in yes[:5]]},
        "without": {"n": len(no_vals), "median": no_med, "mean": _mean(no_vals), "examples": [e.id for e in no[:5]]},
        "median_lift": lift,
        "confidence": "low" if min(len(yes_vals), len(no_vals)) < 5 else "directional",
    }


def insights(j: mj.Journal) -> dict:
    measured = [e for e in j.entries if e.metrics or e.snapshots]
    buckets = ["1d", "3d", "7d", "14d", "30d", "latest"]
    groups = ["theme", "effects", "animators", "music_provider", "sfx_provider", "video_model", "tier"]
    out: dict = {
        "channel": j.channel or "default",
        "phase": "cold-start" if j.in_cold_start else "optimizing",
        "deployed_count": j.deployed_count,
        "snapshot_coverage": {},
        "top": {},
        "cost_efficiency": {},
        "warnings": [],
    }
    for b in buckets:
        out["snapshot_coverage"][b] = sum(1 for e in j.entries if metric_at(e, b)[0])
    if j.deployed_count < j.bootstrap_target:
        out["warnings"].append(f"cold-start: {j.deployed_count}/{j.bootstrap_target} deployed; treat rankings as exploratory")
    for b in buckets:
        if out["snapshot_coverage"][b] < 3:
            continue
        out["top"][b] = {}
        for g in groups:
            rows = [r for r in slice_entries(measured, [g], "virality", b) if r.n >= 2]
            out["top"][b][g] = [r.__dict__ for r in rows[:5]]
        out["cost_efficiency"][b] = [
            r.__dict__ for r in slice_entries(measured, ["theme"], "virality_per_dollar", b)[:5]
        ]
    if not any(out["top"].values()):
        out["warnings"].append("not enough bucketed measurements yet for stable slices")
    return out


def export_rows(j: mj.Journal, include_scenes: bool = False) -> list[dict]:
    rows: list[dict] = []
    for e in j.entries:
        base = {
            "id": e.id,
            "status": e.status,
            "idea": e.idea,
            "theme": e.theme,
            "tags": ",".join(e.tags),
            "run_id": e.run_id,
            "video_id": e.video_id,
            "published_at": e.published_at,
            "cost_usd": e.cost_usd,
            "cost_per_minute": e.cost_per_minute,
            "duration_s": e.duration_s,
            "tier": e.tier,
            "video_model": e.video_model,
            "animators": ",".join(e.animators),
            "effects": ",".join(e.effects),
            "music_provider": e.music_provider,
            "sfx_provider": e.sfx_provider,
            "sfx_count": e.sfx_count,
            "latest_virality": e.virality,
            "latest_percentile": e.percentile,
            "outcome": e.outcome,
        }
        snapshots = e.snapshots or ([] if not e.metrics else [mj.MetricSnapshot(bucket="latest", **e.metrics.model_dump())])
        for s in snapshots:
            row = dict(base)
            row.update({
                "bucket": s.bucket,
                "age_days": s.age_days,
                "views": s.views,
                "likes": s.likes,
                "comments": s.comments,
                "retention": s.retention,
                "subs_gained": s.subs_gained,
                "velocity": s.velocity,
                "engagement": s.engagement,
                "virality": score.virality(s),
                "fetched_at": s.fetched_at,
            })
            rows.append(row)
    return rows


def to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def to_json(data: object) -> str:
    return json.dumps(data, indent=2)
