"""
training_effect.py — TE aerobic/anaerobic из FIT.
Phase 1: читаем из training_effect.
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("training_effect")
def compute(fit: dict) -> dict[str, Any]:
    te = fit.get("training_effect", {})
    return {
        "value": te.get("aerobic_te", 0.0),
        "unit": "TE",
        "target": "2.0-3.0 (recovery/tempo), 3.0-4.0 (build), 4.0-5.0 (specific)",
        "deviation": None,
        "confidence": 0.95,
        "label": te.get("label", "UNKNOWN"),
        "anaerobic": te.get("anaerobic_te", 0.0),
        "notes": "Phase 1: читаем напрямую.",
    }