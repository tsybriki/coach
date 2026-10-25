"""
quality_session.py — выбор конкретной структуры качественной сессии.

Макро-план (season_plan.json → weekly_macro[].quality) хранит только АДАПТАЦИОННУЮ
ЦЕЛЬ (goal) и МАСШТАБ (scale). Конкретная структура (сколько повторов, какой темп,
какой отдых) выбирается здесь — на этапе планирования недели.

Источники:
  state/workout_templates.json  — каталог целей и их вариантов
  state/quality_history.json    — журнал последних качественных сессий (для guard объёма)

Правила выбора:
1. Берём goal из макро. Фильтруем варианты по scale.
2. Если вариантов несколько — берём тот, чей work_m ближе всего к work_m предыдущей
   качественной сессии, но не ниже guard-порога.
3. Guard объёма: work_m не должен быть ниже 0.9 × work_m последней интервальной
   сессии за 21 день. Если подходящих вариантов в полосе нет — берём максимальный
   по объёму в полосе и поднимаем флаг volume_guard_warning.
4. Если goal не найден в каталоге — деградация: generic tempo-структура.

Публичный API:
    choose_quality(goal, scale, history=None, templates=None) -> dict
    build_structure_from_variant(variant, ...) -> list[step]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
TEMPLATES_PATH = REPO / "state/workout_templates.json"
HISTORY_PATH = REPO / "state/quality_history.json"

# Guard: не опускаться ниже 90% от последней интервальной сессии за 21 день
VOLUME_GUARD_RATIO = 0.9
HISTORY_WINDOW_DAYS = 21

# Дефолтная структура, если goal не найден в каталоге
FALLBACK_VARIANT = {
    "id": "fallback_tempo",
    "label": "Tempo (fallback)",
    "scale": "medium",
    "work_m": 5000,
    "blocks": [
        {"type": "continuous", "distance_m": 5000, "pace": "5:00",
         "zone": "Z4", "hr_target": 155}
    ],
    "note": "Goal не найден в каталоге — деградация к базовому tempo.",
}

# Порядок масштабов для выбора «по объёму»
SCALE_ORDER = ["light", "medium", "heavy", "peak"]


def load_templates(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else TEMPLATES_PATH
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("templates", {})


def load_history(path: str | Path | None = None) -> list[dict]:
    p = Path(path) if path else HISTORY_PATH
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("sessions", [])


def _recent_work_m(history: list[dict]) -> int | None:
    """work_m последней качественной сессии в окне HISTORY_WINDOW_DAYS."""
    if not history:
        return None
    sess = sorted(history, key=lambda s: s.get("date", ""), reverse=True)
    if not sess:
        return None
    last = sess[0]
    return last.get("work_m")


def choose_quality(goal: str,
                   scale: str,
                   history: list[dict] | None = None,
                   templates: dict | None = None,
                   variant_id: str | None = None,
                   plan_context_work_m: int | None = None,
                   test_type: str | None = None,
                   variant_source: str | None = None) -> dict:
    """
    Возвращает dict: {goal, scale, variant, work_m, guarded, warning, rationale}.

    variant_id        — точный выбор варианта (перекрывает scale-подбор).
    plan_context_work_m — work_m предыдущей недели макро-плана. Используется для
                        проверки скачков объёма внутри плана (рост > 1.5× = флаг).
    history           — журнал реальных сессий (quality_history.json): guard «не
                        откатываться ниже 0.9 × последней реальной сессии».
    """
    templates = templates if templates is not None else load_templates()
    history = history if history is not None else load_history()

    if goal not in templates:
        variant = dict(FALLBACK_VARIANT)
        return {
            "goal": goal, "scale": scale, "variant": variant,
            "work_m": variant["work_m"], "guarded": False,
            "warning": f"Цель '{goal}' не найдена в каталоге — использован fallback tempo.",
            "rationale": "Деградация: неизвестная адаптационная цель.",
        }

    tpl = templates[goal]
    variants = tpl.get("variants", [])

    # Точный выбор варианта (из override) — приоритетнее всего
    if variant_id:
        exact = next((v for v in variants if v.get("id") == variant_id), None)
        if exact:
            chosen = exact
            in_scale = [exact]
        else:
            in_scale = [v for v in variants if v.get("scale") == scale]
    elif test_type:
        # Выбор по типу теста (CP задаёт: pace / max / sim)
        by_type = [v for v in variants if v.get("test_type") == test_type]
        if by_type:
            in_scale = by_type
        else:
            in_scale = [v for v in variants if v.get("scale") == scale]
    else:
        in_scale = [v for v in variants if v.get("scale") == scale]

    if not in_scale:
        # Откат на ближайший меньший масштаб, затем на любой
        idx = SCALE_ORDER.index(scale) if scale in SCALE_ORDER else 0
        for i in range(idx - 1, -1, -1):
            in_scale = [v for v in variants if v.get("scale") == SCALE_ORDER[i]]
            if in_scale:
                break
        if not in_scale:
            in_scale = variants

    recent = _recent_work_m(history)
    guard_floor = None
    if recent:
        guard_floor = round(recent * VOLUME_GUARD_RATIO)

    # Кандидаты: не ниже guard-порога. Если таких нет — берём максимум в полосе.
    if guard_floor is not None:
        above = [v for v in in_scale if v.get("work_m", 0) >= guard_floor]
    else:
        above = list(in_scale)

    guarded = bool(above)
    if above:
        # Ближайший к guard-порогу снизу (минимальный шаг вверх), иначе — минимальный объём
        chosen = min(above, key=lambda v: (v.get("work_m", 0), v.get("id", "")))
    else:
        chosen = max(in_scale, key=lambda v: v.get("work_m", 0))

    # --- Предупреждения ---
    warnings = []

    # 1. Откат ниже последней реальной сессии (защита от потери формы)
    if guard_floor is not None and not guarded:
        warnings.append(
            f"Ни один вариант цели '{goal}' в масштабе '{scale}' не дотягивает "
            f"до guard-порога {guard_floor} м (последняя реальная сессия {recent} м). "
            f"Взят максимальный доступный: {chosen['work_m']} м.")

    # 2. Скачок объёма внутри макро-лестницы (>1.5× к предыдущей неделе)
    if plan_context_work_m:
        ratio = chosen["work_m"] / plan_context_work_m
        if ratio > 1.5:
            warnings.append(
                f"Скачок объёма работы: {plan_context_work_m} → {chosen['work_m']} м "
                f"(×{ratio:.2f} к предыдущей неделе макро). Проверить готовность или "
                f"разбить на две сессии.")
        elif ratio < 0.6:
            warnings.append(
                f"Объём работы падает: {plan_context_work_m} → {chosen['work_m']} м "
                f"(×{ratio:.2f}). Если это запланированный шаг вниз — норма; "
                f"если нет — проверь лестницу.")

    # 3. Рост относительно последней реальной сессии
    if recent and chosen["work_m"] > recent * 1.15 and plan_context_work_m:
        warnings.append(
            f"Объём работы вырос с {recent} м (последняя реальная) до {chosen['work_m']} м.")

    warning = " ".join(warnings)

    src_note = {"override": "выбрана override'ом недели",
                "макро": "задана макро-планом",
                "каталог по scale": "подобрана каталогом по масштабу"}.get(
        variant_source, "подобрана каталогом")
    rationale = (f"Цель: {tpl.get('goal', goal)}. Масштаб недели: {scale}. "
                 f"Структура {src_note}: {chosen.get('label')} — работа {chosen.get('work_m')} м. "
                 + (f"Опора (реальная сессия): {recent} м, порог {guard_floor} м. "
                    if recent else "Реальных сессий в журнале нет. ")
                 + (f"Объём работы предыдущей недели макро: {plan_context_work_m} м. "
                    if plan_context_work_m else ""))

    # Цель сессии: из шаблона (что развивает) + что измеряем
    session_goal = None
    tpl_goal = (templates.get(goal) or {}).get("goal")
    tpl_dev = (templates.get(goal) or {}).get("develops")
    ind = (templates.get(goal) or {}).get("indicators")
    bits = []
    if tpl_goal:
        bits.append(tpl_goal)
    if tpl_dev:
        bits.append(tpl_dev)
    if ind:
        bits.append("проверяем: " + ind)
    if bits:
        session_goal = " · ".join(bits)

    return {
        "goal": goal,
        "scale": scale,
        "session_goal": session_goal,
        "variant": chosen,
        "work_m": chosen.get("work_m", 0),
        "guarded": guarded,
        "warning": warning,
        "rationale": rationale,
        "template_meta": {
            "label": tpl.get("label"),
            "develops": tpl.get("develops"),
            "work_zone": tpl.get("work_zone"),
            "hr_target": tpl.get("hr_target"),
            "pace": tpl.get("pace"),
            "indicators": tpl.get("indicators"),
        },
    }


def build_structure_from_variant(variant: dict,
                                 warmup_min: int = 15,
                                 cooldown_min: int = 12,
                                 pace_override: str | None = None,
                                 distance_override: int | None = None) -> list[dict]:
    """
    Превращает вариант шаблона в structure[] — формат slot.structure пайплайна.

    Поддерживаемые типы блоков: reps, continuous, pyramid, fartlek, tt, progression.
    """
    steps: list[dict] = [{
        "phase": "warmup",
        "basis": "time",
        "duration_min": warmup_min,
        "zone": "Z1",
        "pace_min_per_km": None,
    }]

    for block in variant.get("blocks", []):
        btype = block.get("type")

        if btype == "reps":
            steps.append({
                "phase": "set",
                "label": _reps_label(block),
                "basis": "distance",
                "reps": block.get("reps"),
                "duration_min": _reps_minutes(block),
                "set_repeats": _reps_substeps(block),
            })

        elif btype == "reps_progression":
            # Повторы с прогрессией темпа внутри серии:
            # '3×800 с 4:15 → 3:50' — каждый следующий повтор быстрее.
            reps = int(block.get("reps", 0))
            paces = block.get("paces") or []
            dist = int(block.get("distance_m", 0))
            subs = []
            for i in range(reps):
                pc = paces[min(i, len(paces) - 1)] if paces else block.get("pace", "4:00")
                subs.append({
                    "phase": "work",
                    "basis": "distance",
                    "distance_m": dist,
                    "zone": block.get("zone", "Z6"),
                    "hr_target": block.get("hr_target"),
                    "pace_min_per_km": pc,
                })
                if i < reps - 1:
                    subs.append({
                        "phase": "recovery",
                        "basis": "distance",
                        "distance_m": int(block.get("rest_distance_m", 200)),
                        "zone": "Z1",
                        "hr_target": 115,
                        "pace_min_per_km": None,
                    })
            steps.append({
                "phase": "set",
                "label": "{}×{}м с прогрессией {} → {}".format(
                    reps, dist,
                    paces[0] if paces else block.get("pace", "—"),
                    paces[-1] if paces else block.get("pace", "—")),
                "basis": "distance",
                "reps": reps,
                "duration_min": _reps_progression_minutes(block, subs),
                "set_repeats": subs,
            })

        elif btype == "continuous":
            mins = _distance_minutes(block["distance_m"], block.get("pace", "5:00"))
            steps.append({
                "phase": "work",
                "basis": "distance",
                "distance_m": block["distance_m"],
                "duration_min": mins,
                "zone": block.get("zone", "Z4"),
                "hr_target": block.get("hr_target"),
                "pace_min_per_km": block.get("pace"),
            })

        elif btype == "pyramid":
            steps.append({
                "phase": "set",
                "label": "пирамида",
                "basis": "distance",
                "reps": 1,
                "duration_min": sum(_distance_minutes(s["distance_m"], s["pace"])
                                    for s in block.get("steps", [])),
                "set_repeats": [{
                    "phase": "work",
                    "basis": "distance",
                    "distance_m": s["distance_m"],
                    "zone": s.get("zone"),
                    "hr_target": s.get("hr_target"),
                    "pace_min_per_km": s.get("pace"),
                } for s in block.get("steps", [])],
            })

        elif btype == "fartlek":
            cycles = block.get("cycles", 1)
            steps.append({
                "phase": "set",
                "label": f"фартлек ×{cycles}",
                "basis": "distance",
                "reps": cycles,
                "duration_min": cycles * (_distance_minutes(block.get("hard_distance_m", 800),
                                                           block.get("hard_pace", "4:00"))
                                         + _distance_minutes(block.get("easy_distance_m", 200),
                                                            block.get("easy_pace", "5:20"))),
                "set_repeats": [
                    {"phase": "work", "basis": "distance",
                     "distance_m": block.get("hard_distance_m", 800),
                     "zone": block.get("hard_zone", "Z5"),
                     "hr_target": block.get("hr_target"),
                     "pace_min_per_km": block.get("hard_pace")},
                    {"phase": "recovery", "basis": "distance",
                     "distance_m": block.get("easy_distance_m", 200),
                     "zone": "Z1", "hr_target": 115,
                     "pace_min_per_km": block.get("easy_pace")},
                ],
            })

        elif btype in ("tt_pace", "tt_max"):
            # Темповый тест (tt_pace) или тест на максимум (tt_max).
            # Дистанция — из цели CP (distance_override): шаблон задаёт лишь форму.
            # Темп: для pace — заданный темп CP, для max — all-out.
            dist = distance_override or block["distance_m"]
            pace = block.get("pace", "all-out")
            if pace == "по цели CP" or not pace:
                pace = pace_override or "4:30"
            is_max = btype == "tt_max" or pace == "all-out"
            if is_max:
                pace_label = "all-out"
                eff_pace = pace_override or "4:20"
                mins = _distance_minutes(dist, eff_pace)
            else:
                pace_label = pace
                mins = _distance_minutes(dist, pace)
            steps.append({
                "phase": "work",
                "basis": "distance",
                "distance_m": dist,
                "duration_min": mins,
                "zone": block.get("zone", "Z7"),
                "hr_target": block.get("hr_target"),
                "pace_min_per_km": pace_label,
            })

        elif btype == "progression":
            steps.append({
                "phase": "work",
                "basis": "time",
                "duration_min": _distance_minutes(block.get("easy_distance_m", 5000),
                                                 block.get("from_pace", "5:00")),
                "zone": "Z2",
                "hr_target": 135,
                "pace_min_per_km": block.get("from_pace"),
            })
            steps.append({
                "phase": "work",
                "basis": "time",
                "duration_min": _distance_minutes(block.get("progression_distance_m", 3000),
                                                 block.get("to_pace", "4:30")),
                "zone": block.get("zone", "Z3"),
                "hr_target": block.get("hr_target"),
                "pace_min_per_km": f"{block.get('from_pace')}→{block.get('to_pace')}",
            })

    steps.append({
        "phase": "cooldown",
        "basis": "time",
        "duration_min": cooldown_min,
        "zone": "Z1",
        "pace_min_per_km": None,
    })
    return steps


def _reps_label(block: dict) -> str:
    d = block.get("distance_m", 0)
    if d >= 1000:
        label = f"{d // 1000}К" if d % 1000 == 0 else f"{d / 1000:.1f}К"
    else:
        label = f"{d}м"
    return f"{block.get('reps')}×{label}"


def _reps_substeps(block: dict) -> list[dict]:
    """Разворачивает reps-блок в пары work/recovery."""
    reps = block.get("reps", 1)
    rest_m = block.get("rest_min", 0)
    rest_d = block.get("rest_distance_m", 0)
    sub: list[dict] = []
    for _ in range(reps):
        sub.append({
            "phase": "work",
            "basis": "distance",
            "distance_m": block.get("distance_m", 0),
            "zone": block.get("zone"),
            "hr_target": block.get("hr_target"),
            "pace_min_per_km": block.get("pace"),
        })
        if rest_m or rest_d:
            sub.append({
                "phase": "recovery",
                "basis": "distance",
                "distance_m": rest_d,
                "zone": "Z1",
                "hr_target": 115,
                "pace_min_per_km": None,
            })
            if rest_m and not rest_d:
                sub[-1]["basis"] = "time"
                sub[-1]["duration_min"] = rest_m
    return sub


def _reps_progression_minutes(block: dict, subs: list[dict]) -> int:
    """Время сета с прогрессией: работа по темпу каждого повтора + отдых."""
    total = 0.0
    paces = block.get("paces") or [block.get("pace", "4:00")]
    dist = int(block.get("distance_m", 0))
    rest_min = float(block.get("rest_min", 0))
    rest_dist = int(block.get("rest_distance_m", 0))
    reps = int(block.get("reps", 0))
    for i in range(reps):
        pc = paces[min(i, len(paces) - 1)]
        psec = _pace_to_sec(pc)
        total += dist / 1000.0 * psec / 60.0
        if i < reps - 1:
            total += rest_min
            if rest_dist:
                total += rest_dist / 1000.0 * _pace_to_sec("5:40") / 60.0
    return int(round(total))


def _pace_to_sec(p: str) -> float:
    try:
        mm, ss = str(p).split(":")
        return int(mm) * 60 + int(ss)
    except (ValueError, AttributeError):
        return 300.0


def _reps_minutes(block: dict) -> int:
    work = _distance_minutes(block.get("distance_m", 0), block.get("pace", "4:00"))
    rest = block.get("rest_min", 0)
    total = block.get("reps", 1) * work
    if rest:
        total += block.get("reps", 1) * rest
    return max(total, 1)


def _distance_minutes(distance_m: int, pace: str) -> int:
    """'4:00' → минуты на 1 км."""
    try:
        mm, ss = pace.split(":")
        pmin = int(mm) + int(ss) / 60
    except (ValueError, AttributeError):
        pmin = 5.0
    return max(1, round(distance_m / 1000 * pmin))
