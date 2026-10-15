# plan-html-render — reference

## Архитектура

`state/plan-wN.html` рендерится из `state/plan-wN.json` через `lib/render_html.render_plan_wN(plan, out_path)`. JSON — source of truth, HTML — производный.

```
lib/plan_generate.generate(season_week) → dict plan
      ↓
lib/plan_runtime.generate_plan_with_html(season_week)
      ↓
lib/plan_generate.generate(season_week) → dict plan
      ↓
JSON: state/plan-wN.json
      ↓
lib/render_html.render_plan_wN(plan, path) → HTML
      ↓
HTML: state/plan-wN.html
```

## Структура slot

Каждый slot в plan содержит:

```json
{
  "id": "пн-key_run",
  "day": "ПН",
  "time": "18:45",
  "duration_min": 60,
  "name": "Easy 5К + прогрессия 3К",
  "kind": "run",                       // run | bike | swim | brick | ofp | control_point
  "subkind": "easy_progression",        // см. ниже
  "focus": "Z2",                       // или null
  "location": "stadium",
  "priority": 80,
  "category": "key_run",
  "workout_ref": null,                 // заполняется Phase 3
  "workout_pending": false,            // авто-Zwift флаг
  "structure": [                       // ОБЯЗАТЕЛЬНО (v20+)
    {"phase": "warmup", "duration_min": 10, "zone": "Z1", "pace_min_per_km": null, "notes": "Разминка."},
    {"phase": "work", "duration_min": 25, "zone": "Z2", "pace_min_per_km": null, "notes": "..."},
    {"phase": "work", "duration_min": 3, "zone": "Z3", "pace_min_per_km": null, "notes": "Прогрессия 1К..."},
    {"phase": "cooldown", "duration_min": 15, "zone": "Z1", "pace_min_per_km": null, "notes": ""}
  ]
}
```

## Step структура

**Run / bike / swim (HR-zone based):**
```json
{
  "phase": "warmup" | "work" | "recovery" | "cooldown",
  "duration_min": 10,
  "zone": "Z1" | "Z2" | "Z2_low" | "Z3" | "Z4" | "Z5",
  "pace_min_per_km": null | "4:30",
  "reps": null,
  "set_repeats": null,
  "notes": ""
}
```

**Set (intervals с reps):**
```json
{
  "phase": "set",
  "duration_min": 30,                // сумма set_repeats * reps
  "zone": null,
  "pace_min_per_km": null,
  "reps": 5,
  "set_repeats": [
    {"phase": "work", "duration_min": 4, "zone": "Z3", "pace_min_per_km": null, "notes": "400м @ 4:00/км (~1:36)."},
    {"phase": "recovery", "duration_min": 2, "zone": "Z1", "pace_min_per_km": null, "notes": "Jog 200м."}
  ],
  "notes": "Интервалы Z3."
}
```

**OFP (отдельный kind, отдельная structure):**
```json
{
  "phase": "warmup" | "main" | "cooldown",
  "duration_min": 5,
  "exercise": "Мобилити: hip openers, glute bridge 2×15.",
  "notes": ""
}
```
или set:
```json
{
  "phase": "main",
  "duration_min": 20,
  "set": {
    "name": "Core circuit x2 rounds",
    "exercises": [
      {"name": "Планка", "reps": "3×45с", "rest": "30с"},
      {"name": "Медведи на коленях", "reps": "2×12/стор", "rest": "30с"},
      ...
    ]
  },
  "notes": ""
}
```

## Виды слотов и subkinds

| kind | subkind | duration_min (run_base) | structure |
|---|---|---|---|
| run | easy_progression | 60 | warmup 10 + easy 25 Z2 + work 3 Z3 + cooldown 15 |
| run | easy | 30 | work 30 Z2_low |
| run | key_intervals | 60 | warmup 12 + set 5× {4 Z3 + 2 Z1} + cooldown 10 |
| run | long_Z2 | 90 | warmup 10 + work 65 Z2_low + cooldown 15 |
| run | tempo | 70 | warmup 12 + work 50 Z3 + cooldown 8 |
| run | intervals | 70 | warmup 15 + set 5× {4 Z3 + 2 Z1} + cooldown 10 |
| run | race_pace | 75 | warmup 15 + work 50 Z4 + cooldown 10 |
| bike | stationary_z2 | 45 | warmup 5 + work 30 Z2 + cooldown 10 |
| bike | stationary_z3 | 60 | warmup 5 + work 45 Z3 + cooldown 10 |
| bike | long_z2 | 90 | warmup 10 + work 70 Z2_low + cooldown 10 |
| swim | easy | 60 | warmup 5 + work 45 Z2_low + cooldown 10 |
| swim | tempo | 60 | warmup 5 + work 45 Z3 + cooldown 10 |
| brick | bike_run | 75 | warmup_bike + bike + T2 + run + cooldown |
| ofp | core | 25 | warmup (exercise) + main (set of exercises) + cooldown |
| ofp | mobility | 30 | main (exercise) |

Phase definitions в `lib/plan_generate._phase_focus_runs()`. Structure builder в `lib/step_builder.py`.

## Design tokens (НЕ менять без спроса)

```css
:root{
  --bg:#0f1115;
  --panel:#161a22;
  --panel2:#1d222c;
  --border:#2a3140;
  --text:#e6e9ef;
  --muted:#9aa3b2;
  --accent:#7aa2ff;
  --accent2:#5cd6c0;
  --warn:#ff9b6a;
  --good:#7ee787;
  --cp:#d8a0ff;
  /* kind-based цвета (compact cards + tags) */
  --run:#7ec8e3;
  --bike:#f08a5a;
  --swim:#5cd6c0;
  --ofp:#d8a0ff;
  --brick:#f0c674;
}
```

Kind → CSS class mapping (для тегов compact-карточек):
- run → `tag-run` (sky)
- bike → `tag-bike` (terra)
- swim → `tag-swim` (teal)
- ofp → `tag-ofp` (violet)
- brick → `tag-brick` (mustard)
- control_point → `tag-cp` (coral)

## Шаблоны карточек в HTML

### Compact (picker)
```
[icon] ПН  18:45      [1ч]
Easy 5К + прогрессия 3К
[tag: run]
```

### Detail (cardWrap)
```
← назад
─────────────────────────────────────
[tag: run]
Easy 5К + прогрессия 3К
ПН 18:45 · 60 мин
─────────────────────────────────────
📍 stadium  🎯 Z2  easy_progression

🎒 Что взять
🏟 Стадион (400м)

СТРУКТУРА ТРЕНИРОВКИ
┌───────────────────────────────┐
│ warmup     10мин              │
└───────────────────────────────┘
┌───────────────────────────────┐
│ work       25мин  Z2         │
│ Easy 5К. HR ~135, темп 5:30  │
└───────────────────────────────┘
┌───────────────────────────────┐
│ work       3мин   Z3         │
│ Прогрессия 1К: 5:00 → 4:30   │
└───────────────────────────────┘
┌───────────────────────────────┐
│ cooldown   15мин              │
└───────────────────────────────┘
```

### Set (intervals)
```
┌─ set 30мин × 5 ──────────┐
│ [Z3] work     4мин       │
│        400м @ 4:00/км    │
│ [Z1] recovery 2мин       │
│        Jog 200м           │
│ (повторить × 5)         │
│ Интервалы Z3.           │
└─────────────────────────┘
```

### OFP (core)
```
[warmup] 5мин
   Мобилити: hip openers, glute bridge 2×15.
   Активация ягодиц.

[main] 20мин — Core circuit x2 rounds
   1. Планка 3×45с · отдых 30с
   2. Медведи на коленях 2×12/стор · отдых 30с
   3. Bird-dog 3×10/стор · отдых 30с
   4. Glute bridge 3×15 · отдых 30с
   5. Гиперэкстензия 2×15 · отдых 30с

[cooldown] 5мин
   Растяжка 5мин. Без агрессии на грушевидную.
```

## Поток JS в HTML

```javascript
const PLAN = <встроенный JSON>;

function showCard(idx) {
  // Построить HTML из PLAN.slots[idx]
  // Подменить содержимое cardHost
  // Показать cardWrap, скрыть picker
  // history.pushState({view:'card',idx}, '', '#slot-'+idx)
}

function showList() {
  // Скрыть cardWrap, показать picker
  // history.pushState({view:'list'}, '', '#list')
}

document.querySelectorAll('.slot-card').forEach(btn => {
  btn.addEventListener('click', () => showCard(parseInt(btn.dataset.slotIdx, 10)));
});

window.addEventListener('popstate', () => {
  const h = (location.hash || '').replace('#','');
  if (h.startsWith('slot-')) showCard(parseInt(h.slice(5), 10));
  else showList();
});
```

## Когда добавлять новую секцию в HTML

1. Добавить поле в `state/plan-wN.json` через `lib/plan_generate.generate()`.
2. Добавить placeholder в `~/.hermes/coach/arch/schemas.json` (для arch HTML).
3. В `lib/render_html.py` — добавить блок в f-string body с условным `if field`.
4. Тест: `test_html_v22_contains_new_field` (в `tests/test_phase1_smoke.py`).

Не пиши HTML-блок вручную — добавь поле и шаблон.