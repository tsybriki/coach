# coach-fit-trend

Lookback по control_points и метрикам. Без FIT, через season_progress.

**Использует:** `lib.analyze(mode='lookback')`, `lib.metrics`, `lib.render_html`.
**Триггеры:** «как я бегал 3 месяца назад», «тренд каденса», «как TE менялся за 8 недель».
**Вход:** N weeks, опц. goal_id для фильтра.
**Выход:** trends[] + render в HTML.

## Запрещено

- Смотреть в FIT старше 14 дней (удалены fit_retention.py). Использовать actual_metrics из season_progress.
- Писать промпты руками.

## Aliases

`garmin-running-analysis`, `coach-trend-lookback`.