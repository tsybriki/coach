"""
plan_generate.py — season_plan + athlete + constraints + overrides → plan-wN.json.
Phase 2: скелет + inline Zwift-поиск для bike/brick-слотов.

INLINE ZWIFT (v16):
  - plan_generate проверяет constraints.auto_zwift для каждого размещённого bike/brick-слота.
  - Если слот удовлетворяет правилу (≤ 90 мин, home_stationary_bike, focus) — вызывает
    coach-plan-zwift.inline_search(criteria) → candidates[] (2-4).
  - Кирилл голосует по каждому slot одним списком (или 'skip' = оставить без workout_ref).
  - Для выбранных: zwift_sync.sync_to_garmin(url) → workout_ref в slot.
  - Это ОДИН этап, не два (ранее был двухшаговый: plan_generate → отдельно zwift_search).
  - Phase 3: проходит. Inline логика для автономного выполнения, без интерактива.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .volume_check import check_volume


def generate(week_iso: str,
             season_plan_path: str | Path = "state/season_plan.json",
             athlete_path: str | Path = "state/athlete.json",
             constraints_path: str | Path = "state/constraints.json",
             overrides_path: str | Path = "state/overrides.json") -> dict[str, Any]:
    """
    Phase 1: возвращает структуру plan-wN, заполненную дефолтами.
    Phase 2: реальная генерация — phase, hours_target, control_point_slots, override merge.
    """
    sp = json.loads(Path(season_plan_path).read_text(encoding="utf-8"))
    at = json.loads(Path(athlete_path).read_text(encoding="utf-8"))
    cn = json.loads(Path(constraints_path).read_text(encoding="utf-8"))
    ov = json.loads(Path(overrides_path).read_text(encoding="utf-8")) if Path(overrides_path).exists() else {"overrides": []}

    today = datetime.now(timezone.utc).date().isoformat()
    current_phase = None
    for ph in sp.get("phases", []):
        if ph["start"] <= today <= ph.get("end", ph["start"]):
            current_phase = ph
            break

    cp_in_range = [
        cp for cp in sp.get("control_points", [])
        if cp.get("date", "")[:7] == week_iso[:7]  # упрощённо — по месяцу
    ]

    vc = check_volume(current_phase, cn) if current_phase else {"ok": True}

    return {
        "$schema": "./plan.schema.md",
        "version": 1,
        "title": f"{week_iso} · Берлин",
        "weekIso": week_iso,
        "phase": current_phase,
        "chosen_allocation": sp.get("chosen_allocation"),
        "rules": {
            "hr_zones": at.get("hr_zones"),
            "metric_split": {
                "by_hr_first": "easy, Z2, Z2-low, long, recovery, warmup, cooldown",
                "by_pace_first": "intervals, progression, tempo, race-pace",
            },
        },
        "slots": [],
        "control_points_in_range": [cp["id"] for cp in cp_in_range],
        "overrides_applied": [],
        "volume_check": vc,
        "_generated_by": "lib.plan_generate (Phase 1 stub)",
    }