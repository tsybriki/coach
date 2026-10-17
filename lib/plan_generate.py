"""
plan_generate.py — season_plan + athlete + constraints + overrides → plan-wN.json.
Phase 2.5: реальная раскладка phase по weekly_windows + focus + control_points + auto_zwift.
Phase 2.6: каждый slot получает structure (детальный план работы) по subkind.

INLINE ZWIFT (v16):
  - plan_generate проверяет constraints.auto_zwift для каждого размещённого bike/brick-слота.
  - Если слот удовлетворяет правилу (≤ 90 мин, home_stationary_bike, focus) — ставит
    workout_pending=True в слот. Кирилл голосует отдельной командой (Phase 3: inline-вызовы).

STRUCTURE (v19):
  - Каждый slot (run/bike/swim/brick) получает structure: list[step] с детальным планом.
  - Для by_hr трениров (лёгкие, длинные) — задаётся зонами (Z1/Z2/Z3 и т.д.).
  - Для by_pace работ (интервалы, tempo, race-pace) — задаётся темпом и reps.
  - OFP слоты получают ofp_structure: список упражнений (core circuit, mobility).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .volume_check import check_volume
from .season_week import (
    season_week_to_iso, season_week_to_dates,
    phase_for_season_week,
)
from .step_builder import build_structure, ofp_structure

DAY_ORDER = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]


def _day_for(week_start, target_date: str) -> str | None:
    """Какой день недели соответствует date. None если вне week."""
    from datetime import date, timedelta
    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        return None
    ws = week_start
    we = ws + timedelta(days=6)
    if d < ws or d > we:
        return None
    idx = (d - ws).days
    return DAY_ORDER[idx]


def _windows_by_day(constraints: dict) -> dict[str, list[dict]]:
    return constraints.get("weekly_windows", {})


def _phase_focus_runs(phase_id: str) -> dict:
    """Возвращает структуру focus для phase_id: что ставим, в какие окна, в каком приоритете.

    Phase 1 logic — base/build/specific/taper для run_10k.
    Phase 2 — добавим triathlon (transition, tri_base, tri_build, tri_specific, tri_taper).
    Phase 2.6 — добавили ofp (2×/нед core 25 мин).
    """
    focus_map = {
        "run_base": {
            "long_run": [{"day": "СР", "window_idx": 0, "duration_min": 90, "kind": "run", "subkind": "long_Z2", "focus": "Z2"}],
            "key_run": [{"day": "ПН", "window_idx": 0, "duration_min": 60, "kind": "run", "subkind": "easy_progression", "focus": "Z2"},
                        {"day": "ВТ", "window_idx": 1, "duration_min": 60, "kind": "run", "subkind": "key_intervals", "focus": "Z3"}],
            "easy_runs": [{"day": "ВТ", "window_idx": 0, "duration_min": 30, "kind": "run", "subkind": "easy", "focus": "Z2"}],
            "bike": [{"day": "ЧТ", "window_idx": 0, "duration_min": 45, "kind": "bike", "subkind": "stationary_z2", "focus": "Z2"},
                     {"day": "ВС", "window_idx": 0, "duration_min": 90, "kind": "bike", "subkind": "long_z2", "focus": "Z2"}],
            "swim": [{"day": "ПТ", "window_idx": 0, "duration_min": 60, "kind": "swim", "subkind": "easy", "focus": "Z1"}],
            "ofp": [{"day": "СБ", "window_idx": 0, "duration_min": 25, "kind": "ofp", "subkind": "core", "focus": "core"}],
        },
        "run_build": {
            "long_run": [{"day": "СР", "window_idx": 0, "duration_min": 100, "kind": "run", "subkind": "long_Z2", "focus": "Z2"}],
            "key_run": [{"day": "ПН", "window_idx": 0, "duration_min": 70, "kind": "run", "subkind": "intervals", "focus": "intervals"},
                        {"day": "ВТ", "window_idx": 1, "duration_min": 70, "kind": "run", "subkind": "tempo", "focus": "Z3"}],
            "easy_runs": [{"day": "ВТ", "window_idx": 0, "duration_min": 30, "kind": "run", "subkind": "easy", "focus": "Z2"}],
            "bike": [{"day": "ЧТ", "window_idx": 0, "duration_min": 45, "kind": "bike", "subkind": "stationary_z2", "focus": "Z2"},
                     {"day": "ВС", "window_idx": 0, "duration_min": 90, "kind": "bike", "subkind": "long_z2", "focus": "Z2"}],
            "swim": [{"day": "ПТ", "window_idx": 0, "duration_min": 60, "kind": "swim", "subkind": "easy", "focus": "Z1"}],
            "ofp": [{"day": "СБ", "window_idx": 0, "duration_min": 25, "kind": "ofp", "subkind": "core", "focus": "core"}],
        },
        "run_specific": {
            "long_run": [{"day": "СР", "window_idx": 0, "duration_min": 110, "kind": "run", "subkind": "long_Z2", "focus": "Z2"}],
            "key_run": [{"day": "ПН", "window_idx": 0, "duration_min": 75, "kind": "run", "subkind": "race_pace", "focus": "race_pace"},
                        {"day": "ВТ", "window_idx": 1, "duration_min": 75, "kind": "run", "subkind": "intervals", "focus": "Z4"}],
            "easy_runs": [{"day": "ВТ", "window_idx": 0, "duration_min": 30, "kind": "run", "subkind": "easy", "focus": "Z2"}],
            "bike": [{"day": "ЧТ", "window_idx": 0, "duration_min": 60, "kind": "bike", "subkind": "stationary_z3", "focus": "Z3"},
                     {"day": "ВС", "window_idx": 0, "duration_min": 100, "kind": "bike", "subkind": "long_z2", "focus": "Z2"}],
            "swim": [{"day": "ПТ", "window_idx": 0, "duration_min": 60, "kind": "swim", "subkind": "easy", "focus": "Z1"}],
            "ofp": [{"day": "ПН", "window_idx": 1, "duration_min": 25, "kind": "ofp", "subkind": "core", "focus": "core"},
                     {"day": "СБ", "window_idx": 0, "duration_min": 25, "kind": "ofp", "subkind": "core", "focus": "core"}],
        },
        "run_taper": {
            "long_run": [{"day": "СР", "window_idx": 0, "duration_min": 60, "kind": "run", "subkind": "easy", "focus": "Z2"}],
            "key_run": [{"day": "ПН", "window_idx": 0, "duration_min": 45, "kind": "run", "subkind": "race_pace", "focus": "race_pace"},
                        {"day": "ВТ", "window_idx": 1, "duration_min": 45, "kind": "run", "subkind": "tempo", "focus": "Z3"}],
            "easy_runs": [],
            "bike": [{"day": "ЧТ", "window_idx": 0, "duration_min": 45, "kind": "bike", "subkind": "stationary_z2", "focus": "Z2"}],
            "swim": [{"day": "ПТ", "window_idx": 0, "duration_min": 45, "kind": "swim", "subkind": "easy", "focus": "Z1"}],
            "ofp": [{"day": "СБ", "window_idx": 0, "duration_min": 25, "kind": "ofp", "subkind": "core", "focus": "core"}],
        },
        # Triathlon phases — добавлены Phase 2.5
        "tri_base": {
            "long_run": [{"day": "ВС", "window_idx": 0, "duration_min": 60, "kind": "run", "subkind": "easy_long", "focus": "Z2"}],
            "key_run": [{"day": "ВТ", "window_idx": 1, "duration_min": 45, "kind": "run", "subkind": "tempo", "focus": "Z3"}],
            "easy_runs": [{"day": "ВТ", "window_idx": 0, "duration_min": 30, "kind": "run", "subkind": "easy", "focus": "Z2"}],
            "bike": [
                {"day": "СР", "window_idx": 0, "duration_min": 60, "kind": "bike", "subkind": "stationary_z2", "focus": "Z2"},
                {"day": "ЧТ", "window_idx": 0, "duration_min": 45, "kind": "bike", "subkind": "stationary_z2", "focus": "Z2"},
                {"day": "ВС", "window_idx": 0, "duration_min": 90, "kind": "bike", "subkind": "long_z2", "focus": "Z2"},
            ],
            "swim": [{"day": "ПТ", "window_idx": 0, "duration_min": 60, "kind": "swim", "subkind": "easy", "focus": "Z1"}],
            "ofp": [{"day": "СБ", "window_idx": 0, "duration_min": 25, "kind": "ofp", "subkind": "core", "focus": "core"}],
        },
        "tri_build": {
            "long_run": [{"day": "ВС", "window_idx": 0, "duration_min": 70, "kind": "run", "subkind": "easy_long", "focus": "Z2"}],
            "key_run": [{"day": "ВТ", "window_idx": 1, "duration_min": 60, "kind": "run", "subkind": "tempo", "focus": "Z3"}],
            "easy_runs": [{"day": "ВТ", "window_idx": 0, "duration_min": 30, "kind": "run", "subkind": "easy", "focus": "Z2"}],
            "bike": [
                {"day": "СР", "window_idx": 0, "duration_min": 90, "kind": "bike", "subkind": "long_z2", "focus": "Z2"},
                {"day": "ЧТ", "window_idx": 0, "duration_min": 60, "kind": "bike", "subkind": "stationary_z3", "focus": "Z3"},
                {"day": "ВС", "window_idx": 0, "duration_min": 100, "kind": "bike", "subkind": "long_z2", "focus": "Z2"},
            ],
            "swim": [
                {"day": "ПТ", "window_idx": 0, "duration_min": 60, "kind": "swim", "subkind": "tempo", "focus": "Z3"},
            ],
            "brick": [{"day": "СБ", "window_idx": 0, "duration_min": 75, "kind": "brick", "subkind": "bike_run", "focus": "endurance"}],
            "ofp": [{"day": "СБ", "window_idx": 1, "duration_min": 25, "kind": "ofp", "subkind": "core", "focus": "core"}],
        },
        "transition": {
            "long_run": [],
            "key_run": [],
            "easy_runs": [{"day": "ВТ", "window_idx": 0, "duration_min": 30, "kind": "run", "subkind": "easy", "focus": "Z2"}],
            "bike": [
                {"day": "ЧТ", "window_idx": 0, "duration_min": 45, "kind": "bike", "subkind": "stationary_z2", "focus": "Z2"},
                {"day": "ВС", "window_idx": 0, "duration_min": 60, "kind": "bike", "subkind": "easy", "focus": "Z2"},
            ],
            "swim": [{"day": "ПТ", "window_idx": 0, "duration_min": 45, "kind": "swim", "subkind": "easy", "focus": "Z1"}],
        },
    }
    return focus_map.get(phase_id, focus_map["run_base"])


def _window_fits(window: dict, duration_min: int) -> bool:
    """Проверяет, помещается ли duration_min в окно."""
    return window.get("duration_min", 0) >= duration_min


def _auto_zwift_check(slot: dict, constraints: dict) -> bool:
    """Проверяет, удовлетворяет ли slot правилу auto_zwift (≤90мин, дома, bike/brick)."""
    az = constraints.get("auto_zwift", {})
    if not az.get("enabled", False):
        return False
    if slot["kind"] not in az.get("kinds", []):
        return False
    if slot["duration_min"] > az.get("duration_min_max", 90):
        return False
    # location берём из window slot-а (через заполнение выше)
    return True


def _layout_slots(phase_focus: dict, constraints: dict) -> list[dict]:
    """Раскладка phase по weekly_windows с учётом приоритетов."""
    windows_by_day = _windows_by_day(constraints)
    forbidden = constraints.get("forbidden", {})
    slots = []

    # Категории по приоритету
    categories = [
        ("long_run", phase_focus.get("long_run", []), 100),
        ("brick", phase_focus.get("brick", []), 90),
        ("key_run", phase_focus.get("key_run", []), 80),
        ("bike", phase_focus.get("bike", []), 70),
        ("swim", phase_focus.get("swim", []), 60),
        ("easy_runs", phase_focus.get("easy_runs", []), 50),
        ("ofp", phase_focus.get("ofp", []), 40),
    ]

    for cat_name, cat_slots, priority in categories:
        for spec in cat_slots:
            day = spec["day"]
            day_windows = windows_by_day.get(day, [])
            if not day_windows:
                continue
            win_idx = spec.get("window_idx", 0)
            if win_idx >= len(day_windows):
                win_idx = 0
            window = day_windows[win_idx]
            if not _window_fits(window, spec["duration_min"]):
                # Окно не вмещает — пропускаем
                continue
            # Forbidden check
            forbidden_key = f"{day} {window.get('start','')[:5]}"
            forbidden_rule = forbidden.get(forbidden_key, "")
            if forbidden_rule and cat_name in ("key_run", "long_run", "brick"):
                # Интенсивные под запретом — пропускаем
                continue
            slot = {
                "id": f"{day.lower()}-{cat_name}",
                "day": day,
                "time": window.get("start", ""),
                "duration_min": spec["duration_min"],
                "name": _slot_name(spec),
                "kind": spec["kind"],
                "subkind": spec.get("subkind", ""),
                "focus": spec.get("focus", ""),
                "location": window.get("location", ""),
                "priority": priority,
                "category": cat_name,
                "workout_ref": None,
                "structure": _build_slot_structure(spec),
            }
            if _auto_zwift_check(slot, constraints):
                slot["workout_pending"] = True
            slots.append(slot)

    # Сортировка по дню и времени
    slots.sort(key=lambda s: (DAY_ORDER.index(s["day"]), s["time"]))
    return slots


def _build_slot_structure(spec: dict) -> list[dict]:
    """Строит детальную структуру тренировки для слота.

    Возвращает list[step] с warmup/work/cooldown/set и zones.
    OFP использует ofp_structure (упражнения вместо HR-зон).
    """
    from .step_builder import build_structure, ofp_structure
    kind = spec.get("kind", "")
    subkind = spec.get("subkind", "")
    duration = spec.get("duration_min", 0)
    focus = spec.get("focus", "")
    phase_id = spec.get("phase_id", "")
    if kind == "ofp":
        return ofp_structure(subkind, duration)
    return build_structure(subkind, duration, focus, phase_id)


def _slot_name(spec: dict) -> str:
    kind = spec["kind"]
    sub = spec.get("subkind", "")
    focus = spec.get("focus", "")
    if kind == "run":
        if sub == "long_Z2":
            return f"Длинный бег {spec['duration_min']}мин Z2"
        if sub == "easy":
            return f"Easy бег {spec['duration_min']}мин Z2"
        if sub == "easy_long":
            return f"Easy long бег {spec['duration_min']}мин"
        if sub == "easy_progression":
            return f"Easy 5К + прогрессия 3К"
        if sub == "key_intervals":
            return f"Ключевая: Интервалы {spec['duration_min']}мин Z3"
        if sub == "intervals":
            return f"Интервалы {spec['duration_min']}мин"
        if sub == "tempo":
            return f"Tempo бег {spec['duration_min']}мин Z3"
        if sub == "race_pace":
            return f"Race-pace {spec['duration_min']}мин"
    if kind == "bike":
        if sub == "stationary_z2":
            return f"Вел-станок Z2 {spec['duration_min']}мин (дома)"
        if sub == "stationary_z3":
            return f"Вел-станок Z3 {spec['duration_min']}мин (дома)"
        if sub == "long_z2":
            return f"Длинный вел Z2 {spec['duration_min']}мин"
        if sub == "easy":
            return f"Easy вел {spec['duration_min']}мин"
    if kind == "swim":
        if sub == "easy":
            return f"Пул {spec['duration_min']}мин easy"
        if sub == "tempo":
            return f"Пул {spec['duration_min']}мин tempo"
    if kind == "brick":
        if sub == "bike_run":
            return f"Brick вел→бег {spec['duration_min']}мин"
    return f"{kind} {sub} {spec['duration_min']}мин"


def _apply_overrides(slots: list[dict], overrides: list[dict], season_week: int) -> tuple[list[dict], list[dict]]:
    """Применяет overrides для конкретной недели. Возвращает (slots_after, applied_log)."""
    applied_log = []
    week_overrides = [o for o in overrides if o.get("week") == f"W{season_week}" or o.get("season_week") == season_week]

    for ov in week_overrides:
        reason = ov.get("reason", "")
        if not reason:
            continue
        if ov.get("add_swim_sessions"):
            # Добавляем swim-сессию в СБ (окно пустое обычно, но если есть — ставим)
            for sw in ov["add_swim_sessions"]:
                # Phase 3: smarter logic
                applied_log.append({"ov": "add_swim_sessions", "skipped": True, "reason": "Phase 3 stub"})

    return slots, applied_log


def generate(season_week: int | str,
             season_plan_path: str | Path = "state/season_plan.json",
             athlete_path: str | Path = "state/athlete.json",
             constraints_path: str | Path = "state/constraints.json",
             overrides_path: str | Path = "state/overrides.json") -> dict[str, Any]:
    """
    season_week: int (1..48), 'W1', или '2026-W42'.
    Возвращает plan-wN.json с реальной раскладкой slots[].
    """
    sp = json.loads(Path(season_plan_path).read_text(encoding="utf-8"))
    at = json.loads(Path(athlete_path).read_text(encoding="utf-8"))
    cn = json.loads(Path(constraints_path).read_text(encoding="utf-8"))
    ov = json.loads(Path(overrides_path).read_text(encoding="utf-8")) if Path(overrides_path).exists() else {"overrides": []}

    season_start = sp.get("season_start_date", "2026-10-11")

    if isinstance(season_week, str):
        if season_week.startswith("W"):
            sw = int(season_week[1:])
        elif "W" in season_week:
            from .season_week import iso_to_season_week
            sw = iso_to_season_week(season_week, season_start)
        else:
            sw = int(season_week)
    else:
        sw = season_week

    week_start, week_end = season_week_to_dates(sw, season_start)
    iso = season_week_to_iso(sw, season_start)

    current_phase = phase_for_season_week(sw, sp.get("phases", []), season_start)

    cp_in_range = [
        cp for cp in sp.get("control_points", [])
        if cp.get("season_week") == sw
    ]

    phase_id = current_phase["id"] if current_phase else "run_base"
    phase_focus = _phase_focus_runs(phase_id)
    slots = _layout_slots(phase_focus, cn)
    slots, applied_log = _apply_overrides(slots, ov.get("overrides", []), sw)

    # CP-слоты
    cp_slots = []
    for cp in cp_in_range:
        day = _day_for(week_start, cp["date"])
        if day:
            windows = cn.get("weekly_windows", {}).get(day, [])
            if windows:
                cp_slots.append({
                    "id": f"cp-{cp['id']}",
                    "day": day,
                    "time": windows[0].get("start", ""),
                    "duration_min": windows[0].get("duration_min", 60),
                    "name": f"CONTROL: {cp['what']}",
                    "kind": "control_point",
                    "control_point_id": cp["id"],
                    "metric_target": cp.get("metric_target", ""),
                    "target_value": cp.get("target_value", ""),
                    "location": windows[0].get("location", ""),
                })

    all_slots = cp_slots + slots
    all_slots.sort(key=lambda s: (DAY_ORDER.index(s["day"]), s.get("time", "")))

    vc = check_volume(current_phase, cn) if current_phase else {"ok": True}

    # Считаем итоговый объём из slots
    total_planned_min = sum(s["duration_min"] for s in all_slots)
    total_planned_h = round(total_planned_min / 60.0, 1)
    target_h = current_phase.get("hours_per_week_target", 0) if current_phase else 0

    return {
        "$schema": "./plan.schema.md",
        "version": 2,
        "title": f"W{sw} · {week_start.isoformat()}..{week_end.isoformat()} · Берлин",
        "season_week": sw,
        "iso_week": iso,
        "weekIso": iso,
        "season_start_date": season_start,
        "phase": current_phase,
        "chosen_allocation": sp.get("chosen_allocation"),
        "rules": {
            "hr_zones": at.get("hr_zones"),
            "metric_split": {
                "by_hr_first": "easy, Z2, Z2-low, long, recovery, warmup, cooldown",
                "by_pace_first": "intervals, progression, tempo, race-pace",
            },
        },
        "slots": all_slots,
        "control_points_in_range": [cp["id"] for cp in cp_in_range],
        "control_point_slots": cp_slots,
        "overrides_applied": applied_log,
        "volume_check": vc,
        "totals": {
            "planned_hours": total_planned_h,
            "target_hours": target_h,
            "delta_hours": round(target_h - total_planned_h, 1),
            "slots_count": len(all_slots),
        },
        "_generated_by": "lib.plan_generate (Phase 2.5: real layout v18)",
    }