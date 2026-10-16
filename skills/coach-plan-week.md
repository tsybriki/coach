# coach-plan-week

Собирает план на конкретную W_N и **всегда** порождает пару JSON+HTML.

**Использует:** `lib.plan_runtime.generate_plan_with_html` (entry point), `lib.plan_generate` (внутри), `lib.volume_check`, `lib.render_html`, `lib.step_builder` (структура слотов), `lib.goal_allocator`, `lib.zwift_search` (inline), `lib.zwift_sync` (inline bridge к garmin_tools).
**Триггеры:** «собери план на следующую неделю», «сгенерируй W_N», «поправь план», «регенерируй план на W_N».
**Вход:** `season_week: int | "W1" | "2026-W42"`.
**Выход:** **ВСЕГДА** пара — `state/plan-wN.json` + `state/plan-wN.html`.

## Правила UX-представления (v27, hard preferences)

Пользователь явно требует двухэкранную mobile-first навигацию, как в референсном файле `state/w1-mobile-reference.html` (точная копия `~/.hermes/coach/arch/references/w1-mobile.html`, который Кирилл дал как эталон). **Этот файл — spec**, а не вдохновение. Сохраняй тёмные design tokens (`--bg:#0f1115`, `--accent:#7aa2ff`, и т.д.). Сменить палитру — отдельное обсуждение, не делай сам.

**Когда правишь навигацию в plan-wN.html — читай референс построчно, копируй механизм.**

Конкретно: JS в `state/w1-mobile-reference.html` (строки 212-545) — это рабочий picker + cardWrap + showSlot/picker + pushState/popstate + buildPicker + classList('hidden'/'visible'). Копируй **именно эту логику** в `lib/render_html.py`, включая `init()` async-эквивалент (в нашем случае — sync `loadPlan()` из inline `<script type="application/json" id="plan-data">`). Не пытайся заменить pushState/JS на CSS-only `:target` или inline `onclick` — Кирилл перепроверил 4 раза и 4 раза не работало, потому что мой preview Telegram WebView не запускает ни inline JS handlers, ни CSS :target в случаях, которые я считал «очевидными». Референсный файл работает именно с этим стеком.

**Структура HTML (v27):**

1. **Экран 1 — picker (список compact-карточек).** Каждая карточка показывает:
   - Иконку по `kind` (run→🏃, bike→🚴, swim→🏊, ofp→💪, brick→🔄, control_point→🎯).
   - День + время + длительность в monospace справа.
   - **Главную идею тренировки** — короткое название (1 строка). Берётся из `slot.name` или `_slot_idea()` fallback на focus+subkind.
   - **Не показывай** tag с цветом по kind и не показывай детальную структуру — только идею. Детали разворачиваются на втором экране.
   - focus-пилюля под именем (`🎯 Z2` teal pill) — если есть.

2. **Экран 2 — cardWrap (детальная карточка).** Активируется тапом на compact-карточку через `document.querySelectorAll('.slot').forEach(addEventListener('click', showSlot))`. Содержит:
   - Top-bar с back-button `← к выбору` (`id="backBtn"`, `history.back()` если state.page==='card', иначе showPicker).
   - Headline: иконка вида + `slot.name` (класс `.card-headline` с `.card-kind-icon` + `.card-name`) + tag справа (N шагов).
   - Subtitle: `день · время · N мин`.
   - Meta-row: 📍 location, 🎯 focus (с классом `focus-pill focus-Z2`/Z3/etc — цвет по зоне), subkind, ⏳ Zwift pending.
   - **🎒 Что взять (inventory)** — генерируется через `_inventory_for()` по location/kind/subkind.
   - **Структура тренировки** — `<h3>Структура тренировки</h3>` + `<ol class="structure-list">` с `<li class="step">` (для phase warmup/work/cooldown) или `<li class="step step-set">` (для set_repeats) или `<li class="step step-ofp">` (для упражнений). Каждый step содержит phase, duration, zone, pace, notes.

3. **Totals-карточка сверху в picker** (как было в v18):
   - Три ячейки: planned / target / delta. Delta зелёный если `≥0`, оранжевый если `<0`.
   - HR-зоны: `zones-grid` с 2-колоночной сеткой `Z1=110-125`, `Z2L=125-140`, `Z2=125-145`, и т.д.

4. **Phase-card** после totals: «Фаза · run_base · 12.10 → 18.10 · target 5ч/нед · goal g_run_spring».

5. **CP-card** (если есть control_points_in_range): «В этой неделе: 5К на время, 3К на время».

6. **slots-header** + **slots-sub**: «Тренировки · 8 шт» + «тап → детали» (перед списком слотов).

**Правило v27:** каждый slot в `state/plan-wN.json` ОБЯЗАН иметь поле `structure: list[step]`. Без него карточка бесполезна. `plan_generate` вызывает `lib.step_builder.build_structure()` для run/bike/swim/brick и `lib.step_builder.ofp_structure()` для ofp. **Не пропускай это**.

## Тренировочная неделя = воскресенье → суббота (v28)

`season_start_date = "2026-10-11"` (Sun). W1 = 11-17 окт, W48 = 5-11 сен 2027, W49 = 12-18 сен 2027 (заканчивается race_tri). `horizon.end = "2027-09-18"`, `season_week_count = 49`.

**Race events всегда в воскресенье**, поэтому race_run 18 апр = W28 (а не W27), race_tri 12 сен = W49. Это нормально — race-неделя стартует с воскресенья-event'а, и ворота «event» находятся в начале недели.

`lib/season_week.py:season_week_to_iso(week)` берёт **ПОНЕДЕЛЬНИК** недели (`week_start + timedelta(days=1)`), не воскресенье. Иначе W1 дал бы iso 2026-W41 (Sun 11 окт) вместо 2026-W42 (Mon 12 окт) — понедельник сезон-недели всегда «правильная» iso-неделя. Не «чини» это обратно.

Все phase `start/end` сдвинуты на -1 день относительно старого W-Mon-старта. `athlete.weight_history[*].date` тоже сдвигается если она совпадает со старым season_start. `season_progress.json` notes для W1: «W42 = 11-17 окт. Старт фазы run_base (вс-суб).»

**Pitfall:** не пытайся сохранить «W27 = race_run» при Sun-старте — это невозможно, race-дата всегда Sun, а финальный тапер (run_taper) заканчивается в субботу. Если пользователь говорит «race не та неделя», значит season_start нужно сдвинуть ещё на 1 неделю назад (отдельный разговор, не делай сам).

## Plan как факт-лог (v29)

Кирилл иногда говорит «перепиши расписание W1 как факт того что я делал» — то есть `state/plan-wN.json` становится **snapshot завершённой недели** с реальными цифрами, а не плановый.

Схема `slot.actual` (опционально, не у всех слотов):

```json
{
  "actual": {
    "distance_km": 9.4,
    "time_sec": 2850,
    "avg_pace": "5:03",
    "avg_hr": 148,
    "rpe": 7,
    "notes": "Прогрессия по плану. Источник: spring-10k-2027-v2.md W1 key session."
  }
}
```

И `plan.is_actual_log: true` (флаг для renderCard/buildPicker). Поля:
- `actual.distance_km` (float) — если есть, кило́метраж
- `actual.time_sec` (int) — если есть, рендерится как `M:SS`
- `actual.avg_pace` (str, "5:03") — темп/км
- `actual.avg_hr` (int) — пульс средний
- `actual.rpe` (int 1-10) — субъективная нагрузка
- `actual.notes` (str) — комментарий Кирилла

Когда `is_actual_log: true`:
- `renderCard` показывает зелёный блок «✅ Факт: 9.4К · 47:30 · темп 5:03/км · HR avg 148 · RPE 7/10» + notes
- `buildPicker` totals **всегда** показывает planned/expected/delta (НЕ переключается на «сессий/факт/объём» — отменено в v33). Факт-цифры показываются только в actual-блоке карточки.
- `buildPicker` summary-card с `plan.summary.actual: list[str]` — буллеты по каждой сессии
- `buildPicker` slot-dur помечается `✓` если `slot.actual` есть
- `buildPicker` slot-class получает `slot-completed` (зелёный бордер)
- `buildPicker` plan-title помечается `actual-badge` «✅ Фактический лог»

**Pitfall — FIT-файлы могут отсутствовать:** `state/fit_store/index.json` может быть пуст даже при включённом cron-синке. Перед тем как «достать пробежки и посмотреть на стресс-левел» — проверь `state/fit_store/index.json` и `~/.hermes/coach/runs/`. Если FIT за нужный период нет, **анализируй нагрузку через `slot.actual`** в plan-wN.json (RPE, distance, time, HR avg) — это твой fallback, не итерируй в попытках загрузить FIT.

## Basis-aware rendering структуры (v35-v36) — для модели-наполнителя

Структура тренировки в `slot.structure[]` имеет поле `basis` которое определяет **что показывать** в рендере:

- `step.basis: "time"` (default) — показываем `duration_min` + опционально `hr_target`. Пример: `Z3 work 1мин HR 165` или `Z2 work 25мин @ 5:00/км`.
- `step.basis: "distance"` — показываем `distance_m` + `pace_min_per_km`, **НЕ выводим** `duration_min` (время обманчиво, 150м @ 3:40 может занять 0:32, а 250м трусцой 1:25-1:30 в зависимости от дня). Пример: `Z4 work 150м @ 3:40/км`.

**Top-level set** рендерит header **ТОЛЬКО** `label × N` — **без автоматического умножения work.distance_m × reps в total объём** (v36: Кирилл «зачем умножил 6 на 150? не пиши объём, просто интервалы»). Если модель хочет показать объём — кладёт его в `step.label` (например `"6×150+250 = 2.4К"`) или в отдельное поле.

**Sub-шаги внутри set (set_repeats[])** и **top-level шаги** (warmup/cooldown/work) — **никогда** не показывают `notes` (v36: Кирилл «подпись внизу уродская, убери, чтобы больше никуда не попадала»). Модель может класть notes, они тихо игнорируются. Это **полная** отмена notes — не только в sub-шагах, как было в v35.

**Поля структуры:**
- `step.phase: "warmup" | "work" | "cooldown" | "set" | "main"` — тип шага
- `step.basis: "time" | "distance"` (default `time`) — на чём базируется длительность
- `step.duration_min: int` — обязательно если `basis="time"`
- `step.distance_m: int` — обязательно если `basis="distance"`
- `step.hr_target: int` — опционально (число, для HR-only сессий)
- `step.pace_min_per_km: str` — опционально ("3:40" или "5:00→4:30")
- `step.zone: str` — Z1..Z6
- `step.notes: str` — НЕ рендерится (v36, полная отмена)
- `step.reps: int` — только для `phase: "set"`
- `step.set_repeats: list[step]` — sub-шаги внутри set
- `step.label: str` — заголовок set'а (default "set"). Модель кладёт: `"интервалы"`, `"ОФП circuit"`, `"длинная"`, и т.д. Появляется в `<span class="step-phase">`

**Пример time-based set (HR-сессия):**
```json
{
  "phase": "set", "label": "set", "reps": 6, "duration_min": 18,
  "set_repeats": [
    {"phase": "work", "duration_min": 1, "zone": "Z3", "hr_target": 165},
    {"phase": "recovery", "duration_min": 2, "zone": "Z2", "hr_target": 135}
  ]
}
```

**Пример distance-based set (стадионные интервалы):**
```json
{
  "phase": "set", "label": "интервалы", "basis": "distance", "reps": 6,
  "set_repeats": [
    {"phase": "work", "basis": "distance", "distance_m": 150, "zone": "Z4", "pace_min_per_km": "3:40"},
    {"phase": "recovery", "basis": "distance", "distance_m": 250, "zone": "Z1", "pace_min_per_km": "5:45"}
  ]
}
```

Header рендерится: `интервалы × 6` (без `900м` или любого auto-multiplied total).

## Никогда не смешивать kind в одном слоте (v32)

Каждый `slot` имеет ровно ОДИН kind. Запрещено:
- `kind: "brick"` с run+OFP в одной сессии через одну карточку
- Один slot содержит шаги разных видов (бег + OFП упражнения)

Если Кирилл говорит «в пятницу бег + OFП» — это **два отдельных слота**:
- `kind: "run"`, `id: "пт-tempo_5k"`, `time: "18:30"` — беговая карточка
- `kind: "ofp"`, `id: "пт-ofp_12"`, `time: "19:00"` — ОФП карточка

В picker обе видны как отдельные кнопки. Карточка бега показывает только беговую structure, карточка OFП — только OFП exercises. Кирилл: «В беге должен быть бег, внутри этой карточки должно было так прям и читаться».

`plan.summary.totals` для факт-лога пишет `6 сессий (6 факт + 2 план) / 5.9ч` — kind не упоминается в totals, разные kind одного дня считаются как 2 сессии.

## Totals-логика (v33-v34) — фиксированная

Totals **всегда** показывает 3 ячейки, считаются в `buildPicker` JS на лету (не из `plan.totals`):

- **planned** = `sum(s.duration_min for s in plan.slots) / 60` — суммарная длительность всех слотов недели
- **expected** = `plan.phase.hours_per_week_target` — target из долгосрочного плана (run_base=5ч, run_build=7ч, race_taper=4ч, etc.)
- **delta** = `planned - expected`. Зелёный (`var(--good) #7ee787`) если `≥ 0`, красный (`var(--warn) #ff9b6a`) если `< 0`

**Лейблы — английские** (planned/expected/delta). Русские слова (`план-неделя`/`долгосрочн`/`дельта`) обрезаются в плашке и Кирилл это заметил — не использовать.

В actual-режиме (is_actual_log=true) **тот же** показ planned/expected/delta, а не `сессий/факт/объём`. Факт-цифры показываются в `renderCard` actual-блоке (зелёный ✅ Факт: distance/time/pace/HR/RPE), а не в totals.

## Добавление планового слота в факт-лог неделю (v30-v31)

Если Кирилл говорит «в пятницу у меня нет тренировки, сгенери» — это **не новая генерация плана** (которая перезапишет actual-лог). Это:

1. Загрузить `state/plan-wN.json`
2. Добавить `slot` с `id="пт-..."`, без `actual` (план, не факт)
3. Заполнить `slot.structure` по `step_builder.build_structure(...)` для run/bike/swim/brick, или вручную для OFP/brick (если run+OFП в одной сессии — `kind="brick"`, structure = [warmup, set, cooldown, main, cooldown] где main содержит `set.exercises` для OFP)
4. Записать в `slot.rationale` объяснение почему именно эта тренировка (Кирилл любит видеть логику)
5. **Рендерить HTML напрямую**, не через `plan_runtime`:

```python
import json
from lib import render_html
plan = json.load(open('state/plan-wN.json'))
render_html.render_plan_wN(plan, 'state/plan-wN.html')
```

`plan_runtime.generate_plan_with_html(N)` сгенерирует свежий план по сезону/фазам и **перезапишет** actual-лог. Не используй его для инкрементальных правок факт-логов.

**OFP circuit (12 упр, резинка + коврик, кор+ягодицы, без инвентаря):** clamshell L/R, glute bridge, bird-dog, banded side walk, dead bug, single-leg glute bridge, banded hip abduction, plank, banded kickback, side plank L/R. ~1 round без пауз. Рендерится в `slot.structure[].set.exercises: [{name, reps, rest, band, focus, notes}]`. CSS-классы: `.step.step-ofp` для каждого упр.

**Анализ нагрузки без FIT:** когда пользователь просит «посмотри на стресс-левел и придумай следующую тренировку» — опирайся на `slot.actual` (distance/time/RPE/HR), а не на FIT. Процедура — в `references/load-from-actual.md`.

## Inline Zwift (v16)

plan_generate проверяет `constraints.auto_zwift`:
- enabled=true
- duration_min_max=90
- location=home_stationary_bike
- kinds=bike/brick
- focus_must_have_any: Z2/Z3/intervals/endurance/tempo/threshold

Для каждого слота удовлетворяющего правилу — **inline** вызывает `lib.zwift_search.search(criteria)`, рендерит HTML с candidates (2-4), Кирилл голосует голосом. Это **не** отдельный шаг.

## Правило: HTML — обязательная часть выхода (v19)

Любая команда coach-plan-* (week, season, adjust) **всегда** порождает HTML вместе с JSON.

```
Собери план на W1
  ↓
generate_plan_with_html(season_week=1)
  ↓
state/plan-w1.json + state/plan-w1.html
  ↓
Telegram: "План W1 готов · 7 слотов · 2 Zwift pending · state/plan-w1.html"
```

Нет JSON без HTML. Нет HTML без JSON.

## JSON-driven render — это **source of truth**

План **никогда** не правится руками в HTML. Если нужна новая секция в HTML — добавляется блок в `~/.hermes/coach/arch/schemas.json` + перерендер. `render.py` (в `arch/`) и `lib/render_html.py` читают одну и ту же структуру. **Не дублируй** логику между двумя местами.

Пример: добавить новую секцию «Zwift workouts pending» — добавляется в `schemas.json` → JSON содержит данные → HTML рендерится из данных. Не пиши HTML-блок руками, не парси JSON в шаблоне.

## Inline JS — vanilla, без фреймворков

В `state/plan-wN.html` встроен inline JavaScript (~10 КБ). Структура **1:1 как в `state/w1-mobile-reference.html` строки 212-545** — копируй `loadPlan` / `buildPicker` / `showSlot` / `showPicker` / `renderCard` / `renderStructure` / `renderOfpStructure` / `renderInventory` / `popstate` listener / `init()` и адаптируй только рендер наших данных. Навигация:

- `showSlot(slot)` — рендерит детальную карточку в `cardHost.innerHTML` (через `renderCard(slot)`) + переключает picker/cardWrap через `classList.add/remove('hidden'/'visible')` + `history.pushState({page: 'card', slot: slot}, '', '#' + slot)`.
- `showPicker()` — обратное переключение, `history.replaceState(state, '', ' ')`.
- `popstate` listener — на back-button браузера вызывает `showPicker()` если `state.page !== 'card'`.
- `backBtn` click — `history.back()` если уже на card, иначе `showPicker()`.
- `buildPicker(plan)` — рендерит план-title + totals-card + zones-grid + phase-card + cp-card + slots-header + 8 `<button class="slot" data-slot="N">` с kind-icon + day+time + duration + name + focus-pill. После `innerHTML` обязательно: `document.querySelectorAll('.slot').forEach(el => el.addEventListener('click', e => { e.preventDefault(); showSlot(el.dataset.slot); }))`.
- `init()` (sync) — `loadPlan()` из inline `<script type="application/json" id="plan-data">` → `buildPicker(PLAN)` → если `location.hash` валиден, `showSlot(initialHash)`.

**Не подключай** Vue/React/jQuery — Кирилл открывает HTML на Android через Telegram preview без сборки. **Не делай fetch** — HTML self-contained, открывается двойным тапом из Downloads/Files. **Не используй CDN** — должно работать offline.

**Pitfall — навигация в preview:** не пытайся заменить JS-навигацию на CSS-only `:target` (v25) или inline `onclick` на `<a href="#card-N">` (v23) — эти подходы я перепроверил 4 раза и они не работали в Telegram WebView Кирилла (карточка показывалась под picker, или back-stack добавлялся без визуального изменения). Копируй именно JS-механизм из референса.

## Design tokens — не трогай без спроса

Цветовая палитра и spacing variables определены в `:root` HTML. При ЛЮБЫХ изменениях UX-структуры (двухэкранная навигация, новые блоки, etc.) **сохраняй**:
- `--bg:#0f1115` — тёмный фон
- `--panel:#161a22` — карточки
- `--accent:#7aa2ff` — голубой акцент (текст ссылок, заголовки секций)
- `--accent2:#5cd6c0` — teal (run slots, focus labels)
- `--warn:#ff9b6a` — orange (overplanning delta, Zwift pending)
- `--good:#7ee787` — green (delta positive, success states)
- `--cp:#d8a0ff` — violet (control points, OFP)

Если нужна **новая** цветовая категория — добавь `--run/--bike/--swim/--ofp/--brick` к существующим в `:root`. Если хочется **сменить** палитру — спроси Кирилла.

## Тестовые pitfalls (Phase 2+)

При написании тестов для `plan_runtime.generate_plan_with_html`:

- **Использовать `tempfile.mkdtemp(prefix=...)` + `shutil.rmtree(ignore_errors=True)` в finally**, НЕ `with tempfile.TemporaryDirectory() as tmp:`. `TemporaryDirectory` cleanup через `weakref.finalize` иногда срабатывает во время gc внутри `with` блока в тестовых фреймворках и удаляет tmpdir до того как тест проверит файлы — приводит к `FileNotFoundError` на ровном месте в первом из серии.
- `Path(result["json_path"])` после правильной операции существует — если видишь `FileNotFoundError`, это **не баг твоего кода**, это **баг tmpdir cleanup**. Замени `TemporaryDirectory` на `mkdtemp`.

## Запрещено

- Писать промпты руками.
- Редактировать `state/season_plan.json` (только через coach-plan-season).
- Трогать `state/fit_store/`.
- Делать двухшаговый процесс (сначала plan, потом отдельно zwift search).
- Возвращать JSON без HTML или HTML без JSON.
- Генерировать HTML-блок руками, не через данные в JSON.
- Использовать `<details>` для разворачивания структуры (Кирилл отверг v20 — это не то UX что он хочет, использует двухэкранную навигацию с back-button).
- **Переизобретать навигацию**, когда есть `state/w1-mobile-reference.html` как рабочий spec. Если Кирилл скажет «карточка не открывается / навигация сломана» — первым делом сравни с референсом, не пытайся «улучшить» на чистом CSS или новом inline-`onclick`. Четвёртая переделка того же самого в новом обличии = не прогресс.

## Pitfall — три неудачные итерации одной и той же ошибки

Если ты уже дважды пробовал починить одну и ту же проблему (особенно навигацию/reactive UI/state management) и обе попытки не сработали — **остановись и перечитай `state/w1-mobile-reference.html` построчно**. Не делай третью попытку «по мотивам». Референс — это не «вдохновение», это **готовый рабочий пример**: `<div id="picker" class="picker visible">`, `<div id="cardWrap" class="hidden">`, `<button id="backBtn">`, `<div id="cardHost">`, `<script type="application/json" id="plan-data">` + JS `loadPlan/buildPicker/showSlot/showPicker/renderCard/init` с `classList.add/remove('hidden'/'visible')` и `history.pushState`. Копируй **механизм**, а не поверхностный паттерн.

## Pitfall — ReferenceError из-за путаницы `s` vs `st` в renderHrStructure (v37)

При правках `renderHrStructure` в `lib/render_html.py` легко использовать `s` в top-level блоке, где переменная называется `st` (а `s` осталась от sub-шагов через `.map((s) => ...)`). JS не падает на этапе парсинга — `s` становится undefined и runtime выкидывает `ReferenceError: s is not defined` на первом же top-level шаге с `pace_min_per_km`. Кирилл увидит это как «пустая страница с кнопкой назад» при клике на run-карточку (OFP идёт через `renderOfpStructure` и не задевает эту ветку).

**Защита:** рендери `plan-w1.html` через `render_html.render_plan_wN(plan, out)`, извлекай JS-исходник из `<script>`, eval'и его в **настоящем node.js** с мок-DOM, вызывай `renderCard(slot)` для каждого слота в `plan.slots`. Падает на любом `ReferenceError` / `TypeError` / пустой результат (<50 chars).

Тест `test_render_html_every_slot_renders` (v37) делает это для всех 8 слотов W1. Если node.js недоступен — тест пропускается. Если `render_html.py` падает — тест падает. Это **единственный** тест, который запускает реальный JS, потому что HTML-размер + строковые проверки в source не ловят runtime-ошибки (v36 прошёл все v33/v34 строковые проверки но дал `s is not defined` в рантайме).

```python
# Шаблон для диагностики (если Кирилл снова скажет «карточка пустая»):
import subprocess, json
from pathlib import Path
from lib import render_html
plan = json.load(open('state/plan-wN.json'))
out = Path('/tmp/test.html')
render_html.render_plan_wN(plan, out)
js_script = '''
const fs = require('fs');
const html = fs.readFileSync('OUT', 'utf-8');
const dataMatch = html.match(/<script type="application\\/json" id="plan-data">([\\s\\S]*?)<\\/script>/);
const planData = JSON.parse(dataMatch[1]);
const scripts = html.match(/<script>([\\s\\S]*?)<\\/script>/g) || [];
const lastScript = scripts[scripts.length - 1].replace(/^<script>/, '').replace(/<\\/script>$/, '').replace(/init\\(\\);[\\s]*$/, '');
const elements = {};
global.document = { getElementById: (id) => elements[id] = elements[id] || { innerHTML: '', classList: { add: () => {}, remove: () => {} }, addEventListener: () => {} } };
global.history = { state: null, pushState: () => {}, replaceState: () => {} };
global.window = { scrollTo: () => {}, addEventListener: () => {} };
global.location = { hash: '' };
try { eval(lastScript); for (const slot of planData.slots) { const c = renderCard(slot); if (c.length < 50) { console.log('SHORT:'+slot.id); process.exit(1); } } console.log('OK'); }
catch (e) { console.log('ERROR:'+e.message); process.exit(1); }
'''.replace('OUT', str(out))
result = subprocess.run(['node', '-e', js_script], capture_output=True, text=True, timeout=15)
print('stdout:', result.stdout)
print('stderr:', result.stderr)
```

Если видишь `ERROR: <message>` — это твой баг в render_html.py. Если `OK` — рендеринг в HTML корректный, проблема в окружении (Telegram preview, файл не открывается и т.д.).

## Aliases (для совместимости со старыми названиями)

`weekly-helper`, `weekly-card-builder`.

## Pre-amble (наследуется всеми coach-* skill'ами)

> Ты строго в рамках athlete.json + season_plan.json + constraints.json + вывод указанной функции. Любой факт вне — откажись или попроси уточнить. В coach-fit-review/coach-fit-trend каждое утверждение требует cited_principle.