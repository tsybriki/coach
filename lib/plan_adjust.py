"""
plan_adjust.py — «сегодня перегруз» → diff JSON на остаток недели.

Phase 1: скелет.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def adjust(week_iso: str,
           trigger: str,
           plan_path: str | Path = "state/season_plan.json",
           progress_path: str | Path = "state/season_progress.json") -> dict[str, Any]:
    """
    trigger: 'overload_today' | 'missed_session' | 'illness_short' | ...

    Phase 1: возвращает пустой diff с пометкой. Phase 2: реальная логика
    (найти оставшиеся слоты недели, перераспределить объём, согласовать с CP).
    """
    return {
        "week_iso": week_iso,
        "trigger": trigger,
        "diff_slots": [],
        "rationale": "Phase 1 stub. Phase 2 будет реально перераспределять слоты.",
        "schema_version": "0.1.0",
    }