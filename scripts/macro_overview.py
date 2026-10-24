#!/usr/bin/env python3
"""
macro_overview.py — макро-план сезона → self-contained HTML (overview).

Источник данных: state/season_plan.json (фазы, TT, гонки) + state/athlete.json (зоны)
+ ~/.hermes/coach/plans/spring-10k-2027-v2.md (помесячная/понедельная разбивка по неделям).

Правила:
- JSON — source of truth, HTML — производный (как в lib/render_html.py).
- Self-contained: без fetch(), без CDN. Открывается двойным тапом на Android.
- Тёмная гамма: --bg #0f1115, --accent #7aa2ff и т.д. (design tokens coach-планов).

Запуск:
    python3 macro_overview.py [--out state/macro-overview.html]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MACRO_MD = Path.home() / ".hermes/coach/plans/spring-10k-2027-v2.md"

# Средний темп макро-плана для перевода км → минуты (Z2 + интервалы смешаны).
PACE_MIN_PER_KM = 5.7


def _num(s: str) -> float:
    m = re.search(r"(\d+)", s)
    return float(m.group(1)) if m else 0.0


def _mins(s: str) -> int:
    """'2×25м' → 50, '1×60м' → 60, '1×30м' → 30."""
    m = re.search(r"(\d+)\s*[×x]\s*(\d+)", s)
    if m:
        return int(m.group(1)) * int(m.group(2))
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 0


def parse_macro_weeks(md_path: Path) -> dict[int, dict]:
    """Парсит таблицу 'ПЛАН ПО НЕДЕЛЯМ' из макро- md."""
    text = md_path.read_text(encoding="utf-8")
    out: dict[int, dict] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 9:
            continue
        m = re.fullmatch(r"W(\d+)", cells[0].replace("*", "").strip())
        if not m:
            continue
        out[int(m.group(1))] = dict(
            macro_date=cells[1], run=cells[2], long=cells[3],
            key=re.sub(r"\*\*", "", cells[4]),
            core=cells[5], bike=cells[6], swim=cells[7], total=cells[8],
        )
    return out


def build_data(season_plan_path: Path, athlete_path: Path) -> dict:
    """Данные овервью.

    Источник — season_plan.json (weekly_macro[]): цели, объёмы, компоненты.
    Конкретные структуры качественных сессий НЕ хранятся здесь: макро задаёт
    цель (goal) и масштаб (scale), а вариант подбирает quality_session при
    планировании недели. Список вариантов подтягивается из workout_templates.json
    для отображения «возможных структур» на неделю.
    """
    sys.path.insert(0, str(REPO))
    from lib import season_week

    sp = json.loads(season_plan_path.read_text(encoding="utf-8"))
    at = json.loads(athlete_path.read_text(encoding="utf-8"))
    start = sp.get("season_start_date", "2026-10-11")
    templates = json.loads((REPO / "state/workout_templates.json").read_text(encoding="utf-8")).get("templates", {})

    weeks = []
    for entry in sp.get("weekly_macro", []):
        w = entry["season_week"]
        ws, we = season_week.season_week_to_dates(w, start)
        run_km = entry.get("run_km", 0)
        run_h = round(round(run_km * PACE_MIN_PER_KM) / 60, 1)
        bike_h = round(_mins(entry.get("bike", "")) / 60, 1)
        swim_h = round(_mins(entry.get("swim", "")) / 60, 1)
        ofp_h = round(_mins(entry.get("core", "")) / 60, 1)
        comp_h = round(run_h + bike_h + swim_h + ofp_h, 1)
        total_h = entry.get("total_h", 0)
        q = entry.get("quality", {})
        goal = q.get("goal", "")
        scale = q.get("scale", "")
        tpl = templates.get(goal, {})
        variants = [v for v in tpl.get("variants", []) if v.get("scale") == scale]
        weeks.append({
            "w": w,
            "start": ws.isoformat(),
            "end": we.isoformat(),
            "run_km": run_km,
            "long_km": entry.get("long_km", 0),
            "goal": goal,
            "goal_label": tpl.get("label", goal),
            "goal_text": tpl.get("goal", ""),
            "scale": scale,
            "work_zone": tpl.get("work_zone", ""),
            "develops": tpl.get("develops", ""),
            "variants": [{"id": v.get("id"), "label": v.get("label"), "work_m": v.get("work_m")}
                         for v in variants],
            "run_h": run_h, "bike_h": bike_h, "swim_h": swim_h, "ofp_h": ofp_h,
            "comp_h": comp_h,
            "total_macro_h": total_h,
            "gap_h": round(total_h - comp_h, 1),
            "core": entry.get("core", ""), "bike": entry.get("bike", ""), "swim": entry.get("swim", ""),
        })

    # CP привязаны к неделе (season_week) и дню внутри недели (weekday).
    # Конкретной даты в макро нет — она вычисляется, но не хранится.
    tts = [{
        "id": c["id"], "w": c.get("season_week"),
        "weekday": c.get("weekday", ""),
        "what": c["what"], "target": c.get("target_value"),
        "protocol": c.get("protocol", ""),
    } for c in sp.get("control_points", [])]

    races = [{
        "name": r["name"], "date": r["date"],
        "start": r.get("start_time", ""),
        "w": season_week.date_to_season_week(r["date"], start),
        "weekday": datetime.fromisoformat(r["date"]).strftime("%a"),
    } for r in sp.get("races", [])]

    return {
        "title": "Макро-план сезона · W1–W49",
        "subtitle": (f"Сезон с {start} · гонка 1: S25 Berlin 10K 18.04.2027 · "
                     f"гонка 2: олимпийский триатлон 12.09.2027"),
        "season_start": start,
        "season_weeks": sp.get("horizon", {}).get("season_week_count", 49),
        "weeks": weeks,
        "phases": sp.get("phases", []),
        "tts": tts,
        "races": races,
        "zones": at.get("hr_zones", {}).get("zones", {}),
        "hr_max": at.get("hr_zones", {}).get("hr_max"),
        "rhr": at.get("hr_zones", {}).get("rhr"),
        "pace_min_per_km": PACE_MIN_PER_KM,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
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
body{padding:14px 12px 60px;max-width:860px;margin:0 auto}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:15px;margin:22px 0 8px;color:var(--accent)}
h3{font-size:12px;margin:0 0 6px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:14px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:12px 14px;margin-bottom:10px}

/* сводка */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.kpi{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:8px 6px;text-align:center}
.kpi .v{font-size:15px;font-weight:600;color:var(--accent2);font-family:ui-monospace,SFMono-Regular,monospace}
.kpi .l{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.zones-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:4px;font-size:10.5px;margin-top:10px}
.zone{background:var(--panel2);padding:4px 8px;border-radius:6px;border:1px solid var(--border);color:var(--muted)}
.zone b{color:var(--accent);font-family:ui-monospace,SFMono-Regular,monospace;font-size:10.5px;margin-right:3px}

/* бары объёма */
.bar{height:20px;border-radius:5px;overflow:hidden;display:flex;background:var(--panel2);margin:5px 0 3px}
.bar div{height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  font-size:10px;line-height:20px;padding-left:4px;color:#0f1115;font-weight:600}
.bar .b-run{background:var(--run)}
.bar .b-bike{background:var(--bike)}
.bar .b-swim{background:var(--swim)}
.bar .b-ofp{background:var(--ofp)}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:10.5px;color:var(--muted);margin-top:2px}
.legend span{display:flex;align-items:center;gap:4px}
.dot{width:9px;height:9px;border-radius:2px;display:inline-block}

/* таблица */
table{width:100%;border-collapse:collapse;font-size:11.5px}
th{font-size:9.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;
  text-align:left;padding:6px 4px;border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--bg)}
td{padding:7px 4px;border-bottom:1px solid rgba(42,49,64,.6)}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-family:ui-monospace,SFMono-Regular,monospace}
td.w{color:var(--accent);font-weight:600;font-family:ui-monospace,SFMono-Regular,monospace}
td.date{color:var(--muted);font-size:10.5px}
tr.tt-row td{background:rgba(255,155,106,.07)}
tr.race-row td{background:rgba(126,231,135,.08)}
tr.now-row td{background:rgba(122,162,255,.12)}
.tag{display:inline-block;font-size:9px;padding:1px 5px;border-radius:4px;font-weight:600;letter-spacing:.3px}
.tag-tt{background:rgba(255,155,106,.15);color:var(--warn);border:1px solid rgba(255,155,106,.3)}
.tag-race{background:rgba(126,231,135,.15);color:var(--good);border:1px solid rgba(126,231,135,.3)}
.gap-pos{color:var(--warn)}
.gap-neg{color:var(--good)}
.mini-bar{height:6px;border-radius:3px;background:var(--panel2);overflow:hidden;min-width:44px}
.mini-bar i{display:block;height:100%;background:linear-gradient(90deg,var(--run),var(--accent2))}
.note{background:rgba(122,162,255,.06);border:1px solid rgba(122,162,255,.25);
  border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.5}
.note b{color:var(--accent)}
.warn{background:rgba(255,155,106,.07);border:1px solid rgba(255,155,106,.3);
  border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.5}
.warn b{color:var(--warn)}
details{margin:6px 0}
summary{cursor:pointer;font-size:12.5px;color:var(--accent);padding:4px 0}
ul{margin:6px 0;padding-left:19px;font-size:12.5px;line-height:1.55}
li{margin-bottom:3px}
footer{margin-top:20px;text-align:center;font-size:11px;color:var(--muted)}
</style></head><body>

<h1>__TITLE__</h1>
<div class="sub">__SUBTITLE__</div>

<div class="card">
  <h3>Сезон в цифрах</h3>
  <div class="kpi-grid" id="kpis"></div>
  <div class="zones-grid" id="zones"></div>
</div>

<div class="card">
  <h3>Объём по видам — состав по неделям</h3>
  <p class="sub" style="margin:0 0 8px">Длина полосы = сумма компонентов недели (бег+вел+плав+ОФП). Подписи — часы.</p>
  <div id="bars"></div>
  <div class="legend">
    <span><i class="dot" style="background:var(--run)"></i>бег</span>
    <span><i class="dot" style="background:var(--bike)"></i>вел</span>
    <span><i class="dot" style="background:var(--swim)"></i>плав</span>
    <span><i class="dot" style="background:var(--ofp)"></i>ОФП</span>
  </div>
</div>

<h2>Помесячная разбивка</h2>
<div class="card">
  <table>
    <thead><tr>
      <th>W</th><th>Даты</th><th class="num">Бег</th><th class="num">Long</th>
      <th>Цель (адаптация)</th><th class="num">Бег ч</th><th class="num">Вел</th>
      <th class="num">Плав</th><th class="num">ОФП</th><th class="num">Σ ч</th>
      <th class="num">Total</th><th class="num">Δ</th>
    </tr></thead>
    <tbody id="wtbody"></tbody>
  </table>
</div>

<h2>Контрольные точки и гонки</h2>
<div class="card"><ul id="ctl"></ul></div>

<h2>Читать это</h2>
<div class="note" id="notes"></div>

<footer>Сгенерировано __GENERATED__ · coach · macro_overview.py</footer>

<script type="application/json" id="plan-data">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('plan-data').textContent);
const WEEK = DATA.weeks;
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

const today = new Date();
function inWeek(ws, we){ const a=new Date(ws+'T00:00:00'), b=new Date(we+'T23:59:59');
  return today>=a && today<=b; }

// KPI
const last = WEEK[WEEK.length-1];
const peakKm = Math.max(...WEEK.map(w=>w.run_km));
const peakW  = WEEK.find(w=>w.run_km===peakKm);
document.getElementById('kpis').innerHTML = [
  ['W'+peakW.w, 'пик бега'],
  [peakKm+'К', 'макс. объём'],
  [Math.max(...WEEK.map(w=>w.total_macro_h))+'ч', 'макс. неделя'],
  [DATA.tts.length, 'контрольных точек'],
].map(([v,l])=>'<div class="kpi"><div class="v">'+esc(v)+'</div><div class="l">'+esc(l)+'</div></div>').join('');

document.getElementById('zones').innerHTML = Object.entries(DATA.zones)
  .map(([k,v])=>'<div class="zone"><b>'+esc(k)+'</b> '+esc(v)+'</div>').join('');

// бары по неделям
const maxComp = Math.max(...WEEK.map(w=>w.comp_h));
document.getElementById('bars').innerHTML = WEEK.map(w=>{
  const pct = h => (h/ (maxComp) * 100).toFixed(2) + '%';
  const seg = (cls,h,label)=> h>0 ? '<div class="'+cls+'" style="width:'+pct(h)+'" title="'+label+'">'+label+'</div>' : '';
  return '<div style="display:flex;align-items:center;gap:7px;margin-bottom:3px">'
    + '<div style="width:26px;font-family:ui-monospace,monospace;font-size:10px;color:var(--muted)">W'+w.w+'</div>'
    + '<div class="bar" style="flex:1">'
    + seg('b-run', w.run_h, w.run_h+'ч')
    + seg('b-bike', w.bike_h, w.bike_h+'ч')
    + seg('b-swim', w.swim_h, w.swim_h+'ч')
    + seg('b-ofp', w.ofp_h, w.ofp_h+'ч')
    + '</div>'
    + '<div style="width:42px;text-align:right;font-family:ui-monospace,monospace;font-size:10px;color:var(--accent2)">'+w.comp_h+'ч</div>'
    + '</div>';
}).join('');

// таблица
const ttWeeks = new Set(DATA.tts.map(t=>t.w));
const raceWeeks = new Set(DATA.races.map(r=>r.w));
const nowWeek = WEEK.find(w=>inWeek(w.start,w.end));
document.getElementById('wtbody').innerHTML = WEEK.map(w=>{
  let cls='', tag='';
  if (raceWeeks.has(w.w)) { cls='race-row'; tag='<span class="tag tag-race">ГОНКА</span>'; }
  else if (ttWeeks.has(w.w)) { cls='tt-row'; tag='<span class="tag tag-tt">TT</span>'; }
  if (nowWeek && nowWeek.w===w.w) cls='now-row';
  const gapCls = w.gap_h>=0?'gap-pos':'gap-neg';
  return '<tr class="'+cls+'">'
    + '<td class="w">'+w.w+'</td>'
    + '<td class="date">'+esc(w.start.slice(8))+'.'+esc(w.start.slice(5,7))+' – '+esc(w.end.slice(8))+'.'+esc(w.end.slice(5,7))+'</td>'
    + '<td class="num">'+w.run_km+'К</td>'
    + '<td class="num">'+w.long_km+'К</td>'
    + '<td style="font-size:10.5px"><b>'+esc(w.goal_label||w.goal)+'</b> '
    + '<span style="color:var(--muted)">'+esc(w.scale)+'</span>'
    + (w.variants && w.variants.length
       ? '<div style="color:var(--muted);font-size:9.5px;margin-top:2px">'
         + esc(w.variants.map(v=>v.label+' ('+v.work_m+'м)').join(' · ')) + '</div>'
       : '')
    + ' '+tag+'</td>'
    + '<td class="num">'+w.run_h+'</td>'
    + '<td class="num">'+w.bike_h+'</td>'
    + '<td class="num">'+w.swim_h+'</td>'
    + '<td class="num">'+w.ofp_h+'</td>'
    + '<td class="num" style="color:var(--accent2)">'+w.comp_h+'</td>'
    + '<td class="num">'+w.total_macro_h+'</td>'
    + '<td class="num '+gapCls+'">'+(w.gap_h>=0?'+':'')+w.gap_h+'</td>'
    + '</tr>';
}).join('');

// контрольные точки и гонки
const items = [];
DATA.tts.forEach(t=>{
  items.push('<li><b>'+esc(t.weekday||'')+' недели W'+t.w+'</b> · '+esc(t.what)
    + (t.target? ' · цель '+(t.target>=60? Math.floor(t.target/60)+':'+String(t.target%60).padStart(2,'0') : t.target+'с') : '')
    + '</li>');
});
DATA.races.forEach(r=>{
  items.push('<li><b>'+esc(r.weekday)+' '+esc(r.date)+'</b> · W'+r.w+' · <b>'+esc(r.name)+'</b>'+(r.start?' · старт '+esc(r.start):'')+'</li>');
});
document.getElementById('ctl').innerHTML = items.join('');

// заметки
const gaps = WEEK.map(w=>w.gap_h);
const avgGap = (gaps.reduce((a,b)=>a+b,0)/gaps.length).toFixed(1);
document.getElementById('notes').innerHTML =
  '<b>Колонка Total ≠ сумма компонентов.</b> В макро-плане Total указан как одно число, '
  + 'но сумма бег+вел+плав+ОФП даёт меньше на <b>'+avgGap+' ч в среднем</b> (от '
  + Math.min(...gaps).toFixed(1)+' до '+Math.max(...gaps).toFixed(1)+' ч). Разрыв растёт с объёмом. '
  + 'Именно поэтому факт W1 (6.27 ч) больше, чем сумма компонентов макро W1 (4.65 ч) — '
  + 'фактические недели ближе к Total, чем к сумме. Перед тем как ставить цель «9 ч/нед», '
  + 'надо решить, что считается истиной: Total или сумма компонентов.<br><br>'
  + '<b>Даты в макро-таблице</b> — понедельники (W1 = 12.10), а сезон в season_plan.json начинается '
  + 'с воскресенья (W1 = 11.10). Разница 1 день — именно из-за неё все TT стояли на четверге. '
  + 'Здесь даты приведены к season_week (вс→сб).<br><br>'
  + '<b>Макро задаёт цель, а не структуру.</b> Колонка «Цель» — это адаптационная задача недели '
  + '(VO2max / threshold / tempo и т.д.). Конкретная структура (5×800 или 4×1К) подбирается при '
  + 'планировании недели из каталога шаблонов — варианты показаны мелким шрифтом под целью. '
  + 'Guard: объём работы не откатывается ниже 0.9 × последней реальной интервальной сессии. <br><br>'
  + '<b>Бег переведён в часы</b> по среднему темпу '+DATA.pace_min_per_km+' мин/км (Z2 и интервалы смешаны), '
  + 'поэтому это оценка, а не точный трек.';
</script>
</body></html>"""


def render(data: dict, out_path: Path) -> Path:
    body = (TEMPLATE
            .replace("__TITLE__", data["title"])
            .replace("__SUBTITLE__", data["subtitle"])
            .replace("__GENERATED__", data["generated_at"])
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
    print(f"html: {out} ({out.stat().st_size} B, {len(data['weeks'])} недель)")


if __name__ == "__main__":
    main()
