"""
cadence_30s.py — 30s rolling cadence по сплитам. Цель 84→86.
Phase 1: читаем cadence_avg. Phase 2: реальный rolling по сплитам.
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("cadence_30s")
def compute(fit: dict) -> dict[str, Any]:
    cadence = fit.get("cadence_avg", 0)
    return {
        "value": cadence,
        "unit": "spm",
        "target": "84-86 (cadence.md)",
        "deviation": round(cadence - 85, 1) if cadence else None,
        "confidence": 0.6,
        "notes": "Phase 1: avg. Phase 2: 30s rolling по сплитам.",
    }