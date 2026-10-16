"""
step_builder.py — построение структуры тренировки для каждого subkind.

Два стиля:
- by_hr (по пульсу): [warmup Z1/10min, work Z2/45min, cooldown Z1/10min]
- by_pace (по темпу): [warmup Z1/10min, repeat(1min hard + 4min easy) x5, cooldown Z1/10min]

Структура одного step:
{
  'phase': 'warmup'|'work'|'recovery'|'cooldown'|'set'|'rest'|'break'|'transition',
  'duration_min': int,
  'zone': 'Z1'|'Z2'|'Z2L'|'Z3'|'Z4'|'Z5',
  'pace_min_per_km': '4:30'|'5:00'|None,
  'reps': int,           # только для set-блоков
  'set_repeats': list[step],  # для set-блоков
  'notes': str,
}
"""
from __future__ import annotations

from typing import Optional


def _z(mins: int, zone: str, phase: str, notes: str = "", pace: str | None = None) -> dict:
    return {
        "phase": phase,
        "duration_min": mins,
        "zone": zone,
        "pace_min_per_km": pace,
        "reps": None,
        "set_repeats": None,
        "notes": notes,
    }


def _r(reps: int, set_steps: list[dict], notes: str = "") -> dict:
    return {
        "phase": "set",
        "duration_min": sum(s["duration_min"] for s in set_steps) * reps,
        "zone": None,
        "pace_min_per_km": None,
        "reps": reps,
        "set_repeats": set_steps,
        "notes": notes,
    }


def build_structure(subkind: str, duration_min: int, focus: str = "", phase_id: str = "") -> list[dict]:
    """
    Возвращает list[step] для каждого subkind.
    Использует duration_min как общую длительность, делит на warmup/work/cooldown.
    """
    if subkind == "easy":
        if duration_min <= 30:
            return [_z(duration_min, "Z2L", "work", "Лёгкий бег. Дыхание носовое.")]
        elif duration_min <= 60:
            return [
                _z(5, "Z1", "warmup", "Разминка."),
                _z(duration_min - 15, "Z2L", "work", "Основная часть. Носовое дыхание."),
                _z(10, "Z1", "cooldown", "Заминка."),
            ]
        else:
            return [
                _z(10, "Z1", "warmup"),
                _z(duration_min - 25, "Z2L", "work", "Лёгкий длинный бег."),
                _z(15, "Z1", "cooldown"),
            ]

    if subkind == "long_Z2":
        warmup = 10
        cooldown = 15
        work = duration_min - warmup - cooldown
        return [
            _z(warmup, "Z1", "warmup", "Разминка 10мин Z1."),
            _z(work, "Z2L", "work",
              f"Длинный бег {work}мин Z2L. Дыхание носовое, темп комфортный. "
              f"Если HR > 145 — снизить темп. Источник: spring-10k-2027-v2.md."),
            _z(cooldown, "Z1", "cooldown"),
        ]

    if subkind == "easy_progression":
        return [
            _z(10, "Z1", "warmup", "Разминка."),
            _z(25, "Z2", "work", "Easy 5К. HR ~135, темп 5:30-5:00/км."),
            _z(3, "Z3", "work", "Прогрессия 1К: 5:00 → 4:30/км."),
            _z(15, "Z1", "cooldown"),
        ]

    if subkind == "easy_long":
        return [
            _z(10, "Z1", "warmup"),
            _z(duration_min - 25, "Z2", "work", f"Easy long {duration_min-25}мин Z2."),
            _z(15, "Z1", "cooldown"),
        ]

    if subkind == "key_intervals":
        warmup = 12
        cooldown = 10
        return [
            _z(warmup, "Z1", "warmup", "Разминка с ускорениями 2×100м str."),
            _r(5, [
                    _z(4, "Z3", "work", "400м @ 4:00/км (~1:36)."),
                    _z(2, "Z1", "recovery", "Jog 200м. Восстановить дыхание."),
                ], "Интервалы Z3. Источник: spring-10k-2027-v2.md."),
            _z(cooldown, "Z1", "cooldown"),
        ]

    if subkind == "intervals":
        warmup = 15
        cooldown = 10
        return [
            _z(warmup, "Z1", "warmup", "Разминка + ускорения 3×100м."),
            _r(5, [
                    _z(4, "Z3", "work", "1К @ 4:30/км."),
                    _z(2, "Z1", "recovery", "Jog 200м @ Z1."),
                ], "Интервалы Z3. 5×1К @ 4:30."),
            _z(cooldown, "Z1", "cooldown"),
        ]

    if subkind == "tempo":
        warmup = 12
        cooldown = 8
        return [
            _z(warmup, "Z1", "warmup"),
            _z(duration_min - warmup - cooldown, "Z3", "work",
              f"Tempo {duration_min-warmup-cooldown}мин @ 4:50-5:00/км. HR 145-155."),
            _z(cooldown, "Z1", "cooldown"),
        ]

    if subkind == "race_pace":
        warmup = 15
        cooldown = 10
        return [
            _z(warmup, "Z1", "warmup", "Разминка + ускорения 2×200м."),
            _z(duration_min - warmup - cooldown, "Z4", "work",
              f"Race-pace {duration_min-warmup-cooldown}мин @ 4:20/км. HR 155-165."),
            _z(cooldown, "Z1", "cooldown"),
        ]

    if subkind == "stationary_z2":
        return [
            _z(5, "Z1", "warmup", "Разминка на станке. Каденс 80-85."),
            _z(duration_min - 15, "Z2", "work", "Стабильное Z2. Каденс 85-90. Можно Zwift watch-симулятор."),
            _z(10, "Z1", "cooldown", "Заминка."),
        ]

    if subkind == "stationary_z3":
        return [
            _z(5, "Z1", "warmup"),
            _z(duration_min - 15, "Z3", "work", "Z3 tempo на станке."),
            _z(10, "Z1", "cooldown"),
        ]

    if subkind == "long_z2":
        warmup = 10
        cooldown = 10
        return [
            _z(warmup, "Z1", "warmup"),
            _z(duration_min - 20, "Z2L", "work", f"Длинный вел Z2L {duration_min-20}мин. Zwift watch-сессия."),
            _z(cooldown, "Z1", "cooldown"),
        ]

    if subkind == "bike_run":
        return [
            _z(5, "Z1", "warmup_bike"),
            _z(35, "Z2", "work_bike", f"Вел Z2 35мин."),
            _z(2, "transition", "T2", "Снять велообувь, надеть кроссовки."),
            _z(15, "Z3", "work_run", "Бег Z3 15мин @ race_pace_under_fatigue."),
            _z(5, "Z1", "cooldown"),
        ]

    if subkind == "control_point":
        return [
            _z(15, "Z1", "warmup"),
            _z(20, "Z5", "work", "All-out работа на время."),
            _z(10, "Z1", "cooldown"),
        ]

    return [_z(duration_min, "Z2", "work", "Steady работа.")]


def ofp_structure(subkind: str, duration_min: int) -> list[dict]:
    """
    OFP-сессия (core/мобилити). kind='ofp'. structure — список упражнений.
    """
    if subkind == "core":
        return [
            {"phase": "warmup", "exercise": "Мобилилити: hip openers, glute bridge 2×15.",
             "duration_min": 5, "notes": "Активация ягодиц."},
            {"phase": "main", "set":
                    {"name": "Core circuit x2 rounds",
                     "exercises": [
                         {"name": "Планка", "reps": "3×45с", "rest": "30с"},
                         {"name": "Медведи на коленях", "reps": "2×12/стор", "rest": "30с"},
                         {"name": "Bird-dog", "reps": "3×10/стор", "rest": "30с"},
                         {"name": "Glute bridge", "reps": "3×15", "rest": "30с"},
                         {"name": "Гиперэкстензия", "reps": "2×15", "rest": "30с"},
                     ]},
                 "duration_min": 20, "notes": "Акцент на заднюю цепь (превентивно от защемления спины)."},
            {"phase": "cooldown", "exercise": "Растяжка 5мин. Без агрессии на грушевидную.",
             "duration_min": 5, "notes": "Spring-10k-2027-v2.md core program."},
        ]

    if subkind == "mobility":
        return [
            {"phase": "main", "exercise": "Катание foam-roll 2-3 мин/сторона + динамическая растяжка.",
             "duration_min": duration_min, "notes": "Восстановление."},
        ]

    return [{"phase": "main", "exercise": "OFP-сессия", "duration_min": duration_min, "notes": subkind}]