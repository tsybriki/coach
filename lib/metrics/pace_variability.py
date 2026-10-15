"""
pace_variability.py — std/mean темпа по сплитам.
Phase 2: считаем из parse_fit.py выхода (splits[].pace_min_per_km).
"""
from __future__ import annotations

import statistics
from typing import Any
from .registry import register


@register("pace_variability")
def compute(fit: dict) -> dict[str, Any]:
    splits = fit.get("splits", [])
    paces = [s.get("pace_min_per_km", 0) for s in splits if s.get("pace_min_per_km", 0) > 0]
    if not paces or len(paces) < 2:
        return {
            "value": 0.0,
            "unit": "std/mean %",
            "target": "< 5%",
            "deviation": None,
            "confidence": 0.0,
            "notes": "недостаточно сплитов для расчёта",
        }

    mean_pace = statistics.mean(paces)
    std_pace = statistics.stdev(paces)
    cv_pct = round((std_pace / mean_pace) * 100, 1) if mean_pace else 0.0

    return {
        "value": cv_pct,
        "unit": "std/mean %",
        "target": "< 5%",
        "deviation": round(cv_pct - 5.0, 1),
        "confidence": 0.9 if len(paces) >= 4 else 0.6,
        "notes": f"рассчитано из {len(paces)} сплитов через statistics.stdev",
        "splits_used": len(paces),
        "mean_pace": round(mean_pace, 2),
        "std_pace": round(std_pace, 2),
    }
