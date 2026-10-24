#!/usr/bin/env python3
"""
sync_macro_md.py — человекочитаемый макро-план (.md) генерируется из season_plan.json.

Source of truth — JSON. md это представление, а не отдельная сущность.
Запуск: python3 scripts/sync_macro_md.py
"""
#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from lib import season_week  # noqa: E402

OUT = Path.home() / ".hermes" / "coach" / "plans" / "spring-10k-2027-v2.md"


def fmt(sec):
    sec = float(sec)
    m = int(sec // 60)
    s = int(round(sec - m * 60))
    if s == 60:
        m += 1
        s = 0
    return "{}:{:02d}".format(m, s)


def esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def phase_of(n, phases):
    for p in phases:
        if p.get("_season_week_start") and p["_season_week_start"] <= n <= p["_season_week_end"]:
            return p
    return None


def build(sp, at):
    sg = sp.get("season_goal", {})
    ctx = at.get("context", {})
    cf = at.get("current_form", {})
    start = sp["season_start_date"]

    L = []
    L.append("# Spring 10K Plan v2 · «1 → 2» to S25 Berlin")
    L.append("")
    L.append("> ⚠️ Файл генерируется из `state/season_plan.json` — правь JSON, не этот файл.")
    L.append("> Генератор: `scripts/sync_macro_md.py`")
    L.append("")

    # ---------- ЦЕЛЬ ----------
    L.append("## 🎯 ЦЕЛЬ СЕЗОНА")
    L.append("")
    L.append("**{}**".format(sg.get("headline", "—")))
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append("| Целевой темп | **{}** |".format(sg.get("race_pace_min_per_km", "—")))
    L.append("| Целевое время | **{}** |".format(sg.get("target_time", "—")))
    L.append("| Сейчас | {} |".format(sg.get("current_form", "—")))
    L.append("| Разрыв | **{}** |".format(sg.get("gap", "—")))
    L.append("| PB 10К | {} |".format(ctx.get("pb_10k", "—")))
    L.append("| Вес сейчас / цель | {} / {} кг |".format(ctx.get("current_weight_kg"), ctx.get("target_weight_kg")))
    L.append("")
    L.append("**Правила, которые нельзя нарушать:**")
    L.append("")
    for r in sg.get("rules", []):
        L.append("- {}".format(r))
    L.append("")

    # ---------- ФАЗЫ ----------
    L.append("## Фазы")
    L.append("")
    L.append("| Фаза | Даты | Недели | Цель | Фокус |")
    L.append("|---|---|---|---|---|")
    # Диапазон недель фазы вычисляем из дат (в JSON это не хранится)
    def wk_range(ph):
        try:
            d0 = season_week.date_to_season_week(ph["start"], start)
            d1 = season_week.date_to_season_week(ph["end"], start)
            return "W{}-W{}".format(d0, d1)
        except Exception:
            return "—"

    for p in sp["phases"]:
        rng = wk_range(p)
        L.append("| {} | {} → {} | {} | {} | {} |".format(
            p["id"], p.get("start", "?"), p.get("end", "?"), rng,
            p.get("goal") or p.get("goal_id", "—"),
            (p.get("focus") or "").split(".")[0] + "."))
    L.append("")

    # ---------- НЕДЕЛИ ----------
    L.append("## Недели")
    L.append("")
    L.append("| W | Дата | Бег | Long Z2 | Цель (адаптация) | Структура | Core | Вел | Плав | Total ч/нед |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for w in sp["weekly_macro"]:
        n = w["season_week"]
        d = season_week.season_week_to_dates(n, start)[0]
        ds = "{:02d}.{:02d}".format(d.day, d.month)
        q = w["quality"]
        cell = "{} ({})".format(q.get("goal", ""), q.get("scale", ""))
        L.append("| W{} | {} | {}К | {}К | {} | `{}` | {} | {} | {} | {}ч |".format(
            n, ds, w.get("run_km", ""), w.get("long_km", ""),
            esc(cell), esc(q.get("_legacy_structure", "—")),
            w.get("core", ""), w.get("bike", ""), w.get("swim", ""), w.get("total_h", "")))
    L.append("")

    # ---------- TT ----------
    L.append("## Контрольные точки")
    L.append("")
    L.append("| W | Тест | Тип | Цель | Темп | Что меряем | Прохождение | Если нет |")
    L.append("|---|---|---|---|---|---|---|---|")
    for c in sp.get("control_points", []):
        s = c.get("session") or {}
        if not s.get("target_sec"):
            continue
        n = c["season_week"]
        d = season_week.season_week_to_dates(n, start)[0]
        ds = "{:02d}.{:02d}".format(d.day, d.month)
        L.append("| W{} ({} ) | {} | {} | {} | {} | {} | {} | {} |".format(
            n, ds, c.get("what", ""), s.get("test_type", ""),
            fmt(s["target_sec"]), s.get("pace_min_per_km", "—"),
            ", ".join(s.get("measures", [])),
            esc(s.get("pass_criteria", "")), esc(s.get("fail_action", ""))))
    L.append("")

    # ---------- ГОНКИ ----------
    L.append("## Гонки")
    L.append("")
    for r in sp.get("races", []):
        L.append("- **{}** — {} (goal: {})".format(r.get("name"), r.get("date"), r.get("goal_id", "—")))
    L.append("")

    return "\n".join(L) + "\n"


def main():
    sp = json.loads((REPO / "state/season_plan.json").read_text(encoding="utf-8"))
    at = json.loads((REPO / "state/athlete.json").read_text(encoding="utf-8"))
    md = build(sp, at)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md, encoding="utf-8")
    print("md: {} ({} Б)".format(OUT, len(md.encode("utf-8"))))


if __name__ == "__main__":
    main()
