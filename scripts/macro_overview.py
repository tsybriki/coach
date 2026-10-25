#!/usr/bin/env python3
"""
macro_overview.py — общий план сезона → self-contained HTML.

High-level view: недельные карточки свёрнуты, цвет недели = фокус:
  teal   — объём / база
  orange — threshold / tempo
  red    — VO2max
  violet — анаэробная скорость
  cp     — контрольная точка (независимо от фокуса)

Источник: state/season_plan.json (weekly_macro[], phases[], control_points[], races[])
         + lib/actual_load.py — факт по прошедшим неделям из Garmin.

Запуск:
    python3 scripts/macro_overview.py
    python3 scripts/macro_overview.py --no-actual
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib import season_week  # noqa: E402

PACE_MIN_PER_KM = 5.7

MONTHS_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн",
                "июл", "авг", "сен", "окт", "ноя", "дек"]

# Цвет фокуса недели
FOCUS_COLOR = {
    "progression": "teal",
    "threshold_speed": "orange",
    "threshold_power": "orange",
    "tempo": "orange",
    "mixed": "ember",
    "vo2max": "red",
    "pyramid": "violet",
    "fartlek": "violet",
    "time_trial": "cp",
}
COLOR_LABEL = {
    "teal": "объём",
    "orange": "threshold / tempo",
    "ember": "порог + VO2",
    "red": "VO2max",
    "violet": "анаэробная скорость",
    "cp": "контрольная точка",
    "gray": "не детализировано",
}


def esc(s) -> str:
    return (str(s if s is not None else "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _num(s) -> int:
    import re
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 0


def _mins(s) -> int:
    import re
    m = re.search(r"(\d+)\s*[×x]\s*(\d+)", str(s))
    if m:
        return int(m.group(1)) * int(m.group(2))
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 0


def fmt_range(ws: date, we: date) -> str:
    if ws.month == we.month:
        return "{}–{} {}".format(ws.day, we.day, MONTHS_SHORT[we.month - 1])
    return "{} {} – {} {}".format(ws.day, MONTHS_SHORT[ws.month - 1],
                                 we.day, MONTHS_SHORT[we.month - 1])


def fmt_day(d: date) -> str:
    return "{} {}".format(d.day, MONTHS_SHORT[d.month - 1])


def build_data(season_plan_path: Path, athlete_path: Path,
               actual: dict | None = None) -> dict:
    sp = json.loads(season_plan_path.read_text(encoding="utf-8"))
    at = json.loads(athlete_path.read_text(encoding="utf-8"))
    start = sp.get("season_start_date", "2026-10-11")
    total_weeks = sp.get("horizon", {}).get("season_week_count", 49)

    templates = json.loads(
        (REPO / "state/workout_templates.json").read_text(encoding="utf-8")
    ).get("templates", {})
    wm = {w["season_week"]: w for w in sp.get("weekly_macro", [])}
    actual = actual or {}

    today = date.today()
    now_w = season_week.date_to_season_week(today, start) or None
    next_w = (now_w + 1) if now_w else None

    # Цель недели для TT-недель — конкретный тест из CP, а не общая формулировка
    tt_by_week = {}
    for c in sp.get("control_points", []):
        s = c.get("session", {})
        if c.get("quality_goal") and s:
            tt_by_week[c["season_week"]] = {
                "what": c["what"],
                "test_type": s.get("test_type", ""),
                "pace": s.get("pace_min_per_km", ""),
                "target_sec": s.get("target_sec"),
            }

    weeks = []
    for n in range(1, total_weeks + 1):
        ws, we = season_week.season_week_to_dates(n, start)
        entry = wm.get(n)
        w = {
            "w": n,
            "start": ws.isoformat(),
            "end": we.isoformat(),
            "start_d": fmt_range(ws, we),
            "detailed": entry is not None,
            "is_now": n == now_w,
            "is_next": n == next_w,
        }
        if entry:
            q = entry.get("quality") or {}
            gid = q.get("goal")
            tpl = templates.get(gid, {})
            run_km = entry.get("run_km", 0)
            w.update({
                "run_km": run_km,
                "long_km": entry.get("long_km", 0),
                "run_h": round(round(run_km * PACE_MIN_PER_KM) / 60, 1),
                "bike_h": round(_mins(entry.get("bike", "")) / 60, 1),
                "swim_h": round(_mins(entry.get("swim", "")) / 60, 1),
                "ofp_h": round(_mins(entry.get("core", "")) / 60, 1),
                "goal_text": q.get("goal_text") or tpl.get("goal", ""),
                "phase": entry.get("phase", ""),
                "color": FOCUS_COLOR.get(gid, "gray"),
                "variants": [{"label": v.get("label"), "work_m": v.get("work_m")}
                             for v in tpl.get("variants", []) if v.get("scale") == q.get("scale")],
            })
            w["comp_h"] = round(w["run_h"] + w["bike_h"] + w["swim_h"] + w["ofp_h"], 1)
            w["total_h"] = entry.get("total_h", 0)
            # структурированные данные недели (из каталога, не из строки)
            q = entry.get("quality") or {}
            w["variant_id"] = q.get("variant_id")
            w["quality_label"] = q.get("label")
            w["quality_work_m"] = q.get("work_m")
            w["quality_paces"] = q.get("paces") or []
            w["run_km_long"] = entry.get("run_km_long")
            w["run_km_quality"] = entry.get("run_km_quality")
            w["run_km_easy"] = entry.get("run_km_easy")
            w["intensity_pct"] = entry.get("intensity_pct")
            w["deload"] = entry.get("deload")
            w["sessions_target"] = entry.get("sessions_target")
            # TT-неделя: цель = конкретный тест
            tt = tt_by_week.get(n)
            if tt:
                types = {"pace": "темповый тест", "max": "тест на максимум",
                         "sim": "симуляция", "metric": "замер"}
                label = types.get(tt["test_type"], tt["test_type"])
                w["goal_text"] = label + " · " + tt["what"]
                w["is_tt"] = True
                if tt["pace"]:
                    w["goal_text"] += " · " + tt["pace"] + "/км"
        else:
            w["color"] = "gray"

        # факт
        act = actual.get(n)
        if act:
            w["actual"] = {
                "run_km": act["run_km"], "bike_km": act["bike_km"],
                "swim_km": act["swim_km"], "sessions": act["sessions"],
                "total_h": act["total_h"],
                "run_h": round(act["run_min"] / 60, 1),
                "bike_h": round(act["bike_min"] / 60, 1),
                "swim_h": round(act["swim_min"] / 60, 1),
            }
        weeks.append(w)

    phase_meta = {p["id"]: p for p in sp.get("phases", [])}
    phases = []
    for p in sp.get("phases", []):
        s = season_week.date_to_season_week(p["start"], start)
        e = season_week.date_to_season_week(p.get("end", p["start"]), start)
        ph_weeks = [w for w in weeks if s <= w["w"] <= e]
        fs = datetime.fromisoformat(p["start"]).date()
        fe = datetime.fromisoformat(p.get("end", p["start"])).date()
        phases.append({
            "id": p["id"],
            "goal": p.get("goal", ""),
            "focus": p.get("focus", ""),
            "w_from": s, "w_to": e,
            "date_range": "{} {} — {} {}".format(fmt_day(fs), fs.year, fmt_day(fe), fe.year),
            "weeks_count": len(ph_weeks),
            "target_h": p.get("hours_per_week_target"),
            "is_event": bool(p.get("event")),
            "notes": p.get("notes", ""),
            "detailed": [w for w in ph_weeks if w["detailed"]],
            "has_actual": any("actual" in w for w in ph_weeks),
        })

    tts = []
    for c in sp.get("control_points", []):
        s = c.get("session", {})
        tts.append({
            "w": c.get("season_week"),
            "what": c["what"],
            "test_type": s.get("test_type", ""),
            "target_sec": s.get("target_sec"),
            "pace": s.get("pace_min_per_km", ""),
            "session_goal": s.get("session_goal", ""),
        })
    races = []
    for r in sp.get("races", []):
        d = datetime.fromisoformat(r["date"]).date()
        races.append({
            "name": r["name"], "date": r["date"], "start": r.get("start_time", ""),
            "w": season_week.date_to_season_week(d, start),
            "date_short": fmt_day(d),
            "weekday": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][d.weekday()],
        })

    season_goal = sp.get("season_goal", {})

    # текущая неделя сезона — для статуса gates
    from datetime import date as _date
    try:
        current_week = season_week.date_to_season_week(
            _date.today().isoformat(), sp["season_start_date"])
    except Exception:
        current_week = 0

    # Gates: точки принятия решения после фаз и контрольных точек
    gates = []
    try:
        sys.path.insert(0, str(REPO))
        from lib import review_gates
        gates = [g.to_dict() for g in review_gates.sync_gates(sp)]
    except Exception as e:  # noqa: BLE001 — gates не критичны для овервью
        print(f"предупреждение: gates не загружены ({e})")

    det = [w for w in weeks if w["detailed"]]
    peak = max(det, key=lambda w: w["run_km"]) if det else None
    act_weeks = [w for w in weeks if "actual" in w]

    return {
        "title": "Макро-план сезона",
        "season_start": start,
        "total_weeks": total_weeks,
        "detailed_weeks": len(det),
        "phases": phases,
        "weeks": weeks,
        "tts": tts,
        "races": races,
        "peak_week": peak["w"] if peak else None,
        "peak_km": peak["run_km"] if peak else 0,
        "max_week_h": max((w["total_h"] for w in det), default=0),
        "actual_weeks": len(act_weeks),
        "actual_run_km": sum(w["actual"]["run_km"] for w in act_weeks),
        "actual_h": round(sum(w["actual"]["total_h"] for w in act_weeks), 1),
        "color_label": COLOR_LABEL,
        "season_goal": season_goal,
        "gates": gates,
        "current_week": current_week,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }


TEMPLATE = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<title>__TITLE__</title>
<style>
:root{
  --bg:#0f1115;--panel:#161a22;--panel2:#1d222c;--border:#2a3140;
  --text:#e6e9ef;--muted:#9aa3b2;
  --accent:#7aa2ff;--warn:#ff9b6a;--good:#7ee787;--cp:#d8a0ff;
  --c-teal:#5cd6c0;--c-orange:#ff9b6a;--c-red:#ff6b5a;
  --c-violet:#d8a0ff;--c-ember:#ff8f6b;--c-gray:#5a6472;
  --run:#7ec8e3;--bike:#f08a5a;--swim:#5cd6c0;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  -webkit-text-size-adjust:100%;line-height:1.45}
body{padding:14px 12px 50px;max-width:820px;margin:0 auto}
h1{font-size:20px;margin:0 0 3px}
h2{font-size:14px;margin:24px 0 9px;color:var(--accent);display:flex;
  align-items:baseline;gap:8px;flex-wrap:wrap}
h2 .hint{font-size:11px;color:var(--muted);font-weight:400}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:12px}

/* шапка */
.hero{background:linear-gradient(135deg,rgba(122,162,255,.09),rgba(92,214,192,.05));
  border:1px solid rgba(122,162,255,.26);border-radius:14px;padding:13px 15px;margin-bottom:14px}
.hero h1{font-size:20px}
.goal-hero{border-color:rgba(255,107,90,.35);
  background:linear-gradient(135deg,rgba(255,107,90,.10),rgba(122,162,255,.05))}
.goal-line{font-size:9.5px;color:var(--warn);text-transform:uppercase;letter-spacing:.7px;
  font-weight:700}
.goal-head{font-size:19px;font-weight:700;color:#ff8f7a;line-height:1.25;margin:3px 0 4px}
.goal-gap{font-size:11.5px;color:var(--muted);margin-bottom:9px}

/* GATES — точки принятия решения */
.gates{margin:14px 0}
.gate{border:1px solid var(--border);border-radius:10px;margin-bottom:8px;
  background:var(--panel);overflow:hidden}
.gate-hd{display:flex;align-items:center;gap:9px;padding:9px 11px;cursor:pointer;
  user-select:none;flex-wrap:wrap}
.gate-ico{width:20px;height:20px;border-radius:5px;display:flex;align-items:center;
  justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}
.g-pending{background:#2a3140;color:#9aa3b2}
.g-pass{background:rgba(92,214,192,.18);color:#5cd6c0}
.g-warn{background:rgba(240,180,87,.18);color:#f0b457}
.g-fail{background:rgba(255,107,90,.18);color:#ff6b5a}
.gate-wk{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--muted);flex-shrink:0}
.gate-ttl{font-size:12.5px;font-weight:600;color:var(--text);flex:1 1 auto;min-width:0}
.gate-kind{font-size:9.5px;text-transform:uppercase;letter-spacing:.5px;
  padding:2px 6px;border-radius:4px;background:var(--panel2);color:var(--muted);flex-shrink:0}
.gate-body{padding:0 11px 11px;font-size:12px;color:var(--muted);border-top:1px solid var(--border)}
.gate-body.hidden{display:none}
.gq{color:var(--text);font-weight:600;margin:9px 0 7px;font-size:12px}
.gcheck{display:flex;gap:7px;align-items:baseline;padding:3px 0;font-size:11.5px}
.gcheck .gc-v{font-family:ui-monospace,monospace;flex-shrink:0;min-width:62px}
.gcheck .gc-t{flex:1;color:var(--muted)}
.gwarn{background:rgba(240,180,87,.09);border-left:2px solid rgba(240,180,87,.55);
  padding:7px 9px;margin:6px 0;border-radius:0 6px 6px 0;font-size:11.5px;line-height:1.45;color:#e8d5b0}
.gdec{border-left:2px solid var(--border);padding:6px 0 6px 9px;margin:5px 0;
  font-size:11.5px;line-height:1.45}
.gdec b{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.5px;
  color:var(--muted);margin-bottom:2px}
.gdec.pass{border-color:rgba(92,214,192,.55)} .gdec.pass b{color:#5cd6c0}
.gdec.warn{border-color:rgba(240,180,87,.55)} .gdec.warn b{color:#f0b457}
.gdec.fail{border-color:rgba(255,107,90,.55)} .gdec.fail b{color:#ff6b5a}
.glever{font-size:11px;color:var(--muted);margin-top:8px;padding-top:7px;
  border-top:1px dashed var(--border)}
.glever b{color:var(--accent)}
.hero-sub{font-size:12px;color:var(--muted);margin-top:3px}
.hero-dates{font-family:ui-monospace,monospace;font-size:12px;color:var(--accent2);margin-top:6px}
.peaks{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-top:11px}
.peak{background:rgba(15,17,21,.45);border:1px solid var(--border);border-radius:9px;padding:7px 10px}
.peak .pl{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.peak .pv{font-size:14px;font-weight:600;color:var(--accent2);font-family:ui-monospace,monospace;margin-top:1px}
.peak .pd{font-size:10px;color:var(--muted);margin-top:1px}

/* легенда цвета */
.legend{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.lg{display:flex;align-items:center;gap:5px;font-size:10.5px;color:var(--muted);
  background:var(--panel);border:1px solid var(--border);border-radius:7px;padding:3px 8px}
.lg i{width:9px;height:9px;border-radius:2px;display:inline-block}

/* календарь */
.cal{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:6px}
.cw{width:28px;height:24px;border-radius:5px;display:flex;align-items:center;justify-content:center;
  font-size:9px;font-family:ui-monospace,monospace;background:var(--panel2);
  color:var(--muted);border:1px solid var(--border)}
.cw.det{color:var(--text)}
.cw.tt{background:rgba(255,155,106,.2);color:var(--warn);border-color:rgba(255,155,106,.4)}
.cw.race{background:rgba(126,231,135,.2);color:var(--good);border-color:rgba(126,231,135,.42)}
.cw.now{outline:2px solid var(--accent);outline-offset:1px}

/* неделя — collapsible */
.wk{background:var(--panel);border:1px solid var(--border);border-radius:11px;
  margin-bottom:6px;overflow:hidden}
.wk.t-teal{border-left:3px solid var(--c-teal)}
.wk.t-orange{border-left:3px solid var(--c-orange)}
.wk.t-ember{border-left:3px solid var(--c-ember)}
.wk.t-red{border-left:3px solid var(--c-red)}
.wk.t-violet{border-left:3px solid var(--c-violet)}
.wk.t-cp{border-left:3px solid var(--cp)}
.wk.t-gray{border-left:3px solid var(--c-gray);opacity:.7}
.wk.tt{box-shadow:inset 0 0 0 1px rgba(255,155,106,.25)}
.wk.now{box-shadow:inset 0 0 0 1px rgba(122,162,255,.4)}

.wk-hd{display:flex;align-items:center;gap:9px;padding:9px 12px;cursor:pointer;
  user-select:none;-webkit-tap-highlight-color:transparent;flex-wrap:wrap}
@media (max-width:430px){
  .wk-hd{gap:7px;padding:9px 10px}
  .wk-d{width:auto;font-size:10px;white-space:nowrap}
  .wk-t{flex:1 1 100%;order:3;margin-top:-2px}
  .wk-metrics{order:4;margin-left:auto}
  .wk-gt{font-size:12px}
}
.wk-hd:active{background:var(--panel2)}
.wk-n{font-family:ui-monospace,monospace;font-weight:700;font-size:12px;color:var(--muted);
  width:26px;flex-shrink:0}
.wk-d{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--muted);
  flex-shrink:0;width:92px;white-space:nowrap}
.wk-t{flex:1;min-width:0}
.wk-gt{font-size:12.5px;font-weight:600;color:var(--text);line-height:1.3}
.wk-metrics{display:flex;gap:5px;flex-shrink:0;align-items:center;flex-wrap:wrap;
  justify-content:flex-end}
.chip{font-size:9.5px;font-family:ui-monospace,monospace;padding:1px 6px;border-radius:5px;
  background:var(--panel2);border:1px solid var(--border);color:var(--muted);white-space:nowrap}
.chip.run{color:var(--run);border-color:rgba(126,200,227,.3);background:rgba(126,200,227,.08)}
.chip.bike{color:var(--bike);border-color:rgba(240,138,90,.3);background:rgba(240,138,90,.08)}
.chip.swim{color:var(--swim);border-color:rgba(92,214,192,.3);background:rgba(92,214,192,.08)}
.chip.act{color:var(--good);border-color:rgba(126,231,135,.35);background:rgba(126,231,135,.1)}
.chip.tt{color:var(--warn);border-color:rgba(255,155,106,.4);background:rgba(255,155,106,.12);font-weight:700}
.chip.next{color:var(--accent);border-color:rgba(122,162,255,.4);background:rgba(122,162,255,.12);font-weight:700}
.caret{color:var(--muted);font-size:10px;flex-shrink:0;transition:transform .15s}
.wk.open .caret{transform:rotate(90deg)}

.wk-body{display:none;padding:0 12px 11px 12px;border-top:1px solid var(--border)}
.wk.open .wk-body{display:block}
.wk-goal{font-size:11.5px;color:var(--text);margin:8px 0 7px}
.wk-goal b{color:var(--accent2)}
.wk-vars{font-size:10.5px;color:var(--muted);margin-bottom:8px}
.wk-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:5px;margin-bottom:8px}
.mt{background:var(--panel2);border:1px solid var(--border);border-radius:7px;padding:5px 8px}
.mt .ml{font-size:8.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.mt .mv{font-size:13px;font-weight:600;font-family:ui-monospace,monospace;margin-top:1px}
.mt.run .mv{color:var(--run)} .mt.bike .mv{color:var(--bike)}
.mt.swim .mv{color:var(--swim)} .mt.act .mv{color:var(--good)}
.mt.plan .mv{color:var(--accent2)}
.cmp{display:flex;align-items:center;gap:6px;margin-bottom:8px;font-size:10.5px}
.cmp .cbar{flex:1;height:6px;border-radius:3px;background:var(--panel2);overflow:hidden;display:flex}
.cmp .cbar i{display:block;height:100%}
.cmp .cl{color:var(--muted);font-family:ui-monospace,monospace;white-space:nowrap}
.phase-note{font-size:11px;color:var(--warn);margin-top:6px}
.wk-load{margin:6px 0 2px;padding:6px 8px;background:var(--panel2);border-radius:7px}
.wl-row{display:flex;gap:8px;font-size:10.5px;color:var(--muted);padding:1.5px 0}
.wl-row span:first-child{color:var(--muted);flex-shrink:0;width:88px}
.wl-row span:last-child{flex:1;color:var(--text)}
.wl-id{font-family:ui-monospace,monospace;font-size:9.5px;color:var(--muted)}

.fphase{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:10px 13px;margin-bottom:8px}
.fphase-hd{display:flex;justify-content:space-between;align-items:baseline;gap:9px;
  padding-bottom:7px;border-bottom:1px solid var(--border);margin-bottom:7px}
.fphase-l{font-size:13.5px;font-weight:600}
.fphase-l span{font-size:10px;color:var(--muted);font-family:ui-monospace,monospace;
  background:var(--panel2);padding:1px 6px;border-radius:4px;margin-left:6px}
.fphase-r{font-size:10.5px;color:var(--muted);text-align:right;white-space:nowrap}
.fphase-goal{font-size:12.5px;color:var(--accent2);font-weight:600}
.fphase-focus{font-size:11px;color:var(--muted);margin-top:2px;line-height:1.4}

table.tt-tbl{width:100%;border-collapse:collapse;font-size:11px;margin-top:7px}
table.tt-tbl th{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;
  text-align:left;padding:4px 5px;border-bottom:1px solid var(--border)}
table.tt-tbl td{padding:6px 5px;border-bottom:1px solid rgba(42,49,64,.5);vertical-align:top}
table.tt-tbl tr:last-child td{border-bottom:none}
table.tt-tbl .n{font-family:ui-monospace,monospace;color:var(--accent);font-weight:600}
table.tt-tbl .num{text-align:right;font-family:ui-monospace,monospace;white-space:nowrap}
table.tt-tbl .sm{color:var(--muted);font-size:10px}
.race{display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)}
.race:last-child{border-bottom:none}
.race .rw{font-family:ui-monospace,monospace;font-size:11px;color:var(--good);width:74px;flex-shrink:0}
.race .rn{font-size:12.5px;font-weight:600}
.race .rd{font-size:10.5px;color:var(--muted)}
.note{background:rgba(122,162,255,.06);border:1px solid rgba(122,162,255,.24);
  border-radius:9px;padding:10px 12px;font-size:11.5px;line-height:1.55}
.note b{color:var(--accent)}
footer{margin-top:20px;text-align:center;font-size:11px;color:var(--muted)}
</style></head><body>

<div class="hero goal-hero">
  <div class="goal-line">ЦЕЛЬ СЕЗОНА</div>
  <div class="goal-head" id="goalhead"></div>
  <div class="goal-gap" id="goalgap"></div>
  <h1>__TITLE__</h1>
  <div class="hero-sub">Два пика: S25 Berlin 10K (18.04.2027) → олимпийский триатлон (12.09.2027)</div>
  <div class="hero-dates">__DATES__</div>
  <div class="peaks" id="peaks"></div>
</div>

<h2>Легенда фокуса <span class="hint">цвет недели = что поднимаем</span></h2>
<div class="legend" id="legend"></div>

<h2>Календарь сезона <span class="hint">49 недель</span></h2>
<div class="cal" id="cal"></div>

<h2>Недели <span class="hint">тап — раскрыть: план, факт, цель</span></h2>
<div id="weeks"></div>

<h2>Точки принятия решения <span class="hint">после каждой фазы и каждой контрольной точки</span></h2>
<div id="gates" class="gates"></div>

<h2>Фазы</h2>
<div id="phases"></div>

<h2>Контрольные точки</h2>
<div class="fphase" id="tts"></div>

<footer>Сгенерировано __GENERATED__ · coach · macro_overview.py</footer>

<script type="application/json" id="plan-data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('plan-data').textContent);
const esc = s => String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const ttWeeks = new Set(D.tts.map(t=>t.w));
const raceWeeks = new Set(D.races.map(r=>r.w));
const COLORVAR = {teal:'var(--c-teal)', orange:'var(--c-orange)', ember:'var(--c-ember)',
  red:'var(--c-red)', violet:'var(--c-violet)', cp:'var(--cp)', gray:'var(--c-gray)'};

// Цель сезона
const SG = D.season_goal || {};
if (SG.headline) {
  document.getElementById('goalhead').textContent = SG.headline;
  document.getElementById('goalgap').textContent =
    'сейчас ' + (SG.current_form||'') + ' · разрыв ' + (SG.gap||'');
}

// GATES — точки принятия решения
const GATES = D.gates || [];
const G_ICON = {pass:'✓', warn:'!', fail:'✗', pending:'·'};
const G_KIND = {phase:'фаза', quality:'контрольная', metric:'замер', race:'гонка'};
const CUR_W = D.current_week || 0;
function gStatus(g) {
  // gate ещё не наступил — решения по нему принимать не по чему
  if (g.season_week > CUR_W) return 'pending';
  const st = (g.checks||[]).map(c => c.status);
  if (st.includes('fail')) return 'fail';
  if (st.includes('warn')) return 'warn';
  if (st.includes('pass')) return 'pass';
  return 'pending';
}
document.getElementById('gates').innerHTML = GATES.map((g, i) => {
  const st = gStatus(g);
  const body = 'gbody' + i;
  let h = '<div class="gate">';
  h += '<div class="gate-hd" data-toggle="' + body + '">';
  h += '<span class="gate-ico g-' + st + '">' + (G_ICON[st]||'·') + '</span>';
  h += '<span class="gate-wk">W' + g.season_week + '</span>';
  h += '<span class="gate-ttl">' + esc(g.title) + '</span>';
  h += '<span class="gate-kind">' + (G_KIND[g.kind] || g.kind) + '</span>';
  h += '</div>';
  h += '<div class="gate-body hidden" id="' + body + '">';
  h += '<div class="gq">Вопрос: ' + esc(g.question) + '</div>';
  (g.checks||[]).forEach(c => {
    let v = (c.value === null || c.value === undefined) ? '—'
      : (typeof c.value === 'number' ? (Math.round(c.value*10)/10) : c.value);
    // темпы показываем в мин:сек, не в сырых секундах
    if (c.metric === 'threshold_pace' || c.metric === 'tt_pace') {
      if (typeof v === 'number' && v > 60) {
        v = Math.floor(v/60) + ':' + String(Math.round(v%60)).padStart(2,'0');
      }
    }
    const m = {pass:'✓', warn:'!', fail:'✗', pending:'·'}[c.status] || '·';
    h += '<div class="gcheck"><span class="gc-v" style="color:' +
         (c.status==='fail' ? '#ff6b5a' : c.status==='warn' ? '#f0b457' :
          c.status==='pass' ? '#5cd6c0' : '#9aa3b2') + '">' + m + ' ' + esc(v) + '</span>' +
         '<span class="gc-t">' + esc(c.label) + ' — порог ' + esc(c.threshold) + '</span></div>';
  });
  (g.warnings||[]).forEach(w => { h += '<div class="gwarn">⚠ ' + esc(w) + '</div>'; });
  const D2 = g.decisions || {};
  ['pass','warn','fail'].forEach(k => {
    if (D2[k] && D2[k].length) {
      h += '<div class="gdec ' + k + '"><b>' +
           ({pass:'Если прошли', warn:'Если на грани', fail:'Если провалили'})[k] + '</b>';
      D2[k].forEach(x => { h += '• ' + esc(x) + '<br>'; });
      h += '</div>';
    }
  });
  if (g.lever) h += '<div class="glever"><b>Рычаг:</b> ' + esc(g.lever) + '</div>';
  if (g.decision) h += '<div class="gdec pass"><b>Принято решение</b>' + esc(g.decision) + '</div>';
  h += '</div></div>';
  return h;
}).join('');

// раскрытие gates (делегирование)
const gEl = document.getElementById('gates');
if (gEl && gEl.addEventListener) {
  gEl.addEventListener('click', function(e) {
    const t = e.target;
    const hd = t && t.closest ? t.closest('.gate-hd') : null;
    if (!hd) return;
    const body = document.getElementById(hd.getAttribute('data-toggle'));
    if (body) body.classList.toggle('hidden');
  });
}

// Пики
document.getElementById('peaks').innerHTML = [
  ['Пик бега', 'W'+D.peak_week+' · '+D.peak_km+'К', 'макс. объём недели'],
  ['Детализировано', D.detailed_weeks+'/'+D.total_weeks, 'недель с раскладкой'],
  ['Факт', D.actual_weeks+' нед · '+D.actual_run_km+'К', 'реальный бег за сезон'],
  ['Макс. неделя', D.max_week_h+'ч', 'по колонке Total макро'],
].map(([l,v,d]) => '<div class="peak"><div class="pl">'+esc(l)+'</div><div class="pv">'+esc(v)
  + '</div><div class="pd">'+esc(d)+'</div></div>').join('');

// Легенда
document.getElementById('legend').innerHTML = Object.entries(D.color_label).map(([k,v]) =>
  '<span class="lg"><i style="background:'+(COLORVAR[k]||'var(--c-gray)')+'"></i>'+esc(v)+'</span>').join('');

// Календарь
document.getElementById('cal').innerHTML = D.weeks.map(w => {
  let cls = 'cw';
  if (w.detailed) cls += ' det';
  if (w.is_now) cls += ' now';
  if (ttWeeks.has(w.w)) cls += ' tt';
  if (raceWeeks.has(w.w)) cls += ' race';
  const style = w.detailed && !ttWeeks.has(w.w) && !raceWeeks.has(w.w)
    ? ' style="border-left:2px solid '+(COLORVAR[w.color]||'var(--c-gray)')+'"' : '';
  return '<div class="'+cls+'"'+style+' title="W'+w.w+' · '+w.start_d+'">'+w.w+'</div>';
}).join('');

// Недели — collapsible
document.getElementById('weeks').innerHTML = D.weeks.map(w => {
  const chips = [];
  if (w.is_now) chips.push('<span class="chip next">сейчас</span>');
  if (w.is_next) chips.push('<span class="chip next">планируется</span>');
  if (ttWeeks.has(w.w)) chips.push('<span class="chip tt">TT</span>');
  if (raceWeeks.has(w.w)) chips.push('<span class="chip act">ГОНКА</span>');
  if (w.detailed) {
    chips.push('<span class="chip run">'+w.run_km+'К</span>');
  }
  const a = w.actual;
  if (a) {
    if (a.run_km) chips.push('<span class="chip act">факт '+a.run_km+'К</span>');
    else chips.push('<span class="chip">факт бега 0</span>');
  }

  // тело
  let body = '';
  if (w.detailed) {
    body += '<div class="wk-goal"><b>' + esc(w.goal_text) + '</b></div>';
    if (w.variants && w.variants.length) {
      body += '<div class="wk-vars">варианты структуры: ' + esc(w.variants.map(v=>v.label).join(' · ')) + '</div>';
    }
    body += '<div class="wk-grid">'
      + '<div class="mt plan"><div class="ml">план · бег</div><div class="mv">'+w.run_km+'К</div></div>'
      + '<div class="mt plan"><div class="ml">long Z2</div><div class="mv">'+w.long_km+'К</div></div>'
      + '<div class="mt plan"><div class="ml">нагрузка</div><div class="mv">'+w.total_h+'ч</div></div>'
      + '<div class="mt plan"><div class="ml">сессий</div><div class="mv">'+(w.sessions_target||'—')+'</div></div>'
      + '</div>';
    // разбивка нагрузки и структура
    let ld = '<div class="wk-load">';
    if (w.run_km_long != null) {
      ld += '<div class="wl-row"><span>бег</span><span>'
         + w.run_km + 'К = long ' + w.run_km_long + 'К + качеств. '
         + w.run_km_quality + 'К + лёгк. ' + w.run_km_easy + 'К</span></div>';
    }
    if (w.intensity_pct != null) {
      ld += '<div class="wl-row"><span>интенсивность</span><span>'
         + w.intensity_pct + '% объёма в Z3+</span></div>';
    }
    if (w.quality_label) {
      ld += '<div class="wl-row"><span>структура</span><span>'
         + esc(w.quality_label) + ' <span class="wl-id">' + esc(w.variant_id||'') + '</span></span></div>';
    }
    if (w.deload) {
      ld += '<div class="wl-row"><span>деload</span><span>объём снижен</span></div>';
    }
    ld += '</div>';
    body += ld;
  }
  if (a) {
    body += '<div class="wk-grid">'
      + '<div class="mt run"><div class="ml">факт · бег</div><div class="mv">'+a.run_km+'К</div></div>'
      + '<div class="mt act"><div class="ml">факт · объём</div><div class="mv">'+a.total_h+'ч</div></div>'
      + '<div class="mt bike"><div class="ml">факт · вел</div><div class="mv">'+a.bike_km+'К</div></div>'
      + '<div class="mt swim"><div class="ml">факт · плав</div><div class="mv">'+a.swim_km+'К</div></div>'
      + '</div>';
    body += '<div class="cmp"><span class="cl">сессий: '+a.sessions+'</span></div>';
    // сравнение план/факт по бегу
    if (w.detailed && w.run_km) {
      const p = w.run_km, f = a.run_km;
      const ratio = Math.min(f / p, 1);
      body += '<div class="cmp"><span class="cl">бег план/факт</span>'
        + '<span class="cbar"><i style="width:'+(ratio*100).toFixed(0)+'%;background:var(--good)"></i></span>'
        + '<span class="cl">' + p + 'К → ' + f + 'К</span></div>';
    }
  } else if (!w.detailed) {
    body += '<div class="wk-vars">не детализировано по неделям — фаза задаёт только вектор</div>';
  }

  const title = w.detailed ? w.goal_text : (w.actual ? 'прошедшая неделя' : 'не детализировано');
  return '<div class="wk t-'+(w.color||'gray')+(ttWeeks.has(w.w)?' tt':'')+(w.is_now?' now':'')+'" data-w="'+w.w+'">'
    + '<div class="wk-hd"><span class="wk-n">'+w.w+'</span>'
    + '<span class="wk-d">'+esc(w.start_d)+'</span>'
    + '<span class="wk-t"><span class="wk-gt">'+esc(title)+'</span></span>'
    + '<span class="wk-metrics">'+chips.join('')+'</span>'
    + '<span class="caret">▶</span></div>'
    + '<div class="wk-body">'+body+'</div></div>';
}).join('');

// раскрытие
document.querySelectorAll('.wk-hd').forEach(h => {
  h.addEventListener('click', () => {
    const wk = h.parentElement;
    const open = wk.classList.toggle('open');
    h.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
});

// Фазы
document.getElementById('phases').innerHTML = D.phases.map(p => {
  const head = '<div class="fphase-hd">'
    + '<div class="fphase-l">' + esc(p.id) + '<span>W'+p.w_from+'–W'+p.w_to+'</span></div>'
    + '<div class="fphase-r">' + p.weeks_count + ' нед.'
    + (p.target_h ? ' · ' + p.target_h + 'ч/нед' : '') + '<br>' + esc(p.date_range) + '</div>'
    + '</div>';
  const goal = p.goal ? '<div class="fphase-goal">' + esc(p.goal) + '</div>' : '';
  const focus = p.focus ? '<div class="fphase-focus">' + esc(p.focus) + '</div>' : '';
  const note = p.notes ? '<div class="phase-note">' + esc(p.notes) + '</div>' : '';
  const chips = p.detailed.map(w => {
    let c = '';
    if (w.is_now) c += '<span class="chip next">сейчас</span>';
    if (w.is_next) c += '<span class="chip next">планируется</span>';
    if (ttWeeks.has(w.w)) c += '<span class="chip tt">TT</span>';
    if (w.actual) c += '<span class="chip act">факт ' + w.actual.run_km + 'К</span>';
    c += '<span class="chip run">' + w.run_km + 'К</span>';
    return '<span class="chip" style="margin:2px 3px 0 0">W' + w.w + ' ' + esc(w.start_d) + ' ' + c + '</span>';
  }).join('');
  return '<div class="fphase">' + head + goal + focus + note
    + '<div style="margin-top:7px">' + (chips || '<span class="chip">не детализировано</span>') + '</div>'
    + '</div>';
}).join('');

// TT
const types = {pace:'темповый', max:'max effort', sim:'симуляция', metric:'замер'};
document.getElementById('tts').innerHTML = '<table class="tt-tbl"><thead><tr>'
  + '<th>W</th><th>Тип</th><th>Что и зачем</th><th class="num">Цель</th><th class="num">Темп</th>'
  + '</tr></thead><tbody>'
  + D.tts.map(t => {
      const target = t.target_sec ? Math.floor(t.target_sec/60)+':'+String(t.target_sec%60).padStart(2,'0') : '—';
      return '<tr><td class="n">W'+t.w+'</td>'
        + '<td class="sm">' + (types[t.test_type]||t.test_type) + '</td>'
        + '<td><b>' + esc(t.what) + '</b><div class="sm">' + esc(t.session_goal||'') + '</div></td>'
        + '<td class="num">' + target + '</td>'
        + '<td class="num sm">' + (t.pace ? t.pace+'/км' : '—') + '</td></tr>';
    }).join('')
  + '</tbody></table>'
  + '<div style="margin-top:10px">' + D.races.map(r =>
      '<div class="race"><span class="rw">W'+r.w+' · '+esc(r.weekday)+'</span>'
      + '<span><span class="rn">'+esc(r.name)+'</span>'
      + '<span class="rd"> · '+esc(r.date)+(r.start?' · старт '+esc(r.start):'')+'</span></span></div>').join('')
  + '</div>';
</script>
</body></html>"""


def render(data: dict, out_path: Path) -> Path:
    dates = "{} — 18.09.2027".format(
        datetime.fromisoformat(data["season_start"]).strftime("%d.%m.%Y"))
    body = (TEMPLATE
            .replace("__TITLE__", esc(data["title"]))
            .replace("__DATES__", esc(dates))
            .replace("__GENERATED__", esc(data["generated_at"]))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "state/macro-overview.html"))
    ap.add_argument("--json-out", default=str(REPO / "state/macro-overview.json"))
    ap.add_argument("--no-actual", action="store_true", help="без факта из Garmin")
    args = ap.parse_args()

    actual = {}
    if not args.no_actual:
        try:
            from lib import actual_load
            actual = actual_load.load_actual()
        except Exception as e:  # noqa: BLE001 — факт не критичен для овервью
            print(f"предупреждение: факт не загружен ({e})")

    data = build_data(REPO / "state/season_plan.json", REPO / "state/athlete.json", actual)
    Path(args.json_out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    out = render(data, Path(args.out))
    print(f"json: {args.json_out}")
    print(f"html: {out} ({out.stat().st_size} B, {len(data['weeks'])} недель, "
          f"{len(data['phases'])} фаз, {len(data['tts'])} TT, факт {data['actual_weeks']} нед)")


if __name__ == "__main__":
    main()
