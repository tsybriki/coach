# Анализ нагрузки из slot.actual (без FIT)

Когда `state/fit_store/index.json` пуст и FIT-файлов за нужный период нет
(бывает — cron-синк ещё не подтянул), нагрузку оцениваем из `slot.actual` в `state/plan-wN.json`.

## Что есть в slot.actual

```json
{
  "distance_km": 9.4,
  "time_sec": 2850,
  "avg_pace": "5:03",
  "avg_hr": 148,
  "rpe": 7,
  "notes": "Прогрессия по плану"
}
```

Доступно: дистанция, время, темп, средний HR, RPE (1-10), заметки.

## Как оценить stress level для решения «что делать на следующей тренировке»

1. **Суммарный объём за неделю.** Σ `actual.distance_km` (или duration_min для non-run). Run-объём > 45К/нед в run_base = кандидат на разгрузку.

2. **Пиковые сессии** (RPE ≥ 7). Если за неделю 2+ сессии с RPE ≥ 7 — следующий день **не** ставить ещё одну Z3/Z4 работу.

3. **HR avg vs zone target.** Если `avg_hr` > верхней границы target-зоны (например, Z2 target 125-145, avg_hr=152) — перегруз. Следующий день: Z1/Z2, не Z2/Z3.

4. **HR-drift в long-run (если есть ≥2 сегмента).** Тут нужен FIT; если FIT нет, опирайся на RPE + notes Кирилла.

5. **Дни подряд с одинаковым kind.** Если 3+ дня подряд бег (run) — ставить cross-train (bike/swim/OFП), даже если не было запланировано.

6. **Recovery-окна.** План должен иметь минимум 1 день/нед с RPE ≤ 4 или полный отдых. Если такого нет — добавить rest day или recovery swim (Z1).

## Foster's TRIMP-like (грубая оценка от RPE)

`session_load = rpe * duration_min`. Сумма за неделю = weekly_load.
- < 1500 = лёгкая неделя
- 1500-2500 = средняя
- 2500-3500 = тяжёлая
- > 3500 = перегруз (нужен deload)

Это **грубая** оценка, не заменяет Garmin Training Effect / TSS. Достаточно для решения «сегодня recovery или tempo».

## Какой kind ставить на следующий день

Из `slot.focus` текущей недели смотрим Z-распределение:
- 0 сессий Z3+ → можно поставить interval/tempo
- 1 сессия Z3+ → можно повторить Z3, но осторожно
- 2+ сессий Z3+ → только Z1/Z2, либо recovery-swim/OFП, либо rest
- Cross-train (bike/swim) за неделю = 0 → можно добавить bike 60мин Z2 как «свежий стимул»

## Где смотреть для подтверждения

Если FIT появятся (`~/.hermes/coach/runs/*.fit` или `state/fit_store/index.json` не пуст) — `lib/parse_fit.py` через `garmin_tools/fit_inspect.py json <path>`. Метрики: HR drift, pace variability, fatigue score. Поля мапятся в `slot.actual` для архивных сессий.

## Паттерн recovery после race_test (W1 в season)

Когда W1 содержит race test (10К @ race pace, RPE 8/10, avg_pace 4:24) — **следующий день** это не бег, а **recovery swim Z1** (45мин, носовое дыхание, без форсирования). Стандартный паттерн:

- ВС 10:00 — 10К test (race, RPE 8, baseline)
- ПН 18:30 — пул Z1 (recovery, RPE 5, без distance_km)
- ВТ 09:00 — easy 1.5К Z2 (RPE 3)
- ВТ 18:30 — 5К Z2 + 3К Z3 (key session, RPE 7)
- СР 17:00 — long Z2 1ч (RPE 5)
- ЧТ 10:30 — cross Z2 11К (RPE 5)
- ПТ 18:30 — recovery_swim Z1 (45мин, носовое дыхание)

Это **дефолт** Кирилла для первой недели сезона. Если говорит «пятница пустая, сгенери» после race-test недели — recovery swim, не бег. Если говорит «другая тренировка на пятницу» — спрашивай: easy бег, кросс, или OFП circuit (12 упр)?

## Шаблон race-then-recovery-swim

```python
# Добавить recovery swim в plan-wN.json (actual-лог)
new_slot = {
    "id": "пт-recovery_swim",
    "day": "ПТ", "date": "2026-10-16", "time": "18:00",
    "name": "Пул 45мин Z1 (восстановление)",
    "kind": "swim", "subkind": "easy_recovery", "focus": "Z1",
    "location": "pool", "duration_min": 45,
    "structure": [
        {"phase": "warmup", "duration_min": 5,  "zone": "Z1", "notes": "200м разминка."},
        {"phase": "work",   "duration_min": 30, "zone": "Z1", "notes": "1.5-2К кроль, каждое 4-ое 50м на спине. Носовое дыхание 6-8 гребков."},
        {"phase": "cooldown", "duration_min": 10, "zone": "Z1", "notes": "200м заминка + растяжка плеч."}
    ],
    "rationale": "Active recovery после 4 дней бега с пиковой нагрузкой (10К test + 5К Z2 + 3К Z3 + 10.6К Z2 + 11.2К Z2)."
}
```
