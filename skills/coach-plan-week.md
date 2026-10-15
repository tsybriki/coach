# coach-plan-week

Собирает план на конкретную W_N.

**Использует:** `lib.plan_runtime.generate_plan_with_html` (entry point), `lib.plan_generate` (внутри), `lib.volume_check`, `lib.render_html` (внутри), `lib.goal_allocator`, `lib.zwift_search` (inline), `lib.zwift_sync` (inline bridge к garmin_tools).
**Триггеры:** «собери план на следующую неделю», «сгенерируй W_N», «поправь план», «регенерируй план на W_N».
**Вход:** week_iso.
**Выход:** **ВСЕГДА** пара артефактов — `state/plan-wN.json` + `state/plan-wN.html`. Не один без другого. **HTML — обязательная часть выхода** (v19).

## Inline Zwift (v16)

plan_generate проверяет `constraints.auto_zwift`:
- enabled=true
- duration_min_max=90
- location=home_stationary_bike
- kinds=bike/brick
- focus_must_have_any: Z2/Z3/intervals/endurance/tempo/threshold

Для каждого слота удовлетворяющего правилу — **inline** вызывает `lib.zwift_search.search(criteria)`, рендерит HTML с candidates (2-4), Кирилл голосует голосом. Это **не** отдельный шаг.

## Правило: HTML — обязательная часть выхода (v19)

Любая команда coach-plan-* (week, season, adjust) **всегда** порождает HTML вместе с JSON.

```
Собери план на W1
  ↓
generate_plan_with_html(season_week=1)
  ↓
state/plan-w1.json + state/plan-w1.html
  ↓
Telegram: "План W1 готов · 7 слотов · 2 Zwift pending · state/plan-w1.html"
```

Нет JSON без HTML. Нет HTML без JSON.

## Запрещено

- Писать промпты руками.
- Редактировать `state/season_plan.json` (только через coach-plan-season).
- Трогать `state/fit_store/`.
- Делать двухшаговый процесс (сначала plan, потом отдельно zwift search).
- Возвращать JSON без HTML или HTML без JSON.

## Aliases (для совместимости со старыми названиями)

`weekly-helper`, `weekly-card-builder`.

## Pre-amble (наследуется всеми coach-* skill'ами)

> Ты строго в рамках athlete.json + season_plan.json + constraints.json + вывод указанной функции. Любой факт вне — откажись или попроси уточнить. В coach-fit-review/coach-fit-trend каждое утверждение требует cited_principle.