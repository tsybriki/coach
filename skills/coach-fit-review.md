# coach-fit-review

Разбор FIT: 4 уровня (quick, contextual, coaching, lookback).

**Использует:** `lib.analyze`, `lib.metrics`, `lib.ask_model`, `lib.coaching_corpus`.
**Триггеры:** «разбери FIT», «проанализируй», «что скажет тренер».
**Вход:** fit_id, mode.
**Выход:** dict + (coaching/lookback) обязательный cited_principle.

## Запрещено

- Интерпретировать без cited_principle (coaching/lookback → REJECT).
- Писать промпты руками.

## Aliases

`garmin-fit-inspect`.