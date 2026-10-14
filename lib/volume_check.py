"""
volume_check.py — phase_target vs constraints → STOP/OK + suggestion.
"""
from __future__ import annotations

from typing import Any


def check_volume(phase: dict[str, Any] | None,
                 constraints: dict[str, Any]) -> dict[str, Any]:
    """
    Phase 1: считает available_hours по weekly_windows, сравнивает с phase_target.
    """
    if not phase:
        return {"ok": True, "reason": "no phase"}

    target = phase.get("hours_per_week_target", 0)
    weekly_windows = constraints.get("weekly_windows", {})
    available_min = sum(
        w.get("duration_min", 0)
        for day_windows in weekly_windows.values()
        for w in day_windows
    )
    available_h = round(available_min / 60.0, 2)

    max_total = constraints.get("max_total_hours_per_week", 24)
    min_total = constraints.get("min_total_hours_per_week", 1)

    ok = (min_total <= available_h <= max_total) and (target <= max_total)
    gap = round(target - available_h, 2)

    suggestion = None
    if gap > 0:
        suggestion = (
            f"target={target}h, available={available_h}h. "
            f"gap={gap}h. Рассмотри: расширить constraints (добавить окно) ИЛИ сдвинуть фазу ИЛИ replan сезона."
        )

    return {
        "ok": ok,
        "target_h": target,
        "available_h": available_h,
        "gap_h": gap,
        "max_h": max_total,
        "min_h": min_total,
        "suggestion": suggestion,
    }