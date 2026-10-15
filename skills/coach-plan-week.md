# coach-plan-week

Собирает план на конкретную W_N.

**Использует:** `lib.plan_generate`, `lib.volume_check`, `lib.render_html`, `lib.goal_allocator`, `lib.zwift_search` (inline), `lib.zwift_sync` (inline bridge к garmin_tools).
**Триггеры:** «собери план на следующую неделю», «сгенерируй W_N», «поправь план».
**Вход:** week_iso.
**Выход:** `plan-wN.json` (state) + self-contained `wN-mobile.html`. Bike/brick-слоты приходят УЖЕ с workout_ref-ами (inline), не отдельной командой.

## Inline Zwift (v16)

plan_generate проверяет `constraints.auto_zwift`:
- enabled=true
- duration_min_max=90
- location=home_stationary_bike
- kinds=bike/brick
- focus_must_have_any: Z2/Z3/intervals/endurance/tempo/threshold

Для каждого слота удовлетворяющего правилу — **inline** вызывает `lib.zwift_search.search(criteria)`, рендерит HTML с candidates (2-4), Кирилл голосует голосом. Это **не** отдельный шаг.

## Запрещено

- Писать промпты руками.
- Редактировать `state/season_plan.json` (только через coach-plan-season).
- Трогать `state/fit_store/`.
- Делать двухшаговый процесс (сначала plan, потом отдельно zwift search).

## Aliases (для совместимости со старыми названиями)

`weekly-helper`, `weekly-card-builder`.

## Pre-amble (наследуется всеми coach-* skill'ами)

> Ты строго в рамках athlete.json + season_plan.json + constraints.json + вывод указанной функции. Любой факт вне — откажись или попроси уточнить. В coach-fit-review/coach-fit-trend каждое утверждение требует cited_principle.