"""
build_domain_md.py — пересобрать DOMAIN-MODEL.md из HTML-спецификации.

Источник правды — HTML (`~/projects/coach-app/DOMAIN-SPEC.html`). Markdown — его текстовая
копия для работы в репозитории. Правки вносятся в HTML, потом запускается этот скрипт.

Запуск:
    python3 v2.architecture/build_domain_md.py

Пути overridable через аргументы: --src, --out.
"""
import re
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

DEFAULT_SRC = os.path.expanduser("~/projects/coach-app/DOMAIN-SPEC.html")
DEFAULT_OUT = os.path.join(HERE, "DOMAIN-MODEL.md")


def parse_args(argv):
    src, out = DEFAULT_SRC, DEFAULT_OUT
    i = 0
    while i < len(argv):
        if argv[i] == "--src" and i + 1 < len(argv):
            src = argv[i + 1]
            i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
        else:
            i += 1
    return src, out


SRC, OUT = parse_args(sys.argv[1:])
src = open(SRC, encoding="utf-8").read()


def strip_tags(s):
    s = re.sub(r'<code>(.*?)</code>', r'`\1`', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def md_table(rows):
    if not rows:
        return ""
    head = "| " + " | ".join(rows[0]) + " |"
    sep = "|" + "|".join(["---"] * len(rows[0])) + "|"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows[1:])
    return head + "\n" + sep + "\n" + body


def table_after(anchor):
    i = src.index(anchor)
    m = re.search(r'<table>(.*?)</table>', src[i:], re.S)
    if not m:
        return []
    rows = []
    for tr in re.findall(r'<tr>(.*?)</tr>', m.group(1), re.S):
        cells = [strip_tags(c) for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, re.S)]
        if cells:
            rows.append(cells)
    return rows


# ---- сущности ----
ents = re.findall(
    r'<div class="ent">\s*<div class="eh"><span>(.*?)</span><span class="k">(.*?)</span></div>\s*'
    r'(?:<ul class="role">(.*?)</ul>\s*)?<ul class="pl">(.*?)</ul>\s*</div>', src, re.S)
ENT = []
for name, kind, role, body in ents:
    ENT.append(f"### {name}  *({kind})*")
    if role:
        ENT.append(strip_tags(role))
    for li in re.findall(r'<li>(.*?)</li>', body, re.S):
        ENT.append("- " + strip_tags(li))
    ENT.append("")

# ---- инварианты ----
inv_block = src[src.index("<h3>Инварианты</h3>"):src.index("<h3>Производные значения</h3>")]
INV = []
for m in re.finditer(r'<tr[^>]*><td class="n">(I\d+)</td><td class="st">.*?</td><td>(.*?)</td></tr>', inv_block, re.S):
    INV.append([m.group(1), strip_tags(m.group(2)), "да"])

# ---- вопросы ----
qs = re.findall(r'<li>(.*?)</li>',
                src[src.index('<ol class="probs">'):src.index("</ol>", src.index('<ol class="probs">'))], re.S)
QUESTIONS = [strip_tags(q) for q in qs]

links = table_after('<section id="r">')
inherit = table_after('<h3>Наследование слотов</h3>')
derivs = table_after('<h3>Производные значения</h3>')
lifecycle = table_after('<h3>Жизненный цикл недели</h3>')
appear = table_after('<h4>Что появляется на каждом шаге</h4>')
linkfact = table_after('<h3>Связывание факта и плана</h3>')
closeweek = table_after('<h3>Закрытие недели</h3>')
inweek = table_after('<h3>Неделя в работе</h3>')
decisions = table_after('<h3>Решения по вопросам</h3>')

md = []
A = md.append

A("# Coach App — операционная доменная модель")
A("")
A("> **Статус:** рабочая версия, все инварианты подтверждены Кириллом (25.10.2026).")
A("> **Источник правды для этой части:** `~/projects/coach-app/DOMAIN-SPEC.html` — рисуется и читается как есть.")
A("> **Этот файл:** текстовая копия той же модели. Правки вносятся в HTML, сюда переносится синхронно.")
A("")
A("## Что это")
A("")
A("Операционная часть доменной модели приложения-тренера: сезон, план, неделя, тренировка, шаг, слоты, связывание плана с фактом.")
A("")
A("Модель описывает **операционный контур** — то, что происходит внутри сезона от предложения недели до её закрытия.")
A("За пределами этой части остаётся: UI, синхронизация между устройствами, хранение, адаптеры внешних источников.")
A("")
A("## Счётчики")
A("")
A(f"- Сущностей: **{len(ents)}**")
A(f"- Инвариантов: **{len(INV)}** (подтверждено {sum(1 for r in INV if r[2] == 'да')})")
A(f"- Вопросов: **{len(QUESTIONS)}**")
A("")
A("---")
A("")

A("## 1. Дерево сущностей")
A("")
A("```")
A("Season ── calendar.slots[], equipment[], plan_models[], load_model")
A("  └ Plan (status: active|completed|draft) ─ goal, period, sport_lines{}, load_budget, transition")
A("      ├ Goal ─ metric, race_date, venue, start_time, race_pace_min_per_km, realistic_fork")
A("      └ Phase ─ objective, focus, load_range, volume_range, intensity_pct_mean, deload_weeks[]")
A("          └ Week (status: proposed|active|closed) ─ focus, load_target, requests[],")
A("                                        assignments[], unplaced[], slot_overrides[],")
A("                                        workouts[], summary, detail")
A("              └ Workout ─ request_id, sport, kind, focus, objective, equipment[], steps[], actual_id")
A("                  └ Step ─ role, sport, target_type, target_value, focus, focus_value")
A("```")
A("")
A("Справочники сезона: `Equipment`, `PlanModel`, `LoadModel`, `Athlete`.")
A("Раскладка недели: `Slot` (окно), `SlotOverride` (patch), `Request` (запрос), `Assignment` (размещение).")
A("Факт: `ActualSession`. Итог: `WeekSummary`. Изменения: `Command`.")
A("")

A("## 2. Сущности")
A("")
A("\n".join(ENT))

A("## 3. Связи")
A("")
A("### Владение и ссылки")
A("")
A(md_table(links))
A("")
A("### Наследование слотов")
A("")
A(md_table(inherit))
A("")
A("Слот недели = `Season ← Phase ← Week`. Каждый уровень применяется последним и перекрывает предыдущий.")
A("Patch хранит только отличие от уровня выше.")
A("")

A("## 4. Жизненный цикл недели")
A("")
A(md_table(lifecycle))
A("")
A("**propose_week** — можно вызывать многократно. Планировщик берёт макро фазы, собирает намерения и раскладывает их по слотам.")
A("Всё, что не разложилось, уходит в ручной режим (`unplaced[]`). Каждый новый propose вытирает предыдущий, пока неделя не активна.")
A("")
A("**activate_week** — разложенные тренировки стоят по слотам. Неразложенные остаются висеть: расписание не обязано быть жёстким.")
A("Висялки можно разложить позже командой `place_unplaced`.")
A("")
A("**close_week** — явный ритуал в три шага (см. §6). Само ничего не закрывается.")
A("")
A("**replan_remainder** — переплан остатка недели: сессии на сегодня и позже. Прошедшие сессии не трогаются.")
A("«Сегодня» определяется по календарной дате.")
A("")
A("### Что появляется на каждом шаге")
A("")
A(md_table(appear))
A("")

A("## 5. Инварианты")
A("")
A("Все подтверждены. При добавлении нового — он попадает в конец с новым номером.")
A("")
A(md_table(INV))
A("")

A("## 6. Производные значения")
A("")
A("Не хранятся — считаются.")
A("")
A(md_table(derivs))
A("")

A("## 7. Связывание плана и факта")
A("")
A(md_table(linkfact))
A("")
A("**Цель связывания** — сопоставить задачу сессии с её выполнением.")
A("Всё, что не связано, в любом случае учитывается в actuals: связывание уточняет отчёт, но не решает, что считать сделанным.")
A("Автоматического сопоставления нет вообще — факт и план связывает пользователь, вручную, связь 1:1.")
A("Активности берутся только из Garmin. Поздний факт игнорируется.")
A("")
A("### Закрытие недели")
A("")
A(md_table(closeweek))
A("")
A("Всё, что попало в план до активации, считается планированием.")
A("Всё, что планировалось, но к моменту закрытия не связано с фактом, — **не выполнено**.")
A("Неподтверждённые сессии закрытию не мешают: они попадают в саммари как `missed`.")
A("Переносов между неделями нет: закрываем одну, потом планируем следующую.")
A("")
A("### Неделя в работе")
A("")
A(md_table(inweek))
A("")

A("## 8. Решения")
A("")
A("Зафиксированные ответы Кирилла. Действуют как правила модели.")
A("")
A(md_table(decisions))
A("")

A("## 9. Открытые вопросы")
A("")
for i, q in enumerate(QUESTIONS, 1):
    A(f"{i}. {q}")
A("")

A("## 10. Связанные тикеты")
A("")
A("- [tsybriki/coach#6 — Методология расчёта Training Stress Score / intensity minutes](https://github.com/tsybriki/coach/issues/6)")
A("  Референс: [Training Stress Scores (TSS) Explained — TrainingPeaks](https://share.google/JlFPisYIM7Fczte8R)")
A("- tsybriki/coach#5 — Plan vs actual: реальные тренировки рядом с планом")
A("")

A("## 11. Что впереди")
A("")
A("Операционная часть закрыта. Не сделано:")
A("")
A("- **Реализация.** Домен → код: слои domain/ports/app/adapters, тесты на каждый инвариант.")
A("- **Хранение.** Формат и объём, атомарная запись, миграции схемы.")
A("- **Адаптеры.** Garmin (интенсивность по тренировкам), Stryd, календарь.")
A("- **Методология нагрузки.** Задача #6 — считаем intensity minutes сами, с учётом зон атлета.")
A("- **UI.** Экраны: неделя, детали сессии, сезон, план vs факт, ручное связывание, закрытие недели.")
A("- **Синхронизация.** Mobile + offline: снапшот в IndexedDB, outbox команд.")
A("- **Оценка формы.** Как измерять результат работы мозга.")
A("")

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(md) + "\n")
print("written:", OUT, os.path.getsize(OUT), "bytes")
print("lines:", len(md))
print(f"entities={len(ents)} invariants={len(INV)} questions={len(QUESTIONS)}")
