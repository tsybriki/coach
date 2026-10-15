# coach-fit-review

Разбор FIT: 4 уровня (quick, contextual, coaching, lookback).

**Использует:** `lib.analyze`, `lib.metrics`, `lib.parse_fit`, `lib.ask_model`, `lib.coaching_corpus`.
**Триггеры:** «разбери FIT», «проанализируй», «что скажет тренер».
**Вход:** fit_id, mode.
**Выход:** dict + (coaching/lookback) обязательный cited_principle.

## Запрещено

- Интерпретировать без cited_principle (coaching/lookback → REJECT).
- Писать промпты руками.
- **Считать темп/HR-зоны по `total_elapsed_s` или `total_timer_s`.** Garmin elapsed/timer включают OFP-остановки, переходы через дорогу, ожидания. Это сдвигает средний темп на 30–90 сек/км и пушит среднюю ЧСС из Z2 в Z3. Всегда используй `parse_fit(..., with_streams=True)` → `moving_min` / `splits[]` (per-km по moving records) / `hr_drift_bpm` (по moving partition).

## Правила извлечения и интерпретации

1. **Всегда сообщай три длительности**: `elapsed_min` (по часам), `timer_min` (Garmin timer time, исключает autopause ≥ ~5 сек), `moving_min` (только секунды с прогрессом дистанции). Если `elapsed_min - moving_min > 5 мин` — в тренировке была остановка. Формат: «Разбор без пауз: M:SS (бег). С паузами: M:SS (включая Xм остановок)».

2. **Splits — по `parse_fit._splits_per_km(moving_records)`**, не по elapsed-km. Если `splits[i].dur_s / 60 > 10 мин` при нормальном темпе — внутри километра была пауза; не считай темп «медленным», отметь причину (`pause_segments[]` рядом).

3. **HR-зоны — по moving records.** `session.avg_hr` усредняет по elapsed и занижает; доля Z3 > 70% в заявленной лёгкой пробежке = темп выше Z2 (или калибровка браслета).

4. **Half-split / pace drift — по moving midpoint.** Иначе разминка/остановка исказит «первую половину».

5. **Warm-up splits (km 1-2 с avg HR < 70% от main set) — отбрасывай**, не считай частью основной работы.

6. **Pause cause**: если `pause_segments[].dur_s ≥ 60`, спроси у пользователя «это OFP / вода / травма / ожидание?». Без ответа помечай `pause_cause: unknown` в coach-логе.

## Aliases

`garmin-fit-inspect`.