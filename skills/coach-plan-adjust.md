# coach-plan-adjust

Реактивная правка плана: «сегодня перегруз», «заболел», «уезжаю в отпуск».

**Использует:** `lib.weekly_report`, `lib.plan_adjust`, `lib.volume_check`, `lib.garmin_weight`, `lib.plan_runtime` (для регенерации plan-wN после override).
**Триггеры:** «сегодня был перегруз», «я заболел», «уезжаю», «объём не влезает», «я взвесился — X кг».
**Вход:** trigger + reason.
**Выход:** diff JSON + обновлённые state-файлы + **regenerated plan-wN.json + plan-wN.html** для затронутой недели.
**Правило v19:** После override (или auto_zwift toggle, или правки constraints) — регенерировать план через plan_runtime.generate_plan_with_html(). Один override = один новый plan-wN.json + plan-wN.html.

## UX-представление (v21, см. coach-plan-week)

Регенерированный `state/plan-wN.html` должен следовать **двухэкранной мобильной навигации** (picker → cardWrap), иметь **structure в каждом slot** (warmup/work/cooldown с зонами или reps), и **design tokens** сохранены. Подробности — в `references/plan-html-render.md`.

## Запрещено

- Писать в `state/constraints.json` без подтверждения Кирилла (coach-plan-adjust — единственный, кто это делает).
- Писать промпты руками.

## Aliases

`coaching-running`.