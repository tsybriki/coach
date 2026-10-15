# coach-plan-week

Собирает план на конкретную W_N и **всегда** порождает пару JSON+HTML.

**Использует:** `lib.plan_runtime.generate_plan_with_html` (entry point), `lib.plan_generate` (внутри), `lib.volume_check`, `lib.render_html`, `lib.step_builder` (структура слотов), `lib.goal_allocator`, `lib.zwift_search` (inline), `lib.zwift_sync` (inline bridge к garmin_tools).
**Триггеры:** «собери план на следующую неделю», «сгенерируй W_N», «поправь план», «регенерируй план на W_N».
**Вход:** `season_week: int | "W1" | "2026-W42"`.
**Выход:** **ВСЕГДА** пара — `state/plan-wN.json` + `state/plan-wN.html`.

## Правила UX-представления (v21, hard preferences)

Пользователь явно требует двухэкранную mobile-first навигацию, как в `~/.hermes/coach/arch/references/w1-mobile.html`. Любой рендер plan-wN должен следовать этой структуре, **сохраняя тёмную design tokens** (--bg:#0f1115, --accent:#7aa2ff, и т.д.). Хочется сменить палитру — это отдельное обсуждение, не делай сам.

**Структура HTML:**

1. **Экран 1 — picker (список compact-карточек).** Каждая карточка показывает:
   - Иконку по `kind` (run→🏃, bike→🚴, swim→🏊, ofp→💪, brick→🔄, control_point→🎯).
   - День + время + длительность в monospace справа.
   - **Главную идею тренировки** — короткое название (1 строка). Берётся из `slot.name` или `_slot_idea()` fallback на focus+subkind.
   - Tag с цветом по kind: tag-run (sky #7ec8e3), tag-bike (terra #f08a5a), tag-swim (teal #5cd6c0), tag-ofp (violet #d8a0ff), tag-brick (mustard #f0c674).
   - **Не показывай** в карточке детальную структуру — только идею. Детали разворачиваются на втором экране.

2. **Экран 2 — cardWrap (детальная карточка).** Активируется тапом на compact-карточку. Содержит:
   - Top-bar с back-button `← назад`.
   - Headline: `slot.name` + subtitle (день, время, длительность) + tag справа.
   - Meta-полоски: 📍 location, 🎯 focus, subkind, Zwift pending если есть.
   - **🎒 Что взять (inventory)** — генерируется через `_inventory_for()` по location/kind/subkind. Если outdoor stadium — «Стадион 400м». Если home_stationary_bike — «Велостанок (Tacx)». Для OFP — коврик + резинка. Для workout_pending bike — Zwift-приложение.
   - **Структура тренировки** — list[step] в виде карточек с левым border-color по типу step:
     - step (run/bike/swim): border-left accent2 (Z1), step-zone бейджи (Z1/Z2/Z3/Z4)
     - step-set (интервалы с reps): border-left accent, step-reps "× 5"
     - step-ofp (упражнения): border-left cp (violet), ex-list с reps/rest
   - Для каждого step: duration в моноширинном, notes italic в муцере.

3. **Tracker сверху (опционально).** Показывать только если в плане есть OFP-слоты. Содержит:
   - «N слотов · M pts ofp» (очки: каждая OFP карточка даёт duration_min/5).
   - 7-dot progress bar (1 dot = 1 OFP done). Без реального ПОКа — Phase 3.

**Правило v21:** каждый slot в `state/plan-wN.json` ОБЯЗАН иметь поле `structure: list[step]`. Без него карточка бесполезна. `plan_generate` вызывает `lib.step_builder.build_structure()` для run/bike/swim/brick и `lib.step_builder.ofp_structure()` для ofp. **Не пропускай это**.

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

В `state/plan-wN.html` встроен inline JavaScript (<5 КБ). Он делает:
- `showCard(idx)` — переключение на детальную карточку по индексу.
- `showList()` — возврат в picker.
- `renderCard(slot)`, `renderSteps()`, `renderOfpSteps()`, `renderInventory()` — сериализация slot-данных в HTML.
- `history.pushState()` + `popstate` — hash routing `#list` / `#slot-N`.

**Не подключай** Vue/React/jQuery — Кирилл открывает HTML на Android через Telegram preview без сборки. **Не делай fetch** — HTML self-contained, открывается двойным тапом из Downloads/Files. **Не используй CDN** — должно работать offline.

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

## Aliases (для совместимости со старыми названиями)

`weekly-helper`, `weekly-card-builder`.

## Pre-amble (наследуется всеми coach-* skill'ами)

> Ты строго в рамках athlete.json + season_plan.json + constraints.json + вывод указанной функции. Любой факт вне — откажись или попроси уточнить. В coach-fit-review/coach-fit-trend каждое утверждение требует cited_principle.