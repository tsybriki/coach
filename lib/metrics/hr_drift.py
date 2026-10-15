"""
hr_drift.py — HR drift на длинной. Phase 2: использует garmin_tools/latest_analyse.py для реального расчёта.
"""
from __future__ import annotations

from typing import Any
from .registry import register
from ._garmin_tools import analyse_fit_local, garmin_tools_available


@register("hr_drift")
def compute(fit: dict) -> dict[str, Any]:
    # Если FIT на диске и garmin_tools доступен — запрашиваем реальный анализ
    fit_path = fit.get("_source_path")
    if fit_path and garmin_tools_available():
        analysed = analyse_fit_local(fit_path)
        if analysed and "hr_drift_bpm" in analysed:
            return {
                "value": analysed["hr_drift_bpm"],
                "unit": "bpm",
                "target": "< 5",
                "deviation": None,
                "confidence": 0.9,
                "notes": "via garmin_tools/latest_analyse.py",
            }

    # Fallback: читаем из parse_fit.py вывода
    drift = fit.get("hr_drift_bpm", 0.0)
    return {
        "value": round(drift, 2),
        "unit": "bpm",
        "target": "< 5",
        "deviation": None,
        "confidence": 0.6 if fit.get("type") == "running" else 0.4,
        "notes": "from parse_fit.py (garmin_tools недоступен или FIT не на диске)",
    }
