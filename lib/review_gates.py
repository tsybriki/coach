"""
review_gates.py — точки принятия решения (review gates) в сезоне.

Gate = точка, где план пересматривается ПОСЛЕ события (фаза завершена,
контрольная точка пройдена). У каждого gate:
  - критерий (что именно проверяем, с порогом),
  - сохранённое предупреждение (риск, зафиксированный заранее),
  - ветки решений (что делать при pass / warn / fail),
  - рычаги (что конкретно можно крутить в season_plan.json).

Правило: план не «идёт по рельсам» — после каждого gate принимается решение
(подтвердить / скорректировать / пересобрать фазу). Решение пишется в
state/season_progress.json → gates[].

Запуск:
    python3 -m lib.review_gates --status
    python3 -m lib.review_gates --evaluate
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent

# Статус gate: pending — ещё не наступил, pass/warn/fail — отработал
PASS, WARN, FAIL, PENDING = "pass", "warn", "fail", "pending"


@dataclass
class Check:
    """Одна проверка внутри gate."""
    id: str
    label: str
    metric: str                      # что меряем в факте
    threshold: str                   # порог, читаемый человеком
    op: str = "ge"                   # ge | le | between | eq
    unit: str = ""
    severity: str = "hard"           # hard → fail, soft → warn
    source: str = "auto"             # auto | manual
    value: float | None = None
    status: str = PENDING
    note: str = ""


@dataclass
class Gate:
    id: str
    season_week: int
    kind: str                        # phase | quality | metric | race
    title: str
    question: str                    # что решаем в этом gate
    checks: list[Check] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)   # риски, зафиксированные заранее
    decisions: dict[str, list[str]] = field(default_factory=dict)  # pass|warn|fail → рычаги
    lever: str = ""                  # чем крутим при корректировке
    decided_at: str = ""
    decision: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "season_week": self.season_week,
            "kind": self.kind,
            "title": self.title,
            "question": self.question,
            "checks": [c.__dict__ for c in self.checks],
            "warnings": self.warnings,
            "decisions": self.decisions,
            "lever": self.lever,
            "decided_at": self.decided_at,
            "decision": self.decision,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Gate":
        g = cls(
            id=d["id"], season_week=d["season_week"], kind=d["kind"],
            title=d.get("title", ""), question=d.get("question", ""),
            warnings=d.get("warnings", []), decisions=d.get("decisions", {}),
            lever=d.get("lever", ""), decided_at=d.get("decided_at", ""),
            decision=d.get("decision", ""),
        )
        for c in d.get("checks", []):
            g.checks.append(Check(**c))
        return g


# ──────────────────────────── построение gates ────────────────────────────

def build_gates(sp: dict) -> list[Gate]:
    """Gates строятся из season_plan: после каждой фазы и каждой CP."""
    from lib import season_week

    start = sp["season_start_date"]
    sg = sp.get("season_goal") or {}
    gates: list[Gate] = []

    def week_of(d: str) -> int:
        try:
            return season_week.date_to_season_week(d, start)
        except Exception:
            return 0

    # ── 1. GATE ПОСЛЕ КАЖДОЙ ФАЗЫ ─────────────────────────────────────
    # Пороги берём из цели сезона и из правил объёма.
    phase_specs = {
        "run_base": {
            "title": "Итог базовой фазы",
            "question": "Достигнут ли базовый объём и подтверждён ли порог для входа в build?",
            "run_km_min": 45, "run_km_max": 55,
            "weeks_in_phase": 12,
            "warn": [
                "Фактический порог по FIT 13.10 ≈ 4:35–4:39/км. Цель сезона требует 4:10–4:15 к W13. "
                "Если к концу фазы порог ниже 4:25 — build придётся начинать с чистого порога, "
                "а не с объёма, и лестница к 4:00 сдвинется.",
                "PB 10К = 40:04 при 100 кг; сейчас 101.7 кг. Каждый кг сверх целевых 96 "
                "съедает примерно 4–6 с/км на 10К.",
            ],
            "pass": [
                "Объём бега 45–55 К/нед и ≥8 сессий — подтверждено.",
                "Порог на 4:20–4:30 — можно начинать build с пороговыми блоками.",
            ],
            "warn_dec": [
                "Объём 38–45 К: добавить 5К/нед в W13–W15, но не больше (+10%/нед).",
                "Порог 4:30–4:40: W13–W16 уходят в чистый порог, объёмные недели — на easy.",
            ],
            "fail_dec": [
                "Объём < 38 К или порог > 4:40: цель 40:00 в апреле под вопросом.",
                "Пересобрать фазу build: сократить до 6 недель, отдать время race-specific.",
                "Честно пересмотреть целевое время (41:00 вместо 40:00) — и записать это в season_goal.",
            ],
            "lever": "weekly_macro[].run_km / run_km_long / quality.variant_id, athlete.json training_paces",
        },
        "run_build": {
            "title": "Итог build-фазы: порог vs цель",
            "question": "Успел ли порог уйти к 4:10–4:15, чтобы race-specific шёл к 4:00?",
            "run_km_min": 50, "run_km_max": 60,
            "weeks_in_phase": 7,
            "warn": [
                "Ключевой риск всего сезона: цель 4:00 требует порога 4:10–4:15. "
                "Каждая неделя без движения порога — это шаг назад в гонке.",
                "Стадион в январе–феврале не чистят (мёртвый сезон) — темповые отрезки "
                "придётся делать по шоссе или на станке.",
            ],
            "pass": [
                "Порог 4:10–4:15 — race-specific получает рабочую базу, цель 40:00 достижима.",
                "Объём 50–60 К/нед, длинные интервалы 2К по 4:12 держатся.",
            ],
            "warn_dec": [
                "Порог 4:15–4:25: W20–W22 целиком в пороге, отрезки 5×2К сократить до 4×2К.",
                "Порог 4:25+: гонка на 4:00 в апреле не выходит — пересмотреть цель или сдвинуть гонку.",
            ],
            "fail_dec": [
                "Порог не сдвинулся за 7 недель — проблема не в объёме, а в восстановлении/весе.",
                "Снизить интенсивность, добавить 2 недели базы перед build.",
                "Пересмотреть целевое время в season_goal и не врать себе дальше.",
            ],
            "lever": "weekly_macro[].quality.variant_id, control_points[].session.pace_min_per_km",
        },
        "run_specific": {
            "title": "Готовность к гонке",
            "question": "Закрыт ли гонку-темп 4:00/км и держится ли объём?",
            "run_km_min": 45, "run_km_max": 70,
            "weeks_in_phase": 6,
            "warn": [
                "Это последняя точка принятия решения перед гонкой. После неё — только тапер.",
                "Гонка 18.04.2027 — через 2 недели после конца фазы.",
            ],
            "pass": [
                "5К на гонку-темпе ≤ 20:00 — цель 40:00 подтверждена.",
                "Объём 50+ К/нед и длинный темп 10К @ 4:05 — форма на месте.",
            ],
            "warn_dec": [
                "5К 20:00–20:15 — тапер сдвинуть на 2 дня, объём W24–W25 урезать на 20%.",
                "Длинный темп хуже 4:10 — W24 целиком tempo на 4:08, без объёма.",
            ],
            "fail_dec": [
                "5К > 20:15 — гонка-темп не закрыт. Чистый тапер или смена цели.",
                "Рекомендация: зафиксировать в season_goal новый target (41:00) и ехать на него.",
            ],
            "lever": "weekly_macro[].quality.variant_id, goals[].goal_metric.target",
        },
    }

    for ph in sp.get("phases", []):
        spec = phase_specs.get(ph["id"])
        if not spec:
            continue
        w_end = week_of(ph["end"])
        if not w_end:
            continue
        g = Gate(
            id="gate_phase_{}".format(ph["id"]),
            season_week=w_end,
            kind="phase",
            title="{} · {}".format(spec["title"], ph.get("goal", "")),
            question=spec["question"],
            warnings=list(spec["warn"]),
            lever=spec["lever"],
            decisions={
                PASS: spec["pass"],
                WARN: spec["warn_dec"],
                FAIL: spec["fail_dec"],
            },
        )
        g.checks = [
            Check(id="run_km", label="Объём бега за фазу (К/нед)",
                  metric="run_km_mean", threshold="{}–{} К".format(
                      spec["run_km_min"], spec["run_km_max"]),
                  op="between", unit="К/нед"),
            Check(id="sessions", label="Сессий в неделю",
                  metric="sessions_mean", threshold="≥ 7", op="ge", unit="сессий",
                  severity="soft"),
            Check(id="threshold_pace", label="Фактический порог (темп @ LTH)",
                  metric="threshold_pace", threshold="4:15", op="pace_le", unit="/км"),
            Check(id="volume_hours", label="Тренировочных часов за фазу",
                  metric="hours_mean", threshold="≥ {:.0f} ч/нед".format(
                      ph.get("hours_per_week_target", 5)),
                  op="ge", unit="ч/нед", severity="soft"),
        ]
        gates.append(g)

    # ── 2. GATE ПОСЛЕ КАЖДОЙ КОНТРОЛЬНОЙ ТОЧКИ ──────────────────────
    for cp in sp.get("control_points", []):
        s = cp.get("session") or {}
        w = cp.get("season_week")
        if not w or not s.get("target_sec"):
            continue
        g = Gate(
            id="gate_cp_{}".format(cp["id"]),
            season_week=w,
            kind="quality" if cp.get("kind") == "quality" else "metric",
            title="{} · {}".format(cp.get("what", ""), s.get("test_type", "")),
            question="Что говорит результат: идём по плану или корректируем?",
            warnings=[],
            lever=cp.get("id", ""),
        )
        pace = s.get("pace_min_per_km", "")
        g.checks = [
            Check(id="time", label="Время на дистанции",
                  metric="tt_time", threshold=_fmt(s["target_sec"]), op="le", unit="",
                  severity="hard"),
            Check(id="pace", label="Средний темп",
                  metric="tt_pace", threshold="{}".format(pace) if pace else "—",
                  op="pace_le", unit="/км", severity="soft"),
            Check(id="hr", label="Пульс на финише",
                  metric="tt_hr", threshold="≤ {}".format(
                      _fmt(s.get("target_sec", 0)) and s.get("hr_cap", "по протоколу")),
                  op="le", unit="уд/мин", severity="soft"),
        ]
        g.warnings = [s.get("fail_action", "")] if s.get("fail_action") else []
        g.decisions = {
            PASS: ["Результат в плане — подтверждаем фазу, следующий gate сдвигает план "
                   "на ступень выше."],
            WARN: [s.get("fail_action", "Частично не дотянул — добавляем объём в следующую неделю.")],
            FAIL: ["Результат провален — пересобираем фазу, а не продолжаем по рельсам.",
                    "Пересмотреть season_goal: цель 40:00 может оказаться нереальной."],
        }
        gates.append(g)

    # ── 3. GATE ПЕРЕД ГОНКОЙ ─────────────────────────────────────────
    for r in sp.get("races", []):
        w = week_of(r["date"])
        if not w:
            continue
        g = Gate(
            id="gate_race_{}".format(w),
            season_week=w,
            kind="race",
            title="Перед гонкой: {}".format(r.get("name", "")),
            question="Подтверждаем цель и тапер — или меняем?",
            warnings=[
                "Гонка без подтверждённого гонку-темпа — лотерея.",
                "После этого gate план не меняется: только тапер.",
            ],
            lever="weekly_macro[].quality.variant_id",
            decisions={
                PASS: ["Гонку-темп закрыт — едем с целью {}.".format(
                    (sp.get("season_goal") or {}).get("target_time", "—"))],
                WARN: ["Темп не закрыт — тапер сокращается, но гонка идёт: "
                       "заниженные ожидания лучше, чем срыв."],
                FAIL: ["Гонку-темп не закрыт вовсе — записать новую цель в season_goal "
                       "и ехать на неё. Не импровизировать в апреле."],
            },
        )
        g.checks = [
            Check(id="race_pace", label="Гонку-темп закрыт?",
                  metric="race_pace_confirmed", threshold="да (5К ≤ 20:00)",
                  op="eq", unit=""),
            Check(id="taper", label="Тапер: объём снижен, качество сохранено",
                  metric="taper_ok", threshold="да", op="eq", unit=""),
        ]
        gates.append(g)

    gates.sort(key=lambda g: (g.season_week, g.kind))
    return gates


def _fmt(sec: float) -> str:
    sec = float(sec)
    m = int(sec // 60)
    s = int(round(sec - m * 60))
    if s == 60:
        m += 1
        s = 0
    return "{}:{:02d}".format(m, s)


# ──────────────────────────── оценка факта ────────────────────────────

def evaluate_facts(gates: list[Gate], sp: dict) -> dict:
    """Считает фактические значения по чек-метрикам. Метрики без данных → None."""
    from lib import actual_load, season_week

    start = sp["season_start_date"]
    actual = actual_load.load_actual()
    acts = actual_load.load_raw_activities()

    # порог по всем интервальным сессиям: лучший темп при HR около LTH
    lth = 164
    # общий порог по всем сессиям — только для справки, не для чеков
    thr_pace = _estimate_threshold(acts, lth)

    # бег/сессии/часы по неделям
    weeks_fact = {w: d for w, d in actual.items()}

    by_week: dict[int, list[dict]] = {}
    for a in acts:
        if a.get("sport_type") != "running":
            continue
        try:
            from datetime import datetime
            d = datetime.fromisoformat(a["date"]).date()
            w = season_week.date_to_season_week(d, start)
        except Exception:
            continue
        if w:
            by_week.setdefault(w, []).append(a)

    facts: dict[str, float | None] = {}

    # текущая неделя сезона — факт за неё ещё не завершён
    from datetime import date
    today = date.today().isoformat()
    try:
        cur_week = season_week.date_to_season_week(today, start)
    except Exception:
        cur_week = 0

    for g in gates:
        if g.kind != "phase":
            continue
        # недели фазы — только завершённые (до текущей недели)
        ws = [w for w in _phase_weeks(sp, g.id.replace("gate_phase_", ""))
              if w < cur_week and w in weeks_fact]
        rows = [weeks_fact[w] for w in ws]
        if rows:
            facts["{}:run_km_mean".format(g.id)] = round(
                sum(r["run_km"] for r in rows) / len(rows), 1)
            facts["{}:sessions_mean".format(g.id)] = round(
                sum(r["sessions"] for r in rows) / len(rows), 1)
            facts["{}:hours_mean".format(g.id)] = round(
                sum(r["total_h"] for r in rows) / len(rows), 2)
            # порог — по лапсам ТОЛЬКО завершённых недель фазы
            thr_phase = _estimate_threshold(
                [a for a in acts if a.get("sport_type") == "running"
                 and _week_of(a, start) in ws], 164)
            if thr_phase:
                facts["{}:threshold_pace".format(g.id)] = thr_phase
        # фаза ещё не начиналась — факта нет, чек остаётся pending

    return facts


def _week_of(activity: dict, start: str) -> int | None:
    from datetime import datetime
    from lib import season_week
    try:
        d = datetime.fromisoformat(activity["date"]).date()
        return season_week.date_to_season_week(d, start)
    except Exception:
        return None


def _phase_weeks(sp: dict, phase_id: str) -> list[int]:
    from lib import season_week
    start = sp["season_start_date"]
    ph = next((p for p in sp.get("phases", []) if p["id"] == phase_id), None)
    if not ph:
        return []
    out = []
    try:
        w0 = season_week.date_to_season_week(ph["start"], start)
        w1 = season_week.date_to_season_week(ph["end"], start)
    except Exception:
        return []
    for w in range(w0, w1 + 1):
        out.append(w)
    return out


def _estimate_threshold(acts: list[dict], lth: int = 164,
                        window_s: int = 120, min_hr: int = 158,
                        max_hr: int = 168) -> float | None:
    """
    Фактический порог: лучший темп на КОРОТКОМ отрезке, который держался
    при пульсе около LTH.

    Считается по посекундным потокам FIT (fit_inspect.py streams): скользящее
    окно window_s секунд, где средний HR ≥ min_hr → берём темп этого окна.
    Так исключаются соревновательные забеги (avg HR 172 — это не порог)
    и длинные easy-сессии (avg HR 137 — это темп, а не порог).
    """
    import subprocess

    gt = Path.home() / "projects/garmin_tools"
    py = gt / ".venv/bin/python"
    if not py.exists():
        return _estimate_threshold_coarse(acts, lth)

    best = None
    for a in acts:
        if a.get("sport_type") != "running":
            continue
        fp = a.get("fit_path")
        if not fp or not Path(fp).exists():
            continue
        try:
            out = subprocess.run(
                [str(py), "fit_inspect.py", "laps", fp],
                capture_output=True, text=True, timeout=45, cwd=str(gt)).stdout
        except (subprocess.TimeoutExpired, OSError):
            continue
        for pace in _threshold_paces_from_laps(out, min_hr=min_hr, max_hr=max_hr):
            if best is None or pace < best:
                best = pace
    return round(best, 1) if best else None


def _threshold_paces_from_laps(tsv: str, min_hr: int = 158, max_hr: int = 168,
                              min_dur_s: int = 60, min_dist_m: int = 300) -> list[float]:
    """
    Темпы пороговых отрезков из таблицы лапсов fit_inspect.py laps.

    Лапс подходит, если: avg_HR в [min_hr, max_hr] (это работа у порога,
    а не easy и а не спринт), длительность ≥ min_dur_s, дистанция ≥ min_dist_m.

    ВАЖНО: avg_HR на лапсе — среднее по времени внутри лапса. Для коротких
    повторов (200–800м) это может быть 165–167 при пике 179 — то есть
    это верхняя граница, а не порог. Такие лапсы отсекаем по max_HR:
    если max_HR сильно выше max_hr, отрезок содержит спринт и порогом
    не считается.

    Возвращает список темпов (сек/км).
    """
    out: list[float] = []
    for line in tsv.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 10:
            continue
        # колонки laps: idx, start, dur, dist_m, avg_p, max_p, NP, avg_HR, max_HR, cad, ascent
        dur_s = _dur_to_sec(parts[2])
        dist_m = _num(parts[3])
        hr = _num(parts[7])
        hr_max = _num(parts[8])
        if dur_s is None or dist_m is None or hr is None:
            continue
        if dur_s < min_dur_s or dist_m < min_dist_m:
            continue
        if hr < min_hr or hr > max_hr:
            continue
        # спринт внутри лапса → это не пороговая работа
        if hr_max is not None and hr_max > max_hr + 3:
            continue
        out.append(dur_s / (dist_m / 1000.0))
    return out


def _dur_to_sec(s: str) -> float | None:
    """'0:04:17' → 257 секунд; '1:50' → 110."""
    s = s.strip()
    if not s:
        return None
    try:
        parts = [float(x) for x in s.split(":")]
    except ValueError:
        return None
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec


def _parse_streams(tsv: str) -> list[tuple[float, float, float]]:
    """
    → [(sec_offset, hr, distance_m)] из вывода fit_inspect.py streams.

    Формат: t_sec \t timestamp \t dist_m \t power \t hr \t cadence \t ...
    (первая строка — заголовок с '#').
    """
    rows = []
    for line in tsv.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            sec = float(parts[0])
            dist = float(parts[2])
            hr = float(parts[4])
        except ValueError:
            continue
        rows.append((sec, hr, dist))
    return rows


def _sustained_threshold_pace(rows, min_hr: int = 158, max_hr: int = 170,
                              min_run_s: int = 120, hr_smooth_s: int = 30) -> float | None:
    """
    Темп порога по НЕПРЕРЫВНЫМ отрезкам пороговой работы.

    Ключевое отличие от скользящего окна: окно захватывает финишный спринт
    (10 секунд burst'а внутри easy-сессии) и показывает нереально быстрый
    темп. Здесь мы ищем НЕПРЕРЫВНЫЕ отрезки, где сглаженный HR держится
    в диапазоне [min_hr, max_hr] не менее min_run_s секунд.

    - спринт: HR быстро уходит выше max_hr → отрезок обрывается
    - easy: HR ниже min_hr → отрезок не начинается
    - соревнование: HR выше max_hr почти весь забег → отрезок обрывается

    Из найденных отрезков берётся медиана — устойчивая оценка, а не рекорд.
    """
    if not rows:
        return None

    # сглаженный HR (скользящее среднее по hr_smooth_s)
    sm_hr: list[float] = []
    for i in range(len(rows)):
        lo = max(0, i - hr_smooth_s)
        hi = min(len(rows), i + hr_smooth_s)
        sm_hr.append(sum(r[1] for r in rows[lo:hi]) / (hi - lo))

    runs: list[tuple[float, float]] = []   # (pace_sec_per_km, duration_s)
    i = 0
    while i < len(rows):
        if sm_hr[i] < min_hr or sm_hr[i] > max_hr:
            i += 1
            continue
        j = i
        while j < len(rows) and sm_hr[j] >= min_hr and sm_hr[j] <= max_hr:
            j += 1
        dur = rows[j - 1][0] - rows[i][0]
        dist = rows[j - 1][2] - rows[i][2]
        if dur >= min_run_s and dist > 150:
            runs.append((dur / (dist / 1000.0), dur))
        i = j

    if not runs:
        return None
    # взвешенная медиана по длительности: длинная работа весомее
    runs.sort(key=lambda r: r[0])
    total = sum(d for _, d in runs)
    acc = 0.0
    for pace, dur in runs:
        acc += dur
        if acc >= total / 2:
            return pace
    return runs[-1][0]


def _estimate_threshold_coarse(acts: list[dict], lth: int = 164) -> float | None:
    """Запасной вариант без FIT-потоков: по среднему HR сессии."""
    best = None
    for a in acts:
        if a.get("sport_type") != "running":
            continue
        hr = a.get("avg_hr")
        pc = a.get("avg_pace_min_km")
        if not hr or not pc:
            continue
        if abs(hr - lth) > 8:
            continue
        v = float(pc) * 60
        if best is None or v < best:
            best = v
    return round(best, 1) if best else None


# ──────────────────────────── статусы ────────────────────────────

def apply_facts(gates: list[Gate], facts: dict) -> None:
    """Проставляет value/status чекам по фактическим значениям."""
    for g in gates:
        for c in g.checks:
            key = "{}:{}".format(g.id, c.metric)
            val = facts.get(key)
            c.value = val
            if val is None:
                c.status = PENDING
                continue
            c.status = _judge(c, val)


def _judge(c: Check, val: float) -> str:
    if c.op == "pace_le":
        thr = _pace_sec(c.threshold)
        if thr is None:
            return PENDING
        return PASS if val <= thr else (WARN if c.severity == "soft" else FAIL)
    if c.op == "between":
        lo, hi = _range(c.threshold)
        if lo <= val <= hi:
            return PASS
        return WARN if c.severity == "soft" else FAIL
    if c.op == "ge":
        thr = _num(c.threshold)
        if thr is None:
            return PENDING
        return PASS if val >= thr else (WARN if c.severity == "soft" else FAIL)
    if c.op == "le":
        thr = _num(c.threshold)
        if thr is None:
            return PENDING
        return PASS if val <= thr else (WARN if c.severity == "soft" else FAIL)
    return PENDING


def _pace_sec(th: str) -> float | None:
    """'4:15' → 255 секунд на км."""
    import re
    m = re.search(r"(\d+):(\d{2})", str(th))
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def _range(th: str) -> tuple[float, float]:
    nums = [float(x) for x in __import__("re").findall(r"(\d+(?:\.\d+)?)", th)]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if nums:
        return nums[0], nums[0]
    return 0.0, 0.0


def _num(th: str) -> float | None:
    import re
    m = re.search(r"(\d+(?:[.:]\d+)?)", str(th).replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(1).replace(":", "."))
    except ValueError:
        return None


def gate_status(g: Gate, current_week: int | None = None) -> str:
    """Итоговый статус gate по чекам.

    Если неделя гейта ещё не прошла (current_week < season_week) —
    gate в статусе «ожидание», даже если часть чеков имеет значения:
    решение по нему принимать не по чему.
    """
    if not g.checks:
        return PENDING
    if current_week is not None and g.season_week > current_week:
        return PENDING
    st = [c.status for c in g.checks]
    if FAIL in st:
        return FAIL
    if WARN in st:
        return WARN
    if PASS in st:
        return PASS
    return PENDING


# ──────────────────────────── хранение ────────────────────────────

def progress_path() -> Path:
    return REPO / "state/season_progress.json"


def load_progress() -> dict:
    p = progress_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"schema_version": "0.1.0", "gates": []}


def save_progress(prog: dict) -> None:
    progress_path().write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_gates(sp: dict) -> list[Gate]:
    """Синхронизирует gates в season_progress.json, сохраняя принятые решения."""
    prog = load_progress()
    existing = {g["id"]: g for g in prog.get("gates", [])}
    fresh = build_gates(sp)
    out = []
    for g in fresh:
        old = existing.get(g.id)
        if old:
            old_g = Gate.from_dict(old)
            # принятое решение не теряется
            g.decided_at = old_g.decided_at
            g.decision = old_g.decision
            # значения факта, если были, сохраняются
            for c_new, c_old in zip(g.checks, old_g.checks):
                if c_new.id == c_old.id:
                    c_new.value = c_old.value
                    c_new.status = c_old.status
                    c_new.note = c_old.note
        out.append(g)
    prog["gates"] = [g.to_dict() for g in out]
    save_progress(prog)
    return out


def decide(gate_id: str, decision: str, note: str = "") -> dict:
    """Фиксирует принятое решение по gate."""
    prog = load_progress()
    for g in prog.get("gates", []):
        if g["id"] == gate_id:
            from datetime import datetime, timezone
            g["decision"] = decision
            g["decided_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if note:
                for c in g.get("checks", []):
                    c["note"] = note
            save_progress(prog)
            return {"gate": gate_id, "decision": decision, "note": note}
    return {"error": "gate не найден: {}".format(gate_id)}


def main() -> int:
    import argparse
    from lib import season_week
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="показать gates и их статус")
    ap.add_argument("--evaluate", action="store_true", help="посчитать факт и проставить статус")
    args = ap.parse_args()

    sp = json.loads((REPO / "state/season_plan.json").read_text(encoding="utf-8"))
    gates = sync_gates(sp)

    if args.evaluate:
        facts = evaluate_facts(gates, sp)
        apply_facts(gates, facts)
        prog = load_progress()
        by_id = {g["id"]: g for g in prog.get("gates", [])}
        for g in gates:
            if g.id in by_id:
                for c_new, c_old in zip(g.checks, by_id[g.id].get("checks", [])):
                    if c_new.id == c_old.get("id"):
                        c_old["value"] = c_new.value
                        c_old["status"] = c_new.status
        save_progress(prog)
        print("факт посчитан: {} метрик".format(len(facts)))

    from datetime import date
    try:
        cur_week = season_week.date_to_season_week(date.today().isoformat(), sp["season_start_date"])
    except Exception:
        cur_week = 0

    if args.status or not (args.evaluate):
        print("\nGATES\n" + "=" * 72)
        for g in gates:
            st = gate_status(g, cur_week)
            mark = {PASS: "✓", WARN: "!", FAIL: "✗", PENDING: "·"}.get(st, "·")
            print("\n{} W{:<2} [{}] {}".format(mark, g.season_week, g.kind, g.title))
            print("   вопрос: {}".format(g.question))
            for c in g.checks:
                v = "—" if c.value is None else (
                    "{:.1f}".format(c.value) if isinstance(c.value, float) else str(c.value))
                print("   · {}: {} (порог {}) → {} [{}]".format(
                    c.label, v, c.threshold, c.status, c.severity))
            for w in g.warnings:
                print("   ⚠ " + w[:150])
            if g.decision:
                print("   → решение: {}".format(g.decision))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.exit(main())
