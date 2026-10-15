"""
weekly_report.py — athlete + 3 FIT + метрики → сводка недели.
Phase 1: скелет с реальной структурой вывода.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .metrics import registry


def _this_week_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-W%V")


def report(season_week: int | str | None = None,
           athlete_path: str | Path = "state/athlete.json",
           season_plan_path: str | Path = "state/season_plan.json",
           progress_path: str | Path = "state/season_progress.json",
           constraints_path: str | Path = "state/constraints.json",
           fits_dir: str | Path = "state/fit_store") -> dict[str, Any]:
    if season_week is None:
        # По умолчанию — текущая season_week (W_N где сегодня)
        from datetime import date
        from .season_week import date_to_season_week
        sp = json.loads(Path(season_plan_path).read_text(encoding="utf-8"))
        season_start = sp.get("season_start_date", "2026-10-12")
        season_week = date_to_season_week(date.today().isoformat(), season_start)

    athlete = json.loads(Path(athlete_path).read_text(encoding="utf-8"))
    season_plan = json.loads(Path(season_plan_path).read_text(encoding="utf-8"))
    progress = json.loads(Path(progress_path).read_text(encoding="utf-8"))
    constraints = json.loads(Path(constraints_path).read_text(encoding="utf-8"))

    week_key = f"W{season_week}" if isinstance(season_week, int) else str(season_week)

    # Текущая фаза
    today = datetime.now(timezone.utc).date().isoformat()
    current_phase = None
    for ph in season_plan.get("phases", []):
        if ph["start"] <= today <= ph.get("end", ph["start"]):
            current_phase = ph
            break

    # Метрики из последних 3 FIT
    fits = sorted(progress.get("weeks", {}).get(week_key, {}).get("fits_analysed", []),
                  key=lambda x: x.get("date", ""))
    last3 = fits[-3:]
    metrics_summary = {}
    for m_id in registry.list_active():
        try:
            metrics_summary[m_id] = [registry.call(m_id, f) for f in last3]
        except Exception as e:
            metrics_summary[m_id] = {"error": str(e)}

    # Вес (1 строка)
    weight_line = None
    hist = athlete.get("weight_history", [])
    if hist:
        latest = hist[-1]
        prev_7d = next((h for h in reversed(hist[:-1]) if latest["date"] >= h["date"]), None) if len(hist) > 1 else None
        # Простой delta за 7д
        delta = None
        if len(hist) >= 2:
            last_kg = hist[-1]["kg"]
            week_ago_idx = max(0, len(hist) - 8)
            delta = round(last_kg - hist[week_ago_idx]["kg"], 2)
        weight_line = f"Вес: {latest['kg']} кг (Δ {delta:+} за 7д)" if delta is not None else f"Вес: {latest['kg']} кг"

    return {
        "season_week": season_week,
        "week_key": week_key,
        "preamble": {
            "goals": athlete.get("goals", []),
            "current_form": athlete.get("current_form", {}),
            "form_trend_4w": athlete.get("form_trend_4w"),
            "hr_zones": athlete.get("hr_zones"),
            "schedule": _week_schedule_summary(constraints),
        },
        "current_phase": current_phase,
        "fits_count": len(fits),
        "metrics_summary": metrics_summary,
        "weight_line": weight_line,
        "notes": "Phase 1: скелет. Реальные метрики появятся с реальными FIT'ами.",
    }


def _week_schedule_summary(constraints: dict) -> dict:
    weekly = constraints.get("weekly_windows", {})
    return {
        day: [
            {"start": w.get("start"), "end": w.get("end"), "duration_min": w.get("duration_min")}
            for w in wins
        ]
        for day, wins in weekly.items()
    }