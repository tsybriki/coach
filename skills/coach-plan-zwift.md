# coach-plan-zwift

Поиск Zwift-тренировок по критериям + импорт в Garmin Connect.

**Использует:** `lib.zwift_search`, `lib.zwift_sync` (bridge к `garmin_tools/zwift_sync.py`), `lib.render_html`.
**Триггеры:** «нужна 45-мин Z2-вело», «найди Zwift workout», «что-нибудь в Z3 на завтра».
**Вход:** criteria (discipline/duration_min/zones/workout_type/tags) ИЛИ free_text.
**Выход:** candidates[2-4] → после выбора Кирилла → Garmin Connect workout → `workout_ref` в plan-wN.

## Алгоритм

1. Парсинг free_text → criteria (если голосовое).
2. Скрапинг `whatsonzwift.com/workouts/` через `lib.zwift_search.search()`.
3. Ранжирование (`_rank` score): discipline + duration + zones overlap + tags overlap.
4. Возврат **2-4 candidates**, не больше (НЕ «так и штук»).
5. Рендер HTML с cards (заголовок, длительность, описание, ссылка, кнопки голосования).
6. Кирилл говорит «беру 2» → `zwift_sync.sync_to_garmin(url)` → Garmin Connect.
7. `workout_ref = {url, garmin_workout_id, scheduled_date}` записывается в `plan-wN.json`.
8. После выполнения FIT попадает в `fit_ingest` → `season_progress`.

## Запрещено

- Выдумывать workouts вручную — только через `whats_on_zwift.com`.
- Возвращать > 4 candidates. Кирилл не выбирает из 20.
- Писать промпты руками.

## Aliases

Нет (новый skill).