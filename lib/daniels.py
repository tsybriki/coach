"""
daniels.py — таблицы Дэниэлса (Training Paces + VDOT race times).

Источник: скан из "Daniels' Running Formula" (Training Paces table и
таблица «Время на дистанции к VDOT»), присланы Кириллом 24.10.2026.

Хранится в ~/coach/reference/daniels/:
  raw_training_paces.txt   — как прислано (Таблица 1: темпы по зонам)
  raw_vdot_race_times.txt  — как прислано (Таблица 2: время на дистанции)
  daniels_tables.json      — разобранные, машинно-читаемые

Что даёт:
  paces_for_vdot(v)        → темпы всех зон для VDOT
  race_times_for_vdot(v)   → время на дистанции для VDOT
  vdot_for_race(d, t)      → VDOT по результату (с интерполяцией)
  pace_sec(pace, dist)    → темп в с/км

Зоны (Таблица 1):
  JL — Easy (лёгкая),      M — Marathon,     П — Threshold,
  И  — Interval (интервал), Пв — Repetition (повторы)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REF_DIR = Path.home() / "coach" / "reference" / "daniels"
JSON_PATH = REF_DIR / "daniels_tables.json"

MILE_M = 1609.344


# ─────────────────────────── разбор времени ───────────────────────────

def parse_time(token: str) -> int | None:
    """
    '12:40' → 760; '1:47' → 107; '7.10' → 430; '431' → 271 (4:31);
    '98' → 98 (секунды для 400м); '_' / '-' → None.
    """
    s = str(token).strip()
    if s in ("_", "-", "—", "", "НИ Н"):
        return None
    s = s.replace(".", ":")
    if ":" in s:
        parts = s.split(":")
        try:
            vals = [int(p) for p in parts]
        except ValueError:
            return None
        sec = 0
        for v in vals:
            sec = sec * 60 + v
        return sec
    if not s.isdigit():
        return None
    n = int(s)
    if n < 100:
        return n                      # голые секунды (400м в интервалах)
    if n < 1000:
        return (n // 100) * 60 + (n % 100)   # 431 → 4:31
    return n


def fmt_time(sec: int | None) -> str:
    if sec is None:
        return "—"
    if sec < 60:
        return "{}с".format(sec)
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return "{}:{:02d}:{:02d}".format(h, m, s) if h else "{}:{:02d}".format(m, s)


def pace_sec(pace: str) -> float | None:
    """'4:29' → 269 секунд на км."""
    v = parse_time(pace)
    return float(v) if v is not None else None


def pace_per_km(sec_per_dist: int, dist_m: int) -> float:
    """Сек/км по времени на дистанции."""
    return sec_per_dist / (dist_m / 1000.0)


# ─────────────────────────── загрузка ───────────────────────────

def load_tables() -> dict[str, Any]:
    """Разобранные таблицы (из JSON, если есть; иначе парсятся заново)."""
    if JSON_PATH.exists():
        return json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return _parse_all()


def _parse_all() -> dict[str, Any]:
    return {"training_paces": _parse_training_paces(),
            "race_times": _parse_race_times()}


def _parse_training_paces() -> list[dict]:
    """
    Таблица 1 «Training Paces».

    Колонки (проверено по сходимости темпов, VDOT 30–85):
      0     VDOT
      1,2   JL (Easy): миля, км
      3,4   M (Marathon): миля, км
      5,6,7 П (Threshold): 400м, 1000м, миля  → дают один темп/км
      8     И (Interval): VDOT интервального темпа
      9,10,11  И: 400м, 1000м, 1200м → один темп/км
      12    Пв (Repetition): миля
      13,14,15  Пв: 200м, 400м, 800м → один темп/км
    """
    raw = (REF_DIR / "raw_training_paces.txt").read_text(encoding="utf-8")
    out = []
    for line in raw.splitlines():
        p = line.split()
        if not p or not p[0].isdigit():
            continue
        vdot = int(p[0])

        def g(i):
            return p[i] if i < len(p) else "-"

        easy_mile = parse_time(g(1))
        easy_km = parse_time(g(2))
        mar_mile = parse_time(g(3))
        mar_km = parse_time(g(4))
        thr_400 = parse_time(g(5))
        thr_1000 = parse_time(g(6))
        thr_mile = parse_time(g(7))
        int_vdot = int(g(8)) if g(8).isdigit() else None
        int_400 = parse_time(g(9))
        int_1000 = parse_time(g(10))
        int_1200 = parse_time(g(11))
        rep_mile_from_tbl = parse_time(g(12))
        rep_200 = parse_time(g(13))
        rep_400 = parse_time(g(14))
        rep_800 = parse_time(g(15))

        out.append({
            "vdot": vdot,
            "easy": {"mile": easy_mile, "km": easy_km},
            "marathon": {"mile": mar_mile, "km": mar_km},
            "threshold": {
                "400m": thr_400,
                "1000m": thr_1000,
                "mile": thr_mile,
                "pace_per_km": (round(pace_per_km(thr_1000, 1000), 1)
                                if thr_1000 else None),
            },
            "interval": {
                "vdot": int_vdot,
                "400m": int_400,
                "1000m": int_1000,
                "1200m": int_1200,
                "pace_per_km": (round(pace_per_km(int_1000, 1000), 1)
                                if int_1000 else None),
            },
            "repetition": {
                "mile": rep_mile_from_tbl,
                "200m": rep_200,
                "400m": rep_400,
                "800m": rep_800,
                "pace_per_km": (round(pace_per_km(rep_400, 400), 1)
                                if rep_400 else None),
            },
        })
    return out


def _parse_race_times() -> list[dict]:
    """
    Таблица 2 «Время на дистанции к VDOT».

    Колонки: 0 VDOT | 1 1500м | 2 миля | 3 3000м | 4 2 мили |
              5 5000м | 6 10000м | 7 15000м | 8 полумарафон | 9 марафон
    """
    raw = (REF_DIR / "raw_vdot_race_times.txt").read_text(encoding="utf-8")
    out = []
    for line in raw.splitlines():
        p = line.split()
        if not p or not p[0].isdigit():
            continue
        vdot = int(p[0])

        def g(i):
            return p[i] if i < len(p) else "-"

        out.append({
            "vdot": vdot,
            "1500m": parse_time(g(1)),
            "mile": parse_time(g(2)),
            "3000m": parse_time(g(3)),
            "2_miles": parse_time(g(4)),
            "5000m": parse_time(g(5)),
            "10000m": parse_time(g(6)),
            "15000m": parse_time(g(7)),
            "half": parse_time(g(8)),
            "marathon": parse_time(g(9)),
        })
    return out


# ─────────────────────────── запросы ───────────────────────────

def _find(rows: list[dict], vdot: float, key: str = "vdot") -> dict | None:
    """Ближайшая строка с VDOT ≤ запрошенного (для интерполяции)."""
    best = None
    for r in rows:
        if r[key] <= vdot:
            if best is None or r[key] > best[key]:
                best = r
    return best


def paces_for_vdot(vdot: float) -> dict[str, Any]:
    """Темпы всех зон для VDOT (интерполяция по соседним строкам)."""
    rows = load_tables()["training_paces"]
    exact = next((r for r in rows if r["vdot"] == int(vdot)), None)
    if exact:
        return exact
    lo = _find(rows, vdot)
    hi = next((r for r in rows if r["vdot"] > vdot), None)
    if not lo:
        return rows[0]
    if not hi or hi["vdot"] == lo["vdot"]:
        return lo
    frac = (vdot - lo["vdot"]) / (hi["vdot"] - lo["vdot"])

    def lerp(a, b):
        if a is None or b is None:
            return a
        return int(round(a + (b - a) * frac))

    out = {"vdot": vdot, "_interpolated": True, "_between": [lo["vdot"], hi["vdot"]]}
    for zone in ("easy", "marathon", "threshold", "interval", "repetition"):
        out[zone] = {k: lerp(lo[zone].get(k), hi[zone].get(k))
                     for k in lo[zone]}
    return out


def race_times_for_vdot(vdot: float) -> dict[str, Any]:
    """Время на дистанции для VDOT (с интерполяцией)."""
    rows = load_tables()["race_times"]
    exact = next((r for r in rows if r["vdot"] == int(vdot)), None)
    if exact:
        return exact
    lo = _find(rows, vdot)
    hi = next((r for r in rows if r["vdot"] > vdot), None)
    if not lo:
        return rows[0]
    if not hi or hi["vdot"] == lo["vdot"]:
        return lo
    frac = (vdot - lo["vdot"]) / (hi["vdot"] - lo["vdot"])
    out = {"vdot": vdot, "_interpolated": True, "_between": [lo["vdot"], hi["vdot"]]}
    for k in lo:
        if k == "vdot":
            continue
        a, b = lo.get(k), hi.get(k)
        out[k] = int(round(a + (b - a) * frac)) if a and b else a
    return out


def vdot_for_race(distance_m: int, time_sec: int) -> dict[str, Any]:
    """VDOT по результату на дистанции."""
    rows = load_tables()["race_times"]
    key = {1500: "1500m", 1609: "mile", 3000: "3000m", 3218: "2_miles",
           5000: "5000m", 10000: "10000m", 15000: "15000m",
           21097: "half", 42195: "marathon"}.get(distance_m)
    if key is None:
        return {"error": "дистанция {} не представлена в таблице".format(distance_m)}
    for r in rows:
        t = r.get(key)
        if t and abs(t - time_sec) <= 2:
            return {"vdot": r["vdot"], "exact": True, "race_time": t}
    # интерполяция
    for a, b in zip(rows, rows[1:]):
        ta, tb = a.get(key), b.get(key)
        if ta and tb and min(ta, tb) <= time_sec <= max(ta, tb):
            frac = (time_sec - ta) / (tb - ta)
            v = a["vdot"] + (b["vdot"] - a["vdot"]) * frac
            return {"vdot": round(v, 2), "exact": False,
                    "between": [a["vdot"], b["vdot"]]}
    return {"error": "результат вне диапазона таблицы"}


def zone_summary(vdot: float) -> dict[str, Any]:
    """Сводка темпов по зонам — удобно для показа."""
    p = paces_for_vdot(vdot)
    t = p["threshold"]
    i = p["interval"]
    r = p["repetition"]
    e = p["easy"]
    m = p["marathon"]
    return {
        "vdot": p["vdot"],
        "easy_mile": e.get("mile"), "easy_km": e.get("km"),
        "marathon_mile": m.get("mile"), "marathon_km": m.get("km"),
        "threshold_400": t.get("400m"), "threshold_1000": t.get("1000m"),
        "threshold_pace_km": t.get("pace_per_km"),
        "interval_400": i.get("400m"), "interval_1000": i.get("1000m"),
        "interval_1200": i.get("1200m"),
        "interval_pace_km": i.get("pace_per_km"),
        "repetition_200": r.get("200m"), "repetition_400": r.get("400m"),
        "repetition_800": r.get("800m"),
        "repetition_pace_km": r.get("pace_per_km"),
    }


if __name__ == "__main__":
    import sys
    v = float(sys.argv[1]) if len(sys.argv) > 1 else 47
    s = zone_summary(v)
    print("VDOT {}".format(s["vdot"]))
    print("  JL (easy)    миля {} | км {}".format(
        fmt_time(s["easy_mile"]), fmt_time(s["easy_km"])))
    print("  M  (marathon) миля {} | км {}".format(
        fmt_time(s["marathon_mile"]), fmt_time(s["marathon_km"])))
    print("  П  (threshold) 400м {} | 1000м {} | {} с/км".format(
        fmt_time(s["threshold_400"]), fmt_time(s["threshold_1000"]),
        s["threshold_pace_km"]))
    print("  И  (interval)  400м {} | 1000м {} | 1200м {} | {} с/км".format(
        fmt_time(s["interval_400"]), fmt_time(s["interval_1000"]),
        fmt_time(s["interval_1200"]), s["interval_pace_km"]))
    print("  Пв (repetition) 200м {} | 400м {} | 800м {} | {} с/км".format(
        fmt_time(s["repetition_200"]), fmt_time(s["repetition_400"]),
        fmt_time(s["repetition_800"]), s["repetition_pace_km"]))
    rt = race_times_for_vdot(v)
    print("  гонки: 5К {} | 10К {} | полу {} | марафон {}".format(
        fmt_time(rt.get("5000m")), fmt_time(rt.get("10000m")),
        fmt_time(rt.get("half")), fmt_time(rt.get("marathon"))))
