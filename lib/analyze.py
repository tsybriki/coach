"""
analyze.py — analyze(fit_id, mode, context).
mode ∈ {quick, contextual, coaching, lookback}.

Phase 1: скелет с правильной структурой вывода и валидацией mode.
Реальная сборка prompt + вызов модели — в ask_model.py (Phase 2).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

Mode = Literal["quick", "contextual", "coaching", "lookback"]


def analyze(fit_id: str | None,
            mode: Mode,
            context: dict[str, Any] | None = None,
            corpus_root: str | Path = "lib/coaching_corpus") -> dict[str, Any]:
    """
    Phase 1: возвращает dict по структуре, без реального вызова модели.

    Структура зависит от mode:
    - quick: {fit_id, mode, metrics: {<metric_id>: value}}
    - contextual: {..., context: {prev_fits, plan_day, overrides}}
    - coaching: {..., interpretation: {observation, hypothesis, cited_principle, suggested_action, confidence}}
    - lookback: {..., trends: [...], cp_filter: {...}}
    """
    if mode not in ("quick", "contextual", "coaching", "lookback"):
        raise ValueError(f"invalid mode: {mode}")

    context = context or {}
    base = {
        "fit_id": fit_id,
        "mode": mode,
        "schema_version": "0.1.0",
    }

    if mode == "quick":
        base["metrics"] = {}  # Phase 2: registry.call(metric_id, fit_dict)
    elif mode == "contextual":
        base["context"] = {
            "prev_fits_count": 0,
            "plan_day_summary": None,
            "overrides_active": [],
        }
        base["metrics"] = {}
    elif mode == "coaching":
        base["interpretation"] = {
            "observation": None,        # Phase 2: ask_model с cited_principle required
            "hypothesis": None,
            "cited_principle": None,    # MUST be from corpus if not None
            "suggested_action": None,
            "confidence": None,
        }
        base["metrics"] = {}
        base["context"] = {"prev_fits_count": 0}
    elif mode == "lookback":
        base["trends"] = []
        base["cp_filter"] = context.get("cp_filter", {})

    # Audit
    return base