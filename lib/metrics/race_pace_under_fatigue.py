"""
race_pace_under_fatigue.py — темп 10К после велосипеда. Ключевая метрика triathlon.
Phase 1: stub.
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("race_pace_under_fatigue")
def compute(fit: dict) -> dict[str, Any]:
    return {
        "value": 0.0,
        "unit": "min/km",
        "target": "4:25 ±10с",
        "deviation": None,
        "confidence": 0.0,
        "notes": "Phase 1 stub. Phase 2: расчёт из brick-сессий.",
    }