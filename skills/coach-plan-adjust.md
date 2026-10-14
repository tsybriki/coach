# coach-plan-adjust

Реактивная правка плана: «сегодня перегруз», «заболел», «уезжаю в отпуск».

**Использует:** `lib.weekly_report`, `lib.plan_adjust`, `lib.volume_check`, `lib.garmin_weight`.
**Триггеры:** «сегодня был перегруз», «я заболел», «уезжаю», «объём не влезает», «я взвесился — X кг».
**Вход:** trigger + reason.
**Выход:** diff JSON + обновлённые state-файлы.

## Запрещено

- Писать в `state/constraints.json` без подтверждения Кирилла (coach-plan-adjust — единственный, кто это делает).
- Писать промпты руками.

## Aliases

`coaching-running`.