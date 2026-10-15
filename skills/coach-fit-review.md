# coach-fit-review

Разбор FIT: 4 уровня (quick, contextual, coaching, lookback).

**Использует:** `lib.analyze`, `lib.metrics`, `lib.parse_fit`, `lib.ask_model`, `lib.coaching_corpus`, `lib/render_html.render_review`.
**Триггеры:** «разбери FIT», «проанализируй», «что скажет тренер», «разбор тренировки».
**Вход:** fit_id, mode.
**Выход:** JSON → self-contained HTML (3-предложения бриф + клик-разворачиваемые детали) + (coaching/lookback) обязательный cited_principle.

## Процедура разбора FIT'а

1. **Pull FIT с Garmin**, если его нет в `raw/running/fit/` или `raw/today/fit/`:
   - snapshot до: `cp sync_state.json ~/.local/share/garmin_tools/snapshots/<ts>/` (по паттерну `personal-data-integrations` skill: snapshot BEFORE).
   - `cd ~/projects/garmin_tools && .venv/bin/python latest_pull.py --sport running --count 3 --out raw/today`
   - restore после: `cp <snap>/sync_state.json .`, tokens НЕ трогай (Garmin их сам обновляет, это legitimate).

2. **Распарси FIT через `parse_fit(..., with_streams=True)`** (schema ≥ 0.5.0):
   - `moving_min`, `splits[]` (по moving records), `hr_drift_bpm` — канон.
   - `stryd_running_dynamics{}` с `*_source` метками (Garmin RD > Stryd fallback).

3. **Перед написанием брифа — валидация данных**: если какая-то ожидаемая метрика вернулась пустой (например `stryd_running_dynamics: {}` при подключённом Stryd), пробей FIT напрямую через `fitparse`:
   ```python
   python3 -c "
   from fitparse import FitFile
   fit = FitFile('path.fit')
   seen = set()
   for msg in fit.messages:
       if msg.name != 'record': continue
       for f in msg.fields:
           if f.value is not None: seen.add((f.name, msg.name))
   for k,m in sorted(seen): print(m, k)
   "
   ```
   Если видишь поле capitalized (`Vertical Oscillation`) — оно от Stryd и fit_inspect.py его потерял в map. Не говори «нет данных» — почини маппинг.

4. **Собрать review-JSON** по шаблону:
   - `brief[3]` по схеме (что / план / действие).
   - `metrics{}` — 8-12 ключевых значений.
   - `sections[]` — разворачиваемые: hr_zones, splits, stryd, pauses, recos.
   - `state/reviews/{date}-{slug}.json` (source of truth).

5. **Рендерить HTML**: `lib/render_html.render_review(review, path)` → `state/reviews/{date}-{slug}.html`.

6. **Smoke-test** для verification: `python tests/test_review_render.py` (берёт последний review HTML по mtime, прогоняет JS-рендер в node.js, проверяет на отсутствие ReferenceError).

7. **В чате — только 3-предложения бриф** + ссылка на HTML. Не wall-of-text.

## Формат разбора: бриф + детали

Разбор FIT'а — **это не поток текста**, а артефакт:

1. **Бриф — 3 предложения по шаблону**, всегда видимы без клика:
   - **(1) Что произошло** — главное число + наблюдение (`85:18 moving, 15.16 km, HR avg 138`)
   - **(2) Соответствие плану** — попадание / промах по target-зоне (`Z2_low ≤138 — промах, 63% в Z3`)
   - **(3) Действие** — одно конкретное на ближайшие 1-2 дня (`завтра 40 мин лёгкой @ метроном 170 bpm`)
   Не пиши в брифе интерпретации Stryd-метрик, сплиты или pause-анализ — это всё для деталей.

2. **Детали — вкладки / секции**, сворачиваемые по клику:
   - Summary (elapsed / moving / pause_total, distance, avg HR / max HR, cadence обоих источников, pace)
   - HR-зоны (по moving records, не session avg)
   - Per-km splits (только moving, иначе km внутри паузы врут)
   - Stryd Running Dynamics (VO / stance / step length / form power), если footpod есть
   - Pause segments (что и где было)
   - Recommendations (linked to cited_principle)
   - Raw chunks / data appendix (если нужен)

3. **Fit-review JSON source-of-truth** в `state/reviews/{date}-{slug}.json`. Рендерится через `lib/render_html.render_review(review, out_path)` → `state/reviews/{date}-{slug}.html`. **Не пиши HTML руками** — обнови JSON и перерендери. Каждый разбор = новый JSON + новый HTML; не аккумулируй текст.

Никогда не выдавай разбор FIT'а сплошным текстом в чат. Скажи: «Соберу разбор в HTML, кидаю файлом.» → пиши review JSON → рендери → отправляй HTML + 3-предложения бриф в чате. Так обзор не раздувается в wall-of-text и пользователь читает детали только когда захочет.

## Запрещено

- Интерпретировать без cited_principle (coaching/lookback → REJECT).
- Писать промпты руками.
- Выдавать разбор FIT'а сплошным текстом в чате — только JSON/HTML/3-предложения бриф.
- **Считать темп/HR-зоны по `total_elapsed_s` или `total_timer_s`.** Garmin elapsed/timer включают OFP-остановки, переходы через дорогу, ожидания. Это сдвигает средний темп на 30–90 сек/км и пушит среднюю ЧСС из Z2 в Z3. Всегда используй `parse_fit(..., with_streams=True)` → `moving_min` / `splits[]` (per-km по moving records) / `hr_drift_bpm` (по moving partition).
- **Делать вид, что данных нет, если `parse_fit` их не отдаёт.** Если поле пустое — это сигнал проверить FIT напрямую через `fitparse`, а не утверждать «баг парсера» или «Garmin не записал». Прямой probe: `python -c "from fitparse import FitFile; ...; [print(f.name, f.value) for f in msg.fields if f.value is not None]"`. Поле может быть lowercase вместо capitalized (Garmin RD vs Stryd), или фильтр в `FitAnalysis.streams` его пропустил. Цена ошибки: ты говоришь пользователю «нет данных», он открывает Garmin UI — видит — и теряет доверие к агенту.

## Правила извлечения и интерпретации

**Pre-flight check (ПЕРЕД любыми числами):**

- Сначала покажи три длительности: `elapsed_min` (по часам), `timer_min` (Garmin `total_timer_s`, исключает autopause ≥ ~5 сек), `moving_min` (только секунды с прогрессом дистанции). Формат: «Разбор без пауз: M:SS (бег). С паузами: M:SS (включая Xм остановок)». Если `elapsed_min - moving_min > 5 мин` — была остановка, не игнорь. Без этого шага сплиты и HR-зоны будут считаться по времени, которое включает простой, и отчёт — мусор.

**Pitfall — pause-detection `moving_s` ловушка.** Простое `sum(t_cur − t_prev)` для moving records считает **секунды паузы как moving time** (потому что gap в `t_sec` большой, но сама запись ещё «беговая»). Корректная формула: `(t_cur − t_prev) == 1` → +1 секунда; gap > 1 → пропустить целиком (runner's last-stride = 1 сек, не больше). Эмпирически `len(moving_records)` ≈ `moving_s`; сверка: `total_elapsed_s − pause_total_dur_s` для прогонов без OFP обычно сходится до ±2 сек с `moving_s`.

1. **Splits — по `parse_fit._splits_per_km(moving_records)`**, не по elapsed-km. Если `splits[i].dur_s / 60 > 10 мин` при нормальном темпе — внутри километра была пауза; не считай темп «медленным», отметь причину (`pause_segments[]` рядом).

2. **HR-зоны — по moving records.** `session.avg_hr` усредняет по elapsed и занижает; доля Z3 > 70% в заявленной лёгкой пробежке = темп выше Z2 (или калибровка браслета).

3. **Half-split / pace drift — по moving midpoint.** Иначе разминка/остановка исказит «первую половину».

4. **Warm-up splits (km 1-2 с avg HR < 70% от main set) — отбрасывай**, не считай частью основной работы.

5. **Pause cause**: если `pause_segments[].dur_s ≥ 60`, спроси у пользователя «это OFP / вода / травма / ожидание?». Без ответа помечай `pause_cause: unknown`. **Не считай split «медленным» пока не узнан cause** — главный источник мусора в разборах: km 2 = 15:43 внутри 9:21 ОФП выглядит как «ужасный темп», а не как пауза внутри километра. Логируй в `state/pause_log.jsonl` строки `{date, fit_id, t_sec, dur_s, cause}` чтобы трекер тренда видел распределение по причинам.

## Каденс и Running Dynamics — два независимых источника, НЕ путать

Сенсоры с разной физикой — цифры напрямую не сравниваются:

- **Watch (FR 965 accelerometer на запястье)**: `cadence_watch` (lowercase FIT). Garmin Running Dynamics (lowercase FIT) считает Vertical Oscillation, Stance Time, Step Length и т.д. по грубому wrist-integrate.
- **Stryd (IMU в ботинке)**: `cadence_stryd` (capitalized FIT). Stryd Vertical Oscillation, Ground Time, Form Power, Air Power, Stryd Power — это **другая** физика (footpod), другие sensor fusion'ы.
- **Fit-parser** (parse_fit 0.5.0): разводит поля — `garmin_vo_cm` vs `stryd_vo_cm`, `garmin_stance_ms` vs `stryd_ground_time_ms`. Источник возвращается в `stryd_running_dynamics.{vo_source,stance_source}`. **Никогда не подставляй нормы/нормали одного источника к цифрам другого** (на одном и том же беге Garmin VO ≈ 10.7 см и Stryd VO ≈ 6.3 см — это **не** противоречие, это разные метрики).

**Какой источник truth для тренда:**
- Garmin RD — то, что в Garmin Connect UI, архив длиннее.
- Stryd footpod — точнее в моменте, но архив только с W2.
- Выбери один для тренда, держись. Не смешивай цифры в одной таблице без аннотации источника.

**Когда Garmin RD недоступен:** `stryd_running_dynamics.{vertical_oscillation_source,stance_source}` = `"stryd"`. Это нормально для FR 965 (иногда профиль не пишет Garmin RD), не баг парсера. В этом случае в отчёте явно отмечай: «Garmin RD отсутствует, цифры от Stryd».

Детальный разбор двух сенсоров и FIT-уровень: `references/garmin-rd-vs-stryd.md`.

## Stryd Running Dynamics (только если footpod есть)

Когда `stryd_running_dynamics` непустой, используй эти поля в `coaching` режиме. Опорные нормы для любителя 35-45 лет, темп 5:00-5:30/км:

- `vertical_oscillation_cm_avg` < 8.0 — отлично, 8-10 норма, > 11 — высоко (тренировать cadence и шаг).
- `stance_time_ms_avg` 220-260 — норма для элиты; 270-300 — норма для любителя; > 320 — усталость или техника «ударной постановки».
- `step_length_m_avg`: на темпе 5:30 → 1.00-1.10 м; 5:00 → 1.10-1.20 м; 4:30 → 1.25-1.35 м. Если длиннее — ты overstriding.
- `form_power_w_avg` — базовая мощность бега; обычно 200-350 Вт на лёгкой, 400+ на темпе. Используй для отслеживания тренда (если form power растёт при том же темпе — это fatigue / form loss).
- `air_power_w_avg` — мощность против ветра; > 15-20 Вт значит в лицо ветер или terrain с боковым участком. Смотри только как контекст.

## Aliases

`garmin-fit-inspect`.