"""
cadence_30s.py — 30s rolling cadence. Phase 2: реальный rolling из garmin_tools/latest_analyse.py.
"""
from __future__ import annotations

from typing import Any
from .registry import register
from ._garmin_tools import analyse_fit_local, garmin_tools_available


@register("cadence_30s")
def compute(fit: dict) -> dict[str, Any]:
    fit_path = fit.get("_source_path")
    if fit_path and garmin_tools_available():
        analysed = analyse_fit_local(fit_path)
        if analysed and "cadence_30s_avg" in analysed:
            return {
                "value": analysed["cadence_30s_avg"],
                "unit": "spm",
                "target": "84-86 (cadence.md)",
                "deviation": round(analysed["cadence_30s_avg"] - 85, 1),
                "confidence": 0.85,
                "notes": "via garmin_tools/latest_analyse.py (30s rolling)",
            }

    cadence = fit.get("cadence_avg", 0)
    return {
        "value": cadence,
        "unit": "spm",
        "target": "84-86 (cadence.md)",
        "deviation": round(cadence - 85, 1) if cadence else None,
        "confidence": 0.5,
        "notes": "avg only (Phase 2: rolling через garmin_tools когда FIT на диске)",
    }
