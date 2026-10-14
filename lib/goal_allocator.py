"""
goal_allocator.py — распределение объёма между целями.
Возвращает candidates[] с явным trade-off. НЕ выбирает за Кирилла.

Phase 1: скелет. Phase 2: реальная оптимизация по adaptation_rates.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def candidates(season_plan_path: str | Path = "state/season_plan.json",
               constraints_path: str | Path = "state/constraints.json",
               athlete_path: str | Path = "state/athlete.json") -> list[dict[str, Any]]:
    sp = json.loads(Path(season_plan_path).read_text(encoding="utf-8"))
    cn = json.loads(Path(constraints_path).read_text(encoding="utf-8"))
    at = json.loads(Path(athlete_path).read_text(encoding="utf-8"))

    goals = sp.get("goals", [])
    adaptation_rates = at.get("adaptation_rates", {"run": 1.0, "bike": 0.7, "swim": 0.55})

    # Phase 1: возвращает 2 заглушечных кандидата
    cands = []
    if len(goals) >= 2:
        primary = next((g for g in goals if g.get("primary")), goals[0])
        others = [g for g in goals if g["id"] != primary["id"]]
        cands.append({
            "id": "A",
            "strategy": "primary_priority",
            "split": {primary["id"]: 0.7, others[0]["id"]: 0.3},
            "trade_off": f"Phase 1 stub: 70% {primary['discipline']} / 30% {others[0]['discipline']}. Phase 2 покажет реальный trade-off по метрикам.",
        })
        cands.append({
            "id": "B",
            "strategy": "balanced_50_50",
            "split": {primary["id"]: 0.5, others[0]["id"]: 0.5},
            "trade_off": f"Phase 1 stub: 50/50. Риск для обеих целей.",
        })
    else:
        cands.append({
            "id": "A",
            "strategy": "single_goal",
            "split": {goals[0]["id"]: 1.0} if goals else {},
            "trade_off": "Phase 1 stub: один goal — распределять нечего.",
        })

    return cands


def normalize_hours(raw_hours_by_discipline: dict[str, float],
                    adaptation_rates: dict[str, float]) -> dict[str, float]:
    """raw hours → effective_cost hours через adaptation_rates."""
    return {
        disc: round(hrs * adaptation_rates.get(disc, 1.0), 2)
        for disc, hrs in raw_hours_by_discipline.items()
    }