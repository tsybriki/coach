# coach-plan-week

Собирает план на конкретную W_N.

**Использует:** `lib.plan_generate`, `lib.volume_check`, `lib.render_html`, `lib.goal_allocator`.
**Триггеры:** «собери план на следующую неделю», «сгенерируй W_N», «поправь план».
**Вход:** week_iso.
**Выход:** `plan-wN.json` (state) + self-contained `wN-mobile.html`.

## Запрещено

- Писать промпты руками.
- Редактировать `state/season_plan.json` (только через coach-plan-season).
- Трогать `state/fit_store/`.

## Aliases (для совместимости со старыми названиями)

`weekly-helper`, `weekly-card-builder`.

## Pre-amble (наследуется всеми coach-* skill'ами)

> Ты строго в рамках athlete.json + season_plan.json + constraints.json + вывод указанной функции. Любой факт вне — откажись или попроси уточнить. В coach-fit-review/coach-fit-trend каждое утверждение требует cited_principle.