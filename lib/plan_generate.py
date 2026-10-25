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
    phase_for_season_week, DAY_ORDER,
)
from .step_builder import build_structure, ofp_structure


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


def _layout_slots(phase_focus: dict, constraints: dict,
                  quality_selection: dict | None = None) -> list[dict]:
    """Раскладка phase по weekly_windows с учётом приоритетов.

    quality_selection — результат quality_session.choose_quality() для этой недели:
    {goal, scale, variant, ...}. Если задан, ключевой беговой слот получает
    структуру ИЗ ШАБЛОНА (конкретные повторы/темп/отдых), а не из зашитого subkind.
    """
    windows_by_day = _windows_by_day(constraints)
    forbidden = constraints.get("forbidden", {})
    slots = []
    quality_applied = False

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

            # Качественная сессия в неделе ОДНА — цель недели одна.
            # key_run в фазе даёт ДВА беговых слота:
            #   1) первый (ПН) — качественная сессия: структура из шаблона по цели недели;
            #   2) второй (ВТ) — объёмный бег Z2 (не интенсивный).
            # В CP-неделю качественную роль берёт сам CP (первый key_run не создаётся),
            # объёмный бег остаётся.
            is_volume_run = False
            if cat_name == "key_run" and spec["kind"] == "run":
                cp_is_quality = bool(quality_selection and quality_selection.get("is_cp"))
                if cp_is_quality and not quality_applied:
                    # CP занимает роль качественной сессии — обычный key_run не создаём
                    quality_applied = True
                    continue
                if quality_applied:
                    # качественная роль уже занята → этот key_run = объёмный бег Z2
                    spec["subkind"] = "easy"
                    spec["focus"] = "Z2"
                    is_volume_run = True

            is_quality = bool(
                quality_selection
                and cat_name == "key_run"
                and spec["kind"] == "run"
                and not quality_applied
                and not is_volume_run
            )
            if is_quality:
                spec["quality_selection"] = quality_selection

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
            if is_quality:
                quality_applied = True
                slot["subkind"] = "quality"
                slot["focus"] = quality_selection.get("template_meta", {}).get("work_zone", "Z4")
                slot["quality_goal"] = quality_selection.get("goal")
                slot["quality_scale"] = quality_selection.get("scale")
                slot["quality_variant"] = quality_selection.get("variant", {}).get("id")
                slot["quality_work_m"] = quality_selection.get("work_m")
                slot["quality_selection"] = quality_selection
                # метаданные сессии: объём работы, вариант, цель
                sess = dict(slot.get("session") or {})
                sess["work_m"] = quality_selection.get("work_m")
                sess["variant_id"] = slot["quality_variant"]
                sess["variant_source"] = quality_selection.get("variant_source")
                sess["session_goal"] = quality_selection.get("session_goal") or sess.get("session_goal")
                sess["label"] = quality_selection.get("variant", {}).get("label")
                slot["session"] = sess
                slot["structure"] = spec.get("_structure_override") or slot["structure"]
                slot["name"] = _quality_slot_name(quality_selection)
                # Длительность слота = фактическая длительность выбранной структуры
                struct_min = sum(
                    st.get("duration_min") or 0
                    for st in slot["structure"]
                    if st.get("phase") != "set" or not st.get("set_repeats")
                ) + sum(
                    (st.get("duration_min") or 0)
                    for st in slot["structure"]
                    if st.get("phase") == "set" and st.get("set_repeats")
                )
                slot["duration_min"] = struct_min
                if quality_selection.get("rationale"):
                    slot["rationale"] = quality_selection["rationale"]
                if quality_selection.get("warning"):
                    slot["quality_warning"] = quality_selection["warning"]
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
    Если в spec задан готовый quality_selection — берём структуру из шаблона
    (конкретная структура выбирается при планировании недели, а не зашита в макро).
    """
    from .step_builder import build_structure, ofp_structure
    kind = spec.get("kind", "")
    subkind = spec.get("subkind", "")
    duration = spec.get("duration_min", 0)
    focus = spec.get("focus", "")
    phase_id = spec.get("phase_id", "")

    qsel = spec.get("quality_selection")
    if qsel and kind == "run":
        from .quality_session import build_structure_from_variant
        variant = qsel.get("variant") or {}
        steps = build_structure_from_variant(variant)
        spec["_structure_override"] = steps
        return steps

    if kind == "ofp":
        return ofp_structure(subkind, duration)
    return build_structure(subkind, duration, focus, phase_id)


def _select_quality_for_week(season_plan: dict, season_week: int,
                              variant_id: str | None = None,
                              cp: dict | None = None) -> dict | None:
    """
    Достаёт цель качественной сессии недели из макро и выбирает конкретную структуру.

    Макро (weekly_macro[].quality) хранит только {goal, scale}. Структура выбирается
    из state/workout_templates.json через quality_session.choose_quality() —
    с guard'ом объёма по state/quality_history.json.

    variant_id — точный выбор варианта (например из override: "5x800").
    """
    wm = season_plan.get("weekly_macro") or []
    entry = next((w for w in wm if w.get("season_week") == season_week), None)
    if not entry:
        return None
    q = entry.get("quality") or {}
    goal = q.get("goal")
    scale = q.get("scale")

    # CP с quality_goal переопределяет цель недели (TT-недели: goal = time_trial)
    if cp and cp.get("quality_goal"):
        goal = cp["quality_goal"]
        scale = (entry.get("quality") or {}).get("scale") or "light"

    if not goal:
        return None

    # Контекст макро-лестницы: work_m предыдущей недели плана (для флага скачков)
    plan_context = None
    prev = next((w for w in wm if w.get("season_week") == season_week - 1), None)
    if prev:
        from .quality_session import choose_quality as _cq
        prev_q = _cq(prev.get("quality", {}).get("goal", ""),
                     prev.get("quality", {}).get("scale", "medium"),
                     variant_id=prev.get("quality", {}).get("variant_id"))
        plan_context = prev_q.get("work_m")

    from .quality_session import choose_quality
    tt = (cp or {}).get("session", {}).get("test_type")

    # Приоритет выбора структуры:
    #   1) variant_id из override — явное решение на эту неделю
    #   2) variant_id из МАКРО — неделя уже зафиксирована структурой
    #   3) scale-подбор в каталоге + guard объёма
    macro_variant = q.get("variant_id")
    chosen_variant = variant_id or (None if cp and cp.get("quality_goal") else macro_variant)

    variant_source = ("override" if variant_id else
                      "макро" if chosen_variant else "каталог по scale")
    sel = choose_quality(goal, scale or "medium", variant_id=chosen_variant,
                         plan_context_work_m=plan_context, test_type=tt,
                         variant_source=variant_source)
    sel["variant_source"] = variant_source
    if cp and cp.get("quality_goal"):
        sel["is_cp"] = True
        sel["cp_id"] = cp.get("id")
        sel["cp_target"] = cp.get("target_value")
        sel["session"] = cp.get("session", {})
        # Цель сессии — часть выбора, чтобы попала и в rationale, и в карточку
        sess = cp.get("session", {})
        if sess.get("session_goal"):
            sel["session_goal"] = sess["session_goal"]
        if sess.get("pass_criteria"):
            sel["pass_criteria"] = sess["pass_criteria"]
        if sess.get("fail_action"):
            sel["fail_action"] = sess["fail_action"]
        if sess.get("protocol"):
            sel["protocol"] = sess["protocol"]
        if sess.get("pace_min_per_km"):
            sel["pace_min_per_km"] = sess["pace_min_per_km"]
    return sel


def _quality_slot_name(qsel: dict) -> str:
    """Имя слота качественной сессии: цель + выбранный вариант."""
    meta = qsel.get("template_meta") or {}
    variant = qsel.get("variant") or {}
    label = meta.get("label") or qsel.get("goal", "")
    vlabel = variant.get("label", "")
    return f"{label}: {vlabel}" if vlabel else label


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


def _place_cp(cp: dict, constraints: dict, slots: list[dict]) -> tuple[str, dict] | None:
    """Выбирает день и окно для control point.

    В макро у CP нет ни даты, ни дня недели — день определяется ЗДЕСЬ, при
    планировании недели. Порядок предпочтения:
      1. Окна, пригодные для бега (стадион/асфальт/бассейн) — в порядке дней недели.
      2. Дни, где уже стоит качественная сессия (key_run) — день не дублируется.
      3. Если подходящего бегового окна нет — любое окно с максимальной длительностью.

    Возвращает (day, window) или None, если разместить негде.
    """
    windows_by_day = _windows_by_day(constraints)
    if not windows_by_day:
        return None

    busy = {(s["day"], s["time"]) for s in slots if s.get("kind") == "run"}

    # Минимальная длительность окна: разминка 15 + работа + заминка 12 ≈ 35 мин.
    # Короткое окно (Вт 09:00 = 30 мин) для TT не подходит.
    need_min = cp.get("min_window_min", 45)

    run_locs = ("stadium", "asphalt", "pool", "stadium_or_pool", "pool_or_asphalt")

    # 1) Беговые окна достаточной длины, день не занят другой беговой сессией
    for day in DAY_ORDER:
        for win in windows_by_day.get(day, []):
            loc = win.get("location", "")
            if not any(k in loc for k in run_locs):
                continue
            if win.get("duration_min", 0) < need_min:
                continue
            if (day, win.get("start", "")) in busy:
                continue
            return day, win

    # 2) Беговые окна, день свободен (даже если окно короткое) — лучше короткое,
    #    чем контрольная точка вообще без окна
    for day in DAY_ORDER:
        for win in windows_by_day.get(day, []):
            loc = win.get("location", "")
            if not any(k in loc for k in run_locs):
                continue
            if (day, win.get("start", "")) in busy:
                continue
            return day, win

    # 3) Хоть что-то: самое длинное окно недели
    best = None
    for day in DAY_ORDER:
        for win in windows_by_day.get(day, []):
            if best is None or win.get("duration_min", 0) > best[1].get("duration_min", 0):
                best = (day, win)
    return best


def _pick_cp_window(windows: list[dict], cp: dict) -> dict:
    """Выбирает окно для control point.

    CP — это всегда беговая работа (time trial). Поэтому берём окно,
    пригодное для бега (стадион / асфальт / бассейн), а не велотренажёр.
    Если подходящего окна нет — берём последнее окно дня (вечернее).
    """
    run_locs = ("stadium", "asphalt", "pool", "stadium_or_pool", "pool_or_asphalt")
    for w in windows:
        if any(k in w.get("location", "") for k in run_locs):
            return w
    return windows[-1]


def _build_cp_structure(cp: dict, win: dict,
                        quality_selection: dict | None = None) -> list[dict]:
    """Структура контрольной точки.

    Если CP задаёт качественную сессию (quality_goal) — структура берётся
    из выбранного шаблона (вариант time_trial), с разминкой и заминкой.
    Иначе (kind=metric, информационный замер) — разминка → работа → заминка.
    """
    if quality_selection and quality_selection.get("is_cp"):
        from .quality_session import build_structure_from_variant
        return build_structure_from_variant(
            quality_selection.get("variant") or {},
            pace_override=quality_selection.get("pace_min_per_km"),
            distance_override=(quality_selection.get("session") or {}).get("distance_m"))

    dur = win.get("duration_min", 60)
    warmup = 15
    cooldown = 10
    work = max(dur - warmup - cooldown, 5)
    tv = cp.get("target_value")
    target = ""
    if isinstance(tv, int) and tv > 0:
        target = f"цель {tv // 60}:{tv % 60:02d}"
    return [
        {"phase": "warmup", "basis": "time", "duration_min": warmup, "zone": "Z1", "pace_min_per_km": None},
        {"phase": "work", "basis": "time", "duration_min": work, "zone": "Z5", "hr_target": None, "pace_min_per_km": None},
        {"phase": "cooldown", "basis": "time", "duration_min": cooldown, "zone": "Z1", "pace_min_per_km": None},
    ]


def _build_slot_from_spec(spec: dict, quality_selection: dict | None = None) -> dict:
    """Собирает слот из спеки override'а. structure — из spec или через step_builder."""
    slot = {
        "id": spec["id"],
        "day": spec["day"],
        "time": spec.get("time", ""),
        "duration_min": spec.get("duration_min", 0),
        "name": spec.get("name", ""),
        "kind": spec.get("kind", ""),
        "subkind": spec.get("subkind", ""),
        "focus": spec.get("focus", ""),
        "location": spec.get("location", ""),
        "priority": spec.get("priority", 50),
        "category": spec.get("category", ""),
        "workout_ref": None,
    }
    if spec.get("structure"):
        slot["structure"] = spec["structure"]
    elif spec.get("subkind") == "quality" and quality_selection:
        # Слот качественной сессии: структура из выбранного шаблона
        from .quality_session import build_structure_from_variant
        slot["structure"] = build_structure_from_variant(
            quality_selection.get("variant") or {},
            pace_override=quality_selection.get("pace_min_per_km"),
            distance_override=(quality_selection.get("session") or {}).get("distance_m"))
        slot["quality_goal"] = quality_selection.get("goal")
        slot["quality_scale"] = quality_selection.get("scale")
        slot["quality_variant"] = quality_selection.get("variant", {}).get("id")
        slot["quality_work_m"] = quality_selection.get("work_m")
        slot["quality_selection"] = quality_selection
        slot["focus"] = quality_selection.get("template_meta", {}).get("work_zone", slot["focus"])
        slot["duration_min"] = sum(st.get("duration_min") or 0 for st in slot["structure"])
        # метаданные сессии: объём работы, вариант, цель
        slot["session"] = {
            "work_m": quality_selection.get("work_m"),
            "variant_id": slot["quality_variant"],
            "variant_source": quality_selection.get("variant_source"),
            "session_goal": quality_selection.get("session_goal"),
            "label": (quality_selection.get("variant") or {}).get("label"),
        }
    else:
        slot["structure"] = _build_slot_structure({
            "kind": slot["kind"],
            "subkind": slot["subkind"],
            "duration_min": slot["duration_min"],
            "focus": slot["focus"],
        })
    if spec.get("rationale"):
        slot["rationale"] = spec["rationale"]
    if quality_selection and slot.get("subkind") == "quality":
        # Объединяем rationale спеки и rationale выбора шаблона
        parts = [slot.get("rationale", ""), quality_selection.get("rationale", "")]
        slot["rationale"] = " ".join(p for p in parts if p).strip()
        if quality_selection.get("warning"):
            slot["quality_warning"] = quality_selection["warning"]
    if spec.get("workout_pending"):
        slot["workout_pending"] = True
    return slot


def _apply_overrides(slots: list[dict], overrides: list[dict], season_week: int,
                     quality_selection: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Применяет overrides для конкретной недели. Возвращает (slots_after, applied_log)."""
    applied_log = []
    week_overrides = [o for o in overrides if o.get("week") == f"W{season_week}" or o.get("season_week") == season_week]

    for ov in week_overrides:
        reason = ov.get("reason", "")
        if not reason:
            continue
        if ov.get("replace_slots"):
            # Неделя переопределена целиком (travel-неделя, деload, спец-раскладка).
            specs = ov["replace_slots"] if isinstance(ov["replace_slots"], list) else ov.get("slots", [])
            new_slots = [_build_slot_from_spec(s, quality_selection) for s in specs]
            new_slots.sort(key=lambda s: (DAY_ORDER.index(s["day"]), s.get("time", "")))
            applied_log.append({
                "ov": "replace_slots",
                "applied": True,
                "reason": reason,
                "slots_before": len(slots),
                "slots_after": len(new_slots),
            })
            slots = new_slots
        if ov.get("add_slots"):
            for spec in ov["add_slots"]:
                slots.append(_build_slot_from_spec(spec))
            slots.sort(key=lambda s: (DAY_ORDER.index(s["day"]), s.get("time", "")))
            applied_log.append({"ov": "add_slots", "applied": True, "reason": reason})
        if ov.get("add_swim_sessions"):
            # Добавляем swim-сессию в СБ (окно пустое обычно, но если есть — ставим)
            for sw in ov["add_swim_sessions"]:
                # Phase 3: smarter logic
                applied_log.append({"ov": "add_swim_sessions", "skipped": True, "reason": "Phase 3 stub"})

    return slots, applied_log


def _gates_for_week(sp: dict, sw: int) -> list[dict]:
    """Gates для этой недели: её собственные + ближайший следующий.

    Фактические значения берутся из state/season_progress.json — там их
    считает review_gates --evaluate (по FIT из Garmin). Если файл ещё не
    заполнен — gate показывается без значений (pending).
    """
    try:
        from lib import review_gates
        prog = review_gates.load_progress()
        stored = {g["id"]: g for g in prog.get("gates", [])}
        gates = review_gates.build_gates(sp)
    except Exception:
        return []

    out = []
    for g in gates:
        if g.season_week != sw:
            continue
        d = stored.get(g.id)
        out.append(d if d else g.to_dict())

    # ближайший следующий gate — чтобы было видно, что впереди
    nxt = [g for g in gates if g.season_week > sw]
    if nxt:
        g = min(nxt, key=lambda x: x.season_week)
        d = stored.get(g.id)
        dd = d if d else g.to_dict()
        dd = {**dd, "_upcoming": True}
        out.append(dd)
    return out


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

    # Качественная сессия недели: цель берём из макро (weekly_macro[].quality),
    # конкретную структуру выбираем из каталога шаблонов с guard'ом объёма.
    # variant_id можно задать в override недели — точный выбор варианта.
    quality_variant_id = None
    for o in ov.get("overrides", []):
        if o.get("week") == f"W{sw}" or o.get("season_week") == sw:
            qo = o.get("quality") or {}
            if qo.get("variant_id"):
                quality_variant_id = qo["variant_id"]
            break
    # CP с quality_goal переопределяет цель недели (TT-недели).
    # Тогда обычная key_run-сессия не создаётся — качественная сессия одна.
    cp_quality = next((c for c in cp_in_range if c.get("quality_goal")), None)
    quality_selection = _select_quality_for_week(
        sp, sw, variant_id=quality_variant_id, cp=cp_quality)

    slots = _layout_slots(phase_focus, cn, quality_selection=quality_selection)
    slots, applied_log = _apply_overrides(slots, ov.get("overrides", []), sw,
                                         quality_selection=quality_selection)

    # Контекст нагрузки предыдущей недели (для решения «что ставим»)
    load_context = None
    for o in ov.get("overrides", []):
        if o.get("week") == f"W{sw}" or o.get("season_week") == sw:
            if o.get("load_context"):
                load_context = o["load_context"]
                break

    # CP-слоты
    # CP привязан ТОЛЬКО к season_week — ни даты, ни дня недели в макро нет.
    # День качественной сессии выбирается ЗДЕСЬ, при планировании недели:
    # перебираем окна по дням и берём подходящее для бега.
    # CP с quality_goal = качественная сессия недели (заменяет обычную key_run).
    # CP без quality_goal (kind=metric) = информационный замер метрики.
    cp_slots = []
    for cp in cp_in_range:
        placement = _place_cp(cp, cn, slots)
        if not placement:
            continue
        day, win = placement
        cp_slots.append({
            "id": f"cp-{cp['id']}",
            "day": day,
            "time": win.get("start", ""),
            "duration_min": win.get("duration_min", 60),
            "name": f"CONTROL: {cp['what']}",
            "kind": "control_point",
            "control_point_id": cp["id"],
            "metric_target": cp.get("metric_target", ""),
            "target_value": cp.get("target_value", ""),
            "location": win.get("location", ""),
            "structure": _build_cp_structure(cp, win, quality_selection),
        })
        # CP, задающий качественную сессию: прокидываем выбор шаблона,
        # чтобы карточка показывала цель, вариант и объём работы.
        if quality_selection and quality_selection.get("is_cp"):
            cp_slots[-1]["subkind"] = "quality"
            cp_slots[-1]["quality_selection"] = quality_selection
            # Цель тестовой сессии — в сам слот, чтобы рендерить в карточке
            cp_slots[-1]["session"] = cp.get("session", {})
            cp_slots[-1]["goal"] = cp.get("session", {}).get("session_goal", "")
            cp_slots[-1]["quality_goal"] = quality_selection.get("goal")
            cp_slots[-1]["quality_variant"] = quality_selection.get("variant", {}).get("id")
            cp_slots[-1]["quality_work_m"] = quality_selection.get("work_m")
            cp_slots[-1]["session"]["work_m"] = quality_selection.get("work_m")
            cp_slots[-1]["session"]["variant_id"] = cp_slots[-1]["quality_variant"]
            cp_slots[-1]["focus"] = quality_selection.get("template_meta", {}).get("work_zone", "")
            cp_slots[-1]["duration_min"] = sum(st.get("duration_min") or 0
                                               for st in cp_slots[-1]["structure"])
            if quality_selection.get("rationale"):
                cp_slots[-1]["rationale"] = quality_selection["rationale"]
            if quality_selection.get("warning"):
                cp_slots[-1]["quality_warning"] = quality_selection["warning"]

    all_slots = cp_slots + slots

    # Control point имеет приоритет: обычные слоты в том же окне (день+время)
    # вытесняются — иначе TT делит окно с плавкой/велом и обе сессии нереальны.
    if cp_slots:
        cp_keys = {(s["day"], s["time"]) for s in cp_slots}
        dropped = [s for s in all_slots
                   if s["kind"] != "control_point" and (s["day"], s["time"]) in cp_keys]
        if dropped:
            applied_log.append({
                "ov": "control_point_priority",
                "applied": True,
                "reason": "CP вытесняет обычные слоты из своего окна",
                "dropped": [{"id": s["id"], "day": s["day"], "time": s["time"]} for s in dropped],
            })
            all_slots = [s for s in all_slots if s not in dropped]

    all_slots.sort(key=lambda s: (DAY_ORDER.index(s["day"]), s.get("time", "")))

    vc = check_volume(current_phase, cn) if current_phase else {"ok": True}

    # Считаем итоговый объём из slots
    total_planned_min = sum(s["duration_min"] for s in all_slots)
    total_planned_h = round(total_planned_min / 60.0, 1)
    target_h = current_phase.get("hours_per_week_target", 0) if current_phase else 0

    # Цели: фаза → неделя → сессия. Три уровня, все явные.
    week_entry = next((w for w in (sp.get("weekly_macro") or [])
                       if w.get("season_week") == sw), None)
    week_goal = None
    week_goal_detail = None
    if week_entry:
        q = week_entry.get("quality") or {}
        week_goal = q.get("goal_text") or q.get("goal")
        detail_bits = []
        if q.get("scale_text"):
            detail_bits.append("масштаб: " + q["scale_text"])
        if q.get("develops"):
            detail_bits.append(q["develops"])
        if detail_bits:
            week_goal_detail = " · ".join(detail_bits)

    phase_goal = (current_phase or {}).get("goal")
    phase_focus = (current_phase or {}).get("focus")

    # ── СВЕРКА ПЛАНА НЕДЕЛИ С МАКРО ────────────────────────────────────
    # План недели должен попадать в нагрузку, заложенную макро
    # (weekly_macro[].total_h). Отклонение подсвечивается, а не молчит.
    load_target = None
    if week_entry:
        load_target = week_entry.get("total_h") or week_entry.get("target_h")
    load_compare = None
    if load_target:
        from .load_model import compare as _cmp_load
        load_compare = _cmp_load(float(load_target), float(total_planned_h))
        load_compare["target_h"] = round(float(load_target), 2)
        load_compare["actual_h"] = round(total_planned_h, 2)
        load_compare["source"] = "weekly_macro[].total_h (вычисляется из структуры)"
        if load_compare["status"] == "over":
            load_compare["hint"] = (
                "План тяжелее макро на {:.1f}ч ({}%). Либо сократить объём, "
                "либо принять как осознанное решение и записать в макро.".format(
                    load_compare["delta_h"], abs(load_compare["delta_pct"])))
        elif load_compare["status"] == "under":
            load_compare["hint"] = (
                "План легче макро на {:.1f}ч ({}%). Добираем объём или фиксируем "
                "недогрузку как осознанное решение.".format(
                    -load_compare["delta_h"], abs(load_compare["delta_pct"])))

    return {
        "$schema": "./plan.schema.md",
        "version": 2,
        "title": f"W{sw} · {week_start.isoformat()}..{week_end.isoformat()} · Берлин",
        "week_goal": week_goal,
        "week_goal_detail": week_goal_detail,
        "season_goal": sp.get("season_goal"),
        "gates": _gates_for_week(sp, sw),
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
        "load_context": load_context,
        "load_compare": load_compare,
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