"""
transition_efficiency.py — скорость трансфера T1/T2 в триатлоне.
Phase 1: stub.
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("transition_efficiency")
def compute(fit: dict) -> dict[str, Any]:
    return {
        "value": 0.0,
        "unit": "sec",
        "target": "T1<60s, T2<45s",
        "deviation": None,
        "confidence": 0.0,
        "notes": "Phase 1 stub. Phase 2: реальный расчёт из brick-сессий.",
    }