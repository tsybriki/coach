# coach-fit-ingest

Загрузка FIT в fit_store/ + матч с control_points.

**Использует:** `lib.fit_ingest`, `lib.parse_fit`.
**Триггеры:** «загрузи FIT за сегодня», «загрузи FIT за <дата>».
**Вход:** путь к FIT-файлу.
**Выход:** запись в `state/fit_store/` + index.json + (если CP-дата) actual_metrics в season_progress.

## Запрещено

- Удалять FIT (только `lib.fit_retention`).
- Писать промпты руками.

## Aliases

`garmin-fit-inspect`.