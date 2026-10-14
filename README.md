# coach

Coaching machinery for Kirill. Архитектура и реализация.

- Полная архитектура: `ARCHITECTURE.html` (открывается в браузере / Telegram preview).
- JSON-исходник: `architecture.json`.
- Phase 1 issue: https://github.com/tsybriki/coach/issues/1

## Структура

- `lib/` — Python toolkit (вся арифметика, единственная обёртка над моделью)
- `state/` — JSON-файлы правды (athlete, season_plan, constraints, ...)
- `skills/` — переименованные skill'ы (схема `coach-<area>-<verb>`)
- `hooks/` — Hermes hooks (например `load_athlete_context.py`)
- `tests/` — тесты

## Phase 1

Скелет всей машинерии. Без реальных интеграций (Garmin/API/бот — заглушки).

## v13

Версия архитектуры, зафиксированная перед реализацией.