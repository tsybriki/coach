#!/usr/bin/env python3
"""
rebuild_macro_daniels.py — пересобрать макро-план сезона по Дэниэлсу.

Программа Дэниэлса (Табл. 19.1) раскладывается на фазы и недели по сроку
до старта. Каждая неделя программы знает, какая в ней работа (R/T/I/ACC)
и сколько её по объёму. Из этого собирается макро-неделя: цель, масштаб,
объём и часы.

Правила:
- **что** делать в неделе — из недели программы Дэниэлса: вид работы
  (R/T/I/ACC) и её объём по зонам;
- **сколько** бежать — из фазы сезона: недельный километраж, длинный бег;
- **структура** работы — из каталога шаблонов пайплайна по (goal, scale),
  который выбирает `lib/quality_session.choose_quality`;
- часы — из модели нагрузки пайплайна (`lib/load_model.macro_week_load`),
  а не из головы: иначе макро разойдётся с планом недели.

Фаза недели — фаза ПРОГРАММЫ Дэниэлса, а не фаза сезона пайплайна: фазы
программы и есть то, как season разворачивается на срок до старта.

Запуск:
    python3 scripts/rebuild_macro_daniels.py --dry-run
    python3 scripts/rebuild_macro_daniels.py --apply
    python3 scripts/rebuild_macro_daniels.py --apply --from-week 4
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
# Правила Дэниэлса живут в приложении: `app.domain.methodology` — язык
# правил, `app.adapters.daniels` — формат справочника.
COACH_APP = Path.home() / "projects" / "coach-app"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(COACH_APP))

from app.adapters.daniels import load_paces, load_plan  # noqa: E402
from app.domain.methodology import recipe_zone_volume_m  # noqa: E402

from lib import load_model  # noqa: E402
from lib import quality_session  # noqa: E402

STATE = Path.home() / "coach" / "state"
SEASON_PLAN = STATE / "season_plan.json"
ATHLETE = STATE / "athlete.json"
TEMPLATES = STATE / "workout_templates.json"
REFERENCE = COACH_APP / "reference" / "daniels"

# Фаза программы Дэниэлса → фаза сезона пайплайна.
#
# Фазы Дэниэлса (Табл. 19.1):
#   I   — база: лёгкий бег, длинный забег, короткие быстрые отрезки;
#   II  — порог: работа на пороговом темпе;
#   III — VO2 + порог, с соревнованиями;
#   IV  — гонка-специфика: работа на темпе гонки + соревнования.
#
# Беговой сезон — четыре фазы, без дробления (Кирилл, 31.10.2026):
# фазы Дэниэлса и есть фазы сезона, одна к одной. Неделя гонки —
# внутри четвёртой фазы, отдельной фазой она не является.
DANIELS_PHASE_TO_SEASON = {
    1: "run_base",
    2: "run_build",
    3: "run_specific",
    4: "run_taper",
}

# Смысл недели фазы — по-русски, из правил Дэниэлса.
PHASE_OBJECTIVE = {
    "run_base": "Поднимаем базовый объём",
    "run_build": "Поднимаем threshold pace",
    "run_specific": "Поднимаем VO2max и порог",
    "run_taper": "Поднимаем гонка-темп, подводим к гонке",
}

# Главная работа недели программы → цель в каталоге шаблонов пайплайна.
#
# Фаза IV Дэниэлса (недели 19-24) — работа на пороговом темпе, а это
# медленнее гонка-темпа: на 4:00/км гонка на таком блоке не выйдет.
# Поэтому в тапере работа берётся на ГОНКА-темпе — ради этого блок и
# проверяется guard'ом.
KIND_TO_GOAL = {
    "R": "threshold_speed",
    "T": "tempo",
    "I": "vo2max",
    "M": "tempo",
    "ACC": "progression",
}

# Цель для фазы подводки: гонка-темп, а не порог.
SHARPENING_GOAL = "taper_race_pace"

# Зоны Дэниэлса → зоны каталога шаблонов пайплайна.
ZONE_TO_TEMPLATE = {
    "E": "easy",
    "M": "marathon",
    "T": "threshold",
    "I": "interval",
    "R": "repetition",
}

# Доля недельного километража в длинном беге — по правилу Дэниэлса.
LONG_FRACTION = 0.25

# Неделя гонки в макро-плана НЕТ: гонка — событие, а не тренировка, и
# планировать её не нужно (Кирилл, 01.11.2026). Расписание программы
# покрывает недели ДО гонки, макро заканчивается на предпоследней неделе
# перед гонкой.


def control_points_by_week(season_plan: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Контрольные точки по номеру недели сезона.

    Неделя с контрольной точкой определяет качественную работу сама:
    тест — это и есть качественная работа недели. Правило Дэниэлса на
    этой неделе отступает: иначе контрольная точка и недельная
    структура называют разные темпы, и guard это ловит.
    """
    result: dict[int, dict[str, Any]] = {}
    for point in season_plan.get("control_points") or []:
        week = point.get("season_week")
        if not week:
            continue
        session = point.get("session") or {}
        test_type = session.get("test_type")
        if test_type not in ("pace", "max"):
            continue
        # Вариант из каталога по типу теста.
        variant_id = "tt_pace" if test_type == "pace" else "tt_max"
        if point.get("id", "").endswith("_w12") or "3k" in point.get("id", ""):
            variant_id = "tt_max_3k" if test_type == "max" else "tt_pace"
        result[week] = {
            "variant_id": variant_id,
            "test_type": test_type,
            "pace_min_per_km": session.get("pace_min_per_km"),
        }
    return result


def vdot_of(athlete: dict[str, Any]) -> float:
    """VDOT атлета — для темпов зон."""
    return float(athlete.get("vdot") or 48.0)


def _segment_minutes(segment: Any, pace_by_zone: dict[str, float]) -> float:
    """Минуты одного куска: по времени или по расстоянию и темпу зоны."""
    if segment.minutes:
        return float(segment.minutes)
    if segment.distance_m:
        pace = pace_by_zone.get(segment.zone)
        if pace:
            return segment.distance_m / pace * 60.0
    if segment.seconds:
        return segment.seconds / 60.0
    return 0.0


def recipe_minutes(recipe: Any, pace_by_zone: dict[str, float]) -> float:
    """Минуты работы по рецепту: плоские куски и сеты."""
    total = 0.0
    for segment in recipe.flat:
        total += _segment_minutes(segment, pace_by_zone)
    for group in recipe.sets:
        for segment in group.segments:
            total += _segment_minutes(segment, pace_by_zone)
    return total


def week_profile(week: Any, pace_by_zone: dict[str, float]) -> dict[str, Any]:
    """Профиль недели программы: главная работа, её объём и время.

    Главная работа — самая объёмная по времени: в программе Дэниэлса
    неделя содержит одну главную работу и добавки (интервалы к
    порогу, ускорения).
    """
    best = None
    best_minutes = -1.0
    zones: dict[str, float] = {}
    for recipe in week.recipes:
        if recipe.kind == "RACE":
            continue
        minutes = recipe_minutes(recipe, pace_by_zone)
        if minutes > best_minutes:
            best_minutes = minutes
            best = recipe
        for zone, value in recipe_zone_volume_m(recipe).items():
            zones[zone] = zones.get(zone, 0.0) + value
    if best is None:
        return {"goal": None, "minutes": 0.0, "zones": {}}
    return {
        "goal": KIND_TO_GOAL.get(best.kind),
        "minutes": round(best_minutes),
        "zones": {k: round(v) for k, v in sorted(zones.items())},
    }


# Форма фазы I по Дэниэлсу (Кирилл, 02.11.2026).
#
# 7 тренировок в неделю в лёгкой зоне; к четырём из них (не к длинной) —
# 6-8 коротких быстрых отрезков по 100 м через 100 м; к трём — ОФП
# 15 мин в конце; недельный километраж 55-57, не больше.
#
# ОФП идёт **внутри** пробежек, поэтому отдельных тренировок ОФП в
# неделе нет: 7 пробежек + вел + плавание.
PHASE_FORM = {
    1: {
        "runs": 7,
        "ofp_runs": 3,
        "ofp_minutes": 15,
        "km_min": 55.0,
        "km_max": 57.0,
        "ofp_inside_runs": True,
    },
}


# Диапазоны объёма и нагрузки фаз — по программе Дэниэлса.
#
# Объём внутри фазы растёт от её начала к концу; пик — в последней
# фазе перед гонкой, а тапер (неделя гонки) объём снимает.
PHASE_RANGES = {
    # Фаза I: форма недели задаёт 55-57 км (7 пробежек в неделю).
    # Дальше объём только растёт: падение на границе фаз — это
    # «неправильный тапер», а фазы идут подряд.
    "run_base": ((55.0, 57.0), (7.5, 9.5)),
    "run_build": ((57.0, 65.0), (9.69, 11.94)),
    "run_specific": ((65.0, 70.0), (7.34, 12.64)),
    "run_taper": ((16.0, 60.0), (3.1, 10.5)),
}


def phase_km_range(phase_id: str, season_plan: dict[str, Any]) -> tuple[float, float]:
    """Диапазон километража фазы — из правил Дэниэлса."""
    ranges = PHASE_RANGES.get(phase_id)
    if ranges:
        return ranges[0]
    for phase in season_plan.get("phases") or []:
        if phase.get("id") == phase_id:
            rng = phase.get("run_km_range")
            if rng:
                return (float(rng[0]), float(rng[1]))
    return (0.0, 0.0)


def phase_load_range(phase_id: str, season_plan: dict[str, Any]) -> tuple[float, float]:
    """Диапазон часов фазы — из правил Дэниэлса."""
    ranges = PHASE_RANGES.get(phase_id)
    if ranges:
        return ranges[1]
    for phase in season_plan.get("phases") or []:
        if phase.get("id") == phase_id:
            rng = phase.get("load_range_h")
            if rng:
                return (float(rng[0]), float(rng[1]))
    return (0.0, 0.0)


def ramp(count: int, low: float, high: float) -> list[float]:
    """Линейный ход внутри фазы: от её начала к концу.

    Тапер — обратный: объём падает к гонке.
    """
    if count <= 1:
        return [low]
    step = (high - low) / (count - 1)
    return [low + step * index for index in range(count)]


def build_macro(weeks_to_race: int, season_plan: dict[str, Any],
                athlete: dict[str, Any]) -> list[dict[str, Any]]:
    """Макро-недели по программе Дэниэлса на срок до старта."""
    plan = load_plan(REFERENCE)
    paces = load_paces(REFERENCE)
    pace_by_zone = paces.pace_by_zone(vdot_of(athlete))
    schedule = plan.schedule_for(weeks_to_race)
    if schedule is None:
        raise SystemExit("нет расписания на такой срок")

    macro: list[dict[str, Any]] = []
    for daniels_phase in sorted(schedule.phases):
        season_phase = DANIELS_PHASE_TO_SEASON.get(daniels_phase)
        if season_phase is None:
            continue
        program_weeks = schedule.weeks_for(daniels_phase)
        if not program_weeks:
            continue

        km_low, km_high = phase_km_range(season_phase, season_plan)
        h_low, h_high = phase_load_range(season_phase, season_plan)
        count = len(program_weeks)

        # Объём внутри фазы: растёт от её начала к концу. Четвёртая фаза
        # — подводка к гонке: объём держится высоким (работа на
        # гонка-темпе), а к гонке падает.
        if season_phase == "run_taper":
            kms = ramp(count, km_high, km_low)
            hours = ramp(count, h_high, h_low)
        else:
            kms = ramp(count, km_low, km_high)
            hours = ramp(count, h_low, h_high)

        for index, program_week in enumerate(program_weeks):
            entry = plan.week(daniels_phase, schedule.plan_for(program_week))
            if entry is None:
                continue
            profile = week_profile(entry, pace_by_zone)
            # В подводке — работа на гонка-темпе: блок гонки проверяется
            # guard'ом, и пороговый темп (4:12) гонку на 4:00 не
            # обеспечивает.
            goal = profile["goal"]
            if season_phase == "run_taper" and goal:
                goal = SHARPENING_GOAL
            macro.append({
                "season_week": len(macro) + 1,
                "program_week": program_week,
                "plan_week": schedule.plan_for(program_week),
                "daniels_phase": daniels_phase,
                "phase": season_phase,
                "quality_goal": goal,
                "quality_zones": profile["zones"],
                "quality_minutes": profile["minutes"],
                "run_km": round(kms[index]),
                "target_h": round(hours[index], 2),
            })
    return macro


def quality_for(week: dict[str, Any], templates: dict[str, Any],
                history: list[dict],
                control_point: dict[str, Any] | None = None) -> dict[str, Any]:
    """Качественная работа недели: вариант из каталога по (goal, scale).

    Масштаб — по объёму работы программы: сколько работы, такой и
    масштаб. Каталог отдаёт структуру, программа — что делать.

    Неделя с контрольной точкой — исключение: там работу задаёт тест
    (его тип и темп), а не программа.
    """
    if control_point:
        variant_id = control_point["variant_id"]
        variant = next(
            (v for v in templates.get("time_trial", {}).get("variants", [])
             if v.get("id") == variant_id),
            None,
        )
        if variant:
            return {
                "goal": "time_trial",
                "scale": variant.get("scale"),
                "variant_id": variant_id,
                "work_m": variant.get("work_m"),
                "label": variant.get("label"),
                "rationale": "контрольная точка недели",
                "minutes": week.get("quality_minutes") or 0,
            }

    goal = week.get("quality_goal")
    if not goal:
        return {}
    zones = week.get("quality_zones") or {}
    work_m = sum(zones.values())
    minutes = week.get("quality_minutes") or 0

    if goal == "vo2max":
        scale = "medium" if work_m < 5000 else "heavy"
    elif goal == "tempo":
        scale = "medium" if work_m < 9000 else "heavy"
    elif goal == "threshold_speed":
        scale = "light" if work_m < 5000 else "medium"
    elif goal == SHARPENING_GOAL:
        # Гонка-темп: объём работы падает, масштаб — по объёму.
        scale = "light" if work_m < 3000 else "medium"
    else:
        scale = "light"

    chosen = quality_session.choose_quality(
        goal=goal, scale=scale, history=history, templates=templates)
    return {
        "goal": goal,
        "scale": chosen.get("scale", scale),
        "variant_id": (chosen.get("variant") or {}).get("id"),
        "work_m": chosen.get("work_m"),
        "label": (chosen.get("variant") or {}).get("label"),
        "rationale": chosen.get("rationale"),
        "minutes": minutes,
    }


def _sessions_count_form(entry: dict[str, Any], week: dict[str, Any],
                         form: dict[str, Any]) -> int:
    """Число тренировок недели — по форме фазы.

    Пробежки — по форме («7 дней в неделю Л-темп»). ОФП внутри
    пробежек отдельных тренировок не создаёт. Вел и плавание — по
    одной тренировке на вид (плюс разбивка макро).
    """
    sessions = int(form["runs"])
    for kind in ("bike", "swim"):
        sessions += _count_sessions(week.get(kind))
    return sessions


def _sessions_count(entry: dict[str, Any], week: dict[str, Any]) -> int:
    """Число тренировок недели — из разбивки.

    Бег: длинный + качественная работа + лёгкие пробежки. Плюс вел,
    плавание и ОФП — по одной тренировке на вид.

    Число лёгких пробежек — по **числу дней недели**, а не по километражу:
    правило Дэниэлса — «7 дней в неделю Л-темп» в базе, дальше меньше,
    но не «сколько километраж на пробежку». Окна среды — восемь, и на
    них неделя помещается: длинный бег, качественная работа, вел,
    плавание и ОФП занимают свои дни, остальные — лёгкие пробежки.
    """
    long_km = float(week.get("long_km") or 0.0)
    quality = week.get("quality") or {}
    quality_work_km = float(quality.get("work_m") or 0.0) / 1000.0
    run_km = float(week.get("run_km") or 0.0)
    easy_km = max(run_km - long_km - quality_work_km, 0.0)

    # Тренировки недели: длинный бег, качественная работа, лёгкие
    # пробежки и остальные виды спорта.
    sessions = 0
    busy_windows = 0
    if long_km:
        sessions += 1
        busy_windows += 1
    if quality.get("work_m"):
        sessions += 1
        busy_windows += 1
    # «2×60м» — это две тренировки, а не одна: количество в макро.
    for kind in ("bike", "swim", "core"):
        count = _count_sessions(week.get(kind))
        sessions += count
        busy_windows += count
    sessions += _easy_runs(easy_km, busy_windows)
    return sessions


def _easy_runs(easy_km: float, busy_windows: int) -> int:
    """Число лёгких пробежек — по километражу, в пределах свободных окон.

    Лёгкая пробежка в базе — 6-10 км. Число пробежек ограничено
    свободными **окнами**, а не днями: в неделе 8 окон на 7 дней, и в
    один день могут встать две тренировки (утром пробежка, вечером вел).

    Окно занимает одна тренировка, поэтому число пробежек не может
    превысить число свободных окон.
    """
    if easy_km <= 0:
        return 0
    by_km = max(1, round(easy_km / 8.0))
    return max(0, min(by_km, WINDOWS_PER_WEEK - busy_windows, WINDOWS_PER_WEEK))


def _easy_km(week: dict[str, Any]) -> float:
    """Лёгкий километраж недели — всё, кроме длинного и качественного."""
    long_km = float(week.get("long_km") or 0.0)
    quality = week.get("quality") or {}
    quality_km = float(quality.get("work_m") or 0.0) / 1000.0
    return max(float(week.get("run_km") or 0.0) - long_km - quality_km, 0.0)


# Окон в неделе: 8 на 7 дней (в некоторые дни встают две тренировки).
WINDOWS_PER_WEEK = 8


def _busy_windows(week: dict[str, Any]) -> int:
    """Занятые окна недели: длинный бег, качественная работа, прочие виды.

    Окно занимает одна тренировка, поэтому занятые окна — это и есть
    ограничение на число пробежек.
    """
    busy = 0
    if float(week.get("long_km") or 0.0):
        busy += 1
    quality = week.get("quality") or {}
    if quality.get("work_m"):
        busy += 1
    for kind in ("bike", "swim", "core"):
        busy += _count_sessions(week.get(kind))
    return busy


def _count_sessions(spec: str | None) -> int:
    """Число тренировок по описанию вида спорта в макро.

    «1×60м» — одна тренировка, «2×25м» — две. Пусто — ни одной.
    """
    if not spec:
        return 0
    text = str(spec).strip()
    if "×" in text:
        head = text.split("×", 1)[0].strip()
        try:
            return int(head)
        except ValueError:
            return 1
    return 1


def recompute_load(week: dict[str, Any], athlete: dict[str, Any]) -> dict[str, Any]:
    """Нагрузка недели — пересчётом из структуры, моделью пайплайна.

    Рукописное число рядом с вычисляемым — два разных плана рядом: и
    guard это ловит (total_h ≠ пересчёт), и план недели считает по
    своему. Значит, единственный источник — модель.
    """
    return load_model.macro_week_load(week, athlete)


def phase_bounds_from_macro(macro: list[dict[str, Any]],
                             season_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Границы фаз — по новой разбивке макро.

    Фаза охватывает недели подряд; её объём и нагрузка — от первой
    недели фазы до последней. Даты — по календарю сезона.
    """
    start = date.fromisoformat(season_plan["season_start_date"])
    bounds: dict[str, dict[str, Any]] = {}
    for phase_id in dict.fromkeys(w["phase"] for w in macro):
        weeks = [w for w in macro if w["phase"] == phase_id]
        if not weeks:
            continue
        first = weeks[0]["season_week"]
        last = weeks[-1]["season_week"]
        kms = [w["run_km"] for w in weeks]
        hours = [w["total_h"] for w in weeks]
        bounds[phase_id] = {
            "week_from": first,
            "week_to": last,
            "start": (start + timedelta(days=7 * (first - 1))).isoformat(),
            "end": (start + timedelta(days=7 * last - 1)).isoformat(),
            "km_low": round(min(kms), 1),
            "km_high": round(max(kms), 1),
            "h_low": round(min(hours), 2),
            "h_high": round(max(hours), 2),
        }
    return bounds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="показать, что получится, ничего не писать")
    parser.add_argument("--apply", action="store_true",
                        help="записать новый макро-план в план сезона")
    parser.add_argument("--from-week", type=int, default=4,
                        help="с какой недели сезона пересобирать (до неё не трогаем)")
    args = parser.parse_args()

    season_plan = json.loads(SEASON_PLAN.read_text(encoding="utf-8"))
    athlete = json.loads(ATHLETE.read_text(encoding="utf-8"))
    templates = quality_session.load_templates(TEMPLATES)
    history = quality_session.load_history(STATE / "quality_history.json")

    start = date.fromisoformat(season_plan["season_start_date"])
    race = next(r for r in season_plan["races"] if r.get("goal_id") == "g_run_spring")
    race_date = date.fromisoformat(race["date"])
    # Горизонт расписания программы — недели ДО гонки.
    #
    # Неделя гонки в макро-план НЕ входит: гонка — событие, а не
    # тренировка, и планировать её не нужно (Кирилл, 01.11.2026). Гонка
    # живёт в календаре сезона, а не в списке недель макро.
    #
    # Расписание считается на N недель ДО гонки: лишняя неделя программы
    # тогда уходит по `EXTRA` в фазу по кругу, как у планировщика, и макро
    # с планировщиком считают одно (тест
    # `test_macro_planner_agreement.py`).
    weeks_to_race = (race_date - start).days // 7
    race_week = weeks_to_race + 1

    macro = build_macro(weeks_to_race, season_plan, athlete)

    controls = control_points_by_week(season_plan)
    print(f"гонка: {race_date} → W{race_week} · недель до старта {weeks_to_race}")
    print(f"неделя гонки в макро не планируется: макро покрывает W1..W{weeks_to_race}")
    print(f"пересобираем с W{args.from_week} (W1..W{args.from_week - 1} не трогаем)")
    print("контрольные точки: "
          + ", ".join(f"W{week} {point['variant_id']}"
                      for week, point in sorted(controls.items())))
    print()

    for entry in macro:
        marker = "  " if entry["season_week"] < args.from_week else "→ "
        week = {"quality_goal": entry["quality_goal"],
                "quality_zones": entry["quality_zones"],
                "quality_minutes": entry["quality_minutes"]}
        control = controls.get(entry["season_week"])
        quality = quality_for(week, templates, history, control)
        goal = quality.get("goal") or "—"
        scale = quality.get("scale") or "—"
        variant = quality.get("variant_id") or "—"
        print(f"{marker}W{entry['season_week']:>2} · {entry['phase']:<13} · "
              f"Дэниэлс ф{entry['daniels_phase']} · "
              f"программная {str(entry['program_week'] or '—'):>2} · "
              f"план из {str(entry['plan_week'] or '—'):>2} · "
              f"{goal:<16} {scale:<7} {variant:<20} · "
              f"{entry['run_km']:>3.0f} км · {entry['target_h']:>5.1f} ч")
    if not args.apply:
        print()
        print("сухо: ничего не записано (--apply — записать)")
        return 0

    old = season_plan.get("weekly_macro") or []
    by_week = {w["season_week"]: w for w in old}
    rebuilt: list[dict[str, Any]] = []

    for entry in macro:
        season_week = entry["season_week"]
        previous = by_week.get(season_week, {})
        if season_week < args.from_week:
            rebuilt.append(previous)
            continue

        control = controls.get(season_week)
        quality = quality_for(entry, templates, history, control)

        new = dict(previous)
        run_km = entry["run_km"]
        # Длинный бег — доля недельного километража.
        long_km = round(run_km * LONG_FRACTION)

        # Форма фазы — из правил Дэниэлса: сколько пробежек в неделю и
        # где живёт ОФП. В форме ОФП идёт **внутрь** пробежек, поэтому
        # отдельных тренировок ОФП в неделе нет.
        form = PHASE_FORM.get(entry["daniels_phase"])
        if form:
            runs = int(form["runs"])
            # Одна из пробежек — длинная, остальные — лёгкие.
            new["easy_runs"] = max(runs - 1, 1)
            new["core"] = ""
            new["_form"] = {
                "runs": runs,
                "ofp_runs": form["ofp_runs"],
                "ofp_minutes": form["ofp_minutes"],
                "ofp_inside_runs": True,
            }
        new.update({
            "season_week": season_week,
            "run_km": run_km,
            "long_km": long_km,
            "phase": entry["phase"],
            "target_h": entry["target_h"],
            # Число сессий — из разбивки недели, а не руками: длинный
            # бег + качественная работа + лёгкие пробежки + вел, плавание
            # и ОФП. Рукописное число рядом с вычисляемым — два разных
            # ответа на один вопрос.
            "sessions_target": (
                _sessions_count(entry, new) if not form
                else _sessions_count_form(entry, new, form)
            ),
            "easy_runs": (
                _easy_runs(_easy_km(new), _busy_windows(new))
                if not form else new["easy_runs"]
            ),
            "_daniels": {
                "daniels_phase": entry["daniels_phase"],
                "program_week": entry["program_week"],
                "plan_week": entry["plan_week"],
                "quality_goal": quality.get("goal"),
                "quality_scale": quality.get("scale"),
                "quality_minutes": entry["quality_minutes"],
                "quality_zones": entry["quality_zones"],
            },
        })
        if quality.get("goal"):
            block = dict(new.get("quality") or {})
            block.update({
                "goal": quality["goal"],
                "scale": quality.get("scale"),
                "variant_id": quality.get("variant_id"),
                "work_m": quality.get("work_m"),
                "label": quality.get("label"),
            })
            new["quality"] = block

        # Нагрузка — пересчётом из структуры: total_h руками не пишется.
        load = recompute_load(new, athlete)
        new["total_h"] = load["total_h"]
        new["_load_breakdown"] = load
        new["_total_h_model"] = {
            "run_h": load["run_h"],
            "bike_h": load["bike_h"],
            "swim_h": load["swim_h"],
            "ofp_h": load["ofp_h"],
            "note": "вычислено моделью нагрузки пайплайна",
        }
        new["run_km_long"] = load["long_km"]
        new["run_km_quality"] = load["quality_work_km"]
        new["run_km_easy"] = round(
            load["run_km"] - load["long_km"] - load["quality_work_km"], 1)
        rebuilt.append(new)

    rebuilt.sort(key=lambda w: w["season_week"])
    season_plan["weekly_macro"] = rebuilt

    # Фазы сезона — по фазам программы Дэниэлса: границы недель и
    # диапазоны объёма/нагрузки пересчитываются под новую разбивку.
    # Иначе фаза в плане и фаза в макро — разные недели.
    phase_bounds = phase_bounds_from_macro(rebuilt, season_plan)
    for phase in season_plan.get("phases") or []:
        bounds = phase_bounds.get(phase["id"])
        if not bounds:
            continue
        phase["_season_week_start"] = bounds["week_from"]
        phase["_season_week_end"] = bounds["week_to"]
        phase["start"] = bounds["start"]
        phase["end"] = bounds["end"]
        phase["run_km_range"] = [bounds["km_low"], bounds["km_high"]]
        phase["load_range_h"] = [bounds["h_low"], bounds["h_high"]]

    # Фаза подводки к гонке — часть четвёртой фазы: беговой сезон —
    # четыре фазы, без дробления.
    # Цель фазы — по её смыслу в программе Дэниэлса: четвёртая фаза
    # подводит к гонке, а не просто снижает объём.
    for phase in season_plan.get("phases") or []:
        objective = PHASE_OBJECTIVE.get(phase.get("id"))
        if objective and phase.get("id") in DANIELS_PHASE_TO_SEASON.values():
            phase["goal"] = objective

    SEASON_PLAN.write_text(
        json.dumps(season_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"записано: {SEASON_PLAN} · недель {len(rebuilt)}")
    for phase_id, bounds in phase_bounds.items():
        print(f"  {phase_id:<14} W{bounds['week_from']}..W{bounds['week_to']} · "
              f"км {bounds['km_low']}..{bounds['km_high']} · "
              f"ч {bounds['h_low']}..{bounds['h_high']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
