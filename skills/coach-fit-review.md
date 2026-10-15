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

## Каденс — два источника (не игнорь Stryd)

`parse_fit` отдаёт `cadence_avg_watch` (FR 965 / часы), `cadence_avg_stryd` (Stryd footpod, если был), и `cadence_disagreement_abs_mean_spm`. Правила:

- **Каденс в `stryd_running_dynamics` пустой → Stryd footpod не использовался.** Не выдумывай second source из watch-акселерометра.
- **`cadence_disagreement_abs_mean_spm > 2`** на длинной пробежке → либо watch лажает (типично на тредмиле или сильном arm swing), либо Stryd «слепнет». Подсвети это, не используй watch-кад как истину.
- **Stryd «слепнет» в первые секунды после паузы.** Это видно по `stryd_cadence=0` при `cadence_watch>0` в `pause_segments_after` окне (~5 сек). Не считай это за истину о каденсе — нормальный кейс.

## Stryd Running Dynamics (только если footpod есть)

Когда `stryd_running_dynamics` непустой, используй эти поля в `coaching` режиме. Опорные нормы для любителя 35-45 лет, темп 5:00-5:30/км:

- `vertical_oscillation_cm_avg` < 8.0 — отлично, 8-10 норма, > 11 — высоко (тренировать cadence и шаг).
- `stance_time_ms_avg` 220-260 — норма для элиты; 270-300 — норма для любителя; > 320 — усталость или техника «ударной постановки».
- `step_length_m_avg`: на темпе 5:30 → 1.00-1.10 м; 5:00 → 1.10-1.20 м; 4:30 → 1.25-1.35 м. Если длиннее — ты overstriding.
- `form_power_w_avg` — базовая мощность бега; обычно 200-350 Вт на лёгкой, 400+ на темпе. Используй для отслеживания тренда (если form power растёт при том же темпе — это fatigue / form loss).
- `air_power_w_avg` — мощность против ветра; > 15-20 Вт значит в лицо ветер или terrain с боковым участком. Смотри только как контекст.

## Aliases

`garmin-fit-inspect`.