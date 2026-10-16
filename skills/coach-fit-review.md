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

2. **Детали — вкладки / секции**, сворачиваемые по клику. Стандартные kind'ы в `lib/render_html.py`:
   - `hr_zones` — 5 полос Z1..Z5 с долей % и duration в минутах. data: `{"hr_max": 182, "zones": [{name, sec, pct}...]}`. По умолчанию используется HR-profile Кирилла (HRmax 182).
   - `stryd` (через `kv_grid`) — Stryd RD с явной source-меткой. data: `{items: [{label, value, sub, tone}...]}`. Поле VO **обязательно** включает `(Stryd)` или `(Garmin RD)` в sub.
   - `multi_trend` — SVG-line chart с 4-мя нормализованными 0..1 сериями: pace (инвертирован), cadence (Stryd, fallback watch), HR, power. Серые полосы = Garmin autopause-сегменты. Без синтетических km-маркеров (Garmin не пишет их для plain run, и авто-сегментация гадит).
   - `pauses` (через `table`) — каждая пауза с at_km, t (после старта), duration, cause. **Cause спросить у пользователя сразу при pull**, иначе unknown.
   - `recommendations` — список с priority (now/soon/later), text, cited_principle. Recomendations разворачивается по умолчанию (auto-open).

   **NO `km_splits`**: Garmin Connect не пишет interval markers для plain running activities — только для Structured Workouts через Garmin Workout Builder (тогда `laps[]` в FIT содержит явные маркеры). Авто-сегментация по темпу/кад-сигналу даёт шум, не данные. Пока в плане нет interval-тренировок, разбор показывает только то, что Garmin записал. Если пользователю понадобятся интервалы — структурировать через Workout Builder, чтобы FIT имел `lap_trigger="session_end"`-куски.

3. **Fit-review JSON source-of-truth** в `state/reviews/{date}-{slug}.json`. Рендерится через `lib/render_html.render_review(review, out_path)` → `state/reviews/{date}-{slug}.html`. **Не пиши HTML руками** — обнови JSON и перерендери. Каждый разбор = новый JSON + новый HTML; не аккумулируй текст.

Никогда не выдавай разбор FIT'а сплошным текстом в чат. Скажи: «Соберу разбор в HTML, кидаю файлом.» → пиши review JSON → рендери → отправляй HTML + 3-предложения бриф в чате. Так обзор не раздувается в wall-of-text и пользователь читает детали только когда захочет.

## Запрещено

- Интерпретировать без cited_principle (coaching/lookback → REJECT).
- Писать промпты руками.
- Выдавать разбор FIT'а сплошным текстом в чате — только JSON/HTML/3-предложения бриф.
- **Считать темп/HR-зоны по `total_elapsed_s` или `total_timer_s`.** Garmin elapsed/timer включают OFP-остановки, переходы через дорогу, ожидания. Это сдвигает средний темп на 30–90 сек/км и пушит среднюю ЧСС из Z2 в Z3. Всегда используй `parse_fit(..., with_streams=True)` → `moving_min` / `splits[]` (per-km по moving records) / `hr_drift_bpm` (по moving partition).
- **Делать вид, что данных нет, если `parse_fit` их не отдаёт.** Если поле пустое — это сигнал проверить FIT напрямую через `fitparse`, а не утверждать «баг парсера» или «Garmin не записал». Прямой probe: `python -c "from fitparse import FitFile; ...; [print(f.name, f.value) for f in msg.fields if f.value is not None]"`. Поле может быть lowercase вместо capitalized (Garmin RD vs Stryd), или фильтр в `FitAnalysis.streams` его пропустил. Цена ошибки: ты говоришь пользователю «нет данных», он открывает Garmin UI — видит — и теряет доверие к агенту.
- **Автоинференция сегментов по умолчанию.** Не делать в `parse_fit` разделение «интервалов» из pace-сигналов, EMA-фильтров, threshold-логики — Кирилл прямо сказал «давай не усложнять, пока не ищи интервалы сам». Garmin Connect не пишет intervals для plain running FIT (только для structured workouts через Garmin Workout Builder). Используй то, что есть в FIT напрямую — per-km splits (`parse_fit` schema 0.6.0+ уже расширен: на каждый km приходят `cadence_watch_avg`, `cadence_stryd_avg`, `hr_avg`, `hr_max`, `power_avg`). Если пользователь попросит интервалы — спроси заранее формат (одиночные интервалы, repeat groups, темп/jog/recovery) и не делай autodetection, а структурируй через Workout Builder так, чтобы FIT содержал explicit lap-markers.

## Правила извлечения и интерпретации

**Pre-flight check (ПЕРЕД любыми числами):**

- Сначала покажи три длительности: `elapsed_min` (по часам), `timer_min` (Garmin `total_timer_s`, исключает autopause ≥ ~5 сек), `moving_min` (только секунды с прогрессом дистанции). Формат: «Разбор без пауз: M:SS (бег). С паузами: M:SS (включая Xм остановок)». Если `elapsed_min - moving_min > 5 мин` — была остановка, не игнорь. Без этого шага сплиты и HR-зоны будут считаться по времени, которое включает простой, и отчёт — мусор.

**Pause-detection `moving_s` ловушка.** Простое `sum(t_cur − t_prev)` для moving records считает **секунды паузы как moving time** (потому что gap в `t_sec` большой, но сама запись ещё «беговая»). Корректная формула: `(t_cur − t_prev) == 1` → +1 секунда; gap > 1 → пропустить целиком (runner's last-stride = 1 сек, не больше). Эмпирически `len(moving_records)` ≈ `moving_s`; сверка: `total_elapsed_s − pause_total_dur_s` для прогонов без OFP обычно сходится до ±2 сек с `moving_s`.

1. **HR-зоны — по moving records.** `session.avg_hr` усредняет по elapsed и занижает; доля Z3 > 70% в заявленной лёгкой пробежке = темп выше Z2 (или калибровка браслета).

2. **Half-split / pace drift — по moving midpoint.** Иначе разминка/остановка исказит «первую половину».

3. **Pause cause**: если `pause_segments[].dur_s ≥ 60`, спроси у пользователя «это OFP / вода / травма / ожидание?». Без ответа помечай `pause_cause: unknown`. Логируй в `state/pause_log.jsonl` строки `{date, fit_id, t_sec, dur_s, cause}` чтобы трекер тренда видел распределение по причинам.

**Per-km splits НЕ вычислять автоматически для разбора.** Garmin не пишет interval markers для plain running — вычисление per-km-mean из per-second records = synthetic data, не реальность. Это явный запрет (см. «Что НЕ должно быть в разборе» в самом верху).

## Каденс и Running Dynamics — два независимых источника, НЕ путать

Сенсоры с разной физикой — цифры напрямую не сравниваются:

- **Watch (FR 965 accelerometer на запястье)**: `cadence_watch` (lowercase FIT). Garmin Running Dynamics (lowercase FIT) — wrist-integrate. Требует нагрудного ремня для полного RD-профиля.
- **Stryd (IMU в ботинке)**: `cadence_stryd` (capitalized FIT). Stryd Vertical Oscillation, Ground Time, Form/Air/Stryd Power — footpod fusion.

**Source-of-truth: STRYD** (per Кирилл, 2026-10-15: «Берём stryd. Garmin rd требует нагрудного ремня. Я не всегда его беру»). Схема `parse_fit 0.5.0`:
- `_pick("stryd_*", "garmin_*")` — Stryd preferred, Garmin RD fallback.
- `stryd_running_dynamics.{vertical_oscillation_source,stance_source}` = `"stryd"` сейчас.
- `_garmin_*` поля всё равно возвращаются для cross-source sanity (НЕ смешивать цифры в одной таблице без аннотации источника).

**Главный trap**: `_pick` и `vo_source_label`/`stance_source_label` — две независимые переменные. Если переключаешь приоритет — обновляй ОБЕ строчки синхронно. Баг в 0.5.0-rc1: переключил `_pick`, но забыл про resolution-блок ниже, в итоге 14 окт FIT отдавал Garmin RD хотя Stryd 6.5 см уже был. Исправлено: `vo_vals = vo_stryd_raw or vo_garmin`, не наоборот.

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