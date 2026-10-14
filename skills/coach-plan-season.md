# coach-plan-season

Сезонное планирование и перепланирование. Несколько целей, control_points, объём.

**Использует:** `lib.season_replan`, `lib.goal_allocator`, `lib.render_html`.
**Триггеры:** «перепланируй сезон», «replan», «смени цель», «как поделить часы».
**Вход:** reason + новое состояние.
**Выход:** новый `season_plan.json` + `decisions/<date>-replan.json` + архив старого.

## Запрещено

- Менять goals[] без явной команды Кирилла.
- Авто-выбирать между candidates goal_allocator (только Кирилл).
- Писать промпты руками.

## Aliases

`plan-present`.

## Pre-amble

> см. coach-plan-week