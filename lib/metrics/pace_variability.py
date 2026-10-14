"""
pace_variability.py — std/mean темпа по 1К-окнам.
Phase 1: stub.
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("pace_variability")
def compute(fit: dict) -> dict[str, Any]:
    return {
        "value": 0.0,
        "unit": "std/mean %",
        "target": "< 5%",
        "deviation": None,
        "confidence": 0.0,
        "notes": "Phase 1 stub. Phase 2: реальный расчёт по splits.",
    }