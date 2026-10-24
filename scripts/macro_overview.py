#!/usr/bin/env python3
"""
macro_overview.py — общий план сезона → self-contained HTML.

Источник: state/season_plan.json (weekly_macro[], phases[], control_points[], races[]).
Показывает ВСЕ недели сезона (W1–W49) с датами, а не только детализированные.

Структура страницы:
  1. Шапка: сезон, даты, два пика
  2. Дорожная карта фаз: каждая фаза — блок с неделями, целями и объёмом
  3. Контрольные точки и гонки
  4. Как это читать (короткие пояснения)

Запуск:
    python3 scripts/macro_overview.py
    python3 scripts/macro_overview.py --out /tmp/ov.html
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

PACE_MIN_PER_KM = 5.7  # мин/км для перевода бега в часы (оценка)

MONTHS_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн",
                "июл", "авг", "сен", "окт", "ноя", "дек"]

KIND_COLOR = {"run": "var(--run)", "bike": "var(--bike)",
              "swim": "var(--swim)", "ofp": "var(--ofp)"}


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
    """'11 – 17 окт' / '28 апр – 4 мая'"""
    if ws.month == we.month:
        return "{}–{} {}".format(ws.day, we.day, MONTHS_SHORT[we.month - 1])
    return "{} {} – {} {}".format(ws.day, MONTHS_SHORT[ws.month - 1],
                                 we.day, MONTHS_SHORT[we.month - 1])


def fmt_day(d: date) -> str:
    return "{} {}".format(d.day, MONTHS_SHORT[d.month - 1])


def build_data(season_plan_path: Path, athlete_path: Path) -> dict:
    sp = json.loads(season_plan_path.read_text(encoding="utf-8"))
    at = json.loads(athlete_path.read_text(encoding="utf-8"))
    start = sp.get("season_start_date", "2026-10-11")
    total_weeks = sp.get("horizon", {}).get("season_week_count", 49)

    templates = json.loads(
        (REPO / "state/workout_templates.json").read_text(encoding="utf-8")
    ).get("templates", {})

    wm = {w["season_week"]: w for w in sp.get("weekly_macro", [])}

    # --- недели: все 49, детализированные помечены ---
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
                "variants": [{"label": v.get("label"), "work_m": v.get("work_m")}
                             for v in tpl.get("variants", []) if v.get("scale") == q.get("scale")],
            })
            w["comp_h"] = round(w["run_h"] + w["bike_h"] + w["swim_h"] + w["ofp_h"], 1)
            w["total_h"] = entry.get("total_h", 0)
        weeks.append(w)

    # --- фазы: недели каждой фазы + цели ---
    phase_meta = {p["id"]: p for p in sp.get("phases", [])}
    phases = []
    for p in sp.get("phases", []):
        s = season_week.date_to_season_week(p["start"], start)
        e = season_week.date_to_season_week(p.get("end", p["start"]), start)
        ws, we = season_week.season_week_to_dates(s, start)
        ph_weeks = [w for w in weeks if s <= w["w"] <= e]
        detailed = [w for w in ph_weeks if w["detailed"]]
        # Границы даты — фактические даты фазы из season_plan (они не совпадают
        # с границами недель: фаза может кончиться в середине недели).
        fs = datetime.fromisoformat(p["start"]).date()
        fe = datetime.fromisoformat(p.get("end", p["start"])).date()
        phases.append({
            "id": p["id"],
            "goal": p.get("goal", ""),
            "focus": p.get("focus", ""),
            "start": p["start"],
            "end": p.get("end", p["start"]),
            "w_from": s, "w_to": e,
            "date_range": "{} {} — {} {}".format(
                fmt_day(fs), fs.year, fmt_day(fe), fe.year),
            "weeks_count": len(ph_weeks),
            "detailed_count": len(detailed),
            "target_h": p.get("hours_per_week_target"),
            "is_event": bool(p.get("event")),
            "notes": p.get("notes", ""),
            "detailed": detailed,
        })

    # --- TT и гонки ---
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
            "kind": c.get("kind", ""),
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

    # --- KPI ---
    det = [w for w in weeks if w["detailed"]]
    peak = max(det, key=lambda w: w["run_km"]) if det else None

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
        "zones": at.get("hr_zones", {}).get("zones", {}),
        "hr_max": at.get("hr_zones", {}).get("hr_max"),
        "rhr": at.get("hr_zones", {}).get("rhr"),
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
  --accent:#7aa2ff;--accent2:#5cd6c0;--warn:#ff9b6a;--good:#7ee787;--cp:#d8a0ff;
  --run:#7ec8e3;--bike:#f08a5a;--swim:#5cd6c0;--ofp:#d8a0ff;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  -webkit-text-size-adjust:100%;line-height:1.45}
body{padding:16px 12px 60px;max-width:880px;margin:0 auto}
h1{font-size:21px;margin:0 0 3px}
h2{font-size:16px;margin:26px 0 10px;color:var(--accent);display:flex;
  align-items:baseline;gap:9px;flex-wrap:wrap}
h2 .hint{font-size:11.5px;color:var(--muted);font-weight:400}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:14px}

.hero{background:linear-gradient(135deg,rgba(122,162,255,.09),rgba(92,214,192,.05));
  border:1px solid rgba(122,162,255,.28);border-radius:14px;padding:14px 16px;margin-bottom:14px}
.hero-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.hero-dates{font-family:ui-monospace,SFMono-Regular,monospace;font-size:13px;color:var(--accent2)}
.hero h1{font-size:21px}
.hero-sub{font-size:12px;color:var(--muted);margin-top:4px}
.peaks{display:flex;gap:8px;margin-top:11px;flex-wrap:wrap}
.peak{background:rgba(15,17,21,.45);border:1px solid var(--border);border-radius:9px;
  padding:7px 11px;flex:1;min-width:132px}
.peak .pl{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.peak .pv{font-size:14px;font-weight:600;color:var(--accent2);font-family:ui-monospace,monospace;margin-top:2px}
.peak .pd{font-size:10.5px;color:var(--muted);margin-top:1px}

.zones{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;font-size:10.5px;margin-bottom:6px}
.zone{background:var(--panel2);padding:4px 7px;border-radius:6px;border:1px solid var(--border);color:var(--muted)}
.zone b{color:var(--accent);font-family:ui-monospace,monospace;font-size:10.5px;margin-right:2px}

/* фаза */
.phase{background:var(--panel);border:1px solid var(--border);border-radius:13px;
  padding:12px 14px;margin-bottom:11px;overflow:hidden}
.phase.event{border-color:rgba(126,231,135,.4);background:linear-gradient(135deg,rgba(126,231,135,.07),var(--panel))}
.phase-hd{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;
  padding-bottom:8px;border-bottom:1px solid var(--border);margin-bottom:9px}
.phase-l{font-size:14.5px;font-weight:600;display:flex;align-items:center;gap:8px}
.phase-w{font-size:10.5px;color:var(--muted);font-family:ui-monospace,monospace;
  background:var(--panel2);padding:2px 7px;border-radius:5px;border:1px solid var(--border);
  white-space:nowrap}
.phase-r{text-align:right;font-size:11px;color:var(--muted);white-space:nowrap}
.phase-r b{display:block;color:var(--text);font-size:12.5px;font-weight:600}
.phase-goal{font-size:13px;color:var(--accent2);font-weight:600;margin-bottom:3px}
.phase-focus{font-size:11.5px;color:var(--muted);line-height:1.45;margin-bottom:9px}
.phase-note{font-size:11.5px;color:var(--warn);margin-bottom:8px}

/* таблица недель */
.wk{width:100%;border-collapse:collapse;font-size:11.5px}
.wk th{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;
  text-align:left;padding:4px 5px;border-bottom:1px solid var(--border);font-weight:600}
.wk td{padding:6px 5px;border-bottom:1px solid rgba(42,49,64,.5);vertical-align:top}
.wk tr:last-child td{border-bottom:none}
.wk .wn{font-family:ui-monospace,monospace;font-weight:600;color:var(--accent);
  width:52px;white-space:nowrap}
.wk .wd{font-family:ui-monospace,monospace;color:var(--muted);font-size:10.5px;width:92px;white-space:nowrap}
.wk .wg{width:44%}
.wk .wg b{color:var(--accent2);font-weight:600;font-size:11.5px}
.wk .wg .wg-top{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}
.wk .wg span{color:var(--muted);font-size:10px;display:block;margin-top:1px}
.wk .num{text-align:right;font-family:ui-monospace,monospace;white-space:nowrap}
.wk .km{color:var(--run);font-weight:600}
.wk .mk{color:var(--muted);font-size:10px}
.wk tr.ttr td{background:rgba(255,155,106,.07)}
.wk tr.racerow td{background:rgba(126,231,135,.09)}
.wk tr.now td{background:rgba(122,162,255,.13)}
.badge{display:inline-block;font-size:8.5px;font-weight:700;padding:1px 5px;border-radius:4px;
  letter-spacing:.3px;vertical-align:1px;margin-left:4px}
.badge-tt{background:rgba(255,155,106,.16);color:var(--warn);border:1px solid rgba(255,155,106,.3)}
.badge-race{background:rgba(126,231,135,.16);color:var(--good);border:1px solid rgba(126,231,135,.3)}
.badge-now{background:rgba(122,162,255,.18);color:var(--accent);border:1px solid rgba(122,162,255,.35)}
.badge-next{background:rgba(92,214,192,.14);color:var(--accent2);border:1px solid rgba(92,214,192,.3)}
.mini{height:5px;border-radius:3px;background:var(--panel2);overflow:hidden;min-width:38px;margin-top:3px}
.mini i{display:block;height:100%}
.dim{opacity:.42}
.undet{font-size:10.5px;color:var(--muted);font-style:italic}

/* сетка календаря */
.cal{display:flex;flex-wrap:wrap;gap:3px;margin:10px 0 4px}
.cw{width:30px;height:26px;border-radius:5px;display:flex;align-items:center;justify-content:center;
  font-size:9.5px;font-family:ui-monospace,monospace;background:var(--panel2);
  color:var(--muted);border:1px solid var(--border);position:relative}
.cw.det{background:rgba(92,214,192,.14);color:var(--accent2);border-color:rgba(92,214,192,.3)}
.cw.tt{background:rgba(255,155,106,.16);color:var(--warn);border-color:rgba(255,155,106,.35)}
.cw.race{background:rgba(126,231,135,.18);color:var(--good);border-color:rgba(126,231,135,.4)}
.cw.now{outline:2px solid var(--accent);outline-offset:1px}
.cal-legend{display:flex;gap:12px;flex-wrap:wrap;font-size:10.5px;color:var(--muted);margin-top:6px}
.cal-legend span{display:flex;align-items:center;gap:4px}
.dot{width:9px;height:9px;border-radius:2px;display:inline-block}

.note{background:rgba(122,162,255,.06);border:1px solid rgba(122,162,255,.25);
  border-radius:9px;padding:10px 12px;font-size:12px;line-height:1.55;color:var(--text)}
.note b{color:var(--accent)}
.note ul{margin:6px 0 0;padding-left:18px}
.note li{margin-bottom:3px}
footer{margin-top:22px;text-align:center;font-size:11px;color:var(--muted)}
</style></head><body>

<div class="hero">
  <div class="hero-top">
    <div>
      <h1>__TITLE__</h1>
      <div class="hero-sub">__SUB__</div>
    </div>
    <div class="hero-dates">__DATES__</div>
  </div>
  <div class="peaks" id="peaks"></div>
</div>

<h2>Календарь сезона <span class="hint">49 недель · подсвечены детализированные</span></h2>
<div class="cal" id="cal"></div>
<div class="cal-legend">
  <span><i class="dot" style="background:var(--accent2)"></i>детализировано</span>
  <span><i class="dot" style="background:var(--warn)"></i>контрольная точка</span>
  <span><i class="dot" style="background:var(--good)"></i>гонка</span>
</div>

<h2>Фазы</h2>
<div id="phases"></div>

<h2>Контрольные точки</h2>
<div id="tts"></div>

<h2>Как это читать</h2>
<div class="note" id="notes"></div>

<footer>Сгенерировано __GENERATED__ · coach · macro_overview.py</footer>

<script type="application/json" id="plan-data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('plan-data').textContent);
const esc = s => String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const ttWeeks = new Set(D.tts.map(t=>t.w));
const raceWeeks = new Set(D.races.map(r=>r.w));

// Пики
document.getElementById('peaks').innerHTML = [
  ['Пик бега', 'W'+D.peak_week+' · '+D.peak_km+'К', 'неделя максимального объёма'],
  ['Детализировано', D.detailed_weeks+' из '+D.total_weeks, 'недель с понедельной раскладкой'],
  ['Макс. неделя', D.max_week_h+'ч', 'по колонке Total макро'],
  ['Контрольных точек', String(D.tts.length), 'TT внутри сезона'],
].map(([l,v,d]) => '<div class="peak"><div class="pl">'+esc(l)+'</div><div class="pv">'+esc(v)
  + '</div><div class="pd">'+esc(d)+'</div></div>').join('');

// Календарь 49 недель
const cal = document.getElementById('cal');
cal.innerHTML = D.weeks.map(w => {
  let cls = 'cw';
  if (w.detailed) cls += ' det';
  if (ttWeeks.has(w.w)) cls += ' tt';
  if (raceWeeks.has(w.w)) cls += ' race';
  return '<div class="'+cls+'" title="W'+w.w+' · '+w.start_d+'">'+w.w+'</div>';
}).join('');

// Фазы
const nowW = (() => {
  const t = new Date().toISOString().slice(0,10);
  const hit = D.weeks.find(w => w.start <= t && t <= w.end);
  return hit ? hit.w : null;
})();
// Следующая неделя — та, которую планируем (текущая ещё не закончилась)
const nextW = nowW ? ((D.weeks.find(w => w.w > nowW) || {}).w) : null;

document.getElementById('phases').innerHTML = D.phases.map(p => {
  let rows = '';
  if (p.detailed.length) {
    for (const w of p.detailed) {
      let cls = '';
      let badge = '';
      if (ttWeeks.has(w.w)) { cls = 'ttr'; badge = '<span class="badge badge-tt">TT</span>'; }
      if (raceWeeks.has(w.w)) { cls = 'racerow'; badge = '<span class="badge badge-race">ГОНКА</span>'; }
      if (nowW === w.w) { cls = 'now'; badge += '<span class="badge badge-now">сейчас</span>'; }
      else if (nextW === w.w) { badge += '<span class="badge badge-next">планируется</span>'; }
      const vs = (w.variants||[]).map(v=>v.label).join(' · ');
      rows += '<tr class="'+cls+'">'
        + '<td class="wn">'+w.w+'</td>'
        + '<td class="wd">'+esc(w.start_d)+'</td>'
        + '<td class="wg"><div class="wg-top"><b>'+esc(w.goal_text)+'</b>'+badge+'</div>'
        +   (vs ? '<span>'+esc(vs)+'</span>' : '')
        + '</td>'
        + '<td class="num km">'+w.run_km+'К</td>'
        + '<td class="num mk">'+w.long_km+'К</td>'
        + '<td class="num">'+w.comp_h+'ч</td>'
        + '<td class="num mk">'+w.total_h+'ч</td>'
        + '</tr>';
    }
  } else {
    rows = '<tr><td class="wn">' + p.w_from + '–' + p.w_to + '</td>'
      + '<td class="undet" colspan="6">не детализировано по неделям — фаза задаёт только вектор</td></tr>';
  }
  const head = '<div class="phase-hd">'
    + '<div class="phase-l">' + esc(p.id) + ' <span class="phase-w">W' + p.w_from + '–W' + p.w_to + '</span></div>'
    + '<div class="phase-r"><b>' + p.date_range + '</b>' + p.weeks_count + ' нед.'
    + (p.target_h ? ' · target ' + p.target_h + 'ч/нед' : '') + '</div>'
    + '</div>';
  const goal = p.goal ? '<div class="phase-goal">' + esc(p.goal) + '</div>' : '';
  const focus = p.focus ? '<div class="phase-focus">' + esc(p.focus) + '</div>' : '';
  const note = p.notes ? '<div class="phase-note">' + esc(p.notes) + '</div>' : '';
  const cols = p.detailed.length
    ? '<th class="num">Бег</th><th class="num">Long</th>'
      + '<th class="num">Σ ч</th><th class="num">Total</th>'
    : '';
  const tbl = '<table class="wk"><thead><tr>'
    + '<th>W</th><th>Даты</th><th>Цель недели</th>' + cols
    + '</tr></thead><tbody>' + rows + '</tbody></table>';
  return '<div class="phase' + (p.is_event ? ' event' : '') + '">' + head + goal + focus + note + tbl + '</div>';
}).join('');

// TT
const ttRows = D.tts.map(t => {
  const target = t.target_sec ? Math.floor(t.target_sec/60)+':'+String(t.target_sec%60).padStart(2,'0') : '—';
  const types = {pace:'темповый', max:'max effort', sim:'симуляция', metric:'замер'};
  return '<tr><td class="wn">W'+t.w+'</td>'
    + '<td class="wd">' + (t.test_type ? (types[t.test_type]||t.test_type) : 'замер') + '</td>'
    + '<td class="wg"><b>' + esc(t.what) + '</b><span>' + esc(t.session_goal||'') + '</span></td>'
    + '<td class="num">' + target + '</td>'
    + '<td class="num mk">' + (t.pace ? t.pace + '/км' : '—') + '</td></tr>';
}).join('');
document.getElementById('tts').innerHTML = '<div class="phase"><table class="wk"><thead><tr>'
  + '<th>W</th><th>Тип</th><th>Что и зачем</th><th class="num">Цель</th><th class="num">Темп</th>'
  + '</tr></thead><tbody>' + ttRows + '</tbody></table></div>';

// Гонки
const raceHtml = D.races.map(r => '<div class="peak" style="margin-bottom:8px">'
  + '<div class="pl">W' + r.w + ' · ' + esc(r.weekday) + '</div>'
  + '<div class="pv" style="font-size:13px">' + esc(r.name) + '</div>'
  + '<div class="pd">' + esc(r.date) + (r.start ? ' · старт ' + esc(r.start) : '') + '</div></div>').join('');
document.getElementById('tts').innerHTML += '<div class="phase">' + raceHtml + '</div>';

// Пояснения
document.getElementById('notes').innerHTML =
  '<b>Недельная раскладка есть только у ' + D.detailed_weeks + ' недель.</b> '
  + 'Остальные недели сезона заданы фазой (вектор развития и объём), '
  + 'конкретика по ним не расписана — она появится при планировании.<br><br>'
  + '<b>Колонка Σ ч — сумма компонентов</b> (бег + вел + плав + ОФП), '
  + '<b>Total — колонка из макро-плана</b>. Они не сходятся: разрыв растёт с объёмом. '
  + 'Фактические недели ближе к Total, чем к сумме — отсюда вопрос, что считать целью.<br><br>'
  + '<b>Бег переведён в часы</b> по среднему темпу 5.7 мин/км (Z2 и интервалы смешаны) — это оценка.';
</script>
</body></html>"""


def render(data: dict, out_path: Path) -> Path:
    sub = "Два пика: S25 Berlin 10K (18.04.2027) → олимпийский триатлон (12.09.2027)"
    dates = "{} — {}".format(
        datetime.fromisoformat(data["season_start"]).strftime("%d.%m.%Y"),
        "18.09.2027")
    body = (TEMPLATE
            .replace("__TITLE__", esc(data["title"]))
            .replace("__SUB__", esc(sub))
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
    args = ap.parse_args()

    data = build_data(REPO / "state/season_plan.json", REPO / "state/athlete.json")
    Path(args.json_out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    out = render(data, Path(args.out))
    print(f"json: {args.json_out}")
    print(f"html: {out} ({out.stat().st_size} B, {len(data['weeks'])} недель, "
          f"{len(data['phases'])} фаз, {len(data['tts'])} TT)")


if __name__ == "__main__":
    main()
