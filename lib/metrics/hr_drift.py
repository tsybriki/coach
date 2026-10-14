"""
hr_drift.py — HR drift на длинной. (parse_fit хранит hr_drift_bpm в верхнеуровневом поле).
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("hr_drift")
def compute(fit: dict) -> dict[str, Any]:
    drift = fit.get("hr_drift_bpm", 0.0)
    return {
        "value": round(drift, 2),
        "unit": "bpm",
        "target": "< 5",          # эмпирически
        "deviation": None,
        "confidence": 0.9 if fit.get("type") == "running" else 0.4,
        "notes": "Phase 1: читаем из FIT. Phase 2: считать по сплитам.",
    }