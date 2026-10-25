"""
load_model.py — расчёт тренировочной нагрузки недели.

Зачем: в макро у недели есть `total_h` — «примерная тренировочная нагрузка
на макро-уровне». Это НЕ пересчёт по средней 5.7 мин/км: реальное время
зависит от темпа, а темп в неделе разный (длинная по 6:00, интервалы
по 4:00, лёгкая по 5:45).

Модель считает время по КАЖДОЙ СЕССИИ недели отдельно, используя
настоящие темпы из athlete.json:

  бег:
    long_z2       → длинная пробежка, темп Z2 (медленнее среднего)
    quality       → интервалы: работа по темпу цели + отдых + разминка
    easy          → Z2
    progression   → Z2 с прогрессией
  вел / плав / core → из макро напрямую (там минуты)

Результат:
    macro_load_h   — нагрузка недели по макро (что закладывает сезон)
    detail_h       — то же, но посчитано по структуре (если есть план недели)

Проверка: `python3 -m lib.load_model --week 3`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent


def pace_sec(s: str) -> float | None:
    """'5:45' → 345 секунд на км. '5:40-5:50' → 340 (первая граница)."""
    m = re.search(r"(\d+):(\d{2})", str(s))
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def pace_range(s: str) -> tuple[float, float]:
    """'5:40-5:50' → (340, 350)."""
    vals = []
    for m in re.finditer(r"(\d+):(\d{2})", str(s)):
        vals.append(int(m.group(1)) * 60 + int(m.group(2)))
    if not vals:
        return (0.0, 0.0)
    if len(vals) == 1:
        return (vals[0], vals[0])
    return (min(vals), max(vals))


def session_minutes(spec: str) -> int:
    """'2×25м' → 50; '1×60м' → 60; '45м' → 45; '2×25м + 10м' → 60."""
    if not spec:
        return 0
    total = 0
    for part in str(spec).split("+"):
        m = re.search(r"(\d+)\s*[×x]\s*(\d+)\s*м", part)
        if m:
            total += int(m.group(1)) * int(m.group(2))
            continue
        m = re.search(r"(\d+)\s*м", part)
        if m:
            total += int(m.group(1))
    return total


# ─────────────────────────── модель времени ───────────────────────────

def _run_time_for(km: float, pace: float) -> float:
    """Время пробежки в минутах."""
    return km * pace / 60.0


def current_vdot(default: float | None = None) -> float | None:
    """Текущий VDOT атлета — из state/daniels_profile.json."""
    p = REPO / "state" / "daniels_profile.json"
    if not p.exists():
        return default
    try:
        v = json.loads(p.read_text(encoding="utf-8")).get("vdot")
        return float(v) if v is not None else default
    except (json.JSONDecodeError, OSError, ValueError):
        return default


def macro_week_load(week: dict[str, Any], at: dict[str, Any],
                    quality_min: int | None = None,
                    vdot: float | None = None) -> dict[str, Any]:
    """
    Нагрузка недели по макро.

    quality_min — длительность качественной сессии в минутах (берётся из
    плана недели, если известна). Если не задана — оценивается по
    структуре качественной работы из шаблона.
    """
    tp = ((at.get("current_form") or {}).get("training_paces") or {})
    z2 = pace_sec(tp.get("Z2_pace", "5:45")) or 345
    thr = pace_sec(tp.get("threshold_pace", "4:15")) or 255
    vo2 = pace_sec(tp.get("vo2max_pace", "4:00")) or 240

    run_km = float(week.get("run_km") or 0)
    long_km = float(week.get("long_km") or 0)

    # 1) длинная пробежка — по Z2 (медленнее среднего)
    long_h = _run_time_for(long_km, z2) / 60.0

    # 2) качественная сессия: работа по темпу цели + отдых + разминка/заминка
    q_work_km = _quality_work_km(week)
    # темпы для расчёта времени работы — из блоков, с fallback на шкалу зон
    paces: dict[str, float] = {}
    # Темпы берём из структуры (уже вычисленной под VDOT в каталоге)
    for pc in _week_paces(week):
        v = pace_sec(pc)
        if v:
            paces[pc] = v
    paces.setdefault("__easy__", z2)

    if vdot is None:
        vdot = current_vdot()
    q_min = quality_min if quality_min is not None else _quality_minutes(week, paces, vdot)
    q_h = (q_min or 0) / 60.0

    # 3) остальной объём — по Z2
    rest_km = max(0.0, run_km - long_km - q_work_km)
    rest_h = _run_time_for(rest_km, z2) / 60.0

    run_h = long_h + rest_h + q_h

    bike_h = session_minutes(week.get("bike", "")) / 60.0
    swim_h = session_minutes(week.get("swim", "")) / 60.0
    ofp_h = session_minutes(week.get("core", "")) / 60.0

    total = run_h + bike_h + swim_h + ofp_h
    return {
        "run_h": round(run_h, 2),
        "run_long_h": round(long_h, 2),
        "run_easy_h": round(rest_h, 2),
        "run_quality_h": round(q_h, 2),
        "bike_h": round(bike_h, 2),
        "swim_h": round(swim_h, 2),
        "ofp_h": round(ofp_h, 2),
        "total_h": round(total, 2),
        "quality_min": q_min,
        "quality_work_km": q_work_km,
        "run_km": run_km,
        "long_km": long_km,
        "_model": "длинная по Z2 + качественная по темпу цели (с отдыхом) + остальное по Z2",
    }


def _week_paces(week: dict[str, Any]) -> list[str]:
    """Все темпы недели: из макро (если есть) или из каталога по variant_id."""
    q = week.get("quality") or {}
    pl = q.get("paces") or []
    if pl:
        return list(pl)
    vid = q.get("variant_id")
    if not vid:
        return []
    try:
        from .quality_session import get_variant
        v = get_variant(vid)
    except Exception:
        return []
    out: list[str] = []
    for b in ((v or {}).get("blocks") or []):
        for key in ("pace", "from_pace", "to_pace", "easy_pace", "hard_pace"):
            if b.get(key):
                out.append(b[key])
        for pc in (b.get("paces") or []):
            out.append(pc)
    return out


def _quality_work_km(week: dict[str, Any]) -> float:
    """
    Объём работы качественной сессии в км.

    Источник — СТРУКТУРИРОВАННЫЕ блоки (quality.blocks), а не разбор строки.
    Блоки приходят из state/workout_templates.json, где у каждого варианта
    есть work_m — готовое число. Если блоков нет, берём work_m из quality.
    """
    q = week.get("quality") or {}
    blocks = q.get("blocks")
    if not blocks:
        # Структуры в макро нет — она в каталоге (variant_id).
        vid = q.get("variant_id")
        if vid:
            try:
                from .quality_session import get_variant
                v = get_variant(vid)
                blocks = (v or {}).get("blocks")
            except Exception:
                blocks = None
    if not blocks:
        wm = q.get("work_m")
        return round(wm / 1000.0, 3) if wm else 0.0

    total_m = 0
    for b in blocks:
        btype = b.get("type")
        if btype == "reps":
            total_m += int(b.get("reps", 0)) * int(b.get("distance_m", 0))
        elif btype == "reps_progression":
            total_m += int(b.get("reps", 0)) * int(b.get("distance_m", 0))
        elif btype in ("continuous", "tt_pace", "tt_max"):
            total_m += int(b.get("distance_m", 0))
        elif btype == "pyramid":
            for st in (b.get("steps") or []):
                total_m += int(st.get("distance_m", 0))
        elif btype == "fartlek":
            cycles = int(b.get("cycles", 1))
            total_m += cycles * (int(b.get("easy_distance_m", 0))
                                 + int(b.get("hard_distance_m", 0)))
        elif btype == "progression":
            total_m += (int(b.get("easy_distance_m", 0))
                        + int(b.get("progression_distance_m", 0)))
    return round(total_m / 1000.0, 3)


def _quality_minutes(week: dict[str, Any], paces: dict[str, float],
                     vdot: float | None = None) -> int:
    """
    Длительность качественной сессии по блокам:
      время работы (по темпу блока) + отдых + разминка 15 + заминка 12.
    """
    q = week.get("quality") or {}
    blocks = q.get("blocks") or []
    vid = q.get("variant_id")
    if not blocks and vid:
        try:
            from .quality_session import variant_with_paces
            v = variant_with_paces(vid, vdot)
            blocks = (v or {}).get("blocks") or []
        except Exception:
            blocks = []
    if not blocks:
        return 0

    total_min = 0.0
    for b in blocks:
        btype = b.get("type")
        if btype == "reps":
            reps = int(b.get("reps", 0))
            pace = paces.get(b.get("pace", ""), 300.0)
            total_min += reps * int(b.get("distance_m", 0)) / 1000.0 * pace / 60.0
            if reps > 1:
                rest = float(b.get("rest_min", 0))
                # отдых бегом — тоже занимает время
                rest_pace = paces.get("__easy__", 340.0)
                total_min += (reps - 1) * (
                    rest + int(b.get("rest_distance_m", 0)) / 1000.0 * rest_pace / 60.0)
        elif btype == "reps_progression":
            reps = int(b.get("reps", 0))
            plist = b.get("paces") or [b.get("pace", "4:00")]
            dist = int(b.get("distance_m", 0))
            for i in range(reps):
                pc = plist[min(i, len(plist) - 1)]
                total_min += dist / 1000.0 * paces.get(pc, 300.0) / 60.0
                if i < reps - 1:
                    rest = float(b.get("rest_min", 0))
                    rest_pace = paces.get("__easy__", 340.0)
                    total_min += (rest + int(b.get("rest_distance_m", 0)) / 1000.0 * rest_pace / 60.0)
        elif btype in ("continuous", "tt_pace", "tt_max"):
            pace = paces.get(b.get("pace", ""), 300.0)
            total_min += int(b.get("distance_m", 0)) / 1000.0 * pace / 60.0
        elif btype == "pyramid":
            for st in (b.get("steps") or []):
                pace = paces.get(st.get("pace", ""), 300.0)
                total_min += int(st.get("distance_m", 0)) / 1000.0 * pace / 60.0
            rest = float(b.get("rest_min", 0))
            rest_pace = paces.get("__easy__", 340.0)
            total_min += max(0, len(b.get("steps") or []) - 1) * (
                rest + int(b.get("rest_distance_m", 0)) / 1000.0 * rest_pace / 60.0)
        elif btype == "fartlek":
            cycles = int(b.get("cycles", 1))
            easy_p = paces.get(b.get("easy_pace", ""), 320.0)
            hard_p = paces.get(b.get("hard_pace", ""), 250.0)
            total_min += cycles * (
                int(b.get("easy_distance_m", 0)) / 1000.0 * easy_p / 60.0
                + int(b.get("hard_distance_m", 0)) / 1000.0 * hard_p / 60.0)
        elif btype == "progression":
            mid = (paces.get(b.get("from_pace", ""), 300.0)
                   + paces.get(b.get("to_pace", ""), 300.0)) / 2
            total_min += int(b.get("easy_distance_m", 0)) / 1000.0 * mid / 60.0
            total_min += int(b.get("progression_distance_m", 0)) / 1000.0 * mid / 60.0

    return int(round(total_min + 15 + 12))


def _sum_bare_meters(leg: str) -> float:
    """Сумма метров вида '200@5:10 + 800@3:50' (без '×')."""
    total = 0.0
    for m in re.finditer(r"(?<![×x]\s)(\d{2,4})\s*@", leg):
        total += float(m.group(1))
    return total / 1000.0


def plan_week_load(plan: dict[str, Any]) -> dict[str, Any]:
    """Нагрузка по фактическим слотам сгенерированного плана недели."""
    slots = plan.get("slots") or []
    run_h = bike_h = swim_h = ofp_h = 0.0
    for s in slots:
        d = (s.get("duration_min") or 0) / 60.0
        kind = s.get("subkind") or s.get("kind") or ""
        if kind in ("core", "ofp"):
            ofp_h += d
        elif kind in ("bike", "stationary_z2", "stationary_z3", "long_z2", "zwift", "ride"):
            bike_h += d
        elif kind in ("swim", "pool"):
            swim_h += d
        else:
            run_h += d
    return {
        "run_h": round(run_h, 2),
        "bike_h": round(bike_h, 2),
        "swim_h": round(swim_h, 2),
        "ofp_h": round(ofp_h, 2),
        "total_h": round(run_h + bike_h + swim_h + ofp_h, 2),
        "sessions": len(slots),
    }


def compare(target_h: float, actual_h: float, tol_pct: float = 10.0) -> dict[str, Any]:
    """Сравнение плана недели с целью макро."""
    if not target_h:
        return {"status": "unknown", "delta_h": 0, "delta_pct": 0.0}
    delta = round(actual_h - target_h, 2)
    pct = round(delta / target_h * 100, 1)
    if abs(pct) <= tol_pct:
        status = "ok"
    elif pct > 0:
        status = "over"
    else:
        status = "under"
    return {
        "status": status,
        "target_h": round(target_h, 2),
        "actual_h": round(actual_h, 2),
        "delta_h": delta,
        "delta_pct": pct,
        "tol_pct": tol_pct,
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, default=3)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    sp = json.loads((REPO / "state/season_plan.json").read_text(encoding="utf-8"))
    at = json.loads((REPO / "state/athlete.json").read_text(encoding="utf-8"))

    if args.all:
        print("W | план(макро) | всего")
        for w in sp["weekly_macro"]:
            ml = macro_week_load(w, at)
            print("W{:<2} | {:>5.2f}ч | {:>5}ч (макро)".format(
                w["season_week"], ml["total_h"], w.get("total_h")))
        return 0

    w = next((x for x in sp["weekly_macro"] if x["season_week"] == args.week), None)
    if not w:
        print("неделя не найдена")
        return 1
    ml = macro_week_load(w, at)
    print("W{}: рассчитанная нагрузка {:.2f}ч".format(args.week, ml["total_h"]))
    print("  бег {:.2f} | вел {:.2f} | плав {:.2f} | core {:.2f}".format(
        ml["run_h"], ml["bike_h"], ml["swim_h"], ml["ofp_h"]))
    print("  в макро total_h = {}".format(w.get("total_h")))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.exit(main())
