# Running Dynamics: Garmin RD vs Stryd — sensor-level reference

## Two different sensor stacks, two different conventions

`Garmin Connect UI` показывает **Garmin Running Dynamics** (сокращённо Garmin RD). Это цифры от акселерометра на запястье (FR 965, fenix и т.п.), которые Garmin усредняет по акселерометрии корпуса, аппроксимируя вертикальное смещение и контактные фазы. Исторически это первый по-настоящему массовый источник Running Dynamics для бегунов.

`Stryd` — отдельный footpod с IMU в ботинке. Stryd считает по-другому: модель энергии бега Stryd Power + собственная sensor fusion для VO / Ground Time / Impact Loading Rate / Leg Spring Stiffness. Это **другая** физика и **другие** алгоритмы.

Цифры **несопоставимы напрямую**:

| Метрика | Garmin RD | Stryd | Разница |
|---|---|---|---|
| Вертикальное колебание | accelerometer-derived, обычно 8-12 см | footpod-derived, обычно 5-9 см | ~3 см на тех же людях |
| Ground contact time | 240-280 мс типично | 200-260 мс типично | ~30-40 мс |
| Step length | да | нет (только через power × cadence) | — |

Это не «у одного точнее, у другого нет». Это два метода дают два числа, оба правильные в своей методике.

## FIT-уровень: какие поля откуда

В Garmin `.fit` присутствуют **оба набора полей** (если FR 965 пишет Running Dynamics и Stryd подключён):

- **Гармин RD** — lowercase FIT names, источник: fenix device:
  - `vertical_oscillation`
  - `stance_time`
  - `stance_time_percent`
  - `vertical_ratio`
  - `step_length`
  - `stance_time_balance`

- **Stryd footpod** — capitalized FIT names, источник: Stryd (device_index=5, type `stride_speed_distance`):
  - `Vertical Oscillation`
  - `Ground Time`
  - `Cadence` (separate Stryd cadence, не watch)
  - `Form Power`, `Air Power`, `Power`
  - `Impact Loading Rate`, `Leg Spring Stiffness`

Часто Garmin RD-поля присутствуют в FIT только если FR 965 пишет Running Dynamics при этой активности (зависит от профиля и firmware). **Stryd-поля есть почти всегда**, если footpod был активен.

## Координация в `parse_fit`

`parse_fit._summarize_moving` (`lib/parse_fit.py`, schema ≥ 0.5.0):

1. Резолв RD-полей в порядке приоритета: Garmin RD > Stryd fallback.
2. Метрики возвращаются в `stryd_running_dynamics{}` со следующими `*_source` метками:
   - `vertical_oscillation_source`: `"garmin_rd"` | `"stryd"` | `None`
   - `stance_time_source`: `"garmin_rd"` | `"stryd"` | `None`
   - `step_length_source`: `"garmin_rd"` | `None`
3. **Никогда не подставляй нормы одного источника к цифрам другого.**

Если видишь, что `vertical_oscillation_source = "stryd"`, а потом `>11 см high` — это **не** корректная интерпретация (это Stryd-нормали, а цифры от Stryd — там нормы 5-8 для элиты).

## Что выбрать для тренда

| Источник | За | Против |
|---|---|---|
| **Garmin RD** | Исторический архив, UI видимый пользователю | Зависит от нагрудного ремня и профиля/прошивки FR 965 (часто отсутствует) |
| **Stryd** | Точнее в моменте, стабильно в FIT, **не требует нагрудного ремня** | Архив только с момента подключения, не виден в Garmin UI |

**Source-of-truth для разборов: STRYD** (per Кирилл, 2026-10-15: «Берём stryd. Garmin rd требует нагрудного ремня. Я не всегда его беру»). Garmin RD используется как cross-source sanity check и как fallback когда Stryd отсутствует (pool swims / indoor cycling / забытый footpod). Если пользователь откроет Garmin Connect UI и увидит другие цифры — это Garmin RD, другой sensor stack, **не сравнивай** напрямую.

`_pick()` в `parse_fit._summarize_moving` ходит в порядке `stryd_* → garmin_*` для VO/stance и `garmin_* → stryd_*` для step_length (Stryd его не пишет). `vo_source_label`/`stance_source_label` выставляют `"stryd"` или `"garmin_rd"` соответственно. `_garmin_*` поля всё равно возвращаются для cross-source сверки.

## Быстрая диагностика для разбора

Если `stryd_running_dynamics: {}` совсем пустое, перед тем как сказать «нет данных»:
1. Открой FIT напрямую через `fitparse` — какие record-поля реально есть (lowercase + capitalized)?
2. Если есть capitalized (`Vertical Oscillation`, `Ground Time`) — это Stryd. fit_inspect.py их не вытащил. Маппинг в `FitAnalysis.streams.append` где-то прочеркнул: проверь `stryd_*` поля.
3. Если есть lowercase без capitalized — Garmin FR 965 пишет только свой RD. Stryd не подключён.
4. Если есть оба — оба источника работали; проверь, какой парсер приоритизирует (Garmin > Stryd, см. schema 0.5.0).

## Probe-скрипт

```python
from fitparse import FitFile
fit = FitFile('/path/to/activity.fit')
for msg in fit.messages:
    if msg.name not in ('record', 'session', 'lap'):
        continue
    for f in msg.fields:
        if f.value is None: continue
        print(f'{msg.name:8s} {f.name:30s} {f.value}')
```

Это даёт полный список non-null полей в FIT'е без каких-либо фильтров. Если видишь `record Vertical Oscillation` (capitalized) — это Stryd. Видишь `record vertical_oscillation` (lowercase) — это Garmin RD.
