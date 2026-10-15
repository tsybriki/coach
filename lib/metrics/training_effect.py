"""
training_effect.py — TE aerobic/anaerobic + Riegel race prediction.
Phase 2: garmin_tools/latest_analyse.py содержит Riegel.
"""
from __future__ import annotations

from typing import Any
from .registry import register
from ._garmin_tools import analyse_fit_local, garmin_tools_available


@register("training_effect")
def compute(fit: dict) -> dict[str, Any]:
    fit_path = fit.get("_source_path")
    if fit_path and garmin_tools_available():
        analysed = analyse_fit_local(fit_path)
        if analysed and "training_effect" in analysed:
            riegel = analysed.get("riegeL_predictions", {})
            return {
                "value": analysed["training_effect"].get("aerobic_te", 0.0),
                "unit": "TE",
                "target": "2.0-3.0 (recovery/tempo), 3.0-4.0 (build), 4.0-5.0 (specific)",
                "deviation": None,
                "confidence": 0.95,
                "label": analysed["training_effect"].get("label", "UNKNOWN"),
                "anaerobic": analysed["training_effect"].get("anaerobic_te", 0.0),
                "riegel_5k_sec": riegel.get("5k"),
                "riegel_10k_sec": riegel.get("10k"),
                "notes": "via garmin_tools/latest_analyse.py",
            }

    te_data = fit.get("training_effect", {})
    return {
        "value": te_data.get("aerobic_te", 0.0),
        "unit": "TE",
        "target": "2.0-3.0 (recovery/tempo), 3.0-4.0 (build), 4.0-5.0 (specific)",
        "deviation": None,
        "confidence": 0.95,
        "label": te_data.get("label", "UNKNOWN"),
        "anaerobic": te_data.get("anaerobic_te", 0.0),
        "notes": "from parse_fit.py (без Riegel)",
    }
