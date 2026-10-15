# coach-plan-season

Сезонное планирование и перепланирование. Несколько целей, control_points, объём.

**Использует:** `lib.season_replan`, `lib.goal_allocator`, `lib.render_html`, `lib.plan_runtime` (для регенерации планов на затронутые W_N).
**Триггеры:** «перепланируй сезон», «replan», «смени цель», «как поделить часы».
**Вход:** reason + новое состояние.
**Выход:** новый `season_plan.json` + `decisions/<date>-replan.json` + архив старого + **regenerated plans для затронутых W_N** (каждая с JSON+HTML).
**Правило v19:** После replan нужно регенерировать планы на затронутые сезонные недели — каждая регенерация порождает пару `plan-wN.json + plan-wN.html`.

## Запрещено

- Менять goals[] без явной команды Кирилла.
- Авто-выбирать между candidates goal_allocator (только Кирилл).
- Писать промпты руками.

## Aliases

`plan-present`.

## Pre-amble

> см. coach-plan-week