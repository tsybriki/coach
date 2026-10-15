"""
fatigue_score.py — композит: HR drift + cadence drop + темп + дистанция vs plan.
Phase 2: считаем из parse_fit.py полей (splits + session data).
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("fatigue_score")
def compute(fit: dict) -> dict[str, Any]:
    score = 0.0
    notes = []

    # 1. HR drift (есть в parse_fit)
    drift = abs(fit.get("hr_drift_bpm", 0))
    if drift > 0:
        score += drift * 10
        notes.append(f"HR drift={drift}bpm (+{drift*10})")

    # 2. Cadence drop в сплитах (последний vs первый)
    splits = fit.get("splits", [])
    if len(splits) >= 2:
        first_cad = splits[0].get("cadence", 0)
        last_cad = splits[-1].get("cadence", 0)
        if first_cad > 0 and last_cad > 0:
            cad_delta = first_cad - last_cad
            if cad_delta > 0:
                score += cad_delta * 3
                notes.append(f"cadence drop={cad_delta}spm (+{cad_delta*3})")

    # 3. Distance относительно typical easy (~7-10К)
    distance = fit.get("distance_km", 0)
    if distance > 15:
        score += 20
        notes.append("long run >15K (+20)")
    elif distance > 12:
        score += 10
        notes.append("long run >12K (+10)")

    score = min(100, score)
    return {
        "value": round(score, 1),
        "unit": "0..100",
        "target": "< 60",
        "deviation": round(score - 60, 1),
        "confidence": 0.6 if len(notes) >= 2 else 0.3,
        "notes": "; ".join(notes) if notes else "insufficient data",
        "components": notes,
    }
