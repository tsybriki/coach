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
   - HR-зоны: `zones-grid` с 2-колоночной сеткой `Z1=110-125`, `Z2_low=125-140`, `Z2=125-145`, и т.д.

4. **Phase-card** после totals: «Фаза · run_base · 12.10 → 18.10 · target 5ч/нед · goal g_run_spring».

5. **CP-card** (если есть control_points_in_range): «В этой неделе: 5К на время, 3К на время».

6. **slots-header** + **slots-sub**: «Тренировки · 8 шт» + «тап → детали» (перед списком слотов).

**Правило v27:** каждый slot в `state/plan-wN.json` ОБЯЗАН иметь поле `structure: list[step]`. Без него карточка бесполезна. `plan_generate` вызывает `lib.step_builder.build_structure()` для run/bike/swim/brick и `lib.step_builder.ofp_structure()` для ofp. **Не пропускай это**.

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

## Aliases (для совместимости со старыми названиями)

`weekly-helper`, `weekly-card-builder`.

## Pre-amble (наследуется всеми coach-* skill'ами)

> Ты строго в рамках athlete.json + season_plan.json + constraints.json + вывод указанной функции. Любой факт вне — откажись или попроси уточнить. В coach-fit-review/coach-fit-trend каждое утверждение требует cited_principle.