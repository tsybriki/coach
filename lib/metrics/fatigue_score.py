"""
fatigue_score.py — композит: HR drift + recovery drop + TE + отклонение от плана.
Phase 1: stub. Phase 2: реальная формула.
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("fatigue_score")
def compute(fit: dict) -> dict[str, Any]:
    return {
        "value": 0.0,
        "unit": "0..100",
        "target": "< 60",
        "deviation": None,
        "confidence": 0.0,
        "notes": "Phase 1 stub. Phase 2: hr_drift + recovery_hr_drop + TE + plan_deviation.",
    }