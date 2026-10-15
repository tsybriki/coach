# coach-plan-adjust

Реактивная правка плана: «сегодня перегруз», «заболел», «уезжаю в отпуск».

**Использует:** `lib.weekly_report`, `lib.plan_adjust`, `lib.volume_check`, `lib.garmin_weight`, `lib.plan_runtime` (для регенерации plan-wN после override).
**Триггеры:** «сегодня был перегруз», «я заболел», «уезжаю», «объём не влезает», «я взвесился — X кг».
**Вход:** trigger + reason.
**Выход:** diff JSON + обновлённые state-файлы + **regenerated plan-wN.json + plan-wN.html** для затронутой недели.
**Правило v19:** После override (или auto_zwift toggle, или правки constraints) — регенерировать plan через plan_runtime.generate_plan_with_html(). Один override = один новый plan-wN.json + plan-wN.html.

## Запрещено

- Писать в `state/constraints.json` без подтверждения Кирилла (coach-plan-adjust — единственный, кто это делает).
- Писать промпты руками.

## Aliases

`coaching-running`.