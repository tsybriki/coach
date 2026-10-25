# Coach App — операционная доменная модель

> **Статус:** рабочая версия, все инварианты подтверждены Кириллом (25.10.2026).
> **Источник правды для этой части:** `~/projects/coach-app/DOMAIN-SPEC.html` — рисуется и читается как есть.
> **Этот файл:** текстовая копия той же модели. Правки вносятся в HTML, сюда переносится синхронно.

## Что это

Операционная часть доменной модели приложения-тренера: сезон, план, неделя, тренировка, шаг, слоты, связывание плана с фактом.

Модель описывает **операционный контур** — то, что происходит внутри сезона от предложения недели до её закрытия.
За пределами этой части остаётся: UI, синхронизация между устройствами, хранение, адаптеры внешних источников.

## Счётчики

- Сущностей: **18**
- Инвариантов: **43** (подтверждено 43)
- Вопросов: **6**

---

## 1. Дерево сущностей

```
Season ── calendar.slots[], equipment[], plan_models[], load_model
  └ Plan (status: active|completed|draft) ─ goal, period, sport_lines{}, load_budget, transition
      ├ Goal ─ metric, race_date, venue, start_time, race_pace_min_per_km, realistic_fork
      └ Phase ─ objective, focus, load_range, volume_range, intensity_pct_mean, deload_weeks[]
          └ Week (status: proposed|active|closed) ─ focus, load_target, requests[],
                                        assignments[], unplaced[], slot_overrides[],
                                        workouts[], summary, detail
              └ Workout ─ request_id, sport, kind, focus, objective, equipment[], steps[], actual_id
                  └ Step ─ role, sport, target_type, target_value, focus, focus_value
```

Справочники сезона: `Equipment`, `PlanModel`, `LoadModel`, `Athlete`.
Раскладка недели: `Slot` (окно), `SlotOverride` (patch), `Request` (запрос), `Assignment` (размещение).
Факт: `ActualSession`. Итог: `WeekSummary`. Изменения: `Command`.

## 2. Сущности

### Season  *(корень)*
- `id` · `horizon{start,end,season_week_count}`
- `calendar.slots[]` — дефолтные слоты
- `equipment[]` · `plan_models[]` · `load_model`

### Plan  *(aggregate)*
- `id` · `status{active,completed,draft}`
- `goal` — одна цель плана
- `period{start,end}`
- `sport_lines{sport → {model_ref, weight}}`
- `load_budget{hours_range,normalized_min_range,intensity_pct_max}`
- `phase_ids[]` · `transition{overlap_weeks,reason}`

### Goal  *(value)*
- `id` · `discipline` · `race_date` · `venue` · `start_time`
- `metric{type,target,target_friendly}`
- `race_pace_min_per_km` · `realistic_fork{best,likely,conservative}`

### Phase  *(aggregate)*
- `id` · `objective` — цель фазы текстом («набрать беговой объём»). Не путать с `Plan.goal` — это цель плана (10К за 40:00)
- `load_range` · `volume_range` · `intensity_pct_mean` · `deload_weeks[]`
- `sport_weights{}` — распределение внутри фазы
- `slot_overrides[]`

### Week  *(aggregate)*
Три состояния. Расписание не обязано быть жёстким: что не разложилось — остаётся висеть и ждёт решения.
- `plan_id` · `season_week` · `start,end`
- `status{proposed,active,closed}`
- `focus` — адаптационная цель недели
- `load_target{hours,distance_m,sessions,intensity_pct,normalized_min}`
- `requests[]` — намерения из макро
- `assignments[]` — что разложилось по слотам
- `unplaced[]` — висяки: не разложилось, ждёт решения пользователя. Без привязки к дню, учитываются в плане недели
- `workouts[]` — тренировки со счётом шагов; могут быть уже в `proposed`
- `summary` → `WeekSummary`

### WeekSummary  *(value)*
Итог недели: что планировали против того, что сделали. Живёт и обновляется по мере выполнения; окончательно фиксируется при закрытии недели.
- `week_id` · `closed_at` · `updated_at`
- `totals{planned,actual,delta_pct}` — по часам, дистанции, нагрузке
- `per_session[]` — сопоставление: `{request_id, actual_id, verdict}`
- `verdict{done,partial,missed,extra,substituted}` — по каждой сессии
- `missed[]` · `extra[]` — не запланированное, но сделанное
- `deviations[]` — `{metric,planned,actual,reason}`
- `intensity{planned_moderate,actual_moderate,planned_vigorous,actual_vigorous,goal_min}` — интенсивность: план, факт, цель
- `intensity.contributions[]` — `{actual_id, moderate_min, vigorous_min}`: из чего сложился факт
- `intensity.zones{moderate_bpm_low,moderate_bpm_high,vigorous_bpm_low,vigorous_bpm_high}` — пороги источника; приоритет — зоны атлета
- `intensity.sources[]` — `garmin`

### ActualSession  *(value)*
Что фактически сделано. Одна запись на выполненную тренировку: объём, пульс и intensity minutes. Живёт вне плана; связан с планом через `Workout.actual_id`. Всё не связанное всё равно учитывается в actuals.
- `id` · `date` · `sport` · `duration_min` · `distance_m`
- `hr_avg` · `hr_max` · `hr_zones_min{}` — минуты по зонам атлета
- `aerobic_te` · `anaerobic_te` · `vo2max`
- `moderate_min` · `vigorous_min` — intensity minutes тренировки от источника; если источник не делит — всё в moderate
- `source{garmin,manual}` · `external_id` — id активности Garmin, уникален
- `fetched_at` — когда вытянуто из источника
- `linked_workout_id` — обратная ссылка, ставится вручную; null = факт без плана, но он всё равно в actuals

### Command  *(command)*
Любое изменение состояния. Ничего не меняется само — только по команде.
- `id` · `type` — `propose_week · activate_week · close_week · replan_remainder · link_actual · unlink_actual · place_unplaced`
- `target{week_id, ...}` · `args{}`
- `reason` · `issued_at` · `issued_by{user,brain}`
- `status{proposed,applied,rejected}` · `diff[]`

### Request  *(value)*
- `id` · `sport` · `kind` · `focus`
- `duration_min` · `equipment_required[]`
- `priority` · `min_slot_quality`
- статуса нет — состояние выводится: размещён (есть Assignment) или висит (в `unplaced[]`)

### Assignment  *(value)*
- `request_id` · `slot_id` · `start` · `duration_min`
- `equipment` · `fit_score`
- статуса нет — факт выполнения живёт в `Workout.status`

### Slot  *(value)*
- `id` · `day` · `start,end` · `capacity_min`
- `equipment[{equipment_id}]`
- `constraints{max_intensity,forbidden_sports,note}`
- `priority_hint`

### SlotOverride  *(patch)*
- `slot_id` · `ops[]{remove,set_time,set_capacity,add_equipment,remove_equipment,set_constraints,add}`
- `reason` · `scope{season,phase,week}`

### Workout  *(value)*
- `id` · `request_id` → `Request` — из какого намерения выросла
- `sport` · `kind` · `focus`
- `objective{metric,target}`
- `equipment[]` · `location` · `time`
- `steps[]` · `priority` · `status{planned,done,skipped,moved}` · `rationale`
- `actual_id` → `ActualSession` — связь с фактом, ставится вручную

### Step  *(value)*
- `role{warmup,work,rest,cooldown,transition}`
- `sport` · `target_type{time,distance,laps,reps,open}` · `target_value` — длительности в минутах; для силовой/ОФП — общая длительность тренировки, округлённая до минут
- `focus{pace,hr,power,rpe,none,strength_pattern}` · `focus_value{}`
- `group` · `round`
- `label` · `notes`

### Equipment  *(реестр)*
- `id` · `name` · `kind{track,water,machine,route,vehicle}`
- `sports[]` · `availability{days,valid_until,seasonal_note}`
- `limitations{max_distance_m,needs_booking,surface}`

### Athlete  *(value)*
- `vdot` · `hr_zones{zone → bpm}` · `hr_max,rhr,lth`
- `injuries[]` · `form`

### PlanModel  *(стратегия)*
- `id` · `name` · `version` · `sports[]`
- `inputs{}` · `intensity_map{}` · `intensity_units[]`
- `block_rules{}` · `progression_rules{}` · `guard{}`
- `description` — текстовое описание модели

### LoadModel  *(правило)*
- `intensity_factor{zone → доля VO2max}`
- `adaptation_rate{sport → коэффициент}` — единственный владелец (в Athlete нет)
- `formula` · `budget{}`

## 3. Связи

### Владение и ссылки

| Откуда | Куда | Тип | Кардинальность |
|---|---|---|---|
| Season | Plan | владение | 1 → N; ровно 1 active |
| Season | Slot | дефолт | 1 → N |
| Season | Equipment | реестр | 1 → N |
| Season | LoadModel | реестр | 1 → 1 |
| Plan | Goal | владение | 1 → 1 |
| Plan | PlanModel | ссылка | N → N |
| Plan | Phase | владение | 1 → N |
| Plan | Week | владение | 1 → N |
| Phase | SlotOverride | перекрытие | 1 → N |
| Season | Command | журнал | 1 → N |
| Command | Week | применение | N → 1 |
| Week | Request | владение | 1 → N |
| Week | SlotOverride | перекрытие | 1 → N |
| Week | Assignment | владение | 1 → N |
| Request | Assignment | ссылка | 1 → 0..1 |
| Request | Workout | детализация | 1 → 0..1 |
| Assignment | Slot | размещение | N → 1 |
| Slot | Equipment | доступность | N → N |
| Week | Workout | владение | 1 → N |
| Week | WeekSummary | итог | 1 → 0..1 |
| WeekSummary | Request | ссылка | N → 0..1 |
| WeekSummary | ActualSession | вклад в интенсивность | N → 1 |
| Season | ActualSession | факт | 1 → N |
| Workout | ActualSession | связь план↔факт | 0..1 → 1 |
| Workout | Step | владение | 1 → N |
| Step | Equipment | требование | N → N |
| Athlete | Step / PlanModel | вход | 1 → N |
| LoadModel | Step | вход | 1 → N |

### Наследование слотов

| Уровень | Источник | Что делает |
|---|---|---|
| Season | `calendar.slots[]` | базовое окно: день, время, ёмкость, оборудование |
| Phase | `slot_overrides[]` | перекрытие на весь период фазы |
| Week | `slot_overrides[]` | перекрытие на одну неделю |

Слот недели = `Season ← Phase ← Week`. Каждый уровень применяется последним и перекрывает предыдущий.
Patch хранит только отличие от уровня выше.

## 4. Жизненный цикл недели

| Состояние | Что есть | Переход |
|---|---|---|
| `proposed` | план предложил неделю из макро и попробовал разложить по слотам; что не разложилось — в `unplaced` | `propose_week` |
| `active` | разложенные тренировки стоят по слотам; неразложенные висят в `unplaced[]` | `activate_week` |
| `closed` | саммари посчитано и записано; можно планировать следующую | `close_week` |

**propose_week** — можно вызывать многократно. Планировщик берёт макро фазы, собирает намерения и раскладывает их по слотам.
Всё, что не разложилось, уходит в ручной режим (`unplaced[]`). Каждый новый propose вытирает предыдущий, пока неделя не активна.

**activate_week** — разложенные тренировки стоят по слотам. Неразложенные остаются висеть: расписание не обязано быть жёстким.
Висялки можно разложить позже командой `place_unplaced`.

**close_week** — явный ритуал в три шага (см. §6). Само ничего не закрывается.

**replan_remainder** — переплан остатка недели: сессии на сегодня и позже. Прошедшие сессии не трогаются.
«Сегодня» определяется по календарной дате.

### Что появляется на каждом шаге

| Шаг | Появляется | Чего нет |
|---|---|---|
| propose_week | `focus`, `load_target`, `requests[]`, `assignments[]`, `unplaced[]`; частично — `workouts[]` | факта |
| activate_week | полный счёт `workouts[]` со `steps[]`, `inputs_version`; висялки остаются | факта |
| факт загружен | `ActualSession[]`, кандидаты на связывание, вклад в `summary.intensity` | итогов |
| связывание подтверждено | `Workout.actual_id`, `verdict` по каждой сессии | — |
| replan_remainder | новые `workouts[]` для сессий на сегодня и позже | изменений в прошедших |
| close_week | `summary` финализирован, `deviations[]` | — |

## 5. Инварианты

Все подтверждены. При добавлении нового — он попадает в конец с новым номером.

| I1 | В сезоне ровно один Plan со статусом `active` | да |
|---|---|---|
| I2 | Слот определён на уровне сезона; фаза и неделя его перекрывают; неделя может добавить свой | да |
| I3 | Ссылка слота — на существующее оборудование из реестра | да |
| I4 | В тренировке один `sport`; все шаги этого спорта | да |
| I5 | Σ длительностей шагов = длительность тренировки | да |
| I6 | Шаги не пересекаются по времени; `rest` идёт после `work` | да |
| I7 | Запрос без размещения попадает в `unplaced` с причиной | да |
| I8 | У недели со статусом `closed` есть `WeekSummary` | да |
| I9 | `Workout.actual_id` и `ActualSession.linked_workout_id` указывают друг на друга | да |
| I10 | Связь 1:1 — один факт ↔ одна тренировка, и наоборот | да |
| I11 | `actual_id` ставится только через `link_actual`, вручную | да |
| I12 | Всё, что попало в план до активации, — планирование; без связи с фактом к закрытию ⇒ `missed` | да |
| I13 | Факт без плановой сессии ⇒ `linked_workout_id = null`; он всё равно учитывается в actuals | да |
| I14 | Активности берутся только из Garmin | да |
| I15 | Автоматического сопоставления нет: связь ставится только вручную | да |
| I16 | `summary.intensity.actual_moderate` = Σ `summary.intensity.contributions[].moderate_min` по факту недели | да |
| I17 | Вклад в неделю принимается только из факта с датой в её диапазоне | да |
| I18 | Один факт — один вклад в неделю | да |
| I19 | Статус недели меняется только через `Command` | да |
| I20 | Каждый `Workout` вырос из `Request` (`request_id` задан) | да |
| I21 | Повторный `propose_week` полностью заменяет содержимое `proposed`-недели | да |
| I22 | `replan_remainder` меняет только сессии на сегодня и позже | да |
| I23 | Закрытая неделя не меняется; поздний факт игнорируется | да |
| I24 | Неделя закрывается только по команде; сама не закрывается | да |
| I25 | Переносов между неделями нет: закрываем одну, потом планируем следующую | да |
| I26 | Висяки (`unplaced[]`) учитываются в плане недели | да |
| I27 | Intensity minutes берутся только из тренировок; нет тренировок — нет intensity minutes | да |
| I28 | Недельные агрегаты Garmin (пн→вс) не используются — считаем сами по тренировкам | да |
| I29 | Если источник не делит интенсивность — всё в `moderate` | да |
| I30 | Неделя без факта показывается с нулями; причины низких цифр не учитываются | да |
| I31 | Висяк (`unplaced[]`) не привязан к дню | да |
| I32 | Размещение висяка решает пользователь — вручную | да |
| I33 | Неделя гонки принадлежит плану | да |
| I34 | Планы не перекрываются | да |
| I35 | Длительности силовой и ОФП — общая длительность тренировки, округлённая до минут | да |
| I36 | `Plan.goal` и `Phase.objective` — разные вещи, не дублируют друг друга | да |
| I37 | У Request и Assignment нет статуса — состояние выводится из наличия Assignment | да |
| I38 | Висящая тренировка без факта ⇒ пропущена | да |
| I39 | `replan_remainder` определяет «сегодня» по календарной дате | да |
| I40 | Повторный propose переделывает план; привязки факта пользователь ставит заново | да |
| I41 | План готовит propose для одной следующей недели | да |
| I42 | `external_id` уникален (id активности Garmin) | да |
| I43 | Единственный `adaptation_rate` — в `LoadModel` | да |

## 6. Производные значения

Не хранятся — считаются.

| Значение | Формула |
|---|---|
| Нагрузка тренировки | Σ (минуты шага × intensity_factor(зона) × adaptation_rate(спорт)) — `LoadModel` |
| Нагрузка недели | Σ по тренировкам |
| Итоговые слоты недели | Season ← Phase.patch ← Week.patch |
| Темп шага | PlanModel.intensity_map + Athlete.vdot |
| Границы HR-зон | Athlete.hr_max, rhr, lth |
| Длительность / дистанция тренировки | Σ по шагам |
| Норма недели | Phase недели |
| Итог недели (WeekSummary) | план (requests + load_target) против факта (ActualSession) |
| Verdict по сессии | по факту связанной `ActualSession`: полное совпадение, частичное, замена |
| Отклонение недели | факт − план по каждой метрике, с причиной |
| Verdict факта без плана | `extra` — попадает в нагрузку недели, но не в выполнение плана |
| Интенсивность недели | `summary.intensity`: Σ по тренировкам недели; если источник не делит — всё в moderate. Нет тренировок — нет intensity minutes |
| Плановые intensity minutes | расчёт по шагам недели через зоны атлета (решение 7) |
| Граница недели | считаем сами по тренировкам — недельные агрегаты Garmin (пн→вс) не используем |

## 7. Связывание плана и факта

| Шаг | Что происходит |
|---|---|
| Загрузка факта | в любой момент можно вытянуть тренировки из Garmin — вручную или по кнопке. Активность → `ActualSession` с её `moderate_min`/`vigorous_min` |
| Связывание | пользователь выбирает факт для конкретной тренировки → `link_actual`: `Workout.actual_id` + `ActualSession.linked_workout_id`, обновляются вместе |
| Отвязывание | `unlink_actual` — если связали не то |
| Пересчёт | изменение связи пересчитывает `WeekSummary` затронутой недели |

**Цель связывания** — сопоставить задачу сессии с её выполнением.
Всё, что не связано, в любом случае учитывается в actuals: связывание уточняет отчёт, но не решает, что считать сделанным.
Автоматического сопоставления нет вообще — факт и план связывает пользователь, вручную, связь 1:1.
Активности берутся только из Garmin. Поздний факт игнорируется.

### Закрытие недели

| Шаг | Что происходит |
|---|---|
| 1 · вытянуть | достать из Garmin всё, что ещё не вытянуто |
| 2 · сопоставить | связать факт с плановыми тренировками — руками |
| 3 · посчитать | считать цифры и записать в `summary` |

Всё, что попало в план до активации, считается планированием.
Всё, что планировалось, но к моменту закрытия не связано с фактом, — **не выполнено**.
Неподтверждённые сессии закрытию не мешают: они попадают в саммари как `missed`.
Переносов между неделями нет: закрываем одну, потом планируем следующую.

### Неделя в работе

| Момент | Что меняется в неделе |
|---|---|
| Вытянут факт | `ActualSession` появляется в сезоне; вклад в `summary.intensity.contributions[]` не делается, пока факт не связан |
| Факт связан | `link_actual`: `Workout.actual_id` ← факт; статус тренировки → `done`; факт добавляется в `summary.intensity.contributions[]` |
| Неделя закончилась | `close_week` — только по команде: вытянуть остаток факта → сопоставить руками → посчитать и записать. Переносов в следующую неделю нет |

## 8. Решения

Зафиксированные ответы Кирилла. Действуют как правила модели.

| Вопрос | Решение |
|---|---|
| Методология подсчёта TSS | тикет — tsybriki/coach#6. Референс: Training Stress Scores (TSS) Explained |
| Дисбаланс sport_lines | пользователь руками |
| Единицы длительности | силовую и ОФП — общая длительность тренировки, округлять до минут |
| Цель плана vs цель фазы | разные вещи: `Plan.goal` — «10К за 40:00», `Phase.objective` — «набрать беговой объём» |
| Статус Request и Assignment | статуса нет — состояние выводится: размещён (есть Assignment) или висит (в `unplaced[]`) |
| `external_id` | уникален — id активности Garmin |
| Висящая тренировка в итогах | нет факта — пропущена |
| Граница replan_remainder | «сегодня» — по календарной дате |
| Wipe при повторном propose | переделывает план; привязки пользователь может поставить заново |
| Сколько недель планировать наперёд | одну |
| Перекрытие планов | не перекрываются |
| Неделя гонки | плану |
| Висяки | решение за пользователем: остаётся висеть и учитывается в плане недели; без привязки к дню. Факт берётся из факта; при закрытии сравниваем план с фактом |
| Поздний факт | игнорировать |
| Тренировка без факта | нет факта — не выполнено |
| Факт без интенсивности | всё в moderate |
| Intensity minutes | только из тренировок; нет тренировок — нет intensity minutes |
| Граница недели | считать самому — недельные агрегаты Garmin (пн→вс) не используем |
| Неделя без данных | с нулями; всегда показываем фактические цифры, причины не важны |
| Закрытие недели | только по команде, само не закрывается |
| Переносы между неделями | нет — закрываем одну, потом планируем следующую |
| Источник активностей | только Garmin |
| Связывание план↔факт | только ручное, 1:1; всё не связанное учитывается в actuals |

## 9. Открытые вопросы

1. Как устроен переход между планами? Планы не перекрываются — граница проходит по дате цели. Вопрос: как технически закрывается первый план и открывается второй.
2. Какие виды спорта поддержаны и по каким правилам? Набор PlanModel.
3. На каком расстоянии считается темп? Километр / 100 м / миля — база не задана на уровне модели.
4. Обязаны ли шаги соответствовать фокусу тренировки?
5. Что входит в `inputs_version`? vdot, hr_zones, план, модель, слоты — полный набор не зафиксирован.
6. Где и как храним? Формат и объём: JSON-файлы или БД; правило атомарной записи и миграции схемы.

## 10. Связанные тикеты

- [tsybriki/coach#6 — Методология расчёта Training Stress Score / intensity minutes](https://github.com/tsybriki/coach/issues/6)
  Референс: [Training Stress Scores (TSS) Explained — TrainingPeaks](https://share.google/JlFPisYIM7Fczte8R)
- tsybriki/coach#5 — Plan vs actual: реальные тренировки рядом с планом

## 11. Что впереди

Операционная часть закрыта. Не сделано:

- **Реализация.** Домен → код: слои domain/ports/app/adapters, тесты на каждый инвариант.
- **Хранение.** Формат и объём, атомарная запись, миграции схемы.
- **Адаптеры.** Garmin (интенсивность по тренировкам), Stryd, календарь.
- **Методология нагрузки.** Задача #6 — считаем intensity minutes сами, с учётом зон атлета.
- **UI.** Экраны: неделя, детали сессии, сезон, план vs факт, ручное связывание, закрытие недели.
- **Синхронизация.** Mobile + offline: снапшот в IndexedDB, outbox команд.
- **Оценка формы.** Как измерять результат работы мозга.

