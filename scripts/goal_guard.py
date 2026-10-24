#!/usr/bin/env python3
"""
goal_guard.py — проверка: макро ведёт к цели сезона.

Цель сезона (season_plan.json → season_goal) — 10К за 40:00 = 4:00/км.
Этот модуль проверяет, что план не соскальзывает в консервативный тупик:

  1) Цель гонки в season_goal совпадает с goals[primary].goal_metric.
  2) Race-pace блок (последние 6 недель до гонки) выходит на темп цели.
  3) TT на гонку-темп существует и стоит на темпе цели.
  4) Лестница TT монотонна по скорости (не хуже с каждым шагом).
  5) athlete.json training_paces не противоречат цели.

Запуск: python3 scripts/goal_guard.py
Код: 0 — всё ок; 1 — есть нарушения (правило).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def pace_sec(s: str) -> float:
    """'4:00' → 240.0 секунд на км."""
    m = re.fullmatch(r"\s*(\d+):(\d{2})\s*", str(s))
    if not m:
        raise ValueError("не разобрать темп {!r}".format(s))
    return int(m.group(1)) * 60 + int(m.group(2))


def fmt(sec: float) -> str:
    sec = float(sec)
    m = int(sec // 60)
    s = int(round(sec - m * 60))
    if s == 60:
        m += 1
        s = 0
    return "{}:{:02d}".format(m, s)


def check(sp: dict, at: dict) -> list[str]:
    problems: list[str] = []
    sg = sp.get("season_goal") or {}
    if not sg:
        return ["season_goal не задан — нет якоря, к которому ведёт план"]

    target_pace = sg.get("race_pace_min_per_km")
    if not target_pace:
        return ["season_goal.race_pace_min_per_km не задан"]
    tp = pace_sec(target_pace)

    # 1) цель в goals совпадает с season_goal
    prim = next((g for g in sp.get("goals", []) if g.get("primary")), None)
    if not prim:
        problems.append("нет primary-цели в goals[]")
    else:
        gm = prim.get("goal_metric") or {}
        if gm.get("type") == "time_sec":
            goal_pace = gm["target"] / 10.0  # target в секундах на 10К → с/км
            if abs(goal_pace - tp) > 1.0:
                problems.append(
                    "goals[primary] = {} ({:.0f} с/км) ≠ season_goal {} ({:.0f} с/км)".format(
                        gm.get("target_friendly"), goal_pace, target_pace, tp))
        else:
            problems.append("goals[primary].goal_metric.type = {} — ожидается time_sec".format(gm.get("type")))

    # 2) race-pace блок выходит на темп цели
    race_week = None
    for r in sp.get("races", []):
        if r.get("goal_id") == (prim or {}).get("id"):
            race_week = r
            break
    if race_week:
        race_wk = None
        from lib import season_week
        try:
            race_wk = season_week.date_to_season_week(race_week["date"], sp["season_start_date"])
        except Exception:
            pass
        if race_wk:
            block = [w for w in sp.get("weekly_macro", [])
                     if race_wk - 6 <= w["season_week"] <= race_wk]
            best = None
            for w in block:
                leg = (w.get("quality") or {}).get("_legacy_structure", "")
                for ps in re.findall(r"(\d+:\d{2})", leg):
                    try:
                        v = pace_sec(ps)
                    except ValueError:
                        continue
                    if best is None or v < best:
                        best = v
            if best is None:
                problems.append("race-pace блок W{}-W{}: нет ни одного темпа".format(race_wk - 6, race_wk))
            elif best > tp + 0.5:
                problems.append(
                    "race-pace блок W{}-W{}: лучший темп {} ({:.0f} с/км) медленнее цели {} ({:.0f} с/км). "
                    "Гонка на 40:00 не выйдет.".format(
                        race_wk - 6, race_wk, fmt(best), best, target_pace, tp))

    # 3) TT на гонку-темп
    tt_found = False
    for c in sp.get("control_points", []):
        s = c.get("session") or {}
        if s.get("test_type") != "pace" or not s.get("pace_min_per_km"):
            continue
        try:
            v = pace_sec(s["pace_min_per_km"])
        except ValueError:
            continue
        goal_txt = (s.get("session_goal", "") + " " + s.get("measures_text", "")).lower()
        is_race_test = ("race" in goal_txt) or ("гонк" in goal_txt) or ("40:00" in goal_txt)
        if abs(v - tp) <= 1.0:
            tt_found = True
        elif is_race_test:
            problems.append("TT '{}' заявлен как гонка-темп, но темп {} ≠ цель {}".format(
                c.get("id"), s.get("pace_min_per_km"), target_pace))
    if not tt_found:
        problems.append("нет контрольной точки на гонку-темп {} — готовность не проверяется".format(target_pace))

    # 4) лестница TT монотонна
    ladder = []
    for c in sorted(sp.get("control_points", []), key=lambda x: x["season_week"]):
        s = c.get("session") or {}
        if s.get("test_type") and s.get("pace_min_per_km"):
            try:
                ladder.append((c["season_week"], pace_sec(s["pace_min_per_km"])))
            except ValueError:
                pass
    for (w0, p0), (w1, p1) in zip(ladder, ladder[1:]):
        if p1 > p0 + 0.5:
            problems.append(
                "лестница TT: W{} = {} ({:.0f} с/км) медленнее W{} = {} ({:.0f} с/км) — откат назад".format(
                    w0, fmt(p0), p0, w1, fmt(p1), p1))

    # 4b) Согласованность: TT-сессия (control_points) и недельная структура
    #     (weekly_macro._legacy_structure) должны называть ОДИН темп.
    wm = {w["season_week"]: w for w in sp.get("weekly_macro", [])}
    for c in sp.get("control_points", []):
        s = c.get("session") or {}
        if not s.get("pace_min_per_km"):
            continue
        w = wm.get(c["season_week"])
        if not w:
            continue
        leg = (w.get("quality") or {}).get("_legacy_structure", "")
        leg_paces = []
        for ps in re.findall(r"(\d+):(\d{2})", leg):
            try:
                leg_paces.append(pace_sec("{}:{}".format(ps[0], ps[1])))
            except ValueError:
                pass
        if not leg_paces:
            continue
        cp_pace = pace_sec(s["pace_min_per_km"])
        # Расхождение считаем только если недельная структура НЕ содержит
        # времени цели (напр. «цель 14:00») — иначе это одно и то же.
        target_sec_cp = s.get("target_sec")
        has_target_time = bool(target_sec_cp) and "{}".format(fmt(target_sec_cp)) in leg
        if has_target_time:
            continue
        if all(abs(v - cp_pace) > 1.0 for v in leg_paces):
            problems.append(
                "W{}: контрольная точка '{}' требует темп {}, а недельная структура '{}' — расхождение".format(
                    c["season_week"], c.get("id"), s["pace_min_per_km"], leg[:44]))

    # 4c) Неделя гонки: темп должен быть ≤ цели
    if race_wk and race_wk in wm:
        leg = (wm[race_wk].get("quality") or {}).get("_legacy_structure", "")
        vals = []
        for ps in re.findall(r"(\d+):(\d{2})", leg):
            try:
                vals.append(pace_sec("{}:{}".format(ps[0], ps[1])))
            except ValueError:
                pass
        if vals and min(vals) > tp + 0.5:
            problems.append(
                "неделя гонки W{}: лучший темп {} ({:.0f} с/км) медленнее цели {} ({:.0f} с/км)".format(
                    race_wk, fmt(min(vals)), min(vals), target_pace, tp))

    # 5) athlete.json не противоречит
    tp_at = (at.get("current_form") or {}).get("training_paces") or {}
    thr = tp_at.get("threshold_pace")
    if thr:
        v = pace_sec(thr.split("-")[0])
        if v > tp + 20:
            problems.append(
                "athlete.json threshold_pace = {} — порог на {} с/км, цель {} ({:.0f} с/км); разрыв {:.0f} с/км".format(
                    thr, v, target_pace, tp, v - tp))
    vo2 = tp_at.get("vo2max_pace")
    if vo2:
        m = re.search(r"(\d+):(\d{2})", vo2)
        if m:
            v = int(m.group(1)) * 60 + int(m.group(2))
            if v > tp + 5:
                problems.append("athlete.json vo2max_pace = {} — VO2 не быстрее гонки".format(vo2))

    # 6) Каталог шаблонов (workout_templates.json) не должен быть медленнее цели
    tpl_path = REPO / "state" / "workout_templates.json"
    if tpl_path.exists():
        tpl = json.loads(tpl_path.read_text(encoding="utf-8")).get("templates", {})
        for tid, t in tpl.items():
            if not isinstance(t, dict):
                continue
            pc = str(t.get("pace", ""))
            vals = []
            for ps in re.findall(r"(\d+):(\d{2})", pc):
                try:
                    vals.append(pace_sec("{}:{}".format(ps[0], ps[1])))
                except ValueError:
                    pass
            if not vals:
                continue
            # Порог/темпо могут быть медленнее цели — это законно.
            # Но VO2max обязан быть быстрее гонки.
            if tid == "vo2max" and min(vals) > tp + 0.5:
                problems.append(
                    "workout_templates: vo2max pace = {} — VO2max не быстрее гонки-темпа {}".format(
                        pc, target_pace))

    return problems


def main() -> int:
    sp = json.loads((REPO / "state/season_plan.json").read_text(encoding="utf-8"))
    at = json.loads((REPO / "state/athlete.json").read_text(encoding="utf-8"))
    problems = check(sp, at)
    sg = sp.get("season_goal") or {}
    print("Цель: {}".format(sg.get("headline", "—")))
    if not problems:
        print("OK — макро ведёт к цели")
        return 0
    print("НАРУШЕНИЯ ({}):".format(len(problems)))
    for p in problems:
        print("  ✗ " + p)
    return 1


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.exit(main())
