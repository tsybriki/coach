#!/usr/bin/env python3
"""
week_preview.py — компактный read-only превью недели → self-contained HTML.

Отличие от plan-wN.html (интерактивный план с picker'ом и карточками):
превью — плоский список: день → время → название → короткая идея → зона.
Одно экраночное изображение без навигации, чтобы быстро посмотреть неделю.

Данные: state/plan-wN.json (source of truth) — тот же, что у интерактивного плана.

Запуск:
    python3 week_preview.py 3                  # → state/preview-w3.html
    python3 week_preview.py 3 --out /tmp/p.html
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DAY_FULL = {"ВС": "Воскресенье", "ПН": "Понедельник", "ВТ": "Вторник",
            "СР": "Среда", "ЧТ": "Четверг", "ПТ": "Пятница", "СБ": "Суббота"}

KIND_ICON = {"run": "🏃", "bike": "🚴", "swim": "🏊", "ofp": "💪",
             "brick": "🔄", "control_point": "🎯"}
KIND_NAME = {"run": "бег", "bike": "велосипед", "swim": "плавание",
             "ofp": "ОФП", "brick": "брик", "control_point": "контрольная точка"}


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _slot_idea(slot: dict) -> str:
    """Короткая идея тренировки — одна строка."""
    name = slot.get("name", "")
    if name:
        return name
    focus = slot.get("focus") or ""
    sub = slot.get("subkind") or ""
    return f"{focus} · {sub}" if focus else sub


def _duration_str(mins: int) -> str:
    if mins >= 60:
        h, m = divmod(mins, 60)
        return f"{h}ч{m:02d}м" if m else f"{h}ч"
    return f"{mins}мин"


def _structure_summary(structure: list) -> str:
    """Компактная сводка структуры: «15мин разминка → 5×800 @4:00 Z6 → заминка»."""
    if not structure:
        return ""
    bits = []
    for st in structure:
        phase = st.get("phase", "")
        if phase == "set":
            label = st.get("label") or "интервалы"
            reps = st.get("reps")
            dist = st.get("distance_m")
            sub = st.get("set_repeats") or []
            pace = ""
            zone = ""
            if sub:
                pace = sub[0].get("pace_min_per_km") or ""
                zone = sub[0].get("zone") or ""
            d = ""
            if dist:
                d = f"{dist}м" if dist < 1000 else f"{dist // 1000}К"
            # label уже содержит размер ("5×800м") — не дублируем дистанцию
            label_has_dist = bool(re.search(r"\d", str(label)))
            bits.append(f"{label}" + ("" if label_has_dist else (f" ×{reps}" if reps else "")) +
                        ("" if label_has_dist else (f" {d}" if d else "")) +
                        (f" @{pace}" if pace and pace != "all-out" else "") +
                        (f" {zone}" if zone else ""))
        elif phase == "main" and st.get("set"):
            n = len(st["set"].get("exercises", []))
            bits.append(f"core circuit ({n} упражнений)")
        elif phase == "main" and st.get("exercise"):
            bits.append(st["exercise"].split(":")[0].strip())
        elif phase == "work":
            dist = st.get("distance_m")
            mins = st.get("duration_min")
            pace = st.get("pace_min_per_km")
            zone = st.get("zone")
            bits.append((" ".join([
                f"{dist}м" if dist else (f"{mins}мин" if mins else ""),
                f"@{pace}" if pace and pace != "all-out" else (pace if pace == "all-out" else ""),
                zone or "",
            ])).strip())
        elif phase in ("warmup", "cooldown"):
            bits.append(f"{'разминка' if phase == 'warmup' else 'заминка'} {st.get('duration_min', '')}мин")
    return " → ".join(b for b in bits if b)


def build(plan: dict) -> dict:
    slots = plan.get("slots", [])
    by_day: dict[str, list] = {}
    for s in slots:
        by_day.setdefault(s.get("day", ""), []).append(s)

    order = [d for d in ("ВС", "ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ") if d in by_day]
    days = []
    for d in order:
        items = []
        for s in sorted(by_day[d], key=lambda x: x.get("time", "")):
            items.append({
                "id": s.get("id"),
                "time": s.get("time", ""),
                "kind": s.get("kind", ""),
                "icon": KIND_ICON.get(s.get("kind", ""), "•"),
                "kind_name": KIND_NAME.get(s.get("kind", ""), s.get("kind", "")),
                "name": s.get("name", ""),
                "idea": _slot_idea(s),
                "focus": s.get("focus") or "",
                "location": s.get("location") or "",
                "duration_min": s.get("duration_min", 0),
                "duration": _duration_str(s.get("duration_min", 0)),
                "structure": _structure_summary(s.get("structure", [])),
                "rationale": s.get("rationale") or "",
                "session": s.get("session"),
                "is_cp": s.get("kind") == "control_point",
                "is_quality": bool(s.get("quality_selection")),
            })
        days.append({"day": d, "day_full": DAY_FULL.get(d, d), "items": items})

    planned = sum(s.get("duration_min", 0) for s in slots) / 60
    # Цель недели — из макро (weekly_macro[].total_h), а не среднее по фазе:
    # фаза даёт ориентир, а целиться надо в конкретную неделю.
    lc = plan.get("load_compare") or {}
    target = lc.get("target_h") or (plan.get("phase") or {}).get("hours_per_week_target", 0)
    return {
        "title": plan.get("title", "План недели"),
        "iso_week": plan.get("iso_week", ""),
        "week_goal": plan.get("week_goal"),
        "week_goal_detail": plan.get("week_goal_detail"),
        "phase_id": (plan.get("phase") or {}).get("id"),
        "phase_goal": (plan.get("phase") or {}).get("goal"),
        "phase_focus": (plan.get("phase") or {}).get("focus"),
        "zones": ((plan.get("rules") or {}).get("hr_zones") or {}).get("zones", {}),
        "hr_max": ((plan.get("rules") or {}).get("hr_zones") or {}).get("hr_max"),
        "rhr": ((plan.get("rules") or {}).get("hr_zones") or {}).get("rhr"),
        "planned_h": round(planned, 1),
        "target_h": round(target, 1),
        "delta_h": round(planned - target, 1),
        "delta_pct": lc.get("delta_pct"),
        "load_status": lc.get("status"),
        "load_hint": lc.get("hint"),
        "slots_count": len(slots),
        "days": days,
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
  --accent:#7aa2ff;--accent2:#5cd6c0;--warn:#ff9b6a;--good:#7ee787;--cp:#d8a0ff;
  --run:#7ec8e3;--bike:#f08a5a;--swim:#5cd6c0;--ofp:#d8a0ff;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  -webkit-text-size-adjust:100%;line-height:1.45}
body{padding:14px 12px 50px;max-width:760px;margin:0 auto}
h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:12px}
h2{font-size:13px;margin:18px 0 8px;color:var(--accent);text-transform:uppercase;letter-spacing:.5px}

.goal-card{background:linear-gradient(135deg,rgba(92,214,192,.08),rgba(122,162,255,.06));
  border:1px solid rgba(92,214,192,.3);border-radius:12px;padding:11px 14px;margin-bottom:12px}
.goal-card .lbl{font-size:9.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:3px}
.goal-card .main{font-size:15px;font-weight:600;color:var(--accent2);line-height:1.3}
.goal-card .sub2{font-size:11.5px;color:var(--muted);margin-top:4px;line-height:1.4}
.goal-card .phase{font-size:11px;color:var(--accent);margin-top:6px;padding-top:6px;border-top:1px solid var(--border)}

.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px}
.kpi{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:7px 4px;text-align:center}
.kpi .v{font-size:15px;font-weight:600;color:var(--accent2);font-family:ui-monospace,monospace}
.kpi .l{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.kpi .v.pos{color:var(--good)} .kpi .v.neg{color:var(--warn)}

.zones{display:grid;grid-template-columns:repeat(2,1fr);gap:4px;font-size:10.5px;margin-bottom:14px}
.lc-note{margin:7px 0 11px;padding:8px 11px;border-radius:9px;font-size:11.5px;
  line-height:1.45;border:1px solid var(--border)}
.lc-note.over{background:rgba(240,180,87,.09);border-color:rgba(240,180,87,.4);color:#e8d5b0}
.lc-note.under{background:rgba(255,107,90,.09);border-color:rgba(255,107,90,.4);color:#f2c9c2}
.zone{background:var(--panel2);padding:4px 8px;border-radius:6px;border:1px solid var(--border);color:var(--muted)}
.zone b{color:var(--accent);font-family:ui-monospace,monospace;font-size:10.5px;margin-right:3px}

.day{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:10px 12px;margin-bottom:8px}
.day-head{display:flex;justify-content:space-between;align-items:baseline;
  padding-bottom:6px;margin-bottom:7px;border-bottom:1px solid var(--border)}
.day-name{font-size:14px;font-weight:600}
.day-count{font-size:10.5px;color:var(--muted)}

.item{display:flex;gap:9px;padding:7px 0;border-left:3px solid transparent;padding-left:9px;margin-left:-12px}
.item + .item{border-top:1px solid rgba(42,49,64,.55)}
.item.run{border-left-color:var(--run)}
.item.bike{border-left-color:var(--bike)}
.item.swim{border-left-color:var(--swim)}
.item.ofp{border-left-color:var(--ofp)}
.item.control_point{border-left-color:var(--cp)}
.item.brick{border-left-color:#f0c674}
.item-ico{font-size:15px;width:20px;text-align:center;flex-shrink:0;margin-top:1px}
.item-main{flex:1;min-width:0}
.item-top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.item-time{font-size:11px;color:var(--muted);font-family:ui-monospace,monospace;flex-shrink:0}
.item-name{font-size:13.5px;font-weight:600;line-height:1.3}
.item-meta{font-size:11px;color:var(--muted);margin-top:2px;line-height:1.4}
.item-struct{font-size:11px;color:var(--text);margin-top:4px;padding:5px 8px;
  background:var(--panel2);border-radius:6px;line-height:1.4}
.badge{display:inline-block;font-size:9px;font-weight:600;padding:1px 5px;border-radius:4px;
  letter-spacing:.3px;vertical-align:1px}
.badge-q{background:rgba(92,214,192,.15);color:var(--accent2);border:1px solid rgba(92,214,192,.3)}
.badge-cp{background:rgba(216,160,255,.15);color:var(--cp);border:1px solid rgba(216,160,255,.3)}
.focus{font-size:10px;font-family:ui-monospace,monospace;color:var(--accent2);
  background:rgba(92,214,192,.1);padding:1px 5px;border-radius:4px;margin-left:5px}
.goal{font-size:11.5px;color:var(--text);margin-top:4px;padding:6px 8px;
  background:rgba(92,214,192,.07);border:1px solid rgba(92,214,192,.25);border-radius:6px;line-height:1.45}
.goal .g-lbl{font-size:9.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--accent2);
  font-weight:600;margin-bottom:2px;display:block}
.goal .g-row{margin-top:3px;color:var(--muted)}
.goal .g-pass{color:var(--good)} .goal .g-fail{color:var(--warn)}
footer{margin-top:18px;text-align:center;font-size:11px;color:var(--muted)}
</style></head><body>

<h1>__TITLE__</h1>
<div class="sub">__SUB__</div>

<div id="goalcard"></div>

<div class="kpis" id="kpis"></div>
<div class="zones" id="zones"></div>

<h2>Расписание по дням</h2>
<div id="days"></div>

<footer>__FOOTER__</footer>

<script type="application/json" id="plan-data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('plan-data').textContent);
const esc = s => String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

// Цель недели + фаза
if (D.week_goal || D.phase_goal) {
  let g = '<div class="goal-card">';
  if (D.week_goal) {
    g += '<div class="lbl">Цель недели</div><div class="main">' + esc(D.week_goal) + '</div>';
    if (D.week_goal_detail) g += '<div class="sub2">' + esc(D.week_goal_detail) + '</div>';
  }
  if (D.phase_goal) {
    g += '<div class="phase">Фаза · ' + esc(D.phase_id||'') + ': ' + esc(D.phase_goal);
    if (D.phase_focus) g += '<br>' + esc(D.phase_focus);
    g += '</div>';
  }
  document.getElementById('goalcard').innerHTML = g + '</div>';
}

// KPI
const dcls = D.delta_h >= 0 ? 'pos' : 'neg';
document.getElementById('kpis').innerHTML = [
  [D.planned_h + 'ч', 'planned'],
  [D.target_h + 'ч', 'цель макро'],
  [(D.delta_h >= 0 ? '+' : '') + D.delta_h + 'ч', 'delta', dcls],
  [D.slots_count, 'sessions'],
].map(([v,l,c]) => '<div class="kpi"><div class="v ' + (c||'') + '">' + esc(v)
  + '</div><div class="l">' + esc(l) + '</div></div>').join('');

// Отклонение по нагрузке (план против цели макро недели)
if (D.load_status && D.load_status !== 'ok' && D.load_hint) {
  const k = document.getElementById('kpis');
  if (k) {
    const d = document.createElement('div');
    d.className = 'lc-note ' + D.load_status;
    d.innerHTML = 'НАГРУЗКА: ' + esc(D.load_hint);
    k.parentNode.insertBefore(d, k.nextSibling);
  }
}

// Зоны
document.getElementById('zones').innerHTML = Object.entries(D.zones||{})
  .map(([k,v]) => '<div class="zone"><b>' + esc(k) + '</b> ' + esc(v) + '</div>').join('');

// Дни
document.getElementById('days').innerHTML = D.days.map(d => {
  const mins = d.items.reduce((a,b)=>a+(b.duration_min||0),0);
  const h = Math.floor(mins/60), m = mins%60;
  const total = mins>=60 ? (h + (m ? 'ч' + String(m).padStart(2,'0') + 'м' : 'ч')) : (mins + 'мин');
  let html = '<div class="day"><div class="day-head"><span class="day-name">' + esc(d.day_full)
    + '</span><span class="day-count">' + d.items.length + ' · ' + esc(total) + '</span></div>';
  for (const it of d.items) {
    html += '<div class="item ' + esc(it.kind) + '">'
      + '<div class="item-ico">' + esc(it.icon) + '</div>'
      + '<div class="item-main">'
      + '<div class="item-top"><span class="item-name">' + esc(it.name);
    if (it.is_cp) html += ' <span class="badge badge-cp">TT</span>';
    else if (it.is_quality) html += ' <span class="badge badge-q">качественная</span>';
    if (it.focus) html += '<span class="focus">' + esc(it.focus) + '</span>';
    html += '</span><span class="item-time">' + esc(it.time) + ' · ' + esc(it.duration) + '</span></div>';
    if (it.location) html += '<div class="item-meta">' + esc(it.location) + '</div>';
    if (it.structure) html += '<div class="item-struct">' + esc(it.structure) + '</div>';
    const s = it.session;
    if (s && (s.session_goal || s.pass_criteria)) {
      html += '<div class="goal"><span class="g-lbl">Цель сессии</span>' + esc(s.session_goal||'');
      if (s.protocol) html += '<div class="g-row">Протокол: ' + esc(s.protocol) + '</div>';
      if (s.pass_criteria) html += '<div class="g-row g-pass">Критерий: ' + esc(s.pass_criteria) + '</div>';
      if (s.fail_action) html += '<div class="g-row g-fail">Если не дтянул: ' + esc(s.fail_action) + '</div>';
      html += '</div>';
    }
    html += '</div></div>';
  }
  return html + '</div>';
}).join('');
</script>
</body></html>"""


def render(data: dict, out_path: Path) -> Path:
    sub = " · ".join(x for x in [
        data.get("iso_week", ""),
        f"{data['slots_count']} тренировок",
    ] if x)
    body = (TEMPLATE
            .replace("__TITLE__", esc(data["title"]))
            .replace("__SUB__", esc(sub))
            .replace("__FOOTER__", "coach · week_preview.py · " +
                     "план недели: plan-wN.html · общий план: macro-overview.html")
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("week", type=int, help="season_week, напр. 3")
    ap.add_argument("--plan", default=None, help="путь к plan-wN.json")
    ap.add_argument("--out", default=None, help="путь к выходному HTML")
    args = ap.parse_args()

    plan_path = Path(args.plan) if args.plan else REPO / f"state/plan-w{args.week}.json"
    if not plan_path.exists():
        raise SystemExit(f"нет плана: {plan_path} (сначала сгенерируй plan-wN)")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    data = build(plan)
    out = Path(args.out) if args.out else REPO / f"state/preview-w{args.week}.html"
    render(data, out)
    print(f"preview: {out} ({out.stat().st_size} B, {data['slots_count']} слотов, "
          f"{len(data['days'])} дней)")


if __name__ == "__main__":
    main()
