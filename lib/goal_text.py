"""
goal_text.py — канонические тексты целей недели.

Тексты цели недели («Развиваем VO2max», «Сохраняем гонка-темп…») и
масштаба («средняя интенсивность») — это **производные** от каталога
шаблонов, а не рукописные поля. Каталог (`state/workout_templates.json`)
хранит `goal` и `develops` для каждой цели; масштаб переводится по
словарю масштабов.

Почему отдельный модуль, а не строки в макро:

- **макро — производный артефакт.** Пересборка макро по Дэниэлсу меняет
  цель недели (`quality.goal`), а рукописный `goal_text` остаётся от
  прошлой цели: неделя говорит «Развиваем VO2max», а её цель — порог.
  Текст цели обязан переезжать вместе с целью.
- **один источник правды.** Формулировка цели живёт в каталоге, где она
  и живёт вместе со структурой и зонами; в макро — только ссылка.
- **проверяемо.** Guard сверяет `goal_text`/`scale_text`/`develops`
  недели с каталогом: расхождение — нарушение, как и отсутствие
  `variant_id`.

Публичный API:
    goal_text_for(goal, templates) -> str
    scale_text_for(scale) -> str
    week_texts(goal, scale, templates) -> dict
"""
from __future__ import annotations

from typing import Any

# Масштаб работы недели → как он читается в плане.
#
# Словарь живёт здесь, а не в макро: масштаб меняется при пересборке
# (light → medium → heavy), а текст обязан меняться вместе с ним.
SCALE_TEXT = {
    "light": "лёгкая работа",
    "medium": "средняя интенсивность",
    "heavy": "высокая интенсивность",
    "peak": "максимальная",
}


def scale_text_for(scale: str | None) -> str:
    """Масштаб недели → текст. Неизвестный масштаб — пусто, не выдумка."""
    if not scale:
        return ""
    return SCALE_TEXT.get(scale, "")


def goal_text_for(goal: str | None, templates: dict[str, Any] | None) -> str:
    """Цель недели → текст цели из каталога шаблонов.

    Пусто, если цели нет в каталоге: текст цели не выдумывается —
    показывать «Развиваем что-то» хуже, чем ничего.
    """
    if not goal or not templates:
        return ""
    template = templates.get(goal) or {}
    return str(template.get("goal") or "")


def develops_text_for(goal: str | None, templates: dict[str, Any] | None) -> str:
    """Цель недели → что именно развивает (из каталога)."""
    if not goal or not templates:
        return ""
    template = templates.get(goal) or {}
    return str(template.get("develops") or "")


def week_texts(goal: str | None,
               scale: str | None,
               templates: dict[str, Any] | None) -> dict[str, str]:
    """Все тексты недели из её цели и масштаба.

    Возвращает `goal_text`, `scale_text` и `develops` — те же имена, что
    и в макро, чтобы чтение не менялось.
    """
    return {
        "goal_text": goal_text_for(goal, templates),
        "scale_text": scale_text_for(scale),
        "develops": develops_text_for(goal, templates),
    }


def refresh_week_texts(block: dict[str, Any],
                        templates: dict[str, Any] | None) -> dict[str, Any]:
    """Обновить тексты цели недели по её цели и масштабу.

    Тексты, о которых каталог не знает (цели нет в каталоге), не
    затираются: пустой текст хуже прежнего, а отсутствие цели в
    каталоге — дефект данных, который ловит guard.
    """
    if not block:
        return block
    texts = week_texts(block.get("goal"), block.get("scale"), templates)
    for key, value in texts.items():
        if value:
            block[key] = value
    return block


# ───────────────────────────────────────────────────────────── объём недели
#
# Описание недели — про **объём**: сколько бега и в каком масштабе.
# Раньше описание недели бралось из цели качественной работы, и неделя
# с контрольной точкой называлась «Проверяем форму на контрольной
# точке». Это цель одной тренировки, а не недели: по такой подписи
# каждая пробежка недели выглядит подготовкой к тесту, и объём
# недели в описании не читается вовсе.
#
# Масштаб объёма — по недельному километражу относительно диапазона
# фазы: ниже — набор базы, в диапазоне — работа по плану, выше —
# объём выше плана.

def volume_scale_text(run_km: float | None,
                      km_low: float | None,
                      km_high: float | None) -> str:
    """Масштаб объёма недели — по километражу относительно диапазона фазы."""
    if run_km is None or not km_low or not km_high:
        return ""
    if run_km < km_low:
        return "набор базы"
    if run_km > km_high:
        return "объём выше плана"
    return "работа по плану"


def week_volume_text(run_km: float | None,
                     sessions: int | None,
                     km_low: float | None,
                     km_high: float | None) -> str:
    """Описание недели — про объём.

    «Набираем 56 км за 9 тренировок» — это то, что неделя делает.
    Масштаб объёма добавляется, когда он известен: без него читателю
    непонятно, это плановый объём или выше.
    """
    if not run_km:
        return ""
    km = int(round(run_km))
    scale = volume_scale_text(run_km, km_low, km_high)
    if sessions:
        base = f"Набираем {km} км за {sessions} тренировок"
    else:
        base = f"Набираем {km} км"
    return f"{base} · {scale}" if scale else base

